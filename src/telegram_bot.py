"""Отправка сообщений в Telegram."""

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID_SALES


def send_message(text, chat_id=None, parse_mode="HTML"):
    """Отправить сообщение в Telegram чат."""
    chat_id = chat_id or TELEGRAM_CHAT_ID_SALES
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Telegram лимит — 4096 символов. Если больше — разбиваем
    if len(text) <= 4096:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        })
        return resp.json()

    # Разбиваем длинное сообщение по строкам
    lines = text.split("\n")
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 4000:
            requests.post(url, json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
            })
            chunk = line + "\n"
        else:
            chunk += line + "\n"

    if chunk.strip():
        requests.post(url, json={
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
        })
