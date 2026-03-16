"""
Simurg — Автоматизация отдела продаж.

Расписание:
1. Мониторинг неотвеченных клиентов (каждые 10 мин)
2. Мониторинг зависших сделок (каждые 3 часа)
3. Ежедневный отчёт в чат ОП (9:00)
4. Отчёт по менеджерам (9:15)
5. Конверсия воронки (понедельник 9:30)
"""

import sys
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

from config import CHECK_INTERVAL_MINUTES, DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE
from amocrm_client import AmoCRMClient
from monitors.response_monitor import run_monitor
from monitors.stale_deals import run_stale_check
from reports.daily_report import send_daily_report
from reports.manager_report import send_manager_report
from reports.funnel_report import send_funnel_report
from telegram_bot import send_message

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("simurg.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("simurg")


def main():
    logger.info("🚀 Simurg запускается...")

    # Проверяем подключение к AmoCRM
    amo = AmoCRMClient()
    try:
        account = amo.get_account_info()
        logger.info(f"Подключено к AmoCRM: {account.get('name', 'OK')}")
    except Exception as e:
        logger.error(f"Не удалось подключиться к AmoCRM: {e}")
        send_message(f"❌ Simurg: не удалось подключиться к AmoCRM: {e}")
        sys.exit(1)

    send_message("✅ Simurg запущен. Мониторинг и отчёты активны.")

    scheduler = BlockingScheduler(timezone="Europe/Moscow")

    # === МОНИТОРИНГ ===

    # Неотвеченные клиенты — каждые N минут
    scheduler.add_job(
        run_monitor,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        args=[amo],
        id="response_monitor",
        name="Мониторинг неотвеченных клиентов",
    )

    # Зависшие сделки — каждые 3 часа (9:00, 12:00, 15:00, 18:00)
    scheduler.add_job(
        run_stale_check,
        "cron",
        hour="9,12,15,18",
        minute=0,
        args=[amo],
        id="stale_deals",
        name="Мониторинг зависших сделок",
    )

    # === ЕЖЕДНЕВНЫЕ ОТЧЁТЫ ===

    # Ежедневный отчёт ОП
    scheduler.add_job(
        send_daily_report,
        "cron",
        hour=DAILY_REPORT_HOUR,
        minute=DAILY_REPORT_MINUTE,
        args=[amo],
        id="daily_report",
        name="Ежедневный отчёт ОП",
    )

    # Отчёт по менеджерам
    scheduler.add_job(
        send_manager_report,
        "cron",
        hour=DAILY_REPORT_HOUR,
        minute=DAILY_REPORT_MINUTE + 15,
        args=[amo],
        id="manager_report",
        name="Отчёт по менеджерам",
    )

    # === ЕЖЕНЕДЕЛЬНЫЕ ОТЧЁТЫ ===

    # Конверсия воронки — каждый понедельник
    scheduler.add_job(
        send_funnel_report,
        "cron",
        day_of_week="mon",
        hour=DAILY_REPORT_HOUR,
        minute=DAILY_REPORT_MINUTE + 30,
        args=[amo],
        id="funnel_report",
        name="Конверсия воронки (еженедельно)",
    )

    logger.info("Расписание:")
    logger.info(f"  - Неотвеченные клиенты: каждые {CHECK_INTERVAL_MINUTES} мин")
    logger.info(f"  - Зависшие сделки: 9:00, 12:00, 15:00, 18:00")
    logger.info(f"  - Ежедневный отчёт: {DAILY_REPORT_HOUR}:{DAILY_REPORT_MINUTE:02d}")
    logger.info(f"  - Отчёт по менеджерам: {DAILY_REPORT_HOUR}:{DAILY_REPORT_MINUTE + 15:02d}")
    logger.info(f"  - Конверсия воронки: пн {DAILY_REPORT_HOUR}:{DAILY_REPORT_MINUTE + 30:02d}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Simurg остановлен.")


if __name__ == "__main__":
    main()
