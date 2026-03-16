"""
Simurg — Автоматизация отдела продаж.

Запускает:
1. Мониторинг неотвеченных клиентов (каждые 10 мин)
2. Ежедневный отчёт в чат ОП (каждый день в 9:00)
3. Отчёт по менеджерам (каждый день в 9:15)
"""

import sys
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

from config import CHECK_INTERVAL_MINUTES, DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE
from amocrm_client import AmoCRMClient
from monitors.response_monitor import run_monitor
from reports.daily_report import send_daily_report
from reports.manager_report import send_manager_report
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

    # Мониторинг неотвеченных — каждые N минут
    scheduler.add_job(
        run_monitor,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        args=[amo],
        id="response_monitor",
        name="Мониторинг неотвеченных клиентов",
    )

    # Ежедневный отчёт — каждый день
    scheduler.add_job(
        send_daily_report,
        "cron",
        hour=DAILY_REPORT_HOUR,
        minute=DAILY_REPORT_MINUTE,
        args=[amo],
        id="daily_report",
        name="Ежедневный отчёт ОП",
    )

    # Отчёт по менеджерам — каждый день через 15 мин после основного
    scheduler.add_job(
        send_manager_report,
        "cron",
        hour=DAILY_REPORT_HOUR,
        minute=DAILY_REPORT_MINUTE + 15,
        args=[amo],
        id="manager_report",
        name="Отчёт по менеджерам",
    )

    logger.info(f"Расписание:")
    logger.info(f"  - Мониторинг неотвеченных: каждые {CHECK_INTERVAL_MINUTES} мин")
    logger.info(f"  - Ежедневный отчёт: {DAILY_REPORT_HOUR}:{DAILY_REPORT_MINUTE:02d}")
    logger.info(f"  - Отчёт по менеджерам: {DAILY_REPORT_HOUR}:{DAILY_REPORT_MINUTE + 15:02d}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Simurg остановлен.")


if __name__ == "__main__":
    main()
