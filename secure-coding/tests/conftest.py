import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config  # noqa: E402


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    Config.SQLALCHEMY_DATABASE_URI = "sqlite:///" + db_path
    Config.SECRET_KEY = "test-secret-key-not-for-production"
    Config.WTF_CSRF_ENABLED = True

    from app import create_app
    from extensions import db

    flask_app = create_app()
    flask_app.config.update(TESTING=True)

    with flask_app.app_context():
        db.create_all()

    # Deliberately don't keep this app_context open across the test body:
    # Flask reuses an already-active app context for the test client's
    # requests instead of pushing a fresh one, which leaks Flask-WTF's
    # per-context `g`-cached CSRF token across what should be independent
    # requests (stale token survives a session.clear() on login). Real HTTP
    # requests never share a context like this, so the leak is purely a
    # test-fixture artifact -- avoided by not holding the context open here.
    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()
