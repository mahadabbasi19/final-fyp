/* ============================================================
   Working demo chat inside the homepage application screenshot.
   Any message the user sends gets the reply:
   "To use CodeNova AI, download CodeNova AI." — where the phrase
   is a link that triggers the OS-aware download.
   ============================================================ */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('chatForm');
    if (!form) return;
    var input = document.getElementById('chatText');
    var body = document.getElementById('chatBody');

    function scrollDown() { body.scrollTop = body.scrollHeight; }

    function addUser(text) {
      var d = document.createElement('div');
      d.className = 'chat-msg user';
      d.textContent = text;
      body.appendChild(d);
      scrollDown();
    }

    function addTyping() {
      var d = document.createElement('div');
      d.className = 'chat-msg ai typing';
      d.innerHTML = '<span class="dot-typing"><i></i><i></i><i></i></span>';
      body.appendChild(d);
      scrollDown();
      return d;
    }

    function startDownload() {
      var cfg = (window.CodeNova && window.CodeNova.currentDownload()) || { url: '#' };
      var a = document.createElement('a');
      a.href = cfg.url;
      a.setAttribute('download', '');
      document.body.appendChild(a);
      a.click();
      a.remove();
    }

    function fillReply(node) {
      node.classList.remove('typing');
      node.innerHTML = 'To use CodeNova AI, <a href="#" class="chat-dl">download CodeNova AI</a>.';
      node.querySelector('.chat-dl').addEventListener('click', function (e) {
        e.preventDefault();
        startDownload();
      });
      scrollDown();
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var text = (input.value || '').trim();
      if (!text) return;
      addUser(text);
      input.value = '';
      var typing = addTyping();
      setTimeout(function () { fillReply(typing); }, 850);
    });
  });
})();
