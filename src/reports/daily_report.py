"""
Ежедневный отчёт для чата отдела продаж.
Данные берутся из AmoCRM (кастомные поля сделок).

Поля AmoCRM:
- Оплачено (ID 821273) — сумма оплаты
- Осталось оплатить (ID 821275) — дебиторка
- Стоимость тарифа (ID 821277) — полная цена
- Название тарифа (ID 821271) — название тарифа
- Тип оплаты (ID 843125) — Автооплата / Оплата ОП / Консультация / Возврат
- Статус заказа (ID 843285) — Новый / Частично оплачен / Завершен / Отменен

Этапы воронки "База" (ID 9932206):
- Обращения, Предзапись, Заявка, Первое-Четвёртое касание,
  Лид вышел на связь, Оффер озвучен, Счет выставлен,
  Рассрочка одобрена, Дожим, Предоплата, ВР, Автооплата, Возврат
"""

import logging
from datetime import datetime, timedelta

import sys
sys.path.insert(0, "..")

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

# Этапы воронки "База" — ID статусов
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

from amocrm_client import AmoCRMClient
from telegram_bot import send_message

logger = logging.getLogger(__name__)


def _format_number(n):
    """1234567 -> 1 234 567"""
    return f"{n:,.0f}".replace(",", " ")


def _get_cf(lead, field_name):
    """Получить значение кастомного поля сделки."""
    for cf in lead.get("custom_fields_values") or []:
        if cf.get("field_name") == field_name:
            values = cf.get("values", [])
            return values[0]["value"] if values else None
    return None


def _get_cf_num(lead, field_name):
    """Получить числовое значение кастомного поля."""
    val = _get_cf(lead, field_name)
    if val is None:
        return 0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def build_daily_report(amo: AmoCRMClient):
    """Собирает ежедневный отчёт из AmoCRM."""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_start = int(yesterday.replace(hour=0, minute=0, second=0).timestamp())
    yesterday_end = int(yesterday.replace(hour=23, minute=59, second=59).timestamp())
    report_date = f"{today.day} {MONTHS_RU[today.month]}"

    # Все сделки
    all_leads = amo.get_all_leads()

    # === ПОДСЧЁТЫ ===
    total_paid = 0          # Общая сумма оплат (факт)
    total_debitorka = 0     # Общая дебиторка
    sales_yesterday = 0     # Продажи за вчера
    full_payments = 0       # Полные оплаты
    prepayments = 0         # Предоплаты
    returns = 0             # Возвраты (ВР)
    auto_payments = 0       # Автооплаты

    # По тарифам
    tariffs = {}            # {название: {"count": N, "paid": сумма}}

    # По этапам воронки
    stages = {}             # {название_этапа: кол-во}

    # По тегам (базы)
    bases = {}              # {тег: кол-во}

    # По типу оплаты
    op_sales = 0            # Продажи ОП
    consultations = 0       # Консультации

    for lead in all_leads:
        paid = _get_cf_num(lead, "Оплачено")
        left = _get_cf_num(lead, "Осталось оплатить")
        tariff_name = _get_cf(lead, "Название тарифа") or "Не указан"
        payment_type = _get_cf(lead, "Тип оплаты") or ""
        order_status = _get_cf(lead, "Статус заказа") or ""
        status_id = lead.get("status_id", 0)

        # Общие суммы
        total_paid += paid
        total_debitorka += left

        # Продажи за вчера (по дате обновления)
        updated = lead.get("updated_at", 0)
        if yesterday_start <= updated <= yesterday_end and paid > 0:
            sales_yesterday += paid

        # Подсчёт по типу оплаты
        if payment_type == "Оплата ОП":
            op_sales += 1
        elif payment_type == "Консультация":
            consultations += 1
        elif payment_type == "Автооплата":
            auto_payments += 1
        elif payment_type == "Возврат":
            returns += 1

        # Полные vs предоплаты
        if order_status == "Завершен" and paid > 0:
            full_payments += 1
        elif order_status == "Частично оплачен":
            prepayments += 1

        # По этапам воронки
        stage_name = STATUSES.get(status_id, f"Неизвестный ({status_id})")
        stages[stage_name] = stages.get(stage_name, 0) + 1

        # По тарифам (группируем по ключевым словам)
        tariff_key = tariff_name
        if "ментор" in tariff_name.lower():
            tariff_key = "С ментором"
        elif "наставник" in tariff_name.lower():
            tariff_key = "С наставником"

        if tariff_key not in tariffs:
            tariffs[tariff_key] = {"count": 0, "paid": 0}
        tariffs[tariff_key]["count"] += 1
        tariffs[tariff_key]["paid"] += paid

        # По тегам (базы)
        tags = [t["name"] for t in lead.get("_embedded", {}).get("tags", [])]
        for tag in tags:
            bases[tag] = bases.get(tag, 0) + 1

    # Этапы где идёт "дожим" (оффер, счёт, рассрочка, дожим)
    decision_stages = ["Оффер озвучен", "Счет выставлен", "Рассрочка одобрена", "Дожим"]
    decision_count = sum(stages.get(s, 0) for s in decision_stages)

    # === ФОРМИРУЕМ ОТЧЁТ ===
    lines = [f"<b>📊 Отчёт {report_date}</b>\n"]

    # Базы в работе (по тегам)
    if bases:
        lines.append("<b>Какие базы в работе:</b>\n")
        for tag, count in sorted(bases.items(), key=lambda x: -x[1]):
            lines.append(f"– {tag}: {count}")
        lines.append("")

    # Распределение по этапам воронки
    lines.append("<b>По этапам воронки:</b>\n")
    for status_id_key in STATUSES:
        name = STATUSES[status_id_key]
        count = stages.get(name, 0)
        if count > 0:
            lines.append(f"– {name}: {count}")
    lines.append("")

    # Продажи
    lines.append(f"💰 Сумма продаж за {yesterday.day} {MONTHS_RU[yesterday.month]}: <b>{_format_number(sales_yesterday)} руб.</b>")
    lines.append(f"💰 Дебиторка: <b>{_format_number(total_debitorka)} руб.</b>")
    lines.append(f"💰 Сумма запуска (факт): <b>{_format_number(total_paid)} руб.</b>")
    lines.append(f"💰 Факт + дебиторка = <b>{_format_number(total_paid + total_debitorka)} руб.</b>")
    lines.append("")

    # Тарифы
    if tariffs:
        for name, data in sorted(tariffs.items()):
            lines.append(f"<b>{name}:</b>")
            lines.append(f"  Кол-во: {data['count']}")
            lines.append(f"  Оплачено: {_format_number(data['paid'])} руб.")
        lines.append("")

    lines.append(f"Кол-во полных оплат: {full_payments}")
    lines.append(f"Кол-во предоплат: {prepayments}")
    lines.append(f"Кол-во ВР: {stages.get('ВР', 0)}")
    lines.append(f"Кол-во автооплат: {auto_payments}")
    if returns:
        lines.append(f"Кол-во возвратов: {returns}")
    lines.append("")

    lines.append(f"На этапе принятия решения: <b>{decision_count} человек</b>")

    return "\n".join(lines)


def send_daily_report(amo: AmoCRMClient):
    """Собирает и отправляет ежедневный отчёт."""
    logger.info("Формирую ежедневный отчёт...")
    try:
        report = build_daily_report(amo)
        send_message(report)
        logger.info("Ежедневный отчёт отправлен")
    except Exception as e:
        logger.error(f"Ошибка отправки отчёта: {e}")
        send_message(f"❌ Ошибка формирования отчёта: {e}")
