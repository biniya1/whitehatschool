import uuid
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


def _uuid():
    return str(uuid.uuid4())


def utcnow():
    # Naive UTC datetime (matches SQLite's untyped storage) without using
    # the deprecated datetime.utcnow().
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, nullable=True, default="")
    balance = db.Column(db.Integer, nullable=False, default=1_000_000)

    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    # is_active == False means the account is suspended ("휴면 계정") because
    # it crossed the report threshold; suspended users cannot log in.
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    products = db.relationship("Product", backref="seller", lazy="dynamic",
                                foreign_keys="Product.seller_id")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > utcnow())

    def register_failed_login(self, max_attempts, lockout_minutes):
        self.failed_attempts += 1
        if self.failed_attempts >= max_attempts:
            self.locked_until = utcnow() + timedelta(minutes=lockout_minutes)
            self.failed_attempts = 0

    def register_successful_login(self):
        self.failed_attempts = 0
        self.locked_until = None


class Product(db.Model):
    __tablename__ = "product"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    seller_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)

    is_sold = db.Column(db.Boolean, nullable=False, default=False)
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Report(db.Model):
    __tablename__ = "report"
    __table_args__ = (
        db.UniqueConstraint("reporter_id", "target_type", "target_id",
                             name="uq_report_reporter_target"),
    )

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    reporter_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    target_type = db.Column(db.String(10), nullable=False)  # 'user' or 'product'
    target_id = db.Column(db.String(36), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ChatMessage(db.Model):
    """Global chat log."""
    __tablename__ = "chat_message"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    sender_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class DirectMessage(db.Model):
    """1:1 chat log."""
    __tablename__ = "direct_message"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    sender_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Transaction(db.Model):
    """Money transfer / purchase ledger."""
    __tablename__ = "transaction"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    sender_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey("product.id"), nullable=True)
    memo = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
