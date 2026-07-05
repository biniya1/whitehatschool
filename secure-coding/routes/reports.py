from datetime import timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app

from extensions import db
from models import Report, Product, User, utcnow
from forms import ReportForm
from security import login_required, get_current_user

bp = Blueprint("reports", __name__)

# Defense-in-depth against report-flooding beyond the one-report-per-target
# unique constraint: cap how many reports a single user can file in an hour.
REPORTS_PER_HOUR_LIMIT = 20


def _apply_thresholds(config, target_type, target_id):
    count = Report.query.filter_by(target_type=target_type, target_id=target_id).count()
    if target_type == "product" and count >= config["PRODUCT_REPORT_THRESHOLD"]:
        product = db.session.get(Product, target_id)
        if product is not None:
            product.is_blocked = True
    elif target_type == "user" and count >= config["USER_REPORT_THRESHOLD"]:
        target_user = db.session.get(User, target_id)
        if target_user is not None:
            target_user.is_active = False


@bp.route("/report", methods=["GET", "POST"])
@login_required
def report():
    user = get_current_user()
    form = ReportForm()

    if request.method == "GET":
        form.target_type.data = request.args.get("target_type", "product")
        form.target_id.data = request.args.get("target_id", "")

    if form.validate_on_submit():
        target_type = form.target_type.data
        target_id = form.target_id.data.strip()

        target = (db.session.get(Product, target_id) if target_type == "product"
                  else db.session.get(User, target_id))
        if target is None:
            flash("신고 대상을 찾을 수 없습니다.")
            return redirect(url_for("reports.report"))

        if target_type == "user" and target_id == user.id:
            flash("자기 자신은 신고할 수 없습니다.")
            return redirect(url_for("reports.report"))

        already = Report.query.filter_by(
            reporter_id=user.id, target_type=target_type, target_id=target_id,
        ).first()
        if already is not None:
            flash("이미 신고한 대상입니다.")
            return redirect(url_for("reports.report"))

        recent_count = Report.query.filter(
            Report.reporter_id == user.id,
            Report.created_at >= utcnow() - timedelta(hours=1),
        ).count()
        if recent_count >= REPORTS_PER_HOUR_LIMIT:
            flash("신고 횟수 제한을 초과했습니다. 잠시 후 다시 시도해주세요.")
            return redirect(url_for("reports.report"))

        db.session.add(Report(reporter_id=user.id, target_type=target_type,
                               target_id=target_id, reason=form.reason.data))
        db.session.flush()
        _apply_thresholds(current_app.config, target_type, target_id)
        db.session.commit()
        flash("신고가 접수되었습니다.")
        return redirect(url_for("main.dashboard"))

    return render_template("report.html", form=form)
