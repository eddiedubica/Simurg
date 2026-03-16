"""
Мониторинг неотвеченных клиентов.
Если клиенту не ответили > 1.5 часа — уведомление в Telegram.
"""

import time
import logging
from datetime import datetime

import sys
sys.path.insert(0, "..")

from amocrm_client import AmoCRMClient
from telegram_bot import send_message
from config import RESPONSE_TIMEOUT_MINUTES

logger = logging.getLogger(__name__)

# Храним ID сделок по которым уже отправили алерт (чтобы не спамить)
_alerted_leads = {}


def check_unanswered_leads(amo: AmoCRMClient):
    """Проверяет сделки с неотвеченными сообщениями."""
    now = int(time.time())
    timeout_seconds = RESPONSE_TIMEOUT_MINUTES * 60

    # Получаем пользователей (менеджеров) для маппинга ID -> имя
    users = amo.get_users()
    users_map = {u["id"]: u["name"] for u in users}

    # Получаем все события типа "входящее сообщение" / "входящий чат"
    # за последние 3 часа
    since = now - (3 * 3600)
    events = amo.get_all_events(
        **{
            "filter[type]": "incoming_chat_message",
            "filter[created_at][from]": since,
        }
    )

    # Также проверяем входящие звонки без ответа
    call_events = amo.get_all_events(
        **{
            "filter[type]": "incoming_call",
            "filter[created_at][from]": since,
        }
    )
    events.extend(call_events)

    if not events:
        logger.info("Нет входящих событий за последние 3 часа")
        return

    # Группируем по сделке — находим последнее входящее по каждой сделке
    leads_last_incoming = {}
    for event in events:
        entity_id = event.get("entity_id")
        created_at = event.get("created_at", 0)
        if entity_id and created_at > leads_last_incoming.get(entity_id, {}).get("created_at", 0):
            leads_last_incoming[entity_id] = event

    # Проверяем — был ли ответ менеджера после входящего сообщения
    unanswered = []
    for lead_id, incoming_event in leads_last_incoming.items():
        incoming_time = incoming_event["created_at"]
        wait_seconds = now - incoming_time

        if wait_seconds < timeout_seconds:
            continue

        # Проверяем — может уже ответили (исходящее сообщение после входящего)
        outgoing = amo.get_all_events(
            **{
                "filter[type]": "outgoing_chat_message",
                "filter[entity_id]": lead_id,
                "filter[created_at][from]": incoming_time,
            }
        )

        if outgoing:
            # Ответили — убираем из алертов если был
            _alerted_leads.pop(lead_id, None)
            continue

        # Не ответили — добавляем в список
        unanswered.append({
            "lead_id": lead_id,
            "wait_minutes": round(wait_seconds / 60),
            "responsible_user_id": incoming_event.get("created_by"),
            "entity_id": lead_id,
        })

    # Отправляем алерты
    for item in unanswered:
        lead_id = item["lead_id"]

        # Не спамим по одной и той же сделке чаще чем раз в 30 минут
        last_alert = _alerted_leads.get(lead_id, 0)
        if now - last_alert < 1800:
            continue

        # Получаем инфо о сделке
        try:
            lead_data = amo.get_lead_with_contacts(lead_id)
            lead_name = lead_data.get("name", "Без названия")
            responsible_id = lead_data.get("responsible_user_id")
            manager_name = users_map.get(responsible_id, "Не назначен")

            # Получаем имя контакта
            contact_name = "—"
            contacts = lead_data.get("_embedded", {}).get("contacts", [])
            if contacts:
                contact_info = amo.get_contact(contacts[0]["id"])
                contact_name = contact_info.get("name", "—")

            lead_url = f"{amo.base_url}/leads/detail/{lead_id}"

            text = (
                f"⚠️ <b>Клиент ждёт ответа {item['wait_minutes']} мин!</b>\n\n"
                f"👤 Клиент: {contact_name}\n"
                f"📋 Сделка: <a href=\"{lead_url}\">{lead_name}</a>\n"
                f"👨‍💼 Менеджер: {manager_name}\n"
                f"⏰ Без ответа: {item['wait_minutes']} мин"
            )
            send_message(text)
            _alerted_leads[lead_id] = now
            logger.info(f"Алерт: сделка {lead_id}, ждёт {item['wait_minutes']} мин")

        except Exception as e:
            logger.error(f"Ошибка при обработке сделки {lead_id}: {e}")


def run_monitor(amo: AmoCRMClient):
    """Запуск одной итерации мониторинга."""
    logger.info("Проверяю неотвеченных клиентов...")
    try:
        check_unanswered_leads(amo)
    except Exception as e:
        logger.error(f"Ошибка мониторинга: {e}")
