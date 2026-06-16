# api/client.py
import os
import requests
import sseclient
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev_key_123")


def _headers(token: str = None) -> dict:
    h = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(path, token=None, params=None):
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=_headers(token), params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return None  # caller checks for None -> shows cached/warning
    except requests.exceptions.HTTPError:
        return None


def _post(path, body, token=None):
    try:
        r = requests.post(f"{BASE_URL}{path}", headers=_headers(token), json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return None
    except requests.exceptions.HTTPError:
        return None


def _post_stream(path, body, token=None):
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(token), json=body, stream=True, timeout=60)
    r.raise_for_status()
    return sseclient.SSEClient(r)


# AUTH
def login(persona: str) -> dict:
    return _post("/auth/login", {"persona": persona})


# BUSINESS PERSONA
def ask_question(question, user_id, token):
    return _post("/pipelines/ask", {"question": question, "requested_by": user_id, "persona": "business"}, token)


def get_pipeline_status(request_id, token):
    return _get(f"/pipelines/{request_id}/status", token)


def get_pipeline_history(user_id, persona, token):
    return _get("/pipelines/history", token, {"persona": persona, "user_id": user_id})


def get_suggestions(persona, token=None):
    return _get("/pipelines/suggestions", token, {"persona": persona})


def get_pipeline_answer(request_id, token):
    return _get(f"/pipelines/{request_id}/answer", token)




def set_notification(request_id, user_id, token):
    return _post(f"/pipelines/{request_id}/notify", {"user_id": user_id, "notify_via": "slack"}, token)


def delete_pipeline(request_id, token):
    try:
        r = requests.delete(f"{BASE_URL}/pipelines/{request_id}", headers=_headers(token), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ENGINEER PERSONA
def get_review_queue(token):
    return _get("/review/queue", token, {"status": "pending_review"})


def get_review_yaml(request_id, token):
    return _get(f"/review/{request_id}/yaml", token)


def approve_pipeline(request_id, approved_by, token):
    return _post_stream(f"/review/{request_id}/approve", {"approved_by": approved_by, "notes": ""}, token)


def reject_pipeline(request_id, rejected_by, reason, token):
    return _post(f"/review/{request_id}/reject", {"rejected_by": rejected_by, "reason": reason}, token)


def edit_pipeline(request_id, yaml_edited, edited_by, token):
    return _post(f"/review/{request_id}/edit", {"edited_by": edited_by, "yaml_edited": yaml_edited}, token)


def get_deployed_pipelines(token):
    return _get("/review/deployed", token)


# MONITOR
def get_monitor_metrics(token):
    return _get("/monitor/metrics", token)


def get_event_stream(token, limit=50):
    return _get("/monitor/event-stream", token, {"limit": limit})


# SYSTEM / MCP
def get_system_status():
    return _get("/system/status")


def get_mcp_status(token):
    return _get("/mcp/status", token)
