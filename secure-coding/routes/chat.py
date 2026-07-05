from flask import Blueprint, render_template, redirect, url_for, flash
from flask_socketio import emit, join_room, disconnect

from extensions import db, socketio
from models import User, ChatMessage, DirectMessage
from security import login_required, get_current_user, ChatRateLimiter

bp = Blueprint("chat", __name__)

_global_limiter = ChatRateLimiter(max_messages=5, window_seconds=10)
_dm_limiter = ChatRateLimiter(max_messages=5, window_seconds=10)

MAX_MESSAGE_LENGTH = 500


def _dm_room(user_id_a, user_id_b):
    return "dm-" + "-".join(sorted([user_id_a, user_id_b]))


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@bp.route("/messages")
@login_required
def inbox():
    user = get_current_user()
    sent = db.session.query(DirectMessage.receiver_id).filter_by(sender_id=user.id)
    received = db.session.query(DirectMessage.sender_id).filter_by(receiver_id=user.id)
    partner_ids = {row[0] for row in sent.union(received).all()}
    partners = User.query.filter(User.id.in_(partner_ids)).all() if partner_ids else []
    return render_template("messages.html", partners=partners, user=user)


@bp.route("/messages/<peer_id>")
@login_required
def dm_thread(peer_id):
    user = get_current_user()
    peer = db.session.get(User, peer_id)
    if peer is None or peer.id == user.id:
        flash("대화 상대를 찾을 수 없습니다.")
        return redirect(url_for("chat.inbox"))

    history = (DirectMessage.query
               .filter(
                   db.or_(
                       db.and_(DirectMessage.sender_id == user.id, DirectMessage.receiver_id == peer.id),
                       db.and_(DirectMessage.sender_id == peer.id, DirectMessage.receiver_id == user.id),
                   )
               )
               .order_by(DirectMessage.created_at.asc())
               .limit(200)
               .all())
    return render_template("dm_thread.html", peer=peer, history=history, user=user)


# ---------------------------------------------------------------------------
# Socket.IO events
# ---------------------------------------------------------------------------

@socketio.on("connect")
def handle_connect():
    # Reject the socket handshake entirely unless the caller already has a
    # valid, active Flask session -- prevents anonymous/unauthenticated use
    # of the chat channel.
    if get_current_user() is None:
        return False
    return True


@socketio.on("send_message")
def handle_send_message_event(data):
    user = get_current_user()
    if user is None:
        disconnect()
        return

    if _global_limiter.is_limited(user.id):
        emit("chat_error", {"message": "메시지 전송이 너무 빠릅니다. 잠시 후 다시 시도해주세요."})
        return

    content = str((data or {}).get("message", "")).strip()
    if not content or len(content) > MAX_MESSAGE_LENGTH:
        emit("chat_error", {"message": f"메시지는 1~{MAX_MESSAGE_LENGTH}자여야 합니다."})
        return

    msg = ChatMessage(sender_id=user.id, content=content)
    db.session.add(msg)
    db.session.commit()

    # Username always comes from the authenticated session, never trusted
    # from the client payload (the starter code trusted `data['username']`).
    emit("message", {
        "username": user.username,
        "message": content,
        "message_id": msg.id,
    }, broadcast=True)


@socketio.on("join_dm")
def handle_join_dm(data):
    user = get_current_user()
    if user is None:
        disconnect()
        return

    peer_id = str((data or {}).get("peer_id", ""))
    peer = db.session.get(User, peer_id)
    if peer is None or peer.id == user.id:
        emit("chat_error", {"message": "대화 상대를 찾을 수 없습니다."})
        return

    # The room name is always derived server-side from the two participant
    # ids; the client only ever supplies which peer it wants to talk to, so
    # it cannot join or address an arbitrary room it doesn't belong to.
    join_room(_dm_room(user.id, peer.id))


@socketio.on("send_dm")
def handle_send_dm(data):
    user = get_current_user()
    if user is None:
        disconnect()
        return

    peer_id = str((data or {}).get("peer_id", ""))
    peer = db.session.get(User, peer_id)
    if peer is None or peer.id == user.id:
        emit("chat_error", {"message": "대화 상대를 찾을 수 없습니다."})
        return

    if _dm_limiter.is_limited(user.id):
        emit("chat_error", {"message": "메시지 전송이 너무 빠릅니다. 잠시 후 다시 시도해주세요."})
        return

    content = str((data or {}).get("message", "")).strip()
    if not content or len(content) > MAX_MESSAGE_LENGTH:
        emit("chat_error", {"message": f"메시지는 1~{MAX_MESSAGE_LENGTH}자여야 합니다."})
        return

    msg = DirectMessage(sender_id=user.id, receiver_id=peer.id, content=content)
    db.session.add(msg)
    db.session.commit()

    emit("dm_message", {
        "sender_id": user.id,
        "username": user.username,
        "message": content,
        "created_at": msg.created_at.isoformat(),
    }, room=_dm_room(user.id, peer.id))
