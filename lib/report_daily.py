"""Ежедневный отчёт ОП из AmoCRM."""

from datetime import datetime, timedelta

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

STATUSES = {
    78894162: "Неразобранное",
    79023274: "Обращения",
    78894166: "Предзапись",
    78917170: "Заявка",
    84345658: "Первое касание",
    84345662: "Второе касание",
    84345666: "Третье касание",
    84345670: "Четвёртое касание",
    84345674: "Лид вышел на связь",
    84345678: "Оффер озвучен",
    84345682: "Счет выставлен",
    84345686: "Рассрочка одобрена",
    84345690: "Дожим",
    78917202: "Предоплата",
    78917206: "ВР",
    78917210: "Автооплата",
    79048314: "Возврат",
    142: "Успешно реализовано",
    143: "Закрыто и не реализовано",
}


def _fmt(n):
    return f"{n:,.0f}".replace(",", " ")


def _cf(lead, name):
    for cf in lead.get("custom_fields_values") or []:
        if cf.get("field_name") == name:
            vals = cf.get("values", [])
            return vals[0]["value"] if vals else None
    return None


def _cf_num(lead, name):
    val = _cf(lead, name)
    if val is None:
        return 0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def build_daily_report(amo):
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_start = int(yesterday.replace(hour=0, minute=0, second=0).timestamp())
    yesterday_end = int(yesterday.replace(hour=23, minute=59, second=59).timestamp())
    report_date = f"{today.day} {MONTHS_RU[today.month]}"

    all_leads = amo.get_all_leads()

    total_paid = 0
    total_debitorka = 0
    sales_yesterday = 0
    full_payments = 0
    prepayments = 0
    returns = 0
    auto_payments = 0
    auto_payments_sum = 0
    op_sales = 0
    op_sales_sum = 0
    consultations = 0
    consultations_sum = 0
    tariffs = {}
    stages = {}
    bases = {}

    for lead in all_leads:
        paid = _cf_num(lead, "Оплачено")
        left = _cf_num(lead, "Осталось оплатить")
        tariff_name = _cf(lead, "Название тарифа") or "Не указан"
        payment_type = _cf(lead, "Тип оплаты") or ""
        order_status = _cf(lead, "Статус заказа") or ""
        status_id = lead.get("status_id", 0)

        total_paid += paid
        total_debitorka += left

        updated = lead.get("updated_at", 0)
        if yesterday_start <= updated <= yesterday_end and paid > 0:
            sales_yesterday += paid

        # ОП vs Авто — по этапам Предоплата, ВР, Автооплата, Успешно
        payment_stages = {78917202, 78917206, 78917210, 142}
        if status_id in payment_stages and paid > 0:
            if payment_type in ("Оплата ОП", "Автооплата и Оплата ОП"):
                op_sales += 1
                op_sales_sum += paid
            elif payment_type == "Автооплата":
                auto_payments += 1
                auto_payments_sum += paid
            elif payment_type == "Консультация":
                consultations += 1
                consultations_sum += paid
            else:
                if status_id == 78917210:
                    auto_payments += 1
                    auto_payments_sum += paid
                else:
                    op_sales += 1
                    op_sales_sum += paid

        if payment_type == "Возврат" or status_id == 79048314:
            returns += 1

        if order_status == "Завершен" and paid > 0:
            full_payments += 1
        elif order_status == "Частично оплачен":
            prepayments += 1

        stage_name = STATUSES.get(status_id, f"Неизвестный ({status_id})")
        stages[stage_name] = stages.get(stage_name, 0) + 1

        if tariff_name != "Не указан":
            tariff_key = tariff_name
            if "ментор" in tariff_name.lower():
                tariff_key = "С ментором"
            elif "наставник" in tariff_name.lower():
                tariff_key = "С наставником"
            if tariff_key not in tariffs:
                tariffs[tariff_key] = {"count": 0, "paid": 0}
            tariffs[tariff_key]["count"] += 1
            tariffs[tariff_key]["paid"] += paid

        # Базы по тегам
        processed_stages = {
            84345658, 84345662, 84345666, 84345670, 84345674,
            84345678, 84345682, 84345686, 84345690,
            78917202, 78917206, 78917210, 79048314, 142, 143,
        }
        is_processed = status_id in processed_stages
        SKIP_TAGS = {"Автооплата", "Оплата ОП"}
        PRIORITY_TAGS = {"Предоплата", "ВР"}
        all_tags = [t["name"] for t in lead.get("_embedded", {}).get("tags", []) if t["name"] not in SKIP_TAGS]
        priority = [t for t in all_tags if t in PRIORITY_TAGS]
        tags = priority if priority else all_tags
        for tag in tags:
            if tag not in bases:
                bases[tag] = {"total": 0, "processed": 0}
            bases[tag]["total"] += 1
            if is_processed:
                bases[tag]["processed"] += 1

    decision_stages = ["Оффер озвучен", "Счет выставлен", "Рассрочка одобрена", "Дожим"]
    decision_count = sum(stages.get(s, 0) for s in decision_stages)

    # === ОТЧЁТ ===
    lines = [f"<b>📊 Отчёт {report_date}</b>\n"]

    if bases:
        lines.append("<b>Какие базы в работе:</b>\n")
        for tag, data in sorted(bases.items(), key=lambda x: -x[1]["total"]):
            lines.append(f"– {tag} {data['processed']}/{data['total']}")
        lines.append("")

    lines.append("<b>По этапам воронки:</b>\n")
    for sid in STATUSES:
        name = STATUSES[sid]
        count = stages.get(name, 0)
        if count > 0:
            lines.append(f"– {name}: {count}")
    lines.append("")

    lines.append(f"💰 Сумма продаж за {yesterday.day} {MONTHS_RU[yesterday.month]}: <b>{_fmt(sales_yesterday)} руб.</b>")
    lines.append(f"💰 Дебиторка: <b>{_fmt(total_debitorka)} руб.</b>")
    lines.append(f"💰 Сумма запуска (факт): <b>{_fmt(total_paid)} руб.</b>")
    lines.append(f"💰 Факт + дебиторка = <b>{_fmt(total_paid + total_debitorka)} руб.</b>")
    lines.append("")

    if tariffs:
        for name, data in sorted(tariffs.items()):
            lines.append(f"<b>{name}:</b>")
            lines.append(f"  Кол-во: {data['count']}")
            lines.append(f"  Оплачено: {_fmt(data['paid'])} руб.")
        lines.append("")

    lines.append("<b>Продажи ОП:</b>")
    lines.append(f"  Кол-во: {op_sales}")
    lines.append(f"  Сумма: {_fmt(op_sales_sum)} руб.")
    lines.append("")
    lines.append("<b>Автооплаты:</b>")
    lines.append(f"  Кол-во: {auto_payments}")
    lines.append(f"  Сумма: {_fmt(auto_payments_sum)} руб.")
    if consultations:
        lines.append("")
        lines.append("<b>Консультации:</b>")
        lines.append(f"  Кол-во: {consultations}")
        lines.append(f"  Сумма: {_fmt(consultations_sum)} руб.")
    lines.append("")

    lines.append(f"Кол-во полных оплат: {full_payments}")
    lines.append(f"Кол-во предоплат: {prepayments}")
    lines.append(f"Кол-во ВР: {stages.get('ВР', 0)}")
    if returns:
        lines.append(f"Кол-во возвратов: {returns}")
    lines.append("")

    lines.append(f"На этапе принятия решения: <b>{decision_count} человек</b>")

    return "\n".join(lines)
