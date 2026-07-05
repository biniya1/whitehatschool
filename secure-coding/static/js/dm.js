// 1:1 chat widget. The peer id is read from a data attribute; the server
// (not this client code) decides the actual room name, so this file cannot
// be tricked into joining/broadcasting to an arbitrary room.
(function () {
  var container = document.getElementById("dm-chat");
  if (!container) return;

  var peerId = container.dataset.peerId;
  var messages = document.getElementById("dm-messages");
  var input = document.getElementById("dm_input");
  var sendBtn = document.getElementById("dm_send");

  var socket = io();

  function appendMessage(username, text) {
    var item = document.createElement("li");
    item.textContent = username + ": " + text;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
  }

  socket.on("connect", function () {
    socket.emit("join_dm", { peer_id: peerId });
  });

  socket.on("dm_message", function (data) {
    appendMessage(data.username, data.message);
  });

  socket.on("chat_error", function (data) {
    appendMessage("[오류]", data.message);
  });

  function sendMessage() {
    var text = input.value;
    if (text && text.trim()) {
      socket.emit("send_dm", { peer_id: peerId, message: text.slice(0, 500) });
      input.value = "";
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });

  messages.scrollTop = messages.scrollHeight;
})();
