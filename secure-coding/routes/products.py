from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app

from extensions import db
from models import Product
from forms import ProductForm
from security import login_required, get_current_user, save_product_image

bp = Blueprint("products", __name__)


@bp.route("/product/new", methods=["GET", "POST"])
@login_required
def new_product():
    user = get_current_user()
    form = ProductForm()
    if form.validate_on_submit():
        try:
            filename = save_product_image(
                form.image.data,
                current_app.config["UPLOAD_FOLDER"],
                current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
            )
        except ValueError as exc:
            flash(str(exc))
            return render_template("new_product.html", form=form)

        product = Product(
            title=form.title.data,
            description=form.description.data,
            price=form.price.data,
            image_filename=filename,
            seller_id=user.id,
        )
        db.session.add(product)
        db.session.commit()
        flash("상품이 등록되었습니다.")
        return redirect(url_for("main.dashboard"))
    return render_template("new_product.html", form=form)


@bp.route("/product/<product_id>")
@login_required
def view_product(product_id):
    user = get_current_user()
    product = db.session.get(Product, product_id)
    if product is None or (product.is_blocked and not user.is_admin):
        flash("상품을 찾을 수 없습니다.")
        return redirect(url_for("main.dashboard"))
    return render_template("view_product.html", product=product, seller=product.seller, user=user)


@bp.route("/product/<product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    user = get_current_user()
    product = db.session.get(Product, product_id)
    if product is None:
        flash("상품을 찾을 수 없습니다.")
        return redirect(url_for("main.dashboard"))
    if product.seller_id != user.id and not user.is_admin:
        flash("본인이 등록한 상품만 수정할 수 있습니다.")
        return redirect(url_for("main.dashboard"))

    form = ProductForm(obj=product)
    if request.method == "GET":
        form.price.data = product.price

    if form.validate_on_submit():
        try:
            filename = save_product_image(
                form.image.data,
                current_app.config["UPLOAD_FOLDER"],
                current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
            )
        except ValueError as exc:
            flash(str(exc))
            return render_template("edit_product.html", form=form, product=product)

        product.title = form.title.data
        product.description = form.description.data
        product.price = form.price.data
        if filename:
            product.image_filename = filename
        db.session.commit()
        flash("상품이 수정되었습니다.")
        return redirect(url_for("products.view_product", product_id=product.id))

    return render_template("edit_product.html", form=form, product=product)


@bp.route("/product/<product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    user = get_current_user()
    product = db.session.get(Product, product_id)
    if product is None:
        flash("상품을 찾을 수 없습니다.")
        return redirect(url_for("main.dashboard"))
    if product.seller_id != user.id and not user.is_admin:
        flash("본인이 등록한 상품만 삭제할 수 있습니다.")
        return redirect(url_for("main.dashboard"))

    db.session.delete(product)
    db.session.commit()
    flash("상품이 삭제되었습니다.")
    return redirect(url_for("main.dashboard"))
