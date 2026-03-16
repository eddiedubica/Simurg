"""Клиент AmoCRM API v4"""

import os
import time
import requests


class AmoCRMClient:
    def __init__(self):
        self.subdomain = os.getenv("AMOCRM_SUBDOMAIN")
        self.base_url = f"https://{self.subdomain}.amocrm.ru"
        self.access_token = os.getenv("AMOCRM_ACCESS_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        })

    def _request(self, method, endpoint, params=None, json=None):
        """Запрос к API."""
        url = f"{self.base_url}/api/v4/{endpoint}"
        resp = self.session.request(method, url, params=params, json=json)

        if resp.status_code == 204:
            return None
        if resp.status_code == 429:
            time.sleep(1)
            return self._request(method, endpoint, params=params, json=json)

        resp.raise_for_status()
        return resp.json()

    # === СДЕЛКИ ===

    def get_leads(self, page=1, limit=250, **filters):
        params = {"page": page, "limit": limit}
        params.update(filters)
        return self._request("GET", "leads", params=params)

    def get_all_leads(self, **filters):
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

    # === ВОРОНКИ ===

    def get_pipelines(self):
        data = self._request("GET", "leads/pipelines")
        if data and "_embedded" in data:
            return data["_embedded"]["pipelines"]
        return []

    # === ПОЛЬЗОВАТЕЛИ ===

    def get_users(self):
        data = self._request("GET", "users")
        if data and "_embedded" in data:
            return data["_embedded"]["users"]
        return []

    # === СОБЫТИЯ ===

    def get_all_events(self, **filters):
        all_events = []
        page = 1
        while True:
            params = {"page": page, "limit": 100}
            params.update(filters)
            data = self._request("GET", "events", params=params)
            if not data or "_embedded" not in data:
                break
            events = data["_embedded"]["events"]
            all_events.extend(events)
            if len(events) < 100:
                break
            page += 1
        return all_events

    # === КОНТАКТЫ ===

    def get_contact(self, contact_id):
        return self._request("GET", f"contacts/{contact_id}")

    def get_account_info(self):
        return self._request("GET", "account")
