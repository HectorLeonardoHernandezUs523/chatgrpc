// =============================================================================
// script.js — Lógica del frontend del Chat Web gRPC
// Maneja autenticación (registro/login), envío de mensajes y polling
// automático cada 2 segundos para obtener nuevos mensajes.
// =============================================================================

(() => {
  "use strict";

  // ── Configuración ─────────────────────────────────────────────────────
  const API_BASE = window.location.origin;
  const POLL_INTERVAL = 2000;

  // ── Estado de la aplicación ───────────────────────────────────────────
  let currentUser = "";
  let pollingTimer = null;
  let lastMessageCount = 0;

  // ── Referencias al DOM — Auth ─────────────────────────────────────────
  const authScreen           = document.getElementById("auth-screen");
  const authTabs             = document.querySelectorAll(".auth-tab");
  const loginForm            = document.getElementById("login-form");
  const registerForm         = document.getElementById("register-form");
  const loginUsername         = document.getElementById("login-username");
  const loginPassword         = document.getElementById("login-password");
  const loginError            = document.getElementById("login-error");
  const loginBtn              = document.getElementById("login-btn");
  const registerUsername      = document.getElementById("register-username");
  const registerPassword      = document.getElementById("register-password");
  const registerPasswordConfirm = document.getElementById("register-password-confirm");
  const registerError         = document.getElementById("register-error");
  const registerSuccess       = document.getElementById("register-success");
  const registerBtn           = document.getElementById("register-btn");

  // ── Referencias al DOM — Chat ─────────────────────────────────────────
  const chatScreen        = document.getElementById("chat-screen");
  const currentUserLabel  = document.getElementById("current-user");
  const logoutBtn         = document.getElementById("logout-btn");
  const messagesContainer = document.getElementById("messages-container");
  const messagesList      = document.getElementById("messages-list");
  const messageInput      = document.getElementById("message-input");
  const sendBtn           = document.getElementById("send-btn");
  const connectionStatus  = document.getElementById("connection-status");

  // ── Utilidades ────────────────────────────────────────────────────────

  function formatTime(isoString) {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  function formatDate(isoString) {
    try {
      const date = new Date(isoString);
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);

      if (date.toDateString() === today.toDateString()) return "Hoy";
      if (date.toDateString() === yesterday.toDateString()) return "Ayer";

      return date.toLocaleDateString("es-ES", {
        day: "numeric",
        month: "long",
        year: "numeric",
      });
    } catch {
      return "";
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function setConnectionStatus(online) {
    connectionStatus.textContent = online ? "Conectado" : "Sin conexión";
    connectionStatus.className = "status " + (online ? "online" : "offline");
  }

  function clearAuthErrors() {
    loginError.textContent = "";
    registerError.textContent = "";
    registerSuccess.textContent = "";
  }

  // ── Tabs de autenticación ─────────────────────────────────────────────

  authTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      clearAuthErrors();

      authTabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      if (target === "login") {
        loginForm.classList.add("active");
        registerForm.classList.remove("active");
        loginUsername.focus();
      } else {
        registerForm.classList.add("active");
        loginForm.classList.remove("active");
        registerUsername.focus();
      }
    });
  });

  // ── Registro ──────────────────────────────────────────────────────────

  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthErrors();

    const username = registerUsername.value.trim();
    const password = registerPassword.value.trim();
    const passwordConfirm = registerPasswordConfirm.value.trim();

    if (!username || !password || !passwordConfirm) {
      registerError.textContent = "Todos los campos son obligatorios.";
      return;
    }

    if (username.length < 3) {
      registerError.textContent = "El usuario debe tener al menos 3 caracteres.";
      return;
    }

    if (password.length < 4) {
      registerError.textContent = "La contraseña debe tener al menos 4 caracteres.";
      return;
    }

    if (password !== passwordConfirm) {
      registerError.textContent = "Las contraseñas no coinciden.";
      return;
    }

    registerBtn.disabled = true;
    registerBtn.textContent = "Registrando…";

    try {
      const res = await fetch(`${API_BASE}/api/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (data.success) {
        registerSuccess.textContent = "¡Cuenta creada! Ahora inicia sesión.";
        registerUsername.value = "";
        registerPassword.value = "";
        registerPasswordConfirm.value = "";

        setTimeout(() => {
          authTabs[0].click();
          loginUsername.value = username;
          loginPassword.focus();
        }, 1500);
      } else {
        registerError.textContent = data.detail || "Error al registrar.";
      }
    } catch (err) {
      console.error("Error de conexión al registrar:", err);
      registerError.textContent = "Error de conexión. Verifica tu red.";
    } finally {
      registerBtn.disabled = false;
      registerBtn.textContent = "Crear cuenta";
    }
  });

  // ── Login ─────────────────────────────────────────────────────────────

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthErrors();

    const username = loginUsername.value.trim();
    const password = loginPassword.value.trim();

    if (!username || !password) {
      loginError.textContent = "Todos los campos son obligatorios.";
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = "Entrando…";

    try {
      const res = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (data.success) {
        currentUser = username;
        currentUserLabel.textContent = username;
        lastMessageCount = 0;

        authScreen.classList.remove("active");
        chatScreen.classList.add("active");

        messageInput.focus();
        startPolling();
      } else {
        loginError.textContent = data.detail || "Credenciales inválidas.";
      }
    } catch (err) {
      console.error("Error de conexión al iniciar sesión:", err);
      loginError.textContent = "Error de conexión. Verifica tu red.";
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = "Entrar";
    }
  });

  // ── Renderizado de mensajes ───────────────────────────────────────────

  function renderMessages(messages) {
    messagesList.innerHTML = "";

    if (messages.length === 0) {
      messagesList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🗨️</div>
          <p>No hay mensajes aún.<br/>¡Sé el primero en escribir!</p>
        </div>
      `;
      return;
    }

    let lastDate = "";

    messages.forEach((msg) => {
      const msgDate = formatDate(msg.timestamp);
      if (msgDate && msgDate !== lastDate) {
        lastDate = msgDate;
        const separator = document.createElement("div");
        separator.className = "date-separator";
        separator.innerHTML = `<span>${escapeHtml(msgDate)}</span>`;
        messagesList.appendChild(separator);
      }

      const isOwn = msg.username === currentUser;
      const bubble = document.createElement("div");
      bubble.className = "msg " + (isOwn ? "own" : "other");

      bubble.innerHTML = `
        <div class="msg-username">${escapeHtml(msg.username)}</div>
        <p class="msg-text">${escapeHtml(msg.message)}</p>
        <div class="msg-time">${formatTime(msg.timestamp)}</div>
      `;

      messagesList.appendChild(bubble);
    });

    if (messages.length !== lastMessageCount) {
      lastMessageCount = messages.length;
      setTimeout(scrollToBottom, 50);
    }
  }

  // ── Comunicación con el servidor ──────────────────────────────────────

  async function fetchMessages() {
    try {
      const res = await fetch(`${API_BASE}/api/messages`);
      const data = await res.json();

      if (data.success) {
        renderMessages(data.messages);
        setConnectionStatus(true);
      } else {
        console.error("Error al obtener mensajes:", data.error);
        setConnectionStatus(false);
      }
    } catch (err) {
      console.error("Error de conexión:", err);
      setConnectionStatus(false);
    }
  }

  async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    sendBtn.disabled = true;
    messageInput.value = "";

    try {
      const res = await fetch(`${API_BASE}/api/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: currentUser,
          message: text,
        }),
      });

      const data = await res.json();

      if (data.success) {
        await fetchMessages();
      } else {
        console.error("Error al enviar mensaje:", data.error || data.detail);
        alert("No se pudo enviar el mensaje. Inténtalo de nuevo.");
        messageInput.value = text;
      }
    } catch (err) {
      console.error("Error de conexión al enviar:", err);
      alert("Error de conexión. Verifica tu red.");
      messageInput.value = text;
    } finally {
      sendBtn.disabled = false;
      messageInput.focus();
    }
  }

  // ── Polling ───────────────────────────────────────────────────────────

  function startPolling() {
    fetchMessages();
    pollingTimer = setInterval(fetchMessages, POLL_INTERVAL);
  }

  function stopPolling() {
    if (pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }
  }

  // ── Logout ────────────────────────────────────────────────────────────

  function logout() {
    stopPolling();
    currentUser = "";
    messagesList.innerHTML = "";
    loginUsername.value = "";
    loginPassword.value = "";
    clearAuthErrors();

    chatScreen.classList.remove("active");
    authScreen.classList.add("active");

    loginUsername.focus();
  }

  // ── Event listeners — Chat ────────────────────────────────────────────

  sendBtn.addEventListener("click", sendMessage);
  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  logoutBtn.addEventListener("click", logout);

  // ── Inicialización ────────────────────────────────────────────────────
  loginUsername.focus();
})();
