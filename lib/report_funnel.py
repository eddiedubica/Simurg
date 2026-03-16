"""Отчёт по конверсии воронки."""

from datetime import datetime

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

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


def build_funnel_report(amo):
    today = datetime.now()
    report_date = f"{today.day} {MONTHS_RU[today.month]}"

    all_leads = amo.get_all_leads()
    total = len(all_leads)

    stage_counts = {}
    for lead in all_leads:
        sid = lead.get("status_id", 0)
        stage_counts[sid] = stage_counts.get(sid, 0) + 1

    stage_order = {sid: i for i, (sid, _) in enumerate(FUNNEL_STAGES)}
    passed = {}
    for lead in all_leads:
        sid = lead.get("status_id", 0)
        pos = stage_order.get(sid, -1)
        for fsid, _ in FUNNEL_STAGES:
            if stage_order.get(fsid, -1) <= pos:
                passed[fsid] = passed.get(fsid, 0) + 1

    lines = [f"<b>📈 Конверсия воронки на {report_date}</b>\n"]
    lines.append(f"Всего сделок: {total}\n")

    lines.append("<b>Текущее распределение:</b>\n")
    for sid, name in FUNNEL_STAGES:
        count = stage_counts.get(sid, 0)
        if count > 0:
            pct = round(count / total * 100, 1) if total else 0
            bar = "█" * max(1, int(pct / 5))
            lines.append(f"  {name}: {count} ({pct}%) {bar}")

    closed = stage_counts.get(143, 0)
    if closed:
        lines.append(f"  Закрыто: {closed} ({round(closed / total * 100, 1)}%)")
    lines.append("")

    lines.append("<b>Конверсия по этапам:</b>\n")
    prev_count = None
    prev_name = None
    for sid, name in FUNNEL_STAGES:
        cur = passed.get(sid, 0)
        if cur == 0:
            continue
        if prev_count and prev_count > 0:
            conv = round(cur / prev_count * 100, 1)
            emoji = "🟢" if conv >= 50 else "🟡" if conv >= 25 else "🔴"
            lines.append(f"  {prev_name} → {name}: {emoji} {conv}%")
        prev_count = cur
        prev_name = name

    return "\n".join(lines)
