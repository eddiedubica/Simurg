"""Клиент AmoCRM API v4"""

import os
import time
import requests


class AmoCRMClient:
    def __init__(self):
        self.subdomain = os.getenv("AMOCRM_SUBDOMAIN", "").strip()
        self.base_url = f"https://{self.subdomain}.amocrm.ru"
        self.access_token = os.getenv("AMOCRM_ACCESS_TOKEN", "").strip()
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

    # === ЗАМЕТКИ ===

    def get_lead_notes(self, lead_id, **filters):
        """Получить все заметки лида с пагинацией."""
        all_notes = []
        page = 1
        while True:
            params = {"page": page, "limit": 250}
            params.update(filters)
            data = self._request("GET", f"leads/{lead_id}/notes", params=params)
            if not data or "_embedded" not in data:
                break
            notes = data["_embedded"]["notes"]
            all_notes.extend(notes)
            if len(notes) < 250:
                break
            page += 1
        return all_notes

    def get_call_notes_batch(self, events):
        """Пакетное получение заметок звонков. Группирует по lead_id → один запрос на лид."""
        # Собираем маппинг: note_id → created_by (кто звонил)
        note_to_user = {}
        leads_needed = set()
        for e in events:
            va = e.get("value_after", [])
            if not va:
                continue
            note_info = va[0].get("note", {})
            note_id = note_info.get("id")
            entity_id = e.get("entity_id")
            if note_id and entity_id:
                note_to_user[note_id] = e.get("created_by")
                leads_needed.add(entity_id)

        # Пакетно: один запрос на лид, получаем все call-заметки
        result = []
        for lead_id in leads_needed:
            try:
                notes = self.get_lead_notes(lead_id, **{
                    "filter[note_type]": "call_out,call_in",
                })
                for note in notes:
                    nid = note.get("id")
                    if nid in note_to_user:
                        note["_event_created_by"] = note_to_user[nid]
                        result.append(note)
            except Exception:
                continue
        return result

    # === КОНТАКТЫ ===

    def get_contact(self, contact_id):
        return self._request("GET", f"contacts/{contact_id}")

    def get_account_info(self):
        return self._request("GET", "account")
