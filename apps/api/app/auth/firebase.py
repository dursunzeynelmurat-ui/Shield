from __future__ import annotations

import json
import logging
import os

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

logger = logging.getLogger(__name__)

_initialized = False


def _init():
    global _initialized
    if _initialized or firebase_admin._apps:
        _initialized = True
        return
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        sa_dict = json.loads(sa_json)
        cred = credentials.Certificate(sa_dict)
        firebase_admin.initialize_app(cred)
        _initialized = True
        logger.info("Firebase Admin initialized from env var")
    else:
        logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON not set — Firebase auth disabled")


def verify_firebase_token(id_token: str) -> dict | None:
    """Verify a Firebase ID token. Returns decoded claims or None."""
    _init()
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        return None
