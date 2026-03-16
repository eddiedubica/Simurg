"""
Vercel Serverless Function — отправка всех отчётов.
Вызывается по крону каждый день в 9:00 МСК.
"""

import os
import sys
import time
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# Добавляем путь к lib/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from amocrm_client import AmoCRMClient
from telegram_bot import send_message
from report_daily import build_daily_report
from report_managers import build_manager_report
from report_funnel import build_funnel_report

# Секрет для защиты эндпоинта (опционально)
CRON_SECRET = os.getenv("CRON_SECRET", "")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Проверяем секрет если установлен
        if CRON_SECRET:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {CRON_SECRET}":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return

        results = []

        try:
            amo = AmoCRMClient()

            # 1. Ежедневный отчёт
            try:
                report = build_daily_report(amo)
                send_message(report)
                results.append("daily_report: OK")
            except Exception as e:
                results.append(f"daily_report: ERROR - {e}")
                send_message(f"❌ Ошибка ежедневного отчёта: {e}")

            # Пауза чтобы не спамить
            time.sleep(3)

            # 2. Отчёт по менеджерам
            try:
                report = build_manager_report(amo)
                send_message(report)
                results.append("manager_report: OK")
            except Exception as e:
                results.append(f"manager_report: ERROR - {e}")

            # 3. Конверсия воронки — только по понедельникам
            now = datetime.now()
            if now.weekday() == 0:  # Понедельник
                time.sleep(3)
                try:
                    report = build_funnel_report(amo)
                    send_message(report)
                    results.append("funnel_report: OK")
                except Exception as e:
                    results.append(f"funnel_report: ERROR - {e}")
            else:
                results.append("funnel_report: SKIPPED (not Monday)")

        except Exception as e:
            results.append(f"CRITICAL: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"results": results}).encode())
