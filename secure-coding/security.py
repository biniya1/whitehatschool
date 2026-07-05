import os
import time
import uuid
from collections import defaultdict, deque
from functools import wraps

from flask import session, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename

from extensions import db
from models import User


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None:
        session.clear()
        return None
    if not user.is_active:
        # Account was suspended (e.g. crossed the report threshold) after the
        # session was created -- force logout instead of trusting the cookie.
        session.clear()
        return None
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            flash("로그인이 필요합니다.")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            flash("로그인이 필요합니다.")
            return redirect(url_for("auth.login"))
        if not user.is_admin:
            flash("관리자만 접근할 수 있습니다.")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Image upload validation
# ---------------------------------------------------------------------------

def _allowed_extension(filename, allowed_extensions):
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    return ext if ext in allowed_extensions else None


def save_product_image(file_storage, upload_folder, allowed_extensions):
    """Validate and persist an uploaded product image.

    Returns the stored filename, or None if no file was supplied.
    Raises ValueError with a user-safe message if the file is invalid.
    """
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    ext = _allowed_extension(filename, allowed_extensions)
    if ext is None:
        raise ValueError("허용되지 않는 파일 형식입니다.")

    # Verify the bytes are actually a valid image (not just a renamed file)
    # rather than trusting the extension/content-type alone.
    try:
        from PIL import Image
        file_storage.stream.seek(0)
        Image.open(file_storage.stream).verify()
        file_storage.stream.seek(0)
    except Exception:
        raise ValueError("올바른 이미지 파일이 아닙니다.")

    os.makedirs(upload_folder, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_folder, stored_name))
    return stored_name


# ---------------------------------------------------------------------------
# Chat rate limiting (in-memory sliding window; fine for a single dev-server
# process -- a multi-worker production deployment would need a shared store
# such as Redis instead).
# ---------------------------------------------------------------------------

class ChatRateLimiter:
    def __init__(self, max_messages, window_seconds):
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self._log = defaultdict(deque)

    def is_limited(self, key):
        now = time.time()
        dq = self._log[key]
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()
        if len(dq) >= self.max_messages:
            return True
        dq.append(now)
        return False


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

def apply_security_headers(response, request):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response
