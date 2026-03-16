"""
Отчёт по конверсии воронки.
Показывает сколько % переходит с этапа на этап и где "дыра".
"""

import logging
from datetime import datetime

import sys
sys.path.insert(0, "..")

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

from amocrm_client import AmoCRMClient
from telegram_bot import send_message

logger = logging.getLogger(__name__)

# Этапы воронки "База" в порядке движения сделки
FUNNEL_STAGES = [
    (79023274, "Обращения"),
    (78894166, "Предзапись"),
    (78917170, "Заявка"),
    (84345658, "Первое касание"),
    (84345662, "Второе касание"),
    (84345666, "Третье касание"),
    (84345670, "Четвёртое касание"),
    (84345674, "Лид вышел на связь"),
    (84345678, "Оффер озвучен"),
    (84345682, "Счет выставлен"),
    (84345686, "Рассрочка одобрена"),
    (84345690, "Дожим"),
    (78917202, "Предоплата"),
    (78917206, "ВР"),
    (78917210, "Автооплата"),
    (142, "Успешно реализовано"),
]


def build_funnel_report(amo: AmoCRMClient):
    """Строит отчёт по конверсии воронки."""
    today = datetime.now()
    report_date = f"{today.day} {MONTHS_RU[today.month]}"

    all_leads = amo.get_all_leads()

    # Считаем сделки на каждом этапе
    # Важно: сделка на этапе "Оффер" уже ПРОШЛА все предыдущие этапы
    stage_counts = {}
    for lead in all_leads:
        status_id = lead.get("status_id", 0)
        stage_counts[status_id] = stage_counts.get(status_id, 0) + 1

    # Также считаем сделки которые ПРОШЛИ через каждый этап
    # (находятся на этом этапе или дальше)
    stage_order = {sid: i for i, (sid, _) in enumerate(FUNNEL_STAGES)}

    passed_through = {}
    for lead in all_leads:
        status_id = lead.get("status_id", 0)
        lead_position = stage_order.get(status_id, -1)

        # Сделка прошла через все этапы до текущего включительно
        for sid, name in FUNNEL_STAGES:
            stage_pos = stage_order.get(sid, -1)
            if stage_pos <= lead_position:
                passed_through[sid] = passed_through.get(sid, 0) + 1

    # Также учитываем закрытые (143) — они тоже прошли через какие-то этапы
    # но мы не знаем через какие, поэтому не считаем их

    total_leads = len(all_leads)

    # Формируем отчёт
    lines = [f"<b>📈 Конверсия воронки на {report_date}</b>\n"]
    lines.append(f"Всего сделок: {total_leads}\n")

    lines.append("<b>Текущее распределение:</b>\n")

    for sid, name in FUNNEL_STAGES:
        count = stage_counts.get(sid, 0)
        if count > 0:
            pct = round(count / total_leads * 100, 1) if total_leads > 0 else 0
            bar = "█" * max(1, int(pct / 5))
            lines.append(f"  {name}: {count} ({pct}%) {bar}")

    # Закрытые
    closed_lost = stage_counts.get(143, 0)
    if closed_lost:
        pct = round(closed_lost / total_leads * 100, 1)
        lines.append(f"  Закрыто: {closed_lost} ({pct}%)")

    lines.append("")

    # Конверсия между этапами
    lines.append("<b>Конверсия по этапам:</b>\n")

    prev_count = None
    prev_name = None
    for sid, name in FUNNEL_STAGES:
        current = passed_through.get(sid, 0)
        if current == 0:
            continue

        if prev_count is not None and prev_count > 0:
            conversion = round(current / prev_count * 100, 1)
            emoji = "🟢" if conversion >= 50 else "🟡" if conversion >= 25 else "🔴"
            lines.append(f"  {prev_name} → {name}: {emoji} {conversion}%")

        prev_count = current
        prev_name = name

    return "\n".join(lines)


def send_funnel_report(amo: AmoCRMClient):
    """Отправляет отчёт по конверсии."""
    logger.info("Формирую отчёт по конверсии воронки...")
    try:
        report = build_funnel_report(amo)
        send_message(report)
        logger.info("Отчёт по конверсии отправлен")
    except Exception as e:
        logger.error(f"Ошибка отчёта по конверсии: {e}")
        send_message(f"❌ Ошибка отчёта по конверсии: {e}")
