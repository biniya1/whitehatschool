from flask import Blueprint, render_template, redirect, url_for, flash

from extensions import db
from models import Product, User, Transaction
from forms import TransferForm
from security import login_required, get_current_user

bp = Blueprint("trade", __name__)


@bp.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    user = get_current_user()
    form = TransferForm()
    if form.validate_on_submit():
        target = User.query.filter_by(username=form.target_username.data).first()
        if target is None or not target.is_active:
            flash("받는 사람을 찾을 수 없습니다.")
            return redirect(url_for("trade.transfer"))
        if target.id == user.id:
            flash("자기 자신에게는 송금할 수 없습니다.")
            return redirect(url_for("trade.transfer"))

        amount = form.amount.data
        if user.balance < amount:
            flash("잔액이 부족합니다.")
            return redirect(url_for("trade.transfer"))

        user.balance -= amount
        target.balance += amount
        db.session.add(Transaction(sender_id=user.id, receiver_id=target.id,
                                    amount=amount, memo="송금"))
        db.session.commit()
        flash(f"{target.username}님에게 {amount}원을 송금했습니다.")
        return redirect(url_for("main.dashboard"))
    return render_template("transfer.html", form=form, user=user)


@bp.route("/product/<product_id>/buy", methods=["POST"])
@login_required
def buy_product(product_id):
    user = get_current_user()
    product = db.session.get(Product, product_id)
    if product is None or product.is_blocked:
        flash("상품을 찾을 수 없습니다.")
        return redirect(url_for("main.dashboard"))
    if product.is_sold:
        flash("이미 판매된 상품입니다.")
        return redirect(url_for("products.view_product", product_id=product.id))
    if product.seller_id == user.id:
        flash("본인 상품은 구매할 수 없습니다.")
        return redirect(url_for("products.view_product", product_id=product.id))
    if user.balance < product.price:
        flash("잔액이 부족합니다.")
        return redirect(url_for("products.view_product", product_id=product.id))

    seller = product.seller
    user.balance -= product.price
    seller.balance += product.price
    product.is_sold = True
    db.session.add(Transaction(sender_id=user.id, receiver_id=seller.id,
                                amount=product.price, product_id=product.id,
                                memo=f"상품 구매: {product.title}"))
    db.session.commit()
    flash("구매가 완료되었습니다.")
    return redirect(url_for("products.view_product", product_id=product.id))
