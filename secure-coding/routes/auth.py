from flask import Blueprint, render_template, redirect, url_for, session, flash, current_app

from extensions import db
from models import User
from forms import RegisterForm, LoginForm
from security import get_current_user

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(username=form.username.data).first()
        if existing is not None:
            flash("이미 존재하는 사용자명입니다.")
            return redirect(url_for("auth.register"))

        user = User(username=form.username.data,
                    balance=current_app.config["DEFAULT_BALANCE"])
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("회원가입이 완료되었습니다. 로그인 해주세요.")
        return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        # One generic message for "no such user" / "wrong password" / "locked"
        # so a caller can't use the login form to enumerate valid usernames.
        generic_error = "아이디 또는 비밀번호가 올바르지 않거나 계정이 잠겨 있습니다."

        if user is None:
            flash(generic_error)
            return redirect(url_for("auth.login"))

        if not user.is_active:
            flash("휴면 처리된 계정입니다. 관리자에게 문의해주세요.")
            return redirect(url_for("auth.login"))

        if user.is_locked():
            flash(generic_error)
            return redirect(url_for("auth.login"))

        if not user.check_password(form.password.data):
            user.register_failed_login(
                current_app.config["LOGIN_MAX_ATTEMPTS"],
                current_app.config["LOGIN_LOCKOUT_MINUTES"],
            )
            db.session.commit()
            flash(generic_error)
            return redirect(url_for("auth.login"))

        user.register_successful_login()
        db.session.commit()

        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        flash("로그인 성공!")
        return redirect(url_for("main.dashboard"))
    return render_template("login.html", form=form)


@bp.route("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.")
    return redirect(url_for("main.index"))
