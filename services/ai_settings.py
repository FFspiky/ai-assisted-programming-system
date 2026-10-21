"""Per-account AI credentials. Plaintext keys never enter API responses or cookies."""

import os
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from config import API_URL, MODEL_NAME
from models import UserAISettings, db


def cipher():
    key = os.getenv("AI_CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        path = Path(current_app.instance_path) / "ai-credentials.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as handle:
                handle.write(Fernet.generate_key())
        except FileExistsError:
            pass
        key = path.read_bytes()
    return Fernet(key)


def resolve_key(user_id):
    from services.ai_client import API_KEY

    row = db.session.get(UserAISettings, user_id)
    if not row:
        return ""
    if row.mode == "test":
        return API_KEY
    if row.mode == "custom" and row.encrypted_key:
        try:
            return cipher().decrypt(row.encrypted_key).decode()
        except InvalidToken:
            return ""
    return ""


def settings_payload(user_id):
    from services.ai_client import API_KEY

    row = db.session.get(UserAISettings, user_id)
    return {
        "mode": row.mode if row else "none",
        "configured": bool(resolve_key(user_id)),
        "test_available": bool(API_KEY),
        "provider": urlparse(API_URL).hostname,
        "model": MODEL_NAME,
        "has_custom_key": bool(row and row.encrypted_key),
    }
