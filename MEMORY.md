# Simurg — Автоматизация отдела продаж (AmoCRM)

## Цель
Автоматизация отчётности и контроля отдела продаж:
1. Ежедневный отчёт в Telegram-чат ОП (данные из AmoCRM + Google Sheets)
2. Уведомления если клиенту не отвечают 1.5 часа
3. Отчёт по работе менеджеров (клиенты, звонки, диалоги)

## Stack
- Python 3.11+
- amocrm-api / requests (работа с AmoCRM API)
- google-api-python-client (Google Sheets)
- python-telegram-bot / aiogram (Telegram)
- APScheduler или cron (расписание)

## Источники данных
- AmoCRM API — сделки, контакты, события, звонки, воронки
- Google Sheets — таблица оплат: https://docs.google.com/spreadsheets/d/15aUo-QchmT5YFdTyrKuSdX4l6MAYNnC7tYe89LGo_lo/
- Telegram — канал доставки отчётов и уведомлений

## Структура
```
Simurg/
├── MEMORY.md
├── .env.example
├── .gitignore
├── requirements.txt
├── src/
│   ├── config.py          — настройки, env переменные
│   ├── amocrm_client.py   — клиент AmoCRM API
│   ├── sheets_client.py   — клиент Google Sheets API
│   ├── telegram_bot.py    — отправка сообщений в Telegram
│   ├── reports/
│   │   ├── daily_report.py    — ежедневный отчёт ОП
│   │   └── manager_report.py  — отчёт по менеджерам
│   ├── monitors/
│   │   └── response_monitor.py — мониторинг времени ответа
│   └── main.py            — точка входа, расписание
```

## .env секреты
- AMOCRM_SUBDOMAIN — поддомен в AmoCRM
- AMOCRM_CLIENT_ID / CLIENT_SECRET — OAuth приложение AmoCRM
- AMOCRM_ACCESS_TOKEN / REFRESH_TOKEN — токены авторизации
- GOOGLE_SHEETS_ID — ID таблицы оплат
- GOOGLE_SERVICE_ACCOUNT_KEY — путь к ключу сервисного аккаунта Google
- TELEGRAM_BOT_TOKEN — токен Telegram бота
- TELEGRAM_CHAT_ID_SALES — ID чата отдела продаж

## Как запускать
```bash
python src/main.py
```

## Известные проблемы
- (пока нет)

## История изменений
- 2026-03-17: Инициализация проекта, планирование архитектуры
