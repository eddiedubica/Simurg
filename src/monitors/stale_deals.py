"""
Мониторинг зависших сделок.
Если сделка на активном этапе без изменений > N дней — алерт.
"""

import time
import logging
from datetime import datetime

import sys
sys.path.insert(0, "..")

from amocrm_client import AmoCRMClient
from telegram_bot import send_message

logger = logging.getLogger(__name__)

# Этапы на которых сделка не должна висеть долго (активная работа)
ACTIVE_STAGES = {
    84345658: ("Первое касание", 2),      # макс 2 дня
    84345662: ("Второе касание", 2),
    84345666: ("Третье касание", 2),
    84345670: ("Четвёртое касание", 3),
    84345674: ("Лид вышел на связь", 2),
    84345678: ("Оффер озвучен", 3),        # макс 3 дня
    84345682: ("Счет выставлен", 2),       # макс 2 дня
    84345686: ("Рассрочка одобрена", 3),
    84345690: ("Дожим", 5),                # макс 5 дней
}

# Не алертим повторно чаще чем раз в 24 часа
_alerted = {}


def check_stale_deals(amo: AmoCRMClient):
    """Проверяет сделки без активности."""
    now = int(time.time())

    users = amo.get_users()
    users_map = {u["id"]: u["name"] for u in users}

    all_leads = amo.get_all_leads()
    stale = []

    for lead in all_leads:
        status_id = lead.get("status_id", 0)
        if status_id not in ACTIVE_STAGES:
            continue

        stage_name, max_days = ACTIVE_STAGES[status_id]
        updated_at = lead.get("updated_at", 0)
        days_inactive = (now - updated_at) / 86400

        if days_inactive < max_days:
            continue

        lead_id = lead["id"]

        # Не спамим
        last_alert = _alerted.get(lead_id, 0)
        if now - last_alert < 86400:
            continue

        responsible_id = lead.get("responsible_user_id")
        manager = users_map.get(responsible_id, "Не назначен")
        lead_name = lead.get("name", "Без названия")
        lead_url = f"{amo.base_url}/leads/detail/{lead_id}"

        stale.append({
            "lead_id": lead_id,
            "name": lead_name,
            "stage": stage_name,
            "days": round(days_inactive, 1),
            "manager": manager,
            "url": lead_url,
        })
        _alerted[lead_id] = now

    if not stale:
        logger.info("Зависших сделок нет")
        return

    # Группируем по менеджерам
    by_manager = {}
    for s in stale:
        m = s["manager"]
        if m not in by_manager:
            by_manager[m] = []
        by_manager[m].append(s)

    lines = [f"⚠️ <b>Зависшие сделки ({len(stale)} шт.)</b>\n"]

    for manager, deals in sorted(by_manager.items()):
        lines.append(f"<b>{manager}:</b>")
        for d in deals:
            lines.append(
                f"  • <a href=\"{d['url']}\">{d['name']}</a> — "
                f"{d['stage']}, {d['days']} дн. без активности"
            )
        lines.append("")

    send_message("\n".join(lines))
    logger.info(f"Отправлен алерт по {len(stale)} зависшим сделкам")


def run_stale_check(amo: AmoCRMClient):
    """Запуск проверки зависших сделок."""
    logger.info("Проверяю зависшие сделки...")
    try:
        check_stale_deals(amo)
    except Exception as e:
        logger.error(f"Ошибка проверки зависших: {e}")
