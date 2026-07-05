from flask import Blueprint, render_template, redirect, url_for, flash

from extensions import db
from models import User, Product, Report
from security import admin_required, get_current_user

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    stats = {
        "users": User.query.count(),
        "products": Product.query.count(),
        "reports": Report.query.count(),
        "suspended_users": User.query.filter_by(is_active=False).count(),
        "blocked_products": Product.query.filter_by(is_blocked=True).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@bp.route("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)


@bp.route("/users/<user_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_user_active(user_id):
    current = get_current_user()
    target = db.session.get(User, user_id)
    if target is None:
        flash("사용자를 찾을 수 없습니다.")
        return redirect(url_for("admin.users"))
    if target.id == current.id:
        flash("자기 자신의 계정 상태는 변경할 수 없습니다.")
        return redirect(url_for("admin.users"))

    target.is_active = not target.is_active
    if target.is_active:
        target.failed_attempts = 0
        target.locked_until = None
    db.session.commit()
    flash(f"{target.username}님의 계정 상태가 변경되었습니다.")
    return redirect(url_for("admin.users"))


@bp.route("/products")
@admin_required
def products():
    all_products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=all_products)


@bp.route("/products/<product_id>/toggle-block", methods=["POST"])
@admin_required
def toggle_product_block(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        flash("상품을 찾을 수 없습니다.")
        return redirect(url_for("admin.products"))
    product.is_blocked = not product.is_blocked
    db.session.commit()
    flash("상품 상태가 변경되었습니다.")
    return redirect(url_for("admin.products"))


@bp.route("/products/<product_id>/delete", methods=["POST"])
@admin_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        flash("상품을 찾을 수 없습니다.")
        return redirect(url_for("admin.products"))
    db.session.delete(product)
    db.session.commit()
    flash("상품이 삭제되었습니다.")
    return redirect(url_for("admin.products"))


@bp.route("/reports")
@admin_required
def reports():
    all_reports = Report.query.order_by(Report.created_at.desc()).all()
    enriched = []
    for r in all_reports:
        if r.target_type == "product":
            target = db.session.get(Product, r.target_id)
            target_label = target.title if target else "(삭제됨)"
        else:
            target = db.session.get(User, r.target_id)
            target_label = target.username if target else "(삭제됨)"
        reporter = db.session.get(User, r.reporter_id)
        enriched.append({
            "report": r,
            "target_label": target_label,
            "reporter_label": reporter.username if reporter else "(삭제됨)",
        })
    return render_template("admin/reports.html", reports=enriched)
