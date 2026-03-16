"""
Ежедневный отчёт для чата отдела продаж.
Собирает данные из AmoCRM + Google Sheets.
"""

import locale
import logging
from datetime import datetime, timedelta

import sys
sys.path.insert(0, "..")

# Русская локаль для дат
try:
    locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
except locale.Error:
    pass

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

from amocrm_client import AmoCRMClient
from sheets_client import get_payments_data
from telegram_bot import send_message

logger = logging.getLogger(__name__)


def _format_number(n):
    """Форматирует число с разделителями: 1234567 -> 1 234 567"""
    return f"{n:,.0f}".replace(",", " ")


def _get_yesterday():
    """Вчерашняя дата."""
    return datetime.now() - timedelta(days=1)


def build_daily_report(amo: AmoCRMClient):
    """Собирает и форматирует ежедневный отчёт."""
    yesterday = _get_yesterday()
    yesterday_str = yesterday.strftime("%d.%m.%Y")
    report_date = f"{yesterday.day} {MONTHS_RU[yesterday.month]}"

    # === 1. ПОЛУЧАЕМ ВОРОНКИ И СТАТУСЫ ===
    pipelines = amo.get_pipelines()
    pipelines_map = {}
    for p in pipelines:
        statuses = {s["id"]: s["name"] for s in p.get("_embedded", {}).get("statuses", [])}
        pipelines_map[p["id"]] = {
            "name": p["name"],
            "statuses": statuses,
        }

    # === 2. СОБИРАЕМ СТАТИСТИКУ ПО БАЗАМ ===
    # Получаем все активные сделки
    all_leads = amo.get_all_leads()

    # Группируем по тегам/воронкам для формирования "баз в работе"
    bases = {}
    for lead in all_leads:
        tags = [t["name"] for t in lead.get("_embedded", {}).get("tags", [])]
        pipeline_id = lead.get("pipeline_id")
        pipeline_name = pipelines_map.get(pipeline_id, {}).get("name", "Без воронки")

        # Ключ базы — по тегу или по воронке
        base_key = tags[0] if tags else pipeline_name
        if base_key not in bases:
            bases[base_key] = {"total": 0, "processed": 0}

        bases[base_key]["total"] += 1

        # Считаем обработанными если есть примечание/задача/событие
        status_id = lead.get("status_id", 0)
        # Статус 142/143 — успешно/провально закрыта, считаем обработанной
        if status_id in (142, 143) or lead.get("loss_reason_id"):
            bases[base_key]["processed"] += 1
        elif lead.get("updated_at", 0) > lead.get("created_at", 0):
            bases[base_key]["processed"] += 1

    # === 3. ДАННЫЕ ИЗ GOOGLE SHEETS (ОПЛАТЫ) ===
    sales_today = 0
    total_sales = 0
    debitorka = 0
    full_payments = 0
    prepayments = 0

    try:
        payments = get_payments_data()
        for row in payments:
            # Пытаемся распарсить данные. Названия колонок зависят от таблицы
            amount = row.get("Сумма", row.get("сумма", row.get("amount", "0")))
            try:
                amount = float(str(amount).replace(" ", "").replace(",", ".").replace("₽", "").strip())
            except (ValueError, TypeError):
                amount = 0

            date_str = row.get("Дата", row.get("дата", row.get("date", "")))
            payment_type = row.get("Тип", row.get("тип", row.get("type", ""))).lower()
            status = row.get("Статус", row.get("статус", row.get("status", ""))).lower()

            # Суммируем
            total_sales += amount

            if yesterday_str in str(date_str):
                sales_today += amount

            if "дебитор" in status or "частич" in payment_type:
                debitorka += amount

            if "полн" in payment_type:
                full_payments += 1
            elif "предоплат" in payment_type or "аванс" in payment_type:
                prepayments += 1

    except Exception as e:
        logger.warning(f"Не удалось прочитать Google Sheets: {e}")

    # === 4. СДЕЛКИ ПО ТАРИФАМ ===
    tariff_stats = {}
    decision_stage_count = 0

    for lead in all_leads:
        # Кастомные поля — ищем "тариф"
        custom_fields = lead.get("custom_fields_values") or []
        for cf in custom_fields:
            if "тариф" in cf.get("field_name", "").lower():
                values = cf.get("values", [])
                tariff = values[0]["value"] if values else "Не указан"
                tariff_stats[tariff] = tariff_stats.get(tariff, 0) + 1

        # Этап "принятие решения" — ищем по названию статуса
        pipeline_id = lead.get("pipeline_id")
        status_id = lead.get("status_id")
        status_name = pipelines_map.get(pipeline_id, {}).get("statuses", {}).get(status_id, "")
        if "принят" in status_name.lower() and "решен" in status_name.lower():
            decision_stage_count += 1

    # === 5. ДИАГНОСТИКИ ===
    # Ищем воронку или тег "диагностик"
    diag_total = 0
    diag_yesterday = 0
    diag_paid = 0
    diag_offers = 0

    for lead in all_leads:
        tags = [t["name"].lower() for t in lead.get("_embedded", {}).get("tags", [])]
        pipeline_name = pipelines_map.get(lead.get("pipeline_id"), {}).get("name", "").lower()

        if "диагностик" in pipeline_name or any("диагностик" in t for t in tags):
            diag_total += 1
            created = lead.get("created_at", 0)
            created_date = datetime.fromtimestamp(created).date()
            if created_date == yesterday.date():
                diag_yesterday += 1
            if lead.get("status_id") == 142:  # Успешно закрыта
                diag_paid += 1

    diag_conversion = round(diag_paid / diag_total * 100, 1) if diag_total > 0 else 0

    # === 6. ФОРМИРУЕМ ОТЧЁТ ===
    lines = [f"<b>📊 Отчёт {report_date}</b>\n"]

    # Базы в работе
    if bases:
        lines.append("<b>Какие базы в работе:</b>\n")
        for name, counts in sorted(bases.items()):
            lines.append(f"– {name} {counts['processed']}/{counts['total']}")
        lines.append("")

    # Продажи
    lines.append(f"💰 Сумма продаж за {yesterday.strftime('%d %B')}: <b>{_format_number(sales_today)} руб.</b>")
    lines.append(f"💰 Дебиторка: <b>{_format_number(debitorka)} руб.</b>")
    lines.append(f"💰 Сумма запуска (факт): <b>{_format_number(total_sales)} руб.</b>")
    lines.append(f"💰 Сумма запуска (факт) + дебиторка = <b>{_format_number(total_sales + debitorka)} руб.</b>")
    lines.append("")

    # Тарифы
    if tariff_stats:
        for tariff, count in tariff_stats.items():
            lines.append(f"<b>{tariff}:</b>")
            lines.append(f"Кол-во продаж: {count}")
        lines.append("")

    lines.append(f"Кол-во полных продаж: {full_payments}")
    lines.append(f"Кол-во предоплат: {prepayments}")
    lines.append("")

    lines.append(f"На этапе принятия решения: <b>{decision_stage_count} человек</b>")
    lines.append("")

    # Диагностики
    if diag_total > 0:
        lines.append("<b>Статистика по диагностикам:</b>\n")
        lines.append(f"— За вчера проведено {diag_yesterday} диагностик")
        lines.append(f"— Суммарно проведено {diag_total} диагностик")
        lines.append(f"— Оплаты: {diag_paid}")
        lines.append(f"— Конверсия в оплату: {diag_conversion}%")
        lines.append("")

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
