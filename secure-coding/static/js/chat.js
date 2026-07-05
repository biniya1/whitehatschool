// Global chat widget. Reads config from data-* attributes instead of
// inlining server-rendered values into a <script> block, so this file (and
// the page's CSP) never needs 'unsafe-inline'.
(function () {
  var container = document.getElementById("chat");
  if (!container) return;

  var messages = document.getElementById("messages");
  var input = document.getElementById("chat_input");
  var sendBtn = document.getElementById("chat_send");

  var socket = io();

  function appendMessage(text) {
    var item = document.createElement("li");
    item.textContent = text; // textContent -> no HTML injection possible
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
  }

  socket.on("connect", function () {
    console.log("채팅 서버에 연결됨");
  });

  socket.on("message", function (data) {
    appendMessage(data.username + ": " + data.message);
  });

  socket.on("chat_error", function (data) {
    appendMessage("[오류] " + data.message);
  });

  function sendMessage() {
    var text = input.value;
    if (text && text.trim()) {
      socket.emit("send_message", { message: text.slice(0, 500) });
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
})();
