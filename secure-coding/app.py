import logging
import os

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFError

from config import Config
from extensions import db, socketio, csrf
from security import apply_security_headers, get_current_user


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    csrf.init_app(app)
    # cors_allowed_origins is intentionally left at its default (same-origin
    # only) rather than "*", so a page on another site cannot open a
    # cross-site Socket.IO connection using a victim's session cookie.
    socketio.init_app(app)

    from routes.auth import bp as auth_bp
    from routes.main import bp as main_bp
    from routes.products import bp as products_bp
    from routes.trade import bp as trade_bp
    from routes.reports import bp as reports_bp
    from routes.chat import bp as chat_bp  # noqa: F401 (registers socketio events too)
    from routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(trade_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def _security_headers(response):
        return apply_security_headers(response, request)

    @app.context_processor
    def _inject_current_user():
        try:
            return {"current_user": get_current_user()}
        except Exception:
            # Keep error pages renderable even if the DB itself is the
            # thing that's currently failing.
            return {"current_user": None}

    @app.errorhandler(CSRFError)
    def _csrf_error(_e):
        flash("요청이 만료되었거나 보안 토큰이 유효하지 않습니다. 다시 시도해주세요.")
        return redirect(url_for("main.index"))

    @app.errorhandler(403)
    def _forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def _not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def _too_large(_e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def _server_error(e):
        # Never leak stack traces / DB errors to the client -- log server
        # side only and show a generic page.
        app.logger.exception("Unhandled server error: %s", e)
        return render_template("errors/500.html"), 500

    return app


def init_db(app):
    with app.app_context():
        db.create_all()
        _seed_admin(app)


def _seed_admin(app):
    from models import User

    if User.query.filter_by(is_admin=True).first() is not None:
        return

    username = app.config.get("ADMIN_USERNAME")
    password = app.config.get("ADMIN_PASSWORD")
    if not username or not password:
        app.logger.warning(
            "No admin account exists yet and ADMIN_USERNAME/ADMIN_PASSWORD "
            "are not set -- skipping admin bootstrap. Set them in your "
            "environment (see .env.example) and restart to create the first "
            "admin account. Credentials are never hardcoded in source."
        )
        return

    if User.query.filter_by(username=username).first() is not None:
        app.logger.warning(
            "ADMIN_USERNAME '%s' already exists as a non-admin user; skipping bootstrap.",
            username,
        )
        return

    admin = User(username=username, is_admin=True, balance=app.config["DEFAULT_BALANCE"])
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    app.logger.info("Bootstrapped admin account '%s'.", username)


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db(app)
    # This app is run via Werkzeug's development server for this course
    # assignment (as in the original starter). allow_unsafe_werkzeug silences
    # Flask-SocketIO's production-server warning; a real deployment should
    # instead run behind eventlet/gunicorn and a TLS-terminating reverse
    # proxy, which is out of scope here and noted as a limitation in REPORT.md.
    # macOS binds its AirPlay Receiver to port 5000 by default, which can
    # conflict with Flask's default port -- override with PORT if needed.
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, port=port, debug=app.config["DEBUG"], allow_unsafe_werkzeug=True)
