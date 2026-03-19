"""Отчёт по менеджерам из AmoCRM."""

from datetime import datetime, timedelta

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def build_manager_report(amo):
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_start = int(yesterday.replace(hour=0, minute=0, second=0).timestamp())
    yesterday_end = int(yesterday.replace(hour=23, minute=59, second=59).timestamp())
    report_date = f"{yesterday.day} {MONTHS_RU[yesterday.month]}"

    EXCLUDE_USERS = {"Владлена Шатилина", "Симург", "GSG"}
    users = amo.get_users()
    managers = [u for u in users if u.get("rights", {}).get("is_active", True) and u["name"] not in EXCLUDE_USERS]
    managers_map = {m["id"]: m["name"] for m in managers}

    all_leads = amo.get_all_leads()

    leads_by_mgr = {}
    sales_by_mgr = {}
    for lead in all_leads:
        rid = lead.get("responsible_user_id")
        if not rid or rid not in managers_map:
            continue
        if lead.get("status_id") not in (142, 143):
            leads_by_mgr[rid] = leads_by_mgr.get(rid, 0) + 1
        closed_at = lead.get("closed_at", 0)
        if lead.get("status_id") == 142 and yesterday_start <= closed_at <= yesterday_end:
            sales_by_mgr[rid] = sales_by_mgr.get(rid, 0) + 1

    calls_by_mgr = {}
    msgs_by_mgr = {}

    for etype in ("outgoing_call", "incoming_call"):
        events = amo.get_all_events(**{
            "filter[type]": etype,
            "filter[created_at][from]": yesterday_start,
            "filter[created_at][to]": yesterday_end,
        })
        for e in events:
            uid = e.get("created_by")
            if uid in managers_map:
                calls_by_mgr[uid] = calls_by_mgr.get(uid, 0) + 1

    msg_events = amo.get_all_events(**{
        "filter[type]": "outgoing_chat_message",
        "filter[created_at][from]": yesterday_start,
        "filter[created_at][to]": yesterday_end,
    })
    for e in msg_events:
        uid = e.get("created_by")
        if uid in managers_map:
            msgs_by_mgr[uid] = msgs_by_mgr.get(uid, 0) + 1

    lines = [f"<b>📊 Отчёт по менеджерам за {report_date}</b>\n"]

    sorted_mgrs = sorted(managers_map.items(), key=lambda x: leads_by_mgr.get(x[0], 0), reverse=True)

    has_data = False
    for mid, mname in sorted_mgrs:
        lc = leads_by_mgr.get(mid, 0)
        cc = calls_by_mgr.get(mid, 0)
        mc = msgs_by_mgr.get(mid, 0)
        sc = sales_by_mgr.get(mid, 0)
        if lc == 0 and cc == 0 and mc == 0:
            continue
        has_data = True
        lines.append(f"<b>{mname}:</b>")
        lines.append(f"  👥 Клиентов в работе: {lc}")
        lines.append(f"  📞 Звонков: {cc}")
        lines.append(f"  💬 Диалогов: {mc}")
        lines.append(f"  💰 Продаж: {sc}")
        lines.append("")

    if not has_data:
        lines.append("Нет данных по менеджерам за вчера.")

    tl = sum(leads_by_mgr.values())
    tc = sum(calls_by_mgr.values())
    tm = sum(msgs_by_mgr.values())
    ts = sum(sales_by_mgr.values())
    lines.append("<b>📈 Итого:</b>")
    lines.append(f"  👥 Клиентов в работе: {tl}")
    lines.append(f"  📞 Звонков: {tc}")
    lines.append(f"  💬 Диалогов: {tm}")
    lines.append(f"  💰 Продаж: {ts}")

    return "\n".join(lines)
