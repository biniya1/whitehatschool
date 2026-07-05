import io
import re

from extensions import db
from models import User, Product, Report

CSRF_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


def get_csrf(html_bytes):
    match = CSRF_RE.search(html_bytes.decode())
    assert match, "csrf token not found in response"
    return match.group(1)


def register(client, username, password):
    resp = client.get("/register")
    csrf = get_csrf(resp.data)
    return client.post("/register", data={
        "csrf_token": csrf, "username": username,
        "password": password, "confirm_password": password,
    }, follow_redirects=True)


def login(client, username, password):
    resp = client.get("/login")
    csrf = get_csrf(resp.data)
    return client.post("/login", data={
        "csrf_token": csrf, "username": username, "password": password,
    }, follow_redirects=True)


def create_product(client, title="Item", description="Desc", price=1000, extra_data=None):
    resp = client.get("/product/new")
    csrf = get_csrf(resp.data)
    data = {"csrf_token": csrf, "title": title, "description": description, "price": str(price)}
    if extra_data:
        data.update(extra_data)
    # Let the test client pick the encoding itself: multipart (with a proper
    # boundary) whenever a file is present, plain form-encoded otherwise.
    # Forcing content_type manually here breaks boundary generation and the
    # server ends up unable to parse the CSRF token out of the body at all.
    return client.post("/product/new", data=data, follow_redirects=True)


# ---------------------------------------------------------------------------
# Password storage
# ---------------------------------------------------------------------------

def test_password_is_hashed_not_plaintext(app, client):
    register(client, "alice", "Passw0rd1")
    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user is not None
        assert user.password_hash != "Passw0rd1"
        assert "Passw0rd1" not in user.password_hash
        assert user.check_password("Passw0rd1")


# ---------------------------------------------------------------------------
# Login lockout
# ---------------------------------------------------------------------------

def test_login_locks_after_max_failed_attempts(app, client):
    register(client, "locktest", "Passw0rd1")

    for _ in range(app.config["LOGIN_MAX_ATTEMPTS"]):
        login(client, "locktest", "WrongPassword1")

    with app.app_context():
        user = User.query.filter_by(username="locktest").first()
        assert user.is_locked()

    # Even the correct password should now be rejected while locked.
    resp = login(client, "locktest", "Passw0rd1")
    assert "잠겨" in resp.data.decode() or "올바르지 않" in resp.data.decode()
    assert b"dashboard" not in resp.request.path.encode()


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

def test_login_rejected_without_csrf_token(client):
    register(client, "csrftest", "Passw0rd1")
    resp = client.post("/login", data={
        "username": "csrftest", "password": "Passw0rd1",
    })
    # Our CSRFError handler redirects home rather than logging the user in.
    assert resp.status_code in (302, 400)
    if resp.status_code == 302:
        assert resp.headers["Location"] in ("/", "http://localhost/")

    # Confirm the session was never actually authenticated.
    dash = client.get("/dashboard", follow_redirects=True)
    assert "로그인" in dash.data.decode()


# ---------------------------------------------------------------------------
# Ownership / IDOR checks
# ---------------------------------------------------------------------------

def test_cannot_edit_or_delete_other_users_product(app, client):
    register(client, "owner", "Passw0rd1")
    login(client, "owner", "Passw0rd1")
    create_product(client, title="Owner Product")

    with app.app_context():
        product = Product.query.filter_by(title="Owner Product").first()
        product_id = product.id

    other = app.test_client()
    register(other, "attacker", "Passw0rd1")
    login(other, "attacker", "Passw0rd1")

    edit_resp = other.get(f"/product/{product_id}/edit", follow_redirects=True)
    assert "본인이 등록한 상품만" in edit_resp.data.decode()

    new_resp = other.get("/product/new")
    csrf = get_csrf(new_resp.data)
    delete_resp = other.post(f"/product/{product_id}/delete",
                              data={"csrf_token": csrf}, follow_redirects=True)
    assert "본인이 등록한 상품만" in delete_resp.data.decode()

    with app.app_context():
        assert db.session.get(Product, product_id) is not None


# ---------------------------------------------------------------------------
# Report threshold auto-actions
# ---------------------------------------------------------------------------

