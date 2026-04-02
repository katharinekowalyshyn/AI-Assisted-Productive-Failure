class TutorChatApp {
  constructor(options) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/+$/, "");
    this.ui = {
      themeToggle: document.getElementById("themeToggle"),
      timerBadge: document.getElementById("timerBadge"),
      timerSelect: document.getElementById("timerSelect"),
      levelSelect: document.getElementById("levelSelect"),
      sessionId: document.getElementById("session-id"),
      selfConfidence: document.getElementById("selfConfidence"),
      uploadInput: document.getElementById("materialFile"),
      uploadMaterialBtn: document.getElementById("uploadMaterialBtn"),
      uploadStatus: document.getElementById("uploadStatus"),
      topicSelect: document.getElementById("topicSelect"),
      runDiagnosticBtn: document.getElementById("runDiagnosticBtn"),
      diagnosticResult: document.getElementById("diagnosticResult"),
      presentProblemBtn: document.getElementById("presentProblemBtn"),
      problemText: document.getElementById("problemText"),
      conversationLog: document.getElementById("conversationLog"),
      attemptBox: document.getElementById("attemptBox"),
      submitAttempt: document.getElementById("submitAttempt"),
      attemptCount: document.getElementById("attemptCount"),
      attemptWarning: document.getElementById("attemptWarning"),
      hintBtns: Array.from(document.querySelectorAll(".hintBtn")),
      analyticsChart: document.getElementById("analyticsChart"),
      metricAttempts: document.getElementById("metricAttempts"),
      hintsUsed: document.getElementById("hintsUsed"),
      metricProblems: document.getElementById("metricProblems"),
      metricTime: document.getElementById("metricTime"),
      tabButtons: Array.from(document.querySelectorAll(".tab-btn")),
      tabContents: Array.from(document.querySelectorAll(".tab-content")),
    };

    this.state = {
      mode: "pf",
      sessionId: `sess_${Date.now()}`,
      problemActive: false,
      problemText: "",
      attempts: 0,
      hintsUsed: 0,
      problemsSolved: 0,
      timerValue: Number(this.ui.timerSelect.value),
      timerRemaining: 0,
      timerRunning: false,
      timerInterval: null,
      startedAt: null,
      diagnosis: null,
      analyticsHistory: [],
      unlockedHints: [],
    };

    this.ui.sessionId.textContent = this.state.sessionId;
    this._bindEvents();
    this._setMode("problemHubTab");
  }

  _bindEvents() {
    this.ui.themeToggle.addEventListener("click", () => this._toggleTheme());
    this.ui.tabButtons.forEach((btn) => btn.addEventListener("click", () =>
      this._setMode(btn.dataset.tab)
    ));

    this.ui.timerSelect.addEventListener("change", (e) => {
      this.state.timerValue = Number(e.target.value);
    });

    this.ui.levelSelect.addEventListener("change", () => this._runDiagnostic());

    this.ui.runDiagnosticBtn.addEventListener("click", () => this._runDiagnostic());

    this.ui.uploadMaterialBtn.addEventListener("click", () => this._handleUpload());
    this.ui.presentProblemBtn.addEventListener("click", () => this._presentProblem());
    this.ui.submitAttempt.addEventListener("click", () => this._submitAttempt());
    this.ui.hintBtns.forEach((btn) =>
      btn.addEventListener("click", () => this._useHint(btn.dataset.level))
    );
  }

  _setMode(tabId) {
    this.ui.tabContents.forEach((tab) => tab.classList.remove("active"));
    this.ui.tabButtons.forEach((btn) => btn.classList.remove("active"));
    document.getElementById(tabId).classList.add("active");
    document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
  }

  _toggleTheme() {
    document.body.classList.toggle("light");
    document.body.classList.toggle("dark");
  }

  _runDiagnostic() {
    const confidence = Number(this.ui.selfConfidence.value);
    const level = this.ui.levelSelect.value === "auto"
      ? (confidence <= 2? "novice" : confidence <= 4? "intermediate" : "advanced")
      : this.ui.levelSelect.value;

    this.state.diagnosis = level;
    this.ui.diagnosticResult.textContent = `Level set to ${level.toUpperCase()}.`;
    this.state.analyticsHistory.push({ type: "diagnostic", level, timestamp: new Date().toISOString() });
  }

  async _handleUpload() {
  if (!this.ui.uploadInput.files.length) return;
  const file = this.ui.uploadInput.files[0];
  const fd = new FormData();
  fd.append("file", file);
  fd.append("session_id", this.state.sessionId);  // ADD: Tie to session

  this.ui.uploadStatus.textContent = "Uploading...";
  try {
    const rsp = await fetch(`${this.apiBaseUrl}/instructor/upload`, {
      method: "POST",
      body: fd,  // No Content-Type header for FormData
    });
    if (!rsp.ok) throw new Error();
    const data = await rsp.json();
    this.ui.uploadStatus.textContent = `Uploaded: ${data.filename || "OK"}.`;
    this.state.analyticsHistory.push({ type: "upload", filename: data.filename || "n/a", timestamp: new Date().toISOString() });
  } catch {
    this.ui.uploadStatus.textContent = "Upload failed";
  }
}

  
async _presentProblem() {
  try {
    const rsp = await fetch(`${this.apiBaseUrl}/pf/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: this.state.sessionId,
        topic: this.ui.topicSelect.value || "general",
        level: this.state.diagnosis || "intermediate"
      }),
    });
    this.state.problemText = await rsp.text() || "Solve: 3x + 5 = 20";  // Get plain text directly
    this.ui.problemText.textContent = this.state.problemText;
    this.state.problemActive = true;
    this.state.attempts = 0;
    this.ui.attemptCount.textContent = "0";
    this._startHiddenTimer();
    this._resetHints();
    this._logAnalytics("present_problem");
  } catch (e) {
    console.error("Error in _presentProblem:", e);  // Add for debugging
    this.ui.problemText.textContent = "Problem fetch error. Retry.";
  }
}

  _startHiddenTimer() {
    if (this.state.timerInterval) clearInterval(this.state.timerInterval);
    this.state.timerRunning = true;
    this.state.timerRemaining = this.state.timerValue;
    this.state.startedAt = Date.now();
    this.ui.timerBadge.classList.remove("hidden");

    this.state.timerInterval = setInterval(() => {
      this.state.timerRemaining--;
      const elapsed = Math.floor((Date.now() - this.state.startedAt) / 1000);
      this.ui.metricTime.textContent = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2,"0")}`;
      if (this.state.timerRemaining <= 0) {
        this._stopTimer();
      }
    }, 1000);
  }

  _stopTimer() {
    clearInterval(this.state.timerInterval);
    this.state.timerInterval = null;
    this.state.timerRunning = false;
    this.ui.timerBadge.classList.add("hidden");
  }

  _resetHints() {
    this.state.unlockedHints = [];
    this.ui.hintBtns.forEach((btn) => {
      btn.disabled = true;
      btn.textContent = `Hint ${btn.dataset.level}`;
    });
  }

  async _submitAttempt() {
    if (!this.state.problemActive) {
      this.ui.attemptWarning.textContent = "Click Present Problem first.";
      return;
    }
    const answer = this.ui.attemptBox.value.trim();
    if (!answer) return;
    this.state.attempts++;
    this.ui.attemptCount.textContent = this.state.attempts;
    this.ui.attemptWarning.textContent = "Evaluating...";
    this._appendConversation("student", answer);

    try {
      const rsp = await fetch(`${this.apiBaseUrl}/pf/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: this.state.sessionId,
          answer: answer,  // CHANGE: Use "answer" to match AttemptRequest
          attempt_number: this.state.attempts  // This is extra; remove if not needed
        }),
      });
      const data = await rsp.json();
      const tutorMessage = this._normalizeText(data.evaluation || data.reply || "AI response empty");
      this._appendConversation("ai", tutorMessage);
      this.ui.attemptWarning.textContent = "Feedback received.";

      this.state.analyticsHistory.push({
        type: "attempt",
        attempt: this.state.attempts,
        success: data.success ?? false,
        timestamp: new Date().toISOString(),
      });

      if (Math.random() > 0.45 && this.state.attempts > 0) this._unlockRandomHint();
      if (this.state.attempts >= 8) this.state.problemsSolved++;
      this._updateLiveMetrics();
      this._drawAnalyticsChart();
    } catch {
      this.ui.attemptWarning.textContent = "Attempt failed.";
    }
    this.ui.attemptBox.value = "";
  }

  _appendConversation(sender, text) {
    const card = document.createElement("div");
    card.className = `conversation-card ${sender}`;
    card.innerHTML = `<strong>${sender === "ai" ? "AI Tutor" : "You"}</strong><br/>${text.replace(/\n\n+/g, "<br><br>")}`;
    this.ui.conversationLog.appendChild(card);
    this.ui.conversationLog.appendChild(document.createElement("div")); // spacing
    this.ui.conversationLog.scrollTop = this.ui.conversationLog.scrollHeight;
  }

  _normalizeText(text) {
    if (!text) return "";
    let normalized = text.replace(/[^\w\s\.\,\:\;\-]/g, "");
    const lines = normalized.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    return lines.map((line, idx) => `${idx + 1}. ${line}`).join("\n\n");
  }

  _unlockRandomHint() {
    const locked = [...this.ui.hintBtns].filter((b) => b.disabled);
    if (!locked.length) return;
    const candidate = locked[Math.floor(Math.random() * locked.length)];
    candidate.disabled = false;
    this.state.unlockedHints.push(candidate.dataset.level);
    this.ui.hintsUsed.textContent = ++this.state.hintsUsed;
  }

  async _useHint(level) {
    try {
      const rsp = await fetch(`${this.apiBaseUrl}/pf/hint`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          session_id: this.state.sessionId,
          problem_text: this.state.problemText,
          hint_level: Number(level),
        })
      });
      const data = await rsp.json();
      this._appendConversation("ai", `Hint (${level}): ${data.hint || data.explanation || "No hint available."}`);
      this.state.analyticsHistory.push({ type: "hint", level, timestamp: new Date().toISOString() });
      this._updateLiveMetrics();
      this._drawAnalyticsChart();
    } catch {
      this._appendConversation("ai", "Hint call failed.");
    }
  }

  _logAnalytics(type) {
    this.state.analyticsHistory.push({type, timestamp: new Date().toISOString()});
    this._updateLiveMetrics();
  }

  _updateLiveMetrics() {
  const elapsed = this.state.startedAt ? Math.floor((Date.now() - this.state.startedAt) / 1000) : 0;  // ADD: Calculate elapsed time
  this.ui.metricAttempts.textContent = this.state.attempts;
  this.ui.hintsUsed.textContent = this.state.hintsUsed;
  this.ui.metricProblems.textContent = this.state.problemsSolved;
  this.ui.metricTime.textContent = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;
}

  _drawAnalyticsChart() {
    const ctx = this.ui.analyticsChart.getContext("2d");
    const calls = this.state.analyticsHistory.filter((x)=>x.type==="attempt").length;
    const hints = this.state.analyticsHistory.filter((x)=>x.type==="hint").length;
    const uploads = this.state.analyticsHistory.filter((x)=>x.type==="upload").length;

    ctx.clearRect(0,0,ctx.canvas.width,ctx.canvas.height);
    const labels = ["Attempts","Hints","Uploads"];
    const values = [calls,hints,uploads];
    const max = Math.max(...values,1);
    const barWidth = 100;
    labels.forEach((label,i) => {
      const height = (values[i]/max)*180;
      const x = 70 + i*(barWidth+30);
      const y = 220 - height;
      ctx.fillStyle = ["#6c5ce7","#00d4ff","#00e676"][i];
      ctx.fillRect(x, y, barWidth, height);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, x, 240);
      ctx.fillText(values[i], x+barWidth/2-8, y-8);
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const apiBaseUrl = window.TUTORCHAT_API_BASE_URL || "http://localhost:8000/api/v1";
  new TutorChatApp({ apiBaseUrl });
});