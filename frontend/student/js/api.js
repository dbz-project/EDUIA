/**
 * frontend/student/js/api.js
 * Cliente HTTP para el backend local en localhost:8765
 * Toda comunicación es a 127.0.0.1 — nunca sale a internet
 */

const API = {
  BASE: 'http://127.0.0.1:8765',
  token: null,

  // ── Headers ─────────────────────────────────
  _headers() {
    const h = { 'Content-Type': 'application/json' };
    if (this.token) h['Authorization'] = `Bearer ${this.token}`;
    return h;
  },

  // ── Petición base ────────────────────────────
  async _req(method, path, body = null) {
    const opts = { method, headers: this._headers() };
    if (body) opts.body = JSON.stringify(body);
    try {
      const res = await fetch(`${this.BASE}${path}`, opts);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
      return data;
    } catch (err) {
      if (err.message.includes('fetch')) {
        throw new Error('No se puede conectar con EduIA. ¿Está el backend arrancado?');
      }
      throw err;
    }
  },

  // ── Health check ─────────────────────────────
  async health() {
    return this._req('GET', '/health');
  },

  // ── Auth ─────────────────────────────────────
  async login(name, pin, course) {
    const data = await this._req('POST', '/auth/login', {
      name,
      credential: pin,
      role: 'student',
      course,
    });
    this.token = data.token;
    return data;
  },

  async register(name, pin, course, age) {
    return this._req('POST', '/auth/register/student', { name, pin, course, age });
  },

  async logout() {
    await this._req('POST', '/auth/logout');
    this.token = null;
  },

  // ── Chat ─────────────────────────────────────
  async startConversation(subject) {
    return this._req('POST', '/chat/start', { message: '', subject });
  },

  async sendMessage(message, conversationId, subject) {
    return this._req('POST', '/chat/message', {
      message,
      conversation_id: conversationId,
      subject,
    });
  },

  // Streaming — devuelve un ReadableStream
  async sendMessageStream(message, conversationId, subject, onToken, onDone) {
    const res = await fetch(`${this.BASE}/chat/message/stream`, {
      method: 'POST',
      headers: this._headers(),
      body: JSON.stringify({ message, conversation_id: conversationId, subject }),
    });

    if (!res.ok) throw new Error('Error en el streaming');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const token = line.slice(6);
          if (token === '[DONE]') { onDone?.(); return; }
          onToken(token);
        }
      }
    }
    onDone?.();
  },

  // ── Archivos ──────────────────────────────────
  async getEvaluationQuestions(fileType, topic, instructions) {
    return this._req('POST', '/files/evaluate', { file_type: fileType, topic, instructions });
  },

  async generateFile(fileType, topic, instructions, answers) {
    return this._req('POST', '/files/generate', {
      file_type: fileType,
      topic,
      instructions,
      evaluation_answers: answers,
    });
  },

  async getFileTypes() {
    return this._req('GET', '/files/types');
  },

  // ── Portfolio ─────────────────────────────────
  async getPortfolio() {
    return this._req('GET', '/portfolio');
  },

  async getFileContent(itemId) {
    return this._req('GET', `/portfolio/${itemId}/content`);
  },
};
