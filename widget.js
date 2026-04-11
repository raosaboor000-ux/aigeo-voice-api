(function () {
  "use strict";

  var API =
    document.currentScript.getAttribute("data-api") ||
    document.currentScript.src.replace(/\/widget\.js(\?.*)?$/, "");

  /* ---- inject styles ---- */
  var css = document.createElement("style");
  css.textContent =
    "#vw-fab{position:fixed;bottom:28px;right:28px;z-index:2147483647;width:62px;height:62px;border-radius:50%;border:none;background:linear-gradient(135deg,#6366f1,#818cf8);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 24px rgba(99,102,241,.45);transition:transform .15s,box-shadow .2s;font-family:sans-serif}" +
    "#vw-fab:hover{transform:scale(1.08);box-shadow:0 6px 32px rgba(99,102,241,.6)}" +
    "#vw-fab:active{transform:scale(.94)}" +
    "#vw-fab svg{width:28px;height:28px}" +
    "#vw-fab.hidden{display:none}" +
    "#vw-panel{position:fixed;bottom:28px;right:28px;z-index:2147483647;width:320px;background:#0f172a;border-radius:24px;box-shadow:0 20px 60px rgba(0,0,0,.35);display:none;flex-direction:column;align-items:center;overflow:hidden;border:1px solid rgba(148,163,184,.1);font-family:'Inter','Segoe UI',sans-serif}" +
    "#vw-panel.open{display:flex}" +
    ".vw-header{width:100%;display:flex;align-items:center;justify-content:space-between;padding:16px 20px 0}" +
    ".vw-title{font-size:.82rem;font-weight:600;color:#94a3b8;letter-spacing:.03em}" +
    ".vw-close{width:32px;height:32px;border-radius:50%;border:none;background:rgba(148,163,184,.12);color:#94a3b8;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:background .2s}" +
    ".vw-close:hover{background:rgba(248,113,113,.2);color:#fca5a5}" +
    ".vw-close svg{width:16px;height:16px}" +
    ".vw-avatar-area{padding:28px 0 8px;display:flex;flex-direction:column;align-items:center;position:relative}" +
    ".vw-avatar-wrap{position:relative;width:120px;height:120px}" +
    ".vw-ring{width:120px;height:120px;border-radius:50%;background:conic-gradient(from 0deg,#818cf8,#34d399,#60a5fa,#818cf8);padding:3px;transition:transform .4s}" +
    ".vw-ring.active{animation:vw-spin 2.5s linear infinite}" +
    "@keyframes vw-spin{to{transform:rotate(360deg)}}" +
    ".vw-ring-inner{width:100%;height:100%;border-radius:50%;background:#1e293b;display:flex;align-items:center;justify-content:center}" +
    ".vw-ring-inner svg{width:64px;height:64px}" +
    ".vw-pulse{position:absolute;top:50%;left:50%;width:120px;height:120px;border-radius:50%;border:2px solid rgba(129,140,248,.25);transform:translate(-50%,-50%) scale(1);opacity:0;pointer-events:none}" +
    ".vw-avatar-wrap.active .vw-pulse:nth-child(1){animation:vw-p 2s ease-out infinite}" +
    ".vw-avatar-wrap.active .vw-pulse:nth-child(2){animation:vw-p 2s ease-out .6s infinite}" +
    ".vw-avatar-wrap.active .vw-pulse:nth-child(3){animation:vw-p 2s ease-out 1.2s infinite}" +
    "@keyframes vw-p{0%{transform:translate(-50%,-50%) scale(1);opacity:.45}100%{transform:translate(-50%,-50%) scale(1.8);opacity:0}}" +
    ".vw-mic{margin-top:20px;width:58px;height:58px;border-radius:50%;border:none;background:linear-gradient(135deg,#6366f1,#818cf8);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 4px 20px rgba(99,102,241,.4);transition:transform .15s,box-shadow .2s,background .3s}" +
    ".vw-mic:hover{transform:scale(1.08)}" +
    ".vw-mic:active{transform:scale(.93)}" +
    ".vw-mic:disabled{opacity:.4;cursor:not-allowed;transform:none}" +
    ".vw-mic.rec{background:linear-gradient(135deg,#ef4444,#f87171);box-shadow:0 4px 20px rgba(239,68,68,.45)}" +
    ".vw-mic svg{width:26px;height:26px}" +
    ".vw-status{padding:14px 20px 20px;font-size:.78rem;color:#94a3b8;text-align:center;min-height:48px;line-height:1.5}" +
    "@media(max-width:400px){#vw-panel{width:calc(100vw - 24px);right:12px;bottom:12px}#vw-fab{bottom:16px;right:16px}}";
  document.head.appendChild(css);

  /* ---- inject HTML ---- */
  var wrap = document.createElement("div");
  wrap.innerHTML =
    '<button id="vw-fab" aria-label="Open voice assistant"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg></button>' +
    '<div id="vw-panel">' +
      '<div class="vw-header"><span class="vw-title">AI Geo Assistant</span>' +
      '<button class="vw-close" id="vw-close" aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button></div>' +
      '<div class="vw-avatar-area">' +
        '<div class="vw-avatar-wrap" id="vw-avatarWrap">' +
          '<div class="vw-pulse"></div><div class="vw-pulse"></div><div class="vw-pulse"></div>' +
          '<div class="vw-ring" id="vw-ring"><div class="vw-ring-inner">' +
            '<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">' +
              '<circle cx="60" cy="60" r="56" fill="#334155"/>' +
              '<rect x="30" y="28" width="60" height="52" rx="16" fill="#475569"/>' +
              '<rect x="34" y="32" width="52" height="44" rx="13" fill="#1e293b"/>' +
              '<circle cx="45" cy="52" r="6" fill="#818cf8"><animate attributeName="r" values="6;4;6" dur="3s" repeatCount="indefinite"/></circle>' +
              '<circle cx="75" cy="52" r="6" fill="#34d399"><animate attributeName="r" values="6;4;6" dur="3s" begin=".3s" repeatCount="indefinite"/></circle>' +
              '<path d="M44 66 Q60 78 76 66" stroke="#60a5fa" stroke-width="3" stroke-linecap="round" fill="none"><animate attributeName="d" values="M44 66 Q60 78 76 66;M44 68 Q60 72 76 68;M44 66 Q60 78 76 66" dur="4s" repeatCount="indefinite"/></path>' +
              '<line x1="60" y1="28" x2="60" y2="14" stroke="#94a3b8" stroke-width="2.5"/>' +
              '<circle cx="60" cy="12" r="4" fill="#818cf8"><animate attributeName="opacity" values="1;.3;1" dur="1.8s" repeatCount="indefinite"/></circle>' +
            '</svg>' +
          '</div></div>' +
        '</div>' +
        '<button class="vw-mic" id="vw-mic" aria-label="Toggle recording"><svg id="vw-micIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg></button>' +
      '</div>' +
      '<div class="vw-status" id="vw-status">Tap the mic to start</div>' +
    '</div>';

  while (wrap.firstChild) document.body.appendChild(wrap.firstChild);

  /* ---- state ---- */
  var mediaRecorder, chunks = [], isRecording = false, isSpeaking = false;
  var sessionId;
  try { sessionId = sessionStorage.getItem("vw_sid") || crypto.randomUUID(); sessionStorage.setItem("vw_sid", sessionId); }
  catch (_) { sessionId = "w-" + Math.random().toString(36).slice(2); }
  var greetingPlayed = false;
  try { greetingPlayed = sessionStorage.getItem("vw_greeted") === "1"; } catch (_) {}

  var fab      = document.getElementById("vw-fab");
  var panel    = document.getElementById("vw-panel");
  var closeBtn = document.getElementById("vw-close");
  var mic      = document.getElementById("vw-mic");
  var micIcon  = document.getElementById("vw-micIcon");
  var statusEl = document.getElementById("vw-status");
  var ring     = document.getElementById("vw-ring");
  var avatarW  = document.getElementById("vw-avatarWrap");
  var audio    = new Audio();

  var MIC_SVG  = '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/>';
  var STOP_SVG = '<rect x="6" y="6" width="12" height="12" rx="2"/>';
  var SPIN_SVG = '<path d="M12 2a10 10 0 0 1 10 10" stroke-width="2.5"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur=".75s" repeatCount="indefinite"/></path>';

  /* ---- open / close ---- */
  fab.onclick = function () { fab.classList.add("hidden"); panel.classList.add("open"); };

  closeBtn.onclick = function () {
    panel.classList.remove("open");
    fab.classList.remove("hidden");
    if (isSpeaking) stopSpeaking();
    if (isRecording && mediaRecorder && mediaRecorder.state !== "inactive") { mediaRecorder.stop(); isRecording = false; }
    resetUi();
    endSession();
  };

  function resetUi() {
    micIcon.innerHTML = MIC_SVG;
    mic.classList.remove("rec");
    mic.disabled = false;
    ring.classList.remove("active");
    avatarW.classList.remove("active");
    statusEl.textContent = "Tap the mic to start";
  }

  /* ---- greeting ---- */
  function playGreeting(cb) {
    statusEl.textContent = "Saying hello\u2026";
    mic.disabled = true;
    fetch(API + "/voice/greeting", { method: "POST" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.blob(); })
      .then(function (blob) {
        audio.src = URL.createObjectURL(blob);
        audio.play();
        audio.onended = function () { mic.disabled = false; cb(); };
        audio.onerror = function () { mic.disabled = false; cb(); };
      })
      .catch(function () { mic.disabled = false; cb(); });
    try { sessionStorage.setItem("vw_greeted", "1"); } catch (_) {}
    greetingPlayed = true;
  }

  /* ---- recording ---- */
  function setRecording(on) {
    if (on) {
      micIcon.innerHTML = STOP_SVG;
      mic.classList.add("rec");
      ring.classList.add("active");
      avatarW.classList.add("active");
      statusEl.textContent = "Listening\u2026 tap mic to stop";
    } else {
      micIcon.innerHTML = MIC_SVG;
      mic.classList.remove("rec");
      ring.classList.remove("active");
      avatarW.classList.remove("active");
    }
  }

  function setBusy(msg) {
    micIcon.innerHTML = SPIN_SVG;
    mic.disabled = true;
    ring.classList.add("active");
    avatarW.classList.add("active");
    statusEl.textContent = msg;
  }

  function stopSpeaking() {
    audio.pause();
    audio.currentTime = 0;
    audio.src = "";
    isSpeaking = false;
  }

  function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      mediaRecorder = new MediaRecorder(stream);
      chunks = [];
      mediaRecorder.ondataavailable = function (e) { if (e.data.size > 0) chunks.push(e.data); };
      mediaRecorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        sendAudio();
      };
      mediaRecorder.start();
      isRecording = true;
      setRecording(true);
    }).catch(function () {
      statusEl.textContent = "Mic access denied";
    });
  }

  function sendAudio() {
    setBusy("Thinking\u2026");
    var mimeType = (mediaRecorder && mediaRecorder.mimeType) || "audio/webm";
    var blob = new Blob(chunks, { type: mimeType });
    var ext = mimeType.indexOf("ogg") > -1 ? ".ogg" : mimeType.indexOf("mp4") > -1 ? ".mp4" : ".webm";

    var fd = new FormData();
    fd.append("audio", blob, "q" + ext);
    fd.append("session_id", sessionId);

    fetch(API + "/voice", { method: "POST", body: fd })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.blob(); })
      .then(function (audioBlob) {
        audio.src = URL.createObjectURL(audioBlob);
        isSpeaking = true;
        mic.disabled = false;
        micIcon.innerHTML = MIC_SVG;
        statusEl.textContent = "Speaking\u2026 tap mic to interrupt";
        audio.play();
        audio.onended = function () {
          if (isSpeaking) { isSpeaking = false; statusEl.textContent = "Tap the mic to ask another question"; }
          ring.classList.remove("active");
          avatarW.classList.remove("active");
        };
        audio.onerror = function () {
          isSpeaking = false;
          ring.classList.remove("active");
          avatarW.classList.remove("active");
        };
      })
      .catch(function () {
        statusEl.textContent = "Error \u2014 try again";
        mic.disabled = false;
        micIcon.innerHTML = MIC_SVG;
        ring.classList.remove("active");
        avatarW.classList.remove("active");
      });
  }

  /* ---- mic click ---- */
  mic.onclick = function () {
    if (mic.disabled) return;

    if (isSpeaking) {
      stopSpeaking();
      startRecording();
      return;
    }

    if (isRecording) {
      if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
      isRecording = false;
      setRecording(false);
      return;
    }

    if (!greetingPlayed) {
      playGreeting(function () { startRecording(); });
      return;
    }

    startRecording();
  };

  /* ---- session ---- */
  function endSession() {
    try {
      fetch(API + "/session/end", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId })
      });
    } catch (_) {}
    sessionId = crypto.randomUUID();
    try { sessionStorage.setItem("vw_sid", sessionId); sessionStorage.removeItem("vw_greeted"); } catch (_) {}
    greetingPlayed = false;
  }

  window.addEventListener("pagehide", function () {
    try {
      navigator.sendBeacon(
        API + "/session/end",
        new Blob([JSON.stringify({ session_id: sessionId })], { type: "application/json" })
      );
    } catch (_) {}
  });
})();
