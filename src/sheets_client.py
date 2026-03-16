"""Клиент Google Sheets для чтения данных об оплатах."""

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_KEY

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def get_sheets_service():
    """Создать сервис Google Sheets."""
    creds = Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_KEY, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def read_sheet(range_name="Sheet1!A:Z"):
    """Прочитать данные из таблицы."""
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=range_name,
    ).execute()
    return result.get("values", [])


def get_payments_data(range_name="Sheet1!A:Z"):
    """Получить данные об оплатах из таблицы.

    Возвращает список словарей (заголовки = ключи).
    """
    rows = read_sheet(range_name)
    if len(rows) < 2:
        return []

    headers = rows[0]
    data = []
    for row in rows[1:]:
        # Дополняем строку пустыми значениями если она короче заголовков
        row_padded = row + [""] * (len(headers) - len(row))
        data.append(dict(zip(headers, row_padded)))
    return data
