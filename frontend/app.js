class TutorChatApp {
  constructor(options) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/+$/, "");

    /* ---------------- UI ELEMENTS ---------------- */
    this.ui = {
      learningMode: document.getElementById("learningMode"),
      tabButtons: document.querySelectorAll(".tab-btn"),
      tabContents: document.querySelectorAll(".tab-content"),

      chatLog: document.getElementById("chat-log"),
      chatForm: document.getElementById("chat-form"),
      chatInput: document.getElementById("chat-input"),
      sendBtn: document.getElementById("send-btn"),
      resetBtn: document.getElementById("reset-btn"),
      sessionId: document.getElementById("session-id"),

      problemText: document.getElementById("problemText"),
      attemptBox: document.getElementById("attemptBox"),
      submitAttempt: document.getElementById("submitAttempt"),
      attemptCount: document.getElementById("attemptCount"),
      attemptWarning: document.getElementById("attemptWarning"),
      timerDisplay: document.getElementById("timerDisplay"),
      timerSelect: document.getElementById("timerSelect"),
      hintBtns: document.querySelectorAll(".hintBtn"),

      comparisonPanel: document.getElementById("comparisonPanel"),
      reflectionPanel: document.getElementById("reflectionPanel"),
      reflectionText: document.getElementById("reflectionText"),
      submitReflection: document.getElementById("submitReflection"),

      metricAttempts: document.getElementById("metricAttempts"),
      metricHints: document.getElementById("metricHints"),
      metricTime: document.getElementById("metricTime"),
      metricProblems: document.getElementById("metricProblems"),
      exportCSV: document.getElementById("exportCSV"),

      uploadBtn: document.getElementById("uploadMaterialBtn"),
      uploadInput: document.getElementById("materialFile"),
      uploadStatus: document.getElementById("uploadStatus"),
    };

    /* ---------------- STATE ---------------- */
    this.state = {
      mode: "normal",
      sessionId: null,
      history: [],
      sending: false,

      attempts: 0,
      hintsUsed: 0,
      problemsSolved: 0,
      totalTimeSpent: 0,
      timerSeconds: 600,
      timerRemaining: 600,
      timerInterval: null,
      analyticsLog: [],
    };

    this._bindEvents();
    this._addSystemMessage("Welcome to TutorChat Learning Lab.");
  }

  /* ---------------- EVENT BINDINGS ---------------- */

  _bindEvents() {
    this.ui.chatForm.addEventListener("submit", e => {
      e.preventDefault();
      this._handleChatSubmit();
    });

    this.ui.resetBtn.addEventListener("click", () => this._resetSession());

    this.ui.tabButtons.forEach(btn =>
      btn.addEventListener("click", () => this._switchTab(btn.dataset.tab))
    );

    this.ui.learningMode.addEventListener("change", e => {
      this.state.mode = e.target.value;
      if (this.state.mode === "pf") this._enterPFMode();
      else this._switchTab("normalTab");
    });

    this.ui.submitAttempt.addEventListener("click", () => this._submitAttempt());
    this.ui.timerSelect.addEventListener("change", e => this._changeTimer(e));
    this.ui.exportCSV.addEventListener("click", () => this._exportCSV());

    this.ui.hintBtns.forEach(btn =>
      btn.addEventListener("click", () => this._useHint(btn))
    );

    /* Instructor Upload */
    this.ui.uploadBtn.addEventListener("click", () => this._handleUpload());
  }

  /* ---------------- TAB SYSTEM ---------------- */

  _switchTab(tabId) {
    this.ui.tabContents.forEach(t => t.classList.remove("active"));
    this.ui.tabButtons.forEach(b => b.classList.remove("active"));
    document.getElementById(tabId).classList.add("active");
    document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
  }

  _enterPFMode() {
    this._switchTab("pfTab");
    this.ui.problemText.textContent =
      "Solve: If 3x + 5 = 20, find x.";
    this._resetPFState();
  }

  /* ---------------- CHAT ---------------- */

  async _handleChatSubmit() {
    const text = this.ui.chatInput.value.trim();
    if (!text || this.state.sending) return;

    this._appendMessage("user", text);
    this.ui.chatInput.value = "";
    this._setSending(true);

    try {
      const res = await fetch(`${this.apiBaseUrl}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: this.state.sessionId,
          user_message: text,
          history: this.state.history
        })
      });
      const data = await res.json();
      this._appendMessage("assistant", data.reply);
    } catch {
      this._appendMessage("system", "Backend error.");
    }

    this._setSending(false);
  }

  /* ---------------- PF SYSTEM ---------------- */

  async _submitAttempt() {
  const answer = this.ui.attemptBox.value.trim();
  if (!answer) return;

  this.ui.attemptWarning.textContent = "Evaluating attempt...";

  try {
    const res = await fetch(`${this.apiBaseUrl}/pf/attempt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: this.state.sessionId || "default",
        problem_text: this.ui.problemText.textContent,
        student_answer: answer
      })
    });

    const data = await res.json();

    this.ui.comparisonPanel.classList.remove("hidden");
    this.ui.comparisonPanel.innerHTML = `
      <h3>AI Evaluation</h3>
      <div class="feedback-box">${data.evaluation}</div>
    `;

    this.ui.attemptWarning.textContent = "Feedback generated.";
  } catch (err) {
    this.ui.attemptWarning.textContent = "Evaluation failed.";
  }
}

  _changeTimer(e) {
    this.state.timerSeconds = parseInt(e.target.value);
    this._resetTimer();
  }

  _startTimer() {
    this.state.timerRemaining = this.state.timerSeconds;
    this._updateTimerDisplay();

    this.state.timerInterval = setInterval(() => {
      this.state.timerRemaining--;
      this._updateTimerDisplay();

      if (this.state.timerRemaining <= 0) {
        clearInterval(this.state.timerInterval);
        this._unlockNextHint();
      }
    }, 1000);
  }

  _resetTimer() {
    clearInterval(this.state.timerInterval);
    this._startTimer();
  }

  _updateTimerDisplay() {
    const m = Math.floor(this.state.timerRemaining / 60);
    const s = this.state.timerRemaining % 60;
    this.ui.timerDisplay.textContent =
      `${m}:${s.toString().padStart(2, "0")}`;
  }

  _unlockNextHint() {
    for (const btn of this.ui.hintBtns) {
      if (btn.disabled) {
        btn.disabled = false;
        break;
      }
    }
  }

 async _useHint(btn) {
  const level = parseInt(btn.dataset.level);

  btn.disabled = true;
  btn.textContent = "Loading...";

  try {
    const res = await fetch(`${this.apiBaseUrl}/pf/hint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: this.state.sessionId || "default",
        problem_text: this.ui.problemText.textContent,
        student_answer: this.ui.attemptBox.value || "No answer",
        hint_level: level
      })
    });

    const data = await res.json();

    alert(`Hint Level ${level}:\n\n${data.hint}`);
    btn.textContent = `Hint ${level}`;
  } catch {
    alert("Hint failed");
    btn.textContent = `Hint ${level}`;
  }
}

  _resetPFState() {
    this.state.attempts = 0;
    this.ui.attemptCount.textContent = 0;
    this.ui.attemptWarning.textContent = "";
    this.ui.hintBtns.forEach(b => (b.disabled = true));
    this._resetTimer();
  }

  async _submitReflection() {
  const text = this.ui.reflectionText.value.trim();
  if (!text) return;

  try {
    const res = await fetch(`${this.apiBaseUrl}/pf/reflection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: this.state.sessionId || "default",
        problem_text: this.ui.problemText.textContent,
        student_reflection: text
      })
    });

    const data = await res.json();
    alert("Reflection Analysis:\n\n" + data.evaluation);
  } catch {
    alert("Reflection failed");
  }
}

  /* ---------------- ANALYTICS ---------------- */

  _logAnalytics(type) {
    this.state.analyticsLog.push({
      type,
      attempts: this.state.attempts,
      hints: this.state.hintsUsed,
      timeSpent: this.state.totalTimeSpent,
      timestamp: new Date().toISOString()
    });

    this.ui.metricAttempts.textContent = this.state.attempts;
    this.ui.metricTime.textContent =
      Math.floor(this.state.totalTimeSpent / 60) + " min";
  }

  _exportCSV() {
    const rows = [
      ["Type", "Attempts", "HintsUsed", "TimeSpent", "Timestamp"],
      ...this.state.analyticsLog.map(r =>
        [r.type, r.attempts, r.hints, r.timeSpent, r.timestamp]
      )
    ];

    const csv = rows.map(r => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "learning_analytics.csv";
    a.click();
  }

  /* ---------------- INSTRUCTOR UPLOAD ---------------- */

  async _handleUpload() {
    if (!this.ui.uploadInput.files.length) return;

    const file = this.ui.uploadInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    this.ui.uploadStatus.textContent = "Uploading...";

    try {
      const res = await fetch(`${this.apiBaseUrl}/instructor/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error();

      const data = await res.json();
      this.ui.uploadStatus.textContent = `Uploaded: ${data.filename}`;
    } catch {
      this.ui.uploadStatus.textContent = "Upload failed";
    }
  }

  /* ---------------- UTIL ---------------- */

  _appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `chat-bubble ${role}`;
    div.textContent = `${role.toUpperCase()}: ${text}`;
    this.ui.chatLog.appendChild(div);
    this.ui.chatLog.scrollTop = this.ui.chatLog.scrollHeight;
  }

  _addSystemMessage(msg) { this._appendMessage("system", msg); }

  _setSending(s) {
    this.state.sending = s;
    this.ui.sendBtn.disabled = s;
    this.ui.sendBtn.textContent = s ? "Sending…" : "Send";
  }

  _resetSession() {
    this.state.sessionId = null;
    this.state.history = [];
    this.ui.chatLog.innerHTML = "";
    this._addSystemMessage("New session started.");
  }
}

/* INIT */
window.addEventListener("DOMContentLoaded", () => {
  const apiBaseUrl =
    window.TUTORCHAT_API_BASE_URL || "http://localhost:8000/api";
  new TutorChatApp({ apiBaseUrl });
});