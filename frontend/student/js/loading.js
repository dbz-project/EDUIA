const Loading = {
  interval: null,
  msgIndex: 0,
  messages: [
    "Preparando tu tutor...",
    "Cargando la inteligencia artificial...",
    "Ya casi está listo...",
    "Organizando todo para ti...",
    "Un momento más...",
    "Iniciando EduIA...",
  ],
  show(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.style.display = 'flex';
    this.msgIndex = 0;
    this._update();
    this.interval = setInterval(() => this._update(), 3000);
  },
  hide(containerId) {
    clearInterval(this.interval);
    const el = document.getElementById(containerId);
    if (el) el.style.display = 'none';
  },
  _update() {
    const el = document.getElementById('loadingMsg');
    if (!el) return;
    el.textContent = this.messages[this.msgIndex % this.messages.length];
    this.msgIndex++;
  },
};

function getThinkingMessage() {
  const msgs = ["Pensando...","Analizando tu pregunta...","Buscando una buena pista...","Preparando una explicación..."];
  return msgs[Math.floor(Math.random() * msgs.length)];
}
