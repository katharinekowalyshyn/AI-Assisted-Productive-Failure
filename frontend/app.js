class TutorChatApp {
  constructor(options) {
    this.apiBaseUrl = options.apiBaseUrl.replace(/\/+$/, "");
    this.elements = {
      chatLog: document.getElementById("chat-log"),
      form: document.getElementById("chat-form"),
      input: document.getElementById("chat-input"),
      sendBtn: document.getElementById("send-btn"),
      resetBtn: document.getElementById("reset-btn"),
      sessionId: document.getElementById("session-id"),
    };

    this.state = {
      sessionId: null,
      history: [],
      sending: false,
    };

    this._bindEvents();
    this._addSystemMessage(
      "This is a demo tutor. Messages are not persisted and this UI is for development only."
    );
  }

  _bindEvents() {
    this.elements.form.addEventListener("submit", (e) => {
      e.preventDefault();
      this._handleSubmit();
    });

    this.elements.resetBtn.addEventListener("click", () => {
      this._resetSession();
    });
  }

  async _handleSubmit() {
    const text = this.elements.input.value.trim();
    if (!text || this.state.sending) return;

    this._setSending(true);
    this._appendMessage("user", text);
    this.elements.input.value = "";

    try {
      const response = await this._sendToApi(text);
      this._applyResponse(response);
    } catch (error) {
      console.error(error);
      this._appendMessage(
        "system",
        "There was a problem talking to the backend. Check the console and backend logs."
      );
    } finally {
      this._setSending(false);
      this.elements.input.focus();
    }
  }

  async _sendToApi(userMessage) {
    const payload = {
      session_id: this.state.sessionId,
      user_message: userMessage,
      history: this.state.history,
    };

    const res = await fetch(`${this.apiBaseUrl}/chat/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }
    return res.json();
  }

  _applyResponse(data) {
    const { session_id, reply } = data;
    if (!this.state.sessionId && session_id) {
      this.state.sessionId = session_id;
      this.elements.sessionId.textContent = session_id;
    }

    if (reply) {
      this._appendMessage("assistant", reply);
    }

    // Update history used for subsequent requests
    const lastUser = this._lastUserMessage();
    if (lastUser) {
      this.state.history.push({ role: "user", content: lastUser });
    }
    if (reply) {
      this.state.history.push({ role: "assistant", content: reply });
    }
  }

  _lastUserMessage() {
    const items = this.elements.chatLog.querySelectorAll(
      ".chat-bubble.user .chat-body"
    );
    if (!items.length) return null;
    return items[items.length - 1].textContent || null;
  }

  _appendMessage(role, content) {
    const container = document.createElement("div");
    container.className = `chat-bubble ${role}`;

    if (role !== "system") {
      const meta = document.createElement("div");
      meta.className = "chat-meta";
      meta.textContent = role === "user" ? "You" : "Tutor";
      container.appendChild(meta);
    }

    const body = document.createElement("div");
    body.className = "chat-body";
    body.textContent = content;
    container.appendChild(body);

    this.elements.chatLog.appendChild(container);
    this.elements.chatLog.scrollTop = this.elements.chatLog.scrollHeight;
  }

  _addSystemMessage(text) {
    this._appendMessage("system", text);
  }

  _setSending(isSending) {
    this.state.sending = isSending;
    this.elements.sendBtn.disabled = isSending;
    this.elements.sendBtn.textContent = isSending ? "Sending…" : "Send";
  }

  _resetSession() {
    this.state.sessionId = null;
    this.state.history = [];
    this.elements.sessionId.textContent = "–";
    this.elements.chatLog.innerHTML = "";
    this._addSystemMessage(
      "Started a new session. Your next message will create a new conversation with the backend."
    );
  }
}

// Initialize app once DOM is ready
window.addEventListener("DOMContentLoaded", () => {
  /**
   * Default backend URL assumes FastAPI is running on port 8000.
   * Adjust this if you deploy the backend elsewhere.
   */
  const apiBaseUrl =
    window.TUTORCHAT_API_BASE_URL || "http://localhost:8000/api";

  new TutorChatApp({ apiBaseUrl });
});

