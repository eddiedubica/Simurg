"""Отправка сообщений в Telegram."""

import os
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_SALES = os.getenv("TELEGRAM_CHAT_ID_SALES")
TELEGRAM_THREAD_ID_SALES = os.getenv("TELEGRAM_THREAD_ID_SALES")


def send_message(text, chat_id=None, thread_id=None, parse_mode="HTML"):
    """Отправить сообщение в Telegram чат (с поддержкой топиков)."""
    chat_id = chat_id or TELEGRAM_CHAT_ID_SALES
    thread_id = thread_id or TELEGRAM_THREAD_ID_SALES
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if thread_id:
        payload["message_thread_id"] = int(thread_id)

    if len(text) <= 4096:
        resp = requests.post(url, json=payload)
        return resp.json()

    lines = text.split("\n")
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 4000:
            p = {**payload, "text": chunk}
            requests.post(url, json=p)
            chunk = line + "\n"
        else:
            chunk += line + "\n"

    if chunk.strip():
        p = {**payload, "text": chunk}
        requests.post(url, json=p)
