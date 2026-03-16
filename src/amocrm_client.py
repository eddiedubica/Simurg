"""Клиент AmoCRM API v4"""

import time
import requests
from config import (
    AMOCRM_BASE_URL, AMOCRM_ACCESS_TOKEN, AMOCRM_REFRESH_TOKEN,
    AMOCRM_CLIENT_ID, AMOCRM_CLIENT_SECRET, AMOCRM_REDIRECT_URI
)


class AmoCRMClient:
    def __init__(self):
        self.base_url = AMOCRM_BASE_URL
        self.access_token = AMOCRM_ACCESS_TOKEN
        self.refresh_token = AMOCRM_REFRESH_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        })

    def _request(self, method, endpoint, params=None, json=None):
        """Запрос к API с автообновлением токена."""
        url = f"{self.base_url}/api/v4/{endpoint}"
        resp = self.session.request(method, url, params=params, json=json)

        if resp.status_code == 401:
            self._refresh_token()
            resp = self.session.request(method, url, params=params, json=json)

        if resp.status_code == 204:
            return None
        if resp.status_code == 429:
            time.sleep(1)
            return self._request(method, endpoint, params=params, json=json)

        resp.raise_for_status()
        return resp.json()

    def _refresh_token(self):
        """Обновление access_token через refresh_token."""
        resp = requests.post(f"{self.base_url}/oauth2/access_token", json={
            "client_id": AMOCRM_CLIENT_ID,
            "client_secret": AMOCRM_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "redirect_uri": AMOCRM_REDIRECT_URI,
        })
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

        # Сохраняем новые токены в .env
        self._save_tokens(data["access_token"], data["refresh_token"])

    def _save_tokens(self, access_token, refresh_token):
        """Обновляет токены в .env файле."""
        try:
            with open(".env", "r") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                if line.startswith("AMOCRM_ACCESS_TOKEN="):
                    new_lines.append(f"AMOCRM_ACCESS_TOKEN={access_token}\n")
                elif line.startswith("AMOCRM_REFRESH_TOKEN="):
                    new_lines.append(f"AMOCRM_REFRESH_TOKEN={refresh_token}\n")
                else:
                    new_lines.append(line)
            with open(".env", "w") as f:
                f.writelines(new_lines)
        except FileNotFoundError:
            pass

    # === СДЕЛКИ (LEADS) ===

    def get_leads(self, page=1, limit=250, **filters):
        """Получить сделки с фильтрами."""
        params = {"page": page, "limit": limit}
        params.update(filters)
        return self._request("GET", "leads", params=params)

    def get_all_leads(self, **filters):
        """Получить ВСЕ сделки (с пагинацией)."""
        all_leads = []
        page = 1
        while True:
            data = self.get_leads(page=page, **filters)
            if not data or "_embedded" not in data:
                break
            leads = data["_embedded"]["leads"]
            all_leads.extend(leads)
            if len(leads) < 250:
                break
            page += 1
        return all_leads

    def get_leads_by_pipeline(self, pipeline_id, status_id=None):
        """Сделки по воронке и опционально по статусу."""
        filters = {"filter[pipe_id]": pipeline_id}
        if status_id:
            filters["filter[statuses][0][pipeline_id]"] = pipeline_id
            filters["filter[statuses][0][status_id]"] = status_id
        return self.get_all_leads(**filters)

    # === ВОРОНКИ И СТАТУСЫ ===

    def get_pipelines(self):
        """Все воронки со статусами."""
        data = self._request("GET", "leads/pipelines")
        if data and "_embedded" in data:
            return data["_embedded"]["pipelines"]
        return []

    # === КОНТАКТЫ ===

    def get_contact(self, contact_id):
        """Получить контакт по ID."""
        return self._request("GET", f"contacts/{contact_id}")

    # === ПОЛЬЗОВАТЕЛИ (МЕНЕДЖЕРЫ) ===

    def get_users(self):
        """Все пользователи аккаунта."""
        data = self._request("GET", "users")
        if data and "_embedded" in data:
            return data["_embedded"]["users"]
        return []

    # === СОБЫТИЯ ===

    def get_events(self, **filters):
        """Получить события с фильтрами."""
        params = {"limit": 100}
        params.update(filters)
        return self._request("GET", "events", params=params)

    def get_all_events(self, **filters):
        """Все события с пагинацией."""
        all_events = []
        page = 1
        while True:
            filters_with_page = {"page": page, **filters}
            data = self.get_events(**filters_with_page)
            if not data or "_embedded" not in data:
                break
            events = data["_embedded"]["events"]
            all_events.extend(events)
            if len(events) < 100:
                break
            page += 1
        return all_events

    # === ЗВОНКИ ===

    def get_calls(self, **filters):
        """Получить звонки."""
        return self._request("GET", "calls", params=filters)

    # === ЗАДАЧИ ===

    def create_task(self, lead_id, text, responsible_user_id, complete_till):
        """Создать задачу по сделке."""
        return self._request("POST", "tasks", json=[{
            "entity_id": lead_id,
            "entity_type": "leads",
            "text": text,
            "responsible_user_id": responsible_user_id,
            "complete_till": complete_till,
        }])

    # === TALKS (ЧАТЫ) ===

    def get_talks(self, **filters):
        """Получить чаты/диалоги."""
        params = {"limit": 100}
        params.update(filters)
        return self._request("GET", "talks", params=params)

    # === ВСПОМОГАТЕЛЬНЫЕ ===

    def get_lead_with_contacts(self, lead_id):
        """Сделка с контактами."""
        return self._request("GET", f"leads/{lead_id}", params={
            "with": "contacts"
        })

    def get_account_info(self):
        """Информация об аккаунте."""
        return self._request("GET", "account")
