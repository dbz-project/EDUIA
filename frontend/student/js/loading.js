/**
 * frontend/student/js/loading.js
 * Pantalla de carga con mensajes rotativos — idea de ChatGPT
 * Evita que parezca que la app se ha colgado durante los 15-30s de carga del modelo
 */

const Loading = {
  interval: null,
  msgIndex: 0,

  // Mensajes rotativos cada 3s — generados por ChatGPT
  messages: [
    "Preparando tu tutor...",
    "Cargando tu espacio de aprendizaje...",
    "Iniciando la inteligencia artificial...",
    "Ya casi está listo...",
    "Organizando todo para ti...",
    "Un momento más...",
  ],

  show(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.style.display = "flex";
    this.msgIndex = 0;
    this._updateMsg();
    this.interval = setInterval(() => this._updateMsg(), 3000);
  },

  hide(containerId) {
    clearInterval(this.interval);
    const el = document.getElementById(containerId);
    if (el) el.style.display = "none";
  },

  _updateMsg() {
    const el = document.getElementById("loadingMsg");
    if (!el) return;
    el.style.opacity = "0";
    setTimeout(() => {
      el.textContent = this.messages[this.msgIndex % this.messages.length];
      el.style.opacity = "1";
      this.msgIndex++;
    }, 300);
  },
};

// Mensajes mientras la IA "piensa" — de ChatGPT
const ThinkingMessages = [
  "Pensando...",
  "Analizando tu pregunta...",
  "Buscando una buena pista...",
  "Preparando una explicación...",
  "Organizando ideas...",
  "Revisando lo que has escrito...",
  "Intentando ayudarte paso a paso...",
];

function getThinkingMessage() {
  return ThinkingMessages[Math.floor(Math.random() * ThinkingMessages.length)];
}
