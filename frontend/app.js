class TutorChatApp {
  constructor(options) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/+$/, "");

    this.ui = {
      // Setup
      setupScreen:       document.getElementById("setupScreen"),
      taskPicker:        document.getElementById("taskPicker"),
      levelPicker:       document.getElementById("levelPicker"),
      uploadInput:       document.getElementById("materialFile"),
      studentNameInput:  document.getElementById("studentNameInput"),
      uploadMaterialBtn: document.getElementById("uploadMaterialBtn"),
      uploadStatus:      document.getElementById("uploadStatus"),
      startLearningBtn:  document.getElementById("startLearningBtn"),
      setupError:        document.getElementById("setupError"),
      // Learning
      learningScreen:    document.getElementById("learningScreen"),
      historySidebarTitle: document.getElementById("historySidebarTitle"),
      historyList:       document.getElementById("historyList"),
      historyEmpty:      document.getElementById("historyEmpty"),
      endSessionBtn:     document.getElementById("endSessionBtn"),
      exerciseLabel:     document.getElementById("exerciseLabel"),
      learningTaskSwitcher: document.getElementById("learningTaskSwitcher"),
      switchModeBtn:     document.getElementById("switchModeBtn"),
      consolidationLabel: document.getElementById("consolidationLabel"),
      consolidationCard: document.getElementById("consolidationCard"),
      problemText:       document.getElementById("problemText"),
      nextProblemBtn:    document.getElementById("nextProblemBtn"),
      conversationLog:   document.getElementById("conversationLog"),
      attemptWarning:    document.getElementById("attemptWarning"),
      attemptBox:        document.getElementById("attemptBox"),
      submitAttempt:     document.getElementById("submitAttempt"),
      // Modal
      analyticsModal:    document.getElementById("analyticsModal"),
      statExercises:     document.getElementById("statExercises"),
      statAttempts:      document.getElementById("statAttempts"),
      statTime:          document.getElementById("statTime"),
      analyticsChart:    document.getElementById("analyticsChart"),
      newSessionBtn:     document.getElementById("newSessionBtn"),
      closeModalBtn:     document.getElementById("closeModalBtn"),
      historyModal:      document.getElementById("historyModal"),
      historyModalTitle: document.getElementById("historyModalTitle"),
      historyModalMeta:  document.getElementById("historyModalMeta"),
      historyConversationContent: document.getElementById("historyConversationContent"),
      closeHistoryModalBtn: document.getElementById("closeHistoryModalBtn"),
    };

    this.state = {
      sessionId:       `sess_${Date.now()}`,
      studentName:     "",
      taskType:        "translation",
      pendingTaskType: "translation",
      difficultyScore: 2,
      problemActive:   false,
      loadingProblem:  false,
      problemText:     "",
      attempts:        0,   // attempts on current exercise
      totalAttempts:   0,   // across whole session
      problemsSolved:  0,
      startedAt:       null,
      elapsedInterval: null,
      analyticsHistory: [],
      historySessions: [],
    };

    this._bindEvents();
  }

  // ── Event binding ──────────────────────────────────────────────────

  _bindEvents() {
    // Task-type picker
    this.ui.taskPicker.querySelectorAll(".picker-card").forEach(card => {
      card.addEventListener("click", () => {
        this.ui.taskPicker.querySelectorAll(".picker-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        this.state.taskType = card.dataset.value;
      });
    });

    // Level picker
    this.ui.levelPicker.querySelectorAll(".picker-card").forEach(card => {
      card.addEventListener("click", () => {
        this.ui.levelPicker.querySelectorAll(".picker-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        this.state.difficultyScore = Number(card.dataset.value);
      });
    });

    this.ui.uploadMaterialBtn.addEventListener("click",  () => this._handleUpload());
    this.ui.startLearningBtn.addEventListener("click",   () => this._startSession());
    this.ui.endSessionBtn.addEventListener("click",      () => this._endSession());
    this.ui.nextProblemBtn.addEventListener("click",     () => this._nextProblem());
    this.ui.switchModeBtn.addEventListener("click",      () => this._switchMode());
    this.ui.submitAttempt.addEventListener("click",      () => this._submitAttempt());
    this.ui.newSessionBtn.addEventListener("click",      () => this._newSession());
    this.ui.closeModalBtn.addEventListener("click",      () => this.ui.analyticsModal.classList.add("hidden"));
    this.ui.closeHistoryModalBtn.addEventListener("click", () => this.ui.historyModal.classList.add("hidden"));
    this.ui.learningTaskSwitcher.querySelectorAll(".mode-switch-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        this.ui.learningTaskSwitcher.querySelectorAll(".mode-switch-btn").forEach(b => b.classList.remove("selected"));
        btn.classList.add("selected");
        this.state.pendingTaskType = btn.dataset.value;
      });
    });

    // Cmd/Ctrl+Enter submits
    this.ui.attemptBox.addEventListener("keydown", e => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") this._submitAttempt();
    });
  }

  // ── Screen transitions ─────────────────────────────────────────────

  _showSetup() {
    this.ui.learningScreen.classList.add("hidden");
    this.ui.setupScreen.classList.remove("hidden");
  }

  async _startSession() {
    this.ui.startLearningBtn.disabled = true;
    this.ui.startLearningBtn.textContent = "Loading…";
    this.ui.setupError.textContent = "";
    this.state.studentName = (this.ui.studentNameInput.value || "").trim();
    if (!this.state.studentName) {
      this.ui.setupError.textContent = "Please enter your name before starting.";
      this.ui.startLearningBtn.disabled = false;
      this.ui.startLearningBtn.textContent = "Start Learning →";
      return;
    }

    // Switch to learning screen immediately so the user sees progress
    this.ui.setupScreen.classList.add("hidden");
    this.ui.learningScreen.classList.remove("hidden");
    this.ui.historySidebarTitle.textContent = `${this.state.studentName}'s sessions`;
    this.state.pendingTaskType = this.state.taskType;
    this._syncLearningModeButtons();
    await this._loadHistorySidebar();
    this._updateExerciseLabel();

    try {
      await this._presentProblem();
    } catch {
      // _presentProblem shows its own error in problemText; re-show setup
      this.ui.learningScreen.classList.add("hidden");
      this.ui.setupScreen.classList.remove("hidden");
      this.ui.setupError.textContent = "Could not connect — is the backend running on port 8000?";
    } finally {
      this.ui.startLearningBtn.disabled = false;
      this.ui.startLearningBtn.textContent = "Start Learning →";
    }
  }

  _endSession() {
    if (this.state.elapsedInterval) clearInterval(this.state.elapsedInterval);
    this._showAnalytics();
  }

  _newSession() {
    if (this.state.elapsedInterval) clearInterval(this.state.elapsedInterval);
    // Reset all session state
    Object.assign(this.state, {
      sessionId:       `sess_${Date.now()}`,
      studentName:     "",
      pendingTaskType: "translation",
      problemActive:   false,
      loadingProblem:  false,
      problemText:     "",
      attempts:        0,
      totalAttempts:   0,
      problemsSolved:  0,
      startedAt:       null,
      elapsedInterval: null,
      analyticsHistory: [],
    });
    this.ui.conversationLog.innerHTML = "";
    this.ui.studentNameInput.value = "";
    this.state.historySessions = [];
    this._renderHistorySidebar();
    this._syncLearningModeButtons();
    this.ui.analyticsModal.classList.add("hidden");
    this.ui.historyModal.classList.add("hidden");
    this._showSetup();
  }

  // ── Problem flow ───────────────────────────────────────────────────

  async _presentProblem() {
    if (this.state.loadingProblem) return;
    this.state.loadingProblem = true;
    this.ui.problemText.textContent = "Generating your exercise…";
    this.ui.consolidationCard.classList.add("hidden");
    this.ui.consolidationLabel.classList.add("hidden");
    this.ui.nextProblemBtn.classList.add("hidden");
    this.ui.attemptWarning.textContent = "";

    try {
      const rsp = await fetch(`${this.apiBaseUrl}/pf/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id:       this.state.sessionId,
          student_name:     this.state.studentName,
          task_type:        this.state.taskType,
          difficulty_score: this.state.difficultyScore,
        }),
      });
      if (!rsp.ok) throw new Error(`HTTP ${rsp.status}`);

      const raw = await rsp.text();
      this.state.problemText = this._stripJsonQuotes(raw) || "Exercise could not be loaded.";
      this.ui.problemText.textContent = this.state.problemText;
      this.state.problemActive = true;
      this.state.attempts = 0;
      this._startElapsedTimer();
      this.state.analyticsHistory.push({ type: "problem_start", timestamp: new Date().toISOString() });
      await this._loadHistorySidebar();
    } catch (err) {
      console.error("_presentProblem:", err);
      this.ui.problemText.textContent = "Could not load exercise — is the backend running?";
      throw err;
    } finally {
      this.state.loadingProblem = false;
    }
  }

  async _nextProblem() {
    this.ui.nextProblemBtn.disabled = true;
    this.ui.submitAttempt.disabled = true;
    this.ui.nextProblemBtn.textContent = "Loading…";
    this.ui.problemText.textContent = "Finding your next exercise…";

    try {
      const rsp = await fetch(`${this.apiBaseUrl}/pf/next`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: this.state.sessionId,
          task_type:  this.state.taskType,
        }),
      });
      if (!rsp.ok) throw new Error(`HTTP ${rsp.status}`);

      const raw = await rsp.text();
      this.state.problemText = this._stripJsonQuotes(raw) || "Exercise could not be loaded.";
      this.ui.problemText.textContent = this.state.problemText;
      this.ui.consolidationCard.classList.add("hidden");
      this.ui.consolidationLabel.classList.add("hidden");
      this.state.problemActive = true;
      this.ui.submitAttempt.disabled = false;
      this.state.attempts = 0;
      this.state.problemsSolved++;
      this.ui.nextProblemBtn.classList.add("hidden");
      this.ui.attemptWarning.textContent = "";
      this.ui.conversationLog.innerHTML = "";
      this._updateExerciseLabel();
      this._startElapsedTimer();
      this.state.analyticsHistory.push({ type: "next_problem", timestamp: new Date().toISOString() });
      await this._loadHistorySidebar();
    } catch (err) {
      console.error("_nextProblem:", err);
      this.ui.problemText.textContent = "Could not load next exercise — please retry.";
      this.ui.submitAttempt.disabled = false;
    } finally {
      this.ui.nextProblemBtn.disabled = false;
      this.ui.nextProblemBtn.textContent = "Next Exercise →";
    }
  }

  _updateExerciseLabel() {
    const labels = {
      translation:             "Translation Exercise",
      error_correction:        "Error Correction",
      conversation_completion: "Conversation Practice",
    };
    if (this.ui.exerciseLabel) {
      this.ui.exerciseLabel.textContent = labels[this.state.taskType] || "Exercise";
    }
  }

  async _switchMode() {
    const selected = this.state.pendingTaskType;
    if (!selected || selected === this.state.taskType) {
      this.ui.attemptWarning.textContent = "Already in this mode.";
      return;
    }
    this.state.taskType = selected;
    this._updateExerciseLabel();
    this.ui.attemptWarning.textContent = "Switching mode and generating a new exercise...";
    await this._nextProblem();
  }

  // ── Attempting ─────────────────────────────────────────────────────

  async _submitAttempt() {
    if (!this.state.problemActive) {
      this.ui.attemptWarning.textContent = "Waiting for exercise to load…";
      return;
    }
    const answer = this.ui.attemptBox.value.trim();
    if (!answer) return;

    this.state.attempts++;
    this.state.totalAttempts++;
    this.ui.attemptWarning.textContent = "Thinking…";
    this._appendConversation("student", answer);
    this.ui.attemptBox.value = "";

    try {
      const rsp = await fetch(`${this.apiBaseUrl}/pf/attempt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id:     this.state.sessionId,
          answer,
          attempt_number: this.state.attempts,
        }),
      });
      const data = await rsp.json();
      const payload = (data && typeof data.reply === "object" && data.reply !== null)
        ? data.reply
        : data;
      const tutorMsg = this._normalizeText(payload.reply || payload.evaluation || "Keep going!");
      this._appendConversation("ai", tutorMsg);
      this.ui.attemptWarning.textContent = "";

      this.state.analyticsHistory.push({ type: "attempt", timestamp: new Date().toISOString() });

      if (payload.show_consolidation && payload.consolidation) {
       this._appendConsolidation(payload.consolidation);
      }

      if (payload.can_advance) {
        if (payload.show_consolidation) {
          // Consolidation phase: disable further attempts, show Next button
          // with a clear label — student decides when they're ready to move on
          this.state.problemActive = false;
          this.ui.submitAttempt.disabled = true;
          this.ui.attemptWarning.textContent = "Take your time reading the review above, then continue when ready.";
        } else {
          // Correct answer: just show Next button
          this.ui.nextProblemBtn.textContent = "Next Exercise →";
          this.ui.nextProblemBtn.classList.remove("hidden");
        }
      } else if (typeof payload.max_attempts === "number") {
        this.ui.attemptWarning.textContent = `Attempt ${payload.attempts_used || 0} of ${payload.max_attempts}.`;
      }
      await this._loadHistorySidebar();
    } catch (err) {
      console.error("_submitAttempt:", err);
      this.ui.attemptWarning.textContent = "Submission failed — please retry.";
    }
  }
  // ── Upload ─────────────────────────────────────────────────────────

  async _handleUpload() {
    if (!this.ui.uploadInput.files.length) return;
    const file = this.ui.uploadInput.files[0];
    const fd = new FormData();
    fd.append("file", file);
    fd.append("session_id", this.state.sessionId);
    this.ui.uploadStatus.textContent = "Uploading…";
    try {
      const rsp = await fetch(`${this.apiBaseUrl}/instructor/upload`, { method: "POST", body: fd });
      if (!rsp.ok) throw new Error();
      const data = await rsp.json();
      this.ui.uploadStatus.textContent = `✓ ${data.filename || "Uploaded"}`;
    } catch {
      this.ui.uploadStatus.textContent = "Upload failed.";
    }
  }

  // ── Analytics modal ────────────────────────────────────────────────

  _showAnalytics() {
    const elapsed = this.state.startedAt
      ? Math.floor((Date.now() - this.state.startedAt) / 1000) : 0;

    this.ui.statExercises.textContent = this.state.problemsSolved;
    this.ui.statAttempts.textContent  = this.state.totalAttempts;
    this.ui.statTime.textContent      = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;

    this._drawChart();
    this.ui.analyticsModal.classList.remove("hidden");
  }

  _drawChart() {
    const canvas = this.ui.analyticsChart;
    const ctx    = canvas.getContext("2d");
    const values = [
      this.state.analyticsHistory.filter(x => x.type === "attempt").length,
      this.state.problemsSolved,
    ];
    const labels = ["Attempts", "Exercises Done"];
    const colors = ["#4f46e5", "#059669"];
    const max    = Math.max(...values, 1);

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = "12px system-ui, sans-serif";
    ctx.textAlign = "center";

    const barW = 80;
    const totalW = labels.length * barW + (labels.length + 1) * ((canvas.width - labels.length * barW) / (labels.length + 1));
    const gap = (canvas.width - labels.length * barW) / (labels.length + 1);

    labels.forEach((label, i) => {
      const x    = gap + i * (barW + gap);
      const barH = Math.max((values[i] / max) * 120, values[i] > 0 ? 4 : 0);
      const y    = 140 - barH;

      ctx.fillStyle = colors[i] + "22";
      ctx.fillRect(x, 20, barW, 120);

      ctx.fillStyle = colors[i];
      ctx.beginPath();
      if (ctx.roundRect) {
        ctx.roundRect(x, y, barW, barH, [4, 4, 0, 0]);
      } else {
        ctx.rect(x, y, barW, barH);
      }
      ctx.fill();

      ctx.fillStyle = "#64748b";
      ctx.fillText(label, x + barW / 2, 162);
      if (values[i] > 0) {
        ctx.fillStyle = colors[i];
        ctx.fillText(values[i], x + barW / 2, y - 6);
      }
    });
  }

  // ── Timer ──────────────────────────────────────────────────────────

  _startElapsedTimer() {
    if (!this.state.startedAt) this.state.startedAt = Date.now();
    // Timer runs silently; value is only read when End Session is clicked
    if (!this.state.elapsedInterval) {
      this.state.elapsedInterval = setInterval(() => {}, 60000);
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────

  _appendConversation(sender, text) {
    const card = document.createElement("div");
    card.className = `conversation-card ${sender}`;
    const label = sender === "ai" ? "Tutor" : "You";
    card.innerHTML = `<strong>${label}</strong>${text.replace(/\n\n+/g, "<br><br>")}`;
    this.ui.conversationLog.appendChild(card);
    this.ui.conversationLog.scrollTop = this.ui.conversationLog.scrollHeight;
  }

  _appendConsolidation(text) {
  const card = document.createElement("div");
  card.className = "conversation-card consolidation";
  const normalized = text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .split(/\r?\n/).map(l => l.trim()).filter(Boolean).join("<br><br>");
  card.innerHTML = `
    <strong>Review</strong>
    <div class="consolidation-body">${normalized}</div>
    <button class="btn success consolidation-next-btn">I've read this — Next Exercise →</button>
  `;
  card.querySelector(".consolidation-next-btn").addEventListener("click", () => this._nextProblem());
  this.ui.conversationLog.appendChild(card);
  this.ui.conversationLog.scrollTop = this.ui.conversationLog.scrollHeight;
}
  _normalizeText(text) {
    if (!text) return "";
    const escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return escaped.split(/\r?\n/).map(l => l.trim()).filter(Boolean).join("\n\n");
  }

  // FastAPI serialises plain strings as JSON "quoted text" — unwrap if present
  _stripJsonQuotes(str) {
    if (typeof str === "string" && str.startsWith('"') && str.endsWith('"')) {
      try { return JSON.parse(str); } catch { /* fall through */ }
    }
    return str;
  }

  _syncLearningModeButtons() {
    this.ui.learningTaskSwitcher.querySelectorAll(".mode-switch-btn").forEach(btn => {
      btn.classList.toggle("selected", btn.dataset.value === this.state.pendingTaskType);
    });
  }

  async _loadHistorySidebar() {
    if (!this.state.studentName) return;
    try {
      const rsp = await fetch(`${this.apiBaseUrl}/pf/history?student_name=${encodeURIComponent(this.state.studentName)}`);
      if (!rsp.ok) throw new Error(`HTTP ${rsp.status}`);
      this.state.historySessions = await rsp.json();
      this._renderHistorySidebar();
    } catch (err) {
      console.error("_loadHistorySidebar:", err);
      this.state.historySessions = [];
      this._renderHistorySidebar();
    }
  }

  _renderHistorySidebar() {
    this.ui.historyList.innerHTML = "";
    const sessions = this.state.historySessions || [];
    this.ui.historyEmpty.classList.toggle("hidden", sessions.length > 0);

    sessions.forEach((item) => {
      const row = document.createElement("button");
      row.className = `history-item ${item.session_id === this.state.sessionId ? "active" : ""}`;
      row.type = "button";
      const updated = item.last_updated_at ? this._formatDateTime(item.last_updated_at) : "Unknown";
      const attempts = item.stats?.total_attempts ?? 0;
      const solved = item.stats?.problems_completed ?? 0;
      row.innerHTML = `
        <div class="history-item-title">${this._normalizeText(item.task_type || "session")}</div>
        <div class="history-item-meta">${updated}</div>
        <div class="history-item-meta">${attempts} attempts • ${solved} solved</div>
      `;
      row.addEventListener("click", () => this._openHistorySession(item.session_id));
      this.ui.historyList.appendChild(row);
    });
  }

  async _openHistorySession(sessionId) {
    try {
      const rsp = await fetch(`${this.apiBaseUrl}/pf/history/${encodeURIComponent(sessionId)}?student_name=${encodeURIComponent(this.state.studentName)}`);
      if (!rsp.ok) throw new Error(`HTTP ${rsp.status}`);
      const payload = await rsp.json();
      this.ui.historyModalTitle.textContent = `Session ${payload.session_id}`;
      const updated = payload.last_updated_at ? this._formatDateTime(payload.last_updated_at) : "Unknown";
      const attempts = payload.stats?.total_attempts ?? 0;
      const solved = payload.stats?.problems_completed ?? 0;
      this.ui.historyModalMeta.textContent = `${updated} • ${attempts} attempts • ${solved} solved`;

      this.ui.historyConversationContent.innerHTML = "";
      const history = payload.conversation_history || [];
      history.forEach((event) => {
        const item = document.createElement("div");
        item.className = "history-msg";
        const role = event.role || event.event_type || "event";
        item.innerHTML = `
          <div class="history-msg-role">${this._normalizeText(role)}</div>
          <div>${this._normalizeText(event.content || "")}</div>
        `;
        this.ui.historyConversationContent.appendChild(item);
      });
      this.ui.historyModal.classList.remove("hidden");
    } catch (err) {
      console.error("_openHistorySession:", err);
      this.ui.attemptWarning.textContent = "Could not load that saved conversation.";
    }
  }

  _formatDateTime(isoString) {
    const dt = new Date(isoString);
    if (Number.isNaN(dt.getTime())) return "Unknown";
    return dt.toLocaleString();
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const apiBaseUrl = window.TUTORCHAT_API_BASE_URL || "http://localhost:8000/api/v1";
  new TutorChatApp({ apiBaseUrl });
});