def test_product_auto_blocked_after_report_threshold(app, client):
    register(client, "seller", "Passw0rd1")
    login(client, "seller", "Passw0rd1")
    create_product(client, title="Suspicious Item")

    with app.app_context():
        product = Product.query.filter_by(title="Suspicious Item").first()
        product_id = product.id
        threshold = app.config["PRODUCT_REPORT_THRESHOLD"]

    for i in range(threshold):
        reporter = app.test_client()
        register(reporter, f"reporter{i}", "Passw0rd1")
        login(reporter, f"reporter{i}", "Passw0rd1")
        resp = reporter.get("/report")
        csrf = get_csrf(resp.data)
        reporter.post("/report", data={
            "csrf_token": csrf, "target_type": "product",
            "target_id": product_id, "reason": "fake item",
        }, follow_redirects=True)

    with app.app_context():
        product = db.session.get(Product, product_id)
        assert product.is_blocked is True


def test_duplicate_report_from_same_user_is_rejected(app, client):
    register(client, "seller2", "Passw0rd1")
    login(client, "seller2", "Passw0rd1")
    create_product(client, title="Item2")

    with app.app_context():
        product_id = Product.query.filter_by(title="Item2").first().id

    reporter = app.test_client()
    register(reporter, "dupreporter", "Passw0rd1")
    login(reporter, "dupreporter", "Passw0rd1")

    for _ in range(2):
        resp = reporter.get("/report")
        csrf = get_csrf(resp.data)
        result = reporter.post("/report", data={
            "csrf_token": csrf, "target_type": "product",
            "target_id": product_id, "reason": "duplicate report reason",
        }, follow_redirects=True)

    assert "이미 신고한 대상입니다" in result.data.decode()
    with app.app_context():
        count = Report.query.filter_by(target_type="product", target_id=product_id).count()
        assert count == 1


# ---------------------------------------------------------------------------
# XSS escaping
# ---------------------------------------------------------------------------

def test_product_description_is_escaped_in_output(client):
    register(client, "xsstest", "Passw0rd1")
    login(client, "xsstest", "Passw0rd1")
    payload = "<script>alert(1)</script>"
    create_product(client, title="XSS Item", description=payload)

    resp = client.get("/dashboard")
    listing_html = resp.data.decode()
    assert "<script>alert(1)</script>" not in listing_html

    # Follow into the detail page to check the description itself.
    match = re.search(r'/product/([a-f0-9-]+)"[^>]*>XSS Item', listing_html)
    assert match, "product link not found on dashboard"
    detail = client.get(f"/product/{match.group(1)}")
    assert "<script>alert(1)</script>" not in detail.data.decode()
    assert "&lt;script&gt;" in detail.data.decode()


# ---------------------------------------------------------------------------
# Server-side input validation
# ---------------------------------------------------------------------------

def test_negative_price_is_rejected(app, client):
    register(client, "pricetest", "Passw0rd1")
    login(client, "pricetest", "Passw0rd1")
    create_product(client, title="Bad Price Item", price=-100)

    with app.app_context():
        assert Product.query.filter_by(title="Bad Price Item").first() is None


def test_non_image_upload_is_rejected(app, client):
    register(client, "uploadtest", "Passw0rd1")
    login(client, "uploadtest", "Passw0rd1")

    fake_image = (io.BytesIO(b"not actually an image"), "evil.png")
    resp = create_product(client, title="Bad Upload Item",
                           extra_data={"image": fake_image})

    assert "올바른 이미지 파일이 아닙니다" in resp.data.decode()
    with app.app_context():
        assert Product.query.filter_by(title="Bad Upload Item").first() is None


# ---------------------------------------------------------------------------
# Search does not break / leak on adversarial input
# ---------------------------------------------------------------------------

def test_search_handles_adversarial_input_safely(client):
    register(client, "searchtest", "Passw0rd1")
    login(client, "searchtest", "Passw0rd1")
    create_product(client, title="Normal Chair")

    resp = client.get("/search", query_string={"q": "'; DROP TABLE product; --"})
    assert resp.status_code == 200
    assert "검색 결과가 없습니다" in resp.data.decode()

    # Table should still exist and be queryable afterwards.
    resp2 = client.get("/search", query_string={"q": "Chair"})
    assert "Normal Chair" in resp2.data.decode()


# ---------------------------------------------------------------------------
# Admin access control
# ---------------------------------------------------------------------------

def test_non_admin_cannot_access_admin_panel(client):
    register(client, "regularuser", "Passw0rd1")
    login(client, "regularuser", "Passw0rd1")
    resp = client.get("/admin/", follow_redirects=True)
    assert "관리자만 접근할 수 있습니다" in resp.data.decode()
