// Vaani front end. Plain JS, no build step.
// Flow: pick dialect once -> paste / photo / voice -> /api/check -> show + speak.

(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var state = {
    dialect: null,
    ui: {},
    meta: {},
    health: { speech_api: false, llm: false },
    source: "text",
    question: "",
    last: null,
    lastText: "",
    lastSender: "",
    listenEngine: "",
    readEngine: "",
    audio: null
  };

  function store(key, val) {
    try {
      if (val === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, val);
    } catch (e) { return null; }
  }

  function t(key, vars) {
    var s = state.ui[key] || key;
    if (vars) Object.keys(vars).forEach(function (k) { s = s.split("{" + k + "}").join(vars[k]); });
    return s;
  }

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "class") n.className = attrs[k];
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }

  function getJSON(url, opts) {
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        return { status: r.status, ok: r.ok, body: body };
      });
    });
  }

  // ---------- speaking ----------

  function stopAudio() {
    if (state.audio) { state.audio.pause(); state.audio = null; }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function browserSpeak(text) {
    if (!window.speechSynthesis) return;
    var lang = state.meta.tts_lang || "hi-IN";
    var u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = 0.9;
    var voices = window.speechSynthesis.getVoices();
    var v = voices.find(function (x) { return x.lang === lang; }) ||
            voices.find(function (x) { return x.lang && x.lang.slice(0, 2) === lang.slice(0, 2); });
    if (v) u.voice = v;
    window.speechSynthesis.speak(u);
  }

  function playUrl(url) {
    stopAudio();
    state.audio = new Audio(url);
    return state.audio.play();
  }

  // 1) a clip recorded by a native speaker, 2) Sarvam TTS, 3) the phone's own voice
  function speak(text, clip) {
    stopAudio();
    var tryClip = clip
      ? fetch("/audio/" + state.dialect + "/" + clip + ".mp3", { method: "HEAD" }).then(function (r) { return r.ok; }).catch(function () { return false; })
      : Promise.resolve(false);

    return tryClip.then(function (hasClip) {
      if (hasClip) return playUrl("/audio/" + state.dialect + "/" + clip + ".mp3");
      if (!state.health.speech_api) return browserSpeak(text);
      return fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text, dialect: state.dialect })
      }).then(function (r) {
        if (!r.ok) throw new Error("tts");
        return r.blob();
      }).then(function (b) {
        return playUrl(URL.createObjectURL(b));
      }).catch(function () { browserSpeak(text); });
    });
  }

  // ---------- language ----------

  function applyUI() {
    document.querySelectorAll("[data-t]").forEach(function (n) { n.textContent = t(n.getAttribute("data-t")); });
    document.querySelectorAll("[data-t-placeholder]").forEach(function (n) { n.placeholder = t(n.getAttribute("data-t-placeholder")); });
    $("lang-btn").textContent = state.meta.native_name || "Language";
    document.documentElement.lang = (state.meta.speech_lang || "hi-IN").slice(0, 2);
  }

  function loadDialect(d) {
    return getJSON("/api/ui/" + d).then(function (res) {
      state.dialect = d;
      state.ui = res.body.ui || {};
      state.meta = res.body.meta || {};
      store("vaani.dialect", d);
      applyUI();
    });
  }

  var speakerIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/><path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

  function showPicker() {
    $("main").hidden = true;
    $("pick").hidden = false;
    $("result").hidden = true;
    getJSON("/api/dialects").then(function (res) {
      var list = $("dialect-list");
      list.innerHTML = "";
      res.body.forEach(function (d) {
        var play = el("button", { class: "play", type: "button", "aria-label": "Listen" });
        play.innerHTML = speakerIcon;
        play.addEventListener("click", function (e) {
          e.stopPropagation();
          state.meta = { tts_lang: d.speech_lang };
          state.dialect = d.id;
          speak(d.greeting, "greeting");
        });
        var li = el("li", { class: d.id === state.dialect ? "on" : "" }, [
          el("span", { class: "d-name" }, [d.native_name, el("span", { class: "d-en", text: d.name })]),
          play
        ]);
        li.addEventListener("click", function () {
          stopAudio();
          loadDialect(d.id).then(function () {
            showMain();
            if (state.pendingShare) { $("msg").value = state.pendingShare; state.pendingShare = ""; runCheck(false); }
          });
        });
        list.appendChild(li);
      });
    });
  }

  function showMain() {
    $("pick").hidden = true;
    $("main").hidden = false;
  }

  // ---------- photo ----------

  function loadScript(src) {
    return new Promise(function (ok, fail) {
      var s = document.createElement("script");
      s.src = src; s.onload = ok; s.onerror = fail;
      document.head.appendChild(s);
    });
  }

  function readInBrowser(file) {
    // no server OCR configured: read it on the phone with Tesseract
    var langs = /pa|malwai/.test(state.dialect) ? "eng+pan" : "eng+hin";
    var go = window.Tesseract ? Promise.resolve() : loadScript("https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js");
    return go.then(function () {
      return window.Tesseract.recognize(file, langs);
    }).then(function (r) {
      return { text: (r.data && r.data.text) || "", sender: "", engine: "Tesseract " + langs + " (in browser)" };
    });
  }

  function onPhoto(e) {
    var file = e.target.files[0];
    if (!file) return;
    var status = $("photo-status");
    status.hidden = false;
    status.textContent = t("reading_photo");
    var prev = $("photo-preview");
    prev.src = URL.createObjectURL(file);
    prev.hidden = false;

    var form = new FormData();
    form.append("image", file);
    fetch("/api/ocr", { method: "POST", body: form })
      .then(function (r) {
        if (r.status === 501) return readInBrowser(file);
        if (!r.ok) throw new Error("ocr");
        return r.json();
      })
      .then(function (got) {
        $("msg").value = (got.text || "").trim();
        if (got.sender) $("sender").value = got.sender;
        state.source = "screenshot";
        state.readEngine = got.engine || "";
        status.textContent = got.text ? "" : "?";
        status.hidden = !!got.text;
      })
      .catch(function () {
        status.textContent = "Could not read the photo. Please paste the message instead.";
      });
    e.target.value = "";
  }

  // ---------- voice ----------

  var rec = null;
  var recorder = null;
  var chunks = [];

  function setListening(on) {
    $("mic").classList.toggle("on", on);
    $("mic-label").textContent = on ? t("listening") : t("ask_btn");
  }

  function heard(text) {
    state.question = text;
    var h = $("heard");
    h.hidden = !text;
    h.textContent = t("you_said") + ": \u201c" + text + "\u201d";
  }

  function startListening() {
    stopAudio();
    if (state.health.speech_api && navigator.mediaDevices && window.MediaRecorder) {
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        chunks = [];
        recorder = new MediaRecorder(stream);
        recorder.ondataavailable = function (ev) { chunks.push(ev.data); };
        recorder.onstop = function () {
          stream.getTracks().forEach(function (tr) { tr.stop(); });
          var blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
          var form = new FormData();
          form.append("audio", blob, "voice.webm");
          form.append("dialect", state.dialect);
          getJSON("/api/stt", { method: "POST", body: form }).then(function (res) {
            if (res.ok && res.body.text) {
              state.listenEngine = res.body.engine;
              heard(res.body.text);
              afterVoice();
            }
          });
        };
        recorder.start();
        setListening(true);
      }).catch(function () { alert("Microphone permission is needed to ask by voice."); });
      return;
    }

    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Voice is not supported in this browser. Please use Chrome."); return; }
    rec = new SR();
    rec.lang = state.meta.speech_lang || "hi-IN";
    state.listenEngine = "browser speech recognition (" + rec.lang + ")";
    rec.interimResults = true;
    rec.continuous = true;
    var finalText = "";
    rec.onresult = function (ev) {
      var interim = "";
      for (var i = ev.resultIndex; i < ev.results.length; i++) {
        if (ev.results[i].isFinal) finalText += ev.results[i][0].transcript + " ";
        else interim += ev.results[i][0].transcript;
      }
      heard((finalText + interim).trim());
    };
    rec.onend = function () {
      setListening(false);
      if (state.question) afterVoice();
    };
    rec.onerror = function () { setListening(false); };
    state.question = "";
    rec.start();
    setListening(true);
  }

  function stopListening() {
    if (recorder && recorder.state === "recording") { recorder.stop(); setListening(false); }
    if (rec) { rec.stop(); rec = null; }
  }

  function afterVoice() {
    // Already showing an answer for this same message? Then it's a follow-up question.
    var same = state.last && state.last.reply && $("msg").value.trim() === state.lastText;
    if (same) { askFollowup(state.question); return; }
    // Otherwise check the message. If nothing is pasted, the spoken words are the message.
    runCheck(true);
  }

  // ---------- checking ----------

  function runCheck(fromVoice) {
    var text = $("msg").value.trim();
    var question = fromVoice ? state.question : "";
    if (!text && !question) { $("msg").focus(); return; }

    var btn = $("check-btn");
    btn.disabled = true;
    btn.textContent = t("checking");

    var body = {
      text: text,
      sender: $("sender").value.trim(),
      dialect: state.dialect,
      source: text ? state.source : "voice",
      question: question,
      cif: "",
      listen_engine: fromVoice ? state.listenEngine : "",
      read_engine: state.source === "screenshot" ? state.readEngine : ""
    };
    getJSON("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (res) {
      btn.disabled = false;
      btn.textContent = t("check_btn");
      if (!res.ok) return;
      state.last = res.body;
      state.lastText = text;
      state.lastSender = body.sender;
      if (res.body.clicked) showClicked(res.body.clicked);
      if (res.body.reply) showResult(res.body);
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = t("check_btn");
      alert("No internet or the server is not answering. Try again.");
    });
  }

  function smsHref(to, body) {
    // Android wants ?body=, iOS is happy with it too
    return "sms:" + to + "?body=" + encodeURIComponent(body);
  }

  function renderActions(a) {
    var box = el("div", { class: "actions" });
    if (a.sms) {
      var link = el("a", { class: "btn primary", href: smsHref(a.sms.to, a.sms.body) }, [t("send_sms")]);
      if (a.sms.needs_cif) {
        var input = el("input", { type: "text", inputmode: "numeric", placeholder: "CIF" });
        input.addEventListener("input", function () {
          var cif = input.value.replace(/\s/g, "");
          link.href = smsHref(a.sms.to, a.sms.body.replace("<CIF>", cif || "<CIF>"));
        });
        box.appendChild(el("label", { class: "cif" }, [el("span", { class: "small", text: t("cif_prompt") }), input]));
      }
      box.appendChild(link);
    }
    if (a.call) {
      box.appendChild(el("a", { class: "btn", href: "tel:" + a.call.number.replace(/\s/g, "") }, [a.call.label + " (" + a.call.number + ")"]));
    }
    if (a.portal) box.appendChild(el("a", { class: "btn", href: a.portal, target: "_blank", rel: "noopener" }, [t("open_site")]));
    if (a.email) box.appendChild(el("a", { class: "btn", href: "mailto:" + a.email.to + "?subject=" + encodeURIComponent(a.email.subject) }, ["Email " + a.email.to]));
    return box;
  }

  function traceItem(step) {
    var d = step.detail;
    if (step.step === "listen") return el("li", null, [el("strong", { text: "Listen: " }), "\u201c" + d.transcript + "\u201d ", el("span", { class: "eng", text: d.engine })]);
    if (step.step === "photo") return el("li", null, [el("strong", { text: "Photo: " }), "text read by ", el("span", { class: "eng", text: d.engine })]);
    if (step.step === "read") {
      var bits = [];
      bits.push("bank = " + (d.bank || "?"));
      bits.push("type = " + (d.type || "?"));
      if (d.links && d.links.length) bits.push("links = " + d.links.join(", "));
      if (d.amount) bits.push("amount = " + d.amount);
      if (d.deadline) bits.push("deadline = " + d.deadline);
      if (d.sender) bits.push("sender = " + d.sender);
      if (d.claude_says_asks_for_secret) bits.push("claude: asks for a secret");
      return el("li", null, [el("strong", { text: "Read: " }), el("code", { text: bits.join("; ") }), " ", el("span", { class: "eng", text: d.filled_by })]);
    }
    if (step.step === "check") {
      var ul = el("ul");
      d.forEach(function (c) {
        var extra = Object.keys(c).filter(function (k) { return k !== "code" && k !== "level"; })
          .map(function (k) { return k + ": " + (Array.isArray(c[k]) ? c[k].join(", ") : c[k]); }).join("; ");
        ul.appendChild(el("li", null, [el("span", { class: "lvl " + c.level, text: c.level }), el("code", { text: c.code }), extra ? " " + extra : ""]));
      });
      return el("li", null, [el("strong", { text: "Check:" }), ul]);
    }
    if (step.step === "decide") return el("li", null, [el("strong", { text: "Decide: " }), el("code", { text: d.verdict }), " because " + d.rule + " ", el("span", { class: "eng", text: d.engine })]);
    if (step.step === "reply") return el("li", null, [el("strong", { text: "Reply: " }), "lines " + d.template + " in " + d.dialect + ", ", el("span", { class: "eng", text: d.voice })]);
    return null;
  }

  function showResult(r) {
    var rep = r.reply;
    var box = $("result");
    box.innerHTML = "";
    box.hidden = false;

    var again = el("button", { class: "btn btn-small", type: "button" }, [t("listen_again")]);
    again.addEventListener("click", function () { speak(rep.speak, rep.clip); });
    box.appendChild(el("div", { class: "verdict " + r.verdict }, [
      el("p", { class: "word", text: rep.headline }),
      el("p", { class: "say", text: rep.summary }),
      again
    ]));

    var reasons = el("ul", { class: "reasons" });
    rep.reasons.forEach(function (x) { reasons.appendChild(el("li", { class: x.level, text: x.text })); });
    box.appendChild(reasons);

    var steps = el("ol", { class: "steps" });
    rep.steps.forEach(function (s) { steps.appendChild(el("li", { text: s })); });
    box.appendChild(steps);

    if (rep.actions.not_verified) box.appendChild(el("p", { class: "note", text: t("not_verified_note") }));
    box.appendChild(renderActions(rep.actions));

    box.appendChild(askBox());

    var ol = el("ol");
    r.trace.forEach(function (s) { var li = traceItem(s); if (li) ol.appendChild(li); });
    box.appendChild(el("details", { class: "trace" }, [el("summary", { text: t("how_checked") }), ol]));

    var wrong = el("button", { class: "link-btn", type: "button" }, [t("wrong_answer")]);
    wrong.addEventListener("click", function () {
      var note = prompt(t("wrong_answer")) || "";
      getJSON("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ check_id: r.id, note: note })
      }).then(function () { wrong.textContent = t("thanks"); wrong.disabled = true; });
    });
    var fresh = el("button", { class: "link-btn", type: "button" }, [t("new_check")]);
    fresh.addEventListener("click", reset);
    box.appendChild(el("div", { class: "after" }, [wrong, fresh]));

    box.scrollIntoView({ behavior: "smooth", block: "start" });
    speak(rep.speak, rep.clip);
  }

  function askBox() {
    var input = el("input", { type: "text", id: "ask-input", placeholder: t("ask_hint") });
    var go = el("button", { class: "btn btn-small", type: "button" }, [t("ask_send")]);
    var answer = el("div", { id: "ask-answer", class: "answer", hidden: "" });
    function send() { if (input.value.trim()) askFollowup(input.value.trim()); }
    go.addEventListener("click", send);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") send(); });
    return el("div", { class: "ask-more" }, [
      el("label", { class: "label", for: "ask-input", text: t("ask_more") }),
      el("div", { class: "ask-row" }, [input, go]),
      el("p", { class: "small", text: t("ask_btn") + " \u2191" }),
      answer
    ]);
  }

  function askFollowup(question) {
    var out = $("ask-answer");
    if (!out) return;
    out.hidden = false;
    out.textContent = t("ask_thinking");
    getJSON("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, text: state.lastText, sender: state.lastSender, dialect: state.dialect })
    }).then(function (res) {
      if (!res.ok) { out.textContent = "?"; return; }
      if (res.body.clicked) { out.hidden = true; showClicked(res.body.clicked); return; }
      out.innerHTML = "";
      out.appendChild(el("p", { class: "q", text: "\u201c" + question + "\u201d" }));
      out.appendChild(el("p", { text: res.body.answer }));
      out.appendChild(el("p", { class: "eng", text: res.body.engine + (res.body.guard === "replaced" ? " (answer blocked by safety check, showing safe reply)" : "") }));
      speak(res.body.answer);
    });
  }

  function showClicked(c) {
    var box = $("clicked");
    box.innerHTML = "";
    var steps = el("ol", { class: "steps" });
    c.steps.forEach(function (s) { steps.appendChild(el("li", { text: s })); });
    box.appendChild(el("h2", { text: c.title }));
    box.appendChild(steps);
    box.appendChild(el("a", { class: "btn primary", href: "tel:" + c.call.cyber }, ["1930"]));
    if (c.call.bank) box.appendChild(el("a", { class: "btn", href: "tel:" + c.call.bank.replace(/\s/g, "") }, [c.call.bank]));
    box.appendChild(el("a", { class: "btn", href: c.portal, target: "_blank", rel: "noopener" }, ["cybercrime.gov.in"]));
    var close = el("button", { class: "link-btn", type: "button" }, [t("close")]);
    close.addEventListener("click", function () { stopAudio(); box.hidden = true; });
    box.appendChild(close);
    box.hidden = false;
    // put it right under the header, above everything else
    document.body.insertBefore(box, $("pick"));
    window.scrollTo({ top: 0, behavior: "smooth" });
    speak(c.speak, c.clip);
  }

  function openClicked() {
    var bank = state.last && state.last.bank ? state.last.bank : "";
    getJSON("/api/clicked?dialect=" + state.dialect + "&bank=" + bank).then(function (res) { showClicked(res.body); });
  }

  function reset() {
    stopAudio();
    $("msg").value = "";
    $("sender").value = "";
    $("photo-preview").hidden = true;
    $("photo-status").hidden = true;
    $("result").hidden = true;
    $("clicked").hidden = true;
    heard("");
    state.source = "text";
    state.last = null;
    window.scrollTo({ top: 0, behavior: "smooth" });
    $("msg").focus();
  }

  // ---------- wiring ----------

  function wire() {
    $("lang-btn").addEventListener("click", showPicker);
    $("photo").addEventListener("change", onPhoto);
    $("check-btn").addEventListener("click", function () { runCheck(false); });
    $("clicked-btn").addEventListener("click", openClicked);
    $("msg").addEventListener("input", function () { if (!$("msg").value) state.source = "text"; });
    $("paste-btn").addEventListener("click", function () {
      if (!navigator.clipboard || !navigator.clipboard.readText) { $("msg").focus(); return; }
      navigator.clipboard.readText().then(function (txt) { $("msg").value = txt; state.source = "text"; }).catch(function () { $("msg").focus(); });
    });

    var mic = $("mic");
    mic.addEventListener("pointerdown", function (e) { e.preventDefault(); startListening(); });
    ["pointerup", "pointerleave", "pointercancel"].forEach(function (ev) {
      mic.addEventListener(ev, function () { if (mic.classList.contains("on")) stopListening(); });
    });
    mic.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  }

  function sharedText() {
    // Android "Share -> Vaani" lands here as /?text=... (see manifest share_target)
    var q = new URLSearchParams(location.search);
    var txt = [q.get("title"), q.get("text"), q.get("url")].filter(Boolean).join(" ").trim();
    if (txt) history.replaceState(null, "", "/");
    return txt;
  }

  function start() {
    wire();
    if (window.speechSynthesis) window.speechSynthesis.getVoices();
    getJSON("/api/health").then(function (res) { if (res.ok) state.health = res.body; });

    var shared = sharedText();
    var saved = store("vaani.dialect");
    if (!saved) { state.pendingShare = shared; showPicker(); return; }
    loadDialect(saved).then(function () {
      showMain();
      if (shared) { $("msg").value = shared; runCheck(false); }
    });
  }

  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(function () {});
  start();
})();
