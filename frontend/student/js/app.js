/**
 * frontend/student/js/app.js
 * Punto de entrada — login, navegación, estado global
 * Se carga el último para tener acceso a api.js, chat.js, portfolio.js
 */

// ── Estado global ──────────────────────────────
const AppState = {
  student: null,     // { id, name, course, age }
  currentPanel: 'chat',
};

// ── Arranque ───────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  setupPinInputs();
  setupRoleTabs();
  await checkBackend();
});

async function checkBackend() {
  try {
    const health = await API.health();
    if (!health.model_loaded) {
      showLoginError('El modelo de IA está cargando, espera unos segundos e inténtalo de nuevo.');
    }
  } catch (e) {
    showLoginError('No se puede conectar con EduIA. Asegúrate de que el programa está abierto.');
  }
}

// ── Login ──────────────────────────────────────
function setupRoleTabs() {
  document.querySelectorAll('.role-tab').forEach((tab, i) => {
    tab.addEventListener('click', () => switchRole(i === 0 ? 'student' : 'teacher'));
  });
}

function switchRole(role) {
  document.querySelectorAll('.role-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(role === 'student' ? 'tabStudent' : 'tabTeacher').classList.add('active');
  // El campo curso solo aplica a alumnos
  document.getElementById('courseField').style.display = role === 'student' ? 'block' : 'none';
  document.getElementById('loginError').style.display = 'none';
}

function setupPinInputs() {
  const pins = document.querySelectorAll('.pin-digit');
  pins.forEach((input, i) => {
    input.addEventListener('input', () => {
      // Solo números
      input.value = input.value.replace(/\D/g, '');
      if (input.value && i < pins.length - 1) pins[i + 1].focus();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !input.value && i > 0) pins[i - 1].focus();
      if (e.key === 'Enter') doLogin();
    });
    // Pegar el PIN completo en el primer campo
    input.addEventListener('paste', (e) => {
      const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 4);
      pasted.split('').forEach((digit, j) => {
        if (pins[j]) pins[j].value = digit;
      });
      if (pins[pasted.length - 1]) pins[pasted.length - 1].focus();
      e.preventDefault();
    });
  });
}

function getPin() {
  return [...document.querySelectorAll('.pin-digit')].map(i => i.value).join('');
}

function showLoginError(msg) {
  const el = document.getElementById('loginError');
  el.textContent = msg;
  el.style.display = 'block';
}

async function doLogin() {
  const name   = document.getElementById('loginName').value.trim();
  const course = document.getElementById('loginCourse').value;
  const pin    = getPin();

  if (!name) { showLoginError('Escribe tu nombre.'); return; }
  if (pin.length < 4) { showLoginError('Introduce los 4 dígitos de tu PIN.'); return; }

  const btn = document.getElementById('loginBtn');
  btn.textContent = 'Entrando...';
  btn.disabled = true;
  document.getElementById('loginError').style.display = 'none';

  try {
    // Intentar login; si no existe, registrar automáticamente
    let data;
    try {
      data = await API.login(name, pin, course);
    } catch (loginErr) {
      if (loginErr.message.includes('Credenciales incorrectas')) {
        throw loginErr;
      }
      // Perfil no existe — crear nuevo alumno
      const age = estimateAge(course);
      await API.register(name, pin, course, age);
      data = await API.login(name, pin, course);
    }

    AppState.student = { name, course };

    // Actualizar sidebar
    document.getElementById('sidebarName').textContent = name;
    document.getElementById('sidebarCourse').textContent = `${course} · ${document.getElementById('subjectSelect')?.value || 'Programación'}`;

    // Ocultar login, mostrar app
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appShell').style.display   = 'flex';

    // Arrancar el chat
    await Chat.init();

  } catch (err) {
    showLoginError(err.message || 'Error al entrar. Inténtalo de nuevo.');
  } finally {
    btn.textContent = 'Entrar';
    btn.disabled = false;
  }
}

function estimateAge(course) {
  const ages = {
    '1.º ESO': 12, '2.º ESO': 13, '3.º ESO': 14, '4.º ESO': 15,
    '1.º Bachillerato': 16, '2.º Bachillerato': 17,
    '1.º DAM': 18, '2.º DAM': 19, '1.º DAW': 18, '2.º DAW': 19,
    '1.º SMR': 18, '2.º SMR': 19,
  };
  return ages[course] || 16;
}

// ── Navegación ─────────────────────────────────
function showPanel(name, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));

  const panel = document.getElementById('panel-' + name);
  if (panel) panel.classList.add('active');
  if (btn) btn.classList.add('active');

  AppState.currentPanel = name;

  // Cargar datos según el panel
  if (name === 'portfolio') Portfolio.load();
  if (name === 'history') loadHistory();
}

async function loadHistory() {
  // Por ahora muestra las conversaciones del estado local
  // En la próxima iteración se conecta al endpoint /conversations
  const list = document.getElementById('historyList');

  // Placeholder hasta tener el endpoint de historial
  list.innerHTML = `
    <div style="padding:20px;font-size:13px;color:var(--text-3);">
      El historial se activará en la próxima versión.<br>
      Por ahora, tus conversaciones se guardan en la base de datos local.
    </div>`;
}

// ── Cambio de asignatura ───────────────────────
async function changeSubject() {
  const subject = document.getElementById('subjectSelect').value;
  Chat.subject = subject;
  Chat.clear();
  document.getElementById('sidebarCourse').textContent =
    `${AppState.student?.course || ''} · ${subject}`;

  try {
    const conv = await API.startConversation(subject);
    Chat.conversationId = conv.conversation_id;
  } catch (e) { /* seguimos sin conv_id */ }

  Chat.renderWelcome();
}

// ── Crear archivo ──────────────────────────────
function startFileCreation(fileType) {
  // Cambiar al chat y pedir el tema
  showPanel('chat', document.querySelector('[data-panel=chat]'));

  // Pedir el tema del archivo al alumno mediante el chat
  Chat.addMessage('assistant',
    `Vamos a crear un archivo <strong>.${fileType}</strong>. ` +
    `¿Sobre qué tema quieres que sea? Descríbelo brevemente en el chat.`
  );

  // Guardar el tipo de archivo pendiente
  Chat.pendingFileType = fileType;
}
