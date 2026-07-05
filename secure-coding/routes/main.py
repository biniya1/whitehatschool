from flask import Blueprint, render_template, redirect, url_for, request, flash

from extensions import db
from models import Product, User
from forms import SearchForm, ProfileForm
from security import login_required, get_current_user

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if get_current_user():
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    products = (Product.query
                .filter_by(is_blocked=False)
                .order_by(Product.created_at.desc())
                .all())
    return render_template("dashboard.html", products=products, user=user)


@bp.route("/search")
@login_required
def search():
    user = get_current_user()
    form = SearchForm(request.args)
    query = form.q.data.strip() if form.validate() and form.q.data else ""
    products = []
    if query:
        like = f"%{query}%"
        products = (Product.query
                    .filter(Product.is_blocked.is_(False))
                    .filter(Product.title.ilike(like))
                    .order_by(Product.created_at.desc())
                    .all())
    return render_template("search.html", products=products, query=query, user=user)


@bp.route("/user/<user_id>")
@login_required
def view_user(user_id):
    target = db.session.get(User, user_id)
    if target is None or not target.is_active:
        flash("사용자를 찾을 수 없습니다.")
        return redirect(url_for("main.dashboard"))
    products = (Product.query
                .filter_by(seller_id=target.id, is_blocked=False)
                .order_by(Product.created_at.desc())
                .all())
    return render_template("user_view.html", target=target, products=products,
                           user=get_current_user())


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    form = ProfileForm()

    if request.method == "GET":
        form.bio.data = user.bio

    if form.validate_on_submit():
        user.bio = form.bio.data or ""

        if form.new_password.data:
            if not user.check_password(form.current_password.data or ""):
                flash("현재 비밀번호가 올바르지 않습니다.")
                return redirect(url_for("main.profile"))
            user.set_password(form.new_password.data)
            flash("비밀번호가 변경되었습니다.")

        db.session.commit()
        flash("프로필이 업데이트되었습니다.")
        return redirect(url_for("main.profile"))

    return render_template("profile.html", user=user, form=form)
