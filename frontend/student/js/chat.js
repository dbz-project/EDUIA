/**
 * frontend/student/js/chat.js
 * Lógica del chat socrático — mensajes, streaming, evaluaciones
 */

const Chat = {
  conversationId: null,
  subject: 'Programación',
  hintsUsed: 0,
  isWaiting: false,

  // ── Inicialización ───────────────────────────
  async init() {
    this.subject = document.getElementById('subjectSelect').value;
    try {
      const conv = await API.startConversation(this.subject);
      this.conversationId = conv.conversation_id;
    } catch (e) {
      console.error('Error iniciando conversación:', e);
    }
    this.renderWelcome();
    this.bindInput();
  },

  renderWelcome() {
    const name = document.getElementById('sidebarName').textContent;
    this.addMessage('assistant',
      `¡Hola ${name}! Soy EduIA, tu tutor. Estoy aquí para ayudarte a <em>entender</em>, ` +
      `no para darte las respuestas directamente. ¿Con qué estás trabajando hoy en ${this.subject}?`
    );
  },

  bindInput() {
    const input = document.getElementById('chatInput');

    // Auto-resize del textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // Enter envía, Shift+Enter hace salto de línea
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  },

  // ── Enviar mensaje ───────────────────────────
  async send(text) {
    if (this.isWaiting || !text.trim()) return;
    this.isWaiting = true;

    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;

    // Mostrar mensaje del alumno
    this.addMessage('user', this.escapeHtml(text));

    // Mostrar indicador de escritura
    const typingId = this.addTypingIndicator();

    try {
      // Intentar streaming primero
      await this._sendWithStream(text, typingId);
    } catch (streamErr) {
      // Fallback sin streaming
      try {
        const data = await API.sendMessage(text, this.conversationId, this.subject);
        this.removeTypingIndicator(typingId);
        this.addMessage('assistant', data.response, data.hints_used);
        this.updateHints(data.hints_used);
      } catch (err) {
        this.removeTypingIndicator(typingId);
        this.addMessage('assistant', 'Ha ocurrido un error. Comprueba que el backend está funcionando.');
      }
    }

    this.isWaiting = false;
    sendBtn.disabled = false;
    document.getElementById('chatInput').focus();
  },

  async _sendWithStream(text, typingId) {
    let fullResponse = '';
    let hintLevel = 0;
    let bubbleEl = null;

    await API.sendMessageStream(
      text,
      this.conversationId,
      this.subject,
      // onToken — cada token que llega del stream
      (token) => {
        if (!bubbleEl) {
          this.removeTypingIndicator(typingId);
          const msgEl = this.createMessageElement('assistant');
          bubbleEl = msgEl.querySelector('.msg-bubble');
          document.getElementById('chatMessages').appendChild(msgEl);
        }
        fullResponse += token;
        bubbleEl.innerHTML = this.formatResponse(fullResponse);
        this.scrollToBottom();
      },
      // onDone
      () => {
        this.updateHints(this.hintsUsed + 1);
      }
    );
  },

  // ── Renderizado de mensajes ──────────────────
  addMessage(role, content, hints = null) {
    const container = document.getElementById('chatMessages');
    const el = this.createMessageElement(role, content, hints);
    container.appendChild(el);
    this.scrollToBottom();
    return el;
  },

  createMessageElement(role, content = '', hints = null) {
    const msg = document.createElement('div');
    msg.className = `msg ${role}`;

    const avatarHtml = role === 'user'
      ? `<div class="msg-avatar">${this.getInitials()}</div>`
      : `<div class="msg-avatar">
           <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
             <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
           </svg>
         </div>`;

    const hintTag = (role === 'assistant' && hints !== null)
      ? `<div class="hint-tag">Pista ${hints}</div>`
      : '';

    const bubbleContent = content ? this.formatResponse(content) : '';

    if (role === 'user') {
      msg.innerHTML = `${avatarHtml}<div class="msg-bubble">${bubbleContent}</div>`;
    } else {
      msg.innerHTML = `
        ${avatarHtml}
        <div class="msg-body">
          ${hintTag}
          <div class="msg-bubble">${bubbleContent}</div>
        </div>`;
    }

    return msg;
  },

  addTypingIndicator() {
    const id = 'typing-' + Date.now();
    const container = document.getElementById('chatMessages');
    const el = document.createElement('div');
    el.className = 'msg assistant typing-indicator';
    el.id = id;
    el.innerHTML = `
      <div class="msg-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>
      <div class="msg-body">
        <div class="msg-bubble">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>`;
    container.appendChild(el);
    this.scrollToBottom();
    return id;
  },

  removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  },

  // Formatea la respuesta: convierte saltos de línea, código inline, etc.
  formatResponse(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/`([^`]+)`/g, '<code style="font-family:var(--font-mono);font-size:12px;background:rgba(0,0,0,0.06);padding:1px 4px;border-radius:3px;">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  },

  escapeHtml(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  },

  // ── Evaluación antes de crear archivo ────────
  async startEvaluation(fileType, topic) {
    this.addMessage('assistant',
      `Quieres crear un archivo <strong>.${fileType}</strong> sobre "${topic}". ` +
      `Antes de generarlo, voy a hacerte 3 preguntas para asegurarme de que lo entiendes. ` +
      `¡Respóndelas lo mejor que puedas!`
    );

    try {
      const data = await API.getEvaluationQuestions(fileType, topic, '');
      this.renderEvaluationCard(data.questions, fileType, topic);
    } catch (e) {
      this.addMessage('assistant', 'No he podido generar las preguntas. Inténtalo de nuevo.');
    }
  },

  renderEvaluationCard(questions, fileType, topic) {
    const container = document.getElementById('chatMessages');
    const el = document.createElement('div');
    el.className = 'msg assistant';
    el.innerHTML = `
      <div class="msg-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>
      <div class="msg-body">
        <div class="msg-bubble">
          <div class="eval-card">
            <div class="eval-card-header">Evaluación previa · .${fileType} — ${topic}</div>
            <div class="eval-question"><div class="eval-num">1</div><span>${this.escapeHtml(questions.q1 || '')}</span></div>
            <div class="eval-question"><div class="eval-num">2</div><span>${this.escapeHtml(questions.q2 || '')}</span></div>
            <div class="eval-question"><div class="eval-num">3</div><span>${this.escapeHtml(questions.q3 || '')}</span></div>
          </div>
          <div style="margin-top:10px;font-size:12px;color:var(--text-2);">
            Responde las 3 preguntas en el chat y cuando termines escribe <strong>"listo"</strong>.
          </div>
        </div>
      </div>`;
    container.appendChild(el);
    this.scrollToBottom();

    // Guardar estado de evaluación pendiente
    this.pendingEval = { fileType, topic, questions, answers: [] };
  },

  // ── Utilidades ───────────────────────────────
  scrollToBottom() {
    const container = document.getElementById('chatMessages');
    container.scrollTop = container.scrollHeight;
  },

  updateHints(count) {
    this.hintsUsed = count;
    document.getElementById('hintCount').textContent = count;
    const msg = document.getElementById('hintMsg');
    if (count === 0) msg.textContent = '¡Empecemos a aprender!';
    else if (count < 3) msg.textContent = '¡Sigue intentándolo!';
    else if (count < 6) msg.textContent = 'Vas bien, no te rindas.';
    else msg.textContent = 'Muchas pistas hoy. ¡Mañana más!';
  },

  getInitials() {
    const name = document.getElementById('sidebarName').textContent;
    return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  },

  clear() {
    document.getElementById('chatMessages').innerHTML = '';
    this.conversationId = null;
    this.hintsUsed = 0;
    this.isWaiting = false;
    this.pendingEval = null;
  },
};

// Función global que llama el botón de enviar y el HTML
function sendMessage() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  input.style.height = 'auto';
  Chat.send(text);
}
