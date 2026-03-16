"""
Отчёт по работе менеджеров.
Показывает: клиенты в работе, звонки, диалоги, продажи.
"""

import time
import logging
from datetime import datetime, timedelta

import sys
sys.path.insert(0, "..")

from amocrm_client import AmoCRMClient
from telegram_bot import send_message

logger = logging.getLogger(__name__)


def build_manager_report(amo: AmoCRMClient):
    """Собирает отчёт по каждому менеджеру."""
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_start = int(yesterday.replace(hour=0, minute=0, second=0).timestamp())
    yesterday_end = int(yesterday.replace(hour=23, minute=59, second=59).timestamp())

    # Получаем менеджеров
    users = amo.get_users()
    # Фильтруем — только активные менеджеры (не админы/боты)
    managers = [u for u in users if u.get("rights", {}).get("is_active", True)]
    managers_map = {m["id"]: m["name"] for m in managers}

    # Получаем все активные сделки (не закрытые)
    all_leads = amo.get_all_leads()
    active_leads = [l for l in all_leads if l.get("status_id") not in (142, 143)]

    # Считаем сделки по менеджерам
    leads_by_manager = {}
    sales_by_manager = {}
    for lead in all_leads:
        resp_id = lead.get("responsible_user_id")
        if not resp_id or resp_id not in managers_map:
            continue

        # Активные сделки
        if lead.get("status_id") not in (142, 143):
            leads_by_manager[resp_id] = leads_by_manager.get(resp_id, 0) + 1

        # Продажи за вчера (успешно закрытые вчера)
        closed_at = lead.get("closed_at", 0)
        if lead.get("status_id") == 142 and yesterday_start <= closed_at <= yesterday_end:
            sales_by_manager[resp_id] = sales_by_manager.get(resp_id, 0) + 1

    # Получаем события за вчера — звонки и сообщения
    calls_by_manager = {}
    messages_by_manager = {}

    # Исходящие звонки
    call_events = amo.get_all_events(
        **{
            "filter[type]": "outgoing_call",
            "filter[created_at][from]": yesterday_start,
            "filter[created_at][to]": yesterday_end,
        }
    )
    for event in call_events:
        user_id = event.get("created_by")
        if user_id in managers_map:
            calls_by_manager[user_id] = calls_by_manager.get(user_id, 0) + 1

    # Входящие звонки тоже считаем
    incoming_calls = amo.get_all_events(
        **{
            "filter[type]": "incoming_call",
            "filter[created_at][from]": yesterday_start,
            "filter[created_at][to]": yesterday_end,
        }
    )
    for event in incoming_calls:
        user_id = event.get("created_by")
        if user_id in managers_map:
            calls_by_manager[user_id] = calls_by_manager.get(user_id, 0) + 1

    # Исходящие сообщения (диалоги)
    msg_events = amo.get_all_events(
        **{
            "filter[type]": "outgoing_chat_message",
            "filter[created_at][from]": yesterday_start,
            "filter[created_at][to]": yesterday_end,
        }
    )
    for event in msg_events:
        user_id = event.get("created_by")
        if user_id in managers_map:
            messages_by_manager[user_id] = messages_by_manager.get(user_id, 0) + 1

    # === ФОРМИРУЕМ ОТЧЁТ ===
    lines = [f"<b>📊 Отчёт по менеджерам за {yesterday.strftime('%d.%m.%Y')}</b>\n"]

    # Сортируем менеджеров по количеству сделок (от большего к меньшему)
    sorted_managers = sorted(
        managers_map.items(),
        key=lambda x: leads_by_manager.get(x[0], 0),
        reverse=True,
    )

    has_data = False
    for manager_id, manager_name in sorted_managers:
        leads_count = leads_by_manager.get(manager_id, 0)
        calls_count = calls_by_manager.get(manager_id, 0)
        msgs_count = messages_by_manager.get(manager_id, 0)
        sales_count = sales_by_manager.get(manager_id, 0)

        # Пропускаем менеджеров без активности
        if leads_count == 0 and calls_count == 0 and msgs_count == 0:
            continue

        has_data = True
        lines.append(f"<b>{manager_name}:</b>")
        lines.append(f"  👥 Клиентов в работе: {leads_count}")
        lines.append(f"  📞 Звонков: {calls_count}")
        lines.append(f"  💬 Диалогов: {msgs_count}")
        lines.append(f"  💰 Продаж: {sales_count}")
        lines.append("")

    if not has_data:
        lines.append("Нет данных по менеджерам за вчера.")

    # Итого
    total_leads = sum(leads_by_manager.values())
    total_calls = sum(calls_by_manager.values())
    total_msgs = sum(messages_by_manager.values())
    total_sales = sum(sales_by_manager.values())

    lines.append("<b>📈 Итого:</b>")
    lines.append(f"  👥 Клиентов в работе: {total_leads}")
    lines.append(f"  📞 Звонков: {total_calls}")
    lines.append(f"  💬 Диалогов: {total_msgs}")
    lines.append(f"  💰 Продаж: {total_sales}")

    return "\n".join(lines)


def send_manager_report(amo: AmoCRMClient):
    """Собирает и отправляет отчёт по менеджерам."""
    logger.info("Формирую отчёт по менеджерам...")
    try:
        report = build_manager_report(amo)
        send_message(report)
        logger.info("Отчёт по менеджерам отправлен")
    except Exception as e:
        logger.error(f"Ошибка отправки отчёта по менеджерам: {e}")
        send_message(f"❌ Ошибка отчёта по менеджерам: {e}")
