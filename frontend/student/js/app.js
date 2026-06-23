/**
 * frontend/student/js/app.js
 * Pantalla de selección: login existente vs registro nuevo
 * Diseñado para 50-100 alumnos en el mismo PC
 */

const AppState = { student: null };

document.addEventListener('DOMContentLoaded', async () => {
  Loading.show('loadingScreen');
  setupPinInputs('loginPinRow');
  setupPinInputs('registerPinRow');
  await bootSequence();
});

// ── Boot ──────────────────────────────────────
async function bootSequence() {
  const delays = [2000, 3000, 5000, 5000, 10000, 10000, 15000, 10000];
  for (let i = 0; i < delays.length; i++) {
    await sleep(delays[i]);
    try {
      const h = await API.health();
      if (h.ready === true) {
        Loading.hide('loadingScreen');
        showScreen('screenSelector');
        return;
      }
    } catch (e) {}
  }
  Loading.hide('loadingScreen');
  document.getElementById('errorScreen').style.display = 'flex';
}

async function retryConnection() {
  document.getElementById('errorScreen').style.display = 'none';
  Loading.show('loadingScreen');
  await bootSequence();
}

// ── Navegación entre pantallas ─────────────────
function showScreen(id) {
  ['screenSelector','screenLogin','screenRegister'].forEach(s => {
    const el = document.getElementById(s);
    if (el) el.style.display = s === id ? 'flex' : 'none';
  });
  // Limpiar errores al cambiar pantalla
  document.querySelectorAll('.login-error').forEach(e => e.style.display = 'none');
}

// ── PIN inputs ────────────────────────────────
function setupPinInputs(rowId) {
  const pins = document.querySelectorAll(`#${rowId} .pin-digit`);
  pins.forEach((input, i) => {
    input.addEventListener('input', () => {
      input.value = input.value.replace(/\D/g,'');
      if (input.value && i < pins.length - 1) pins[i+1].focus();
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !input.value && i > 0) pins[i-1].focus();
      if (e.key === 'Enter') {
        if (rowId === 'loginPinRow') doLogin();
        else doRegister();
      }
    });
    input.addEventListener('paste', e => {
      const pasted = e.clipboardData.getData('text').replace(/\D/g,'').slice(0,4);
      pasted.split('').forEach((d,j) => { if (pins[j]) pins[j].value = d; });
      e.preventDefault();
    });
  });
}

function getPin(rowId) {
  return [...document.querySelectorAll(`#${rowId} .pin-digit`)]
    .map(i => i.value).join('');
}

function clearPin(rowId) {
  document.querySelectorAll(`#${rowId} .pin-digit`).forEach(p => p.value = '');
}

// ── Login alumno existente ─────────────────────
async function doLogin() {
  const name = document.getElementById('loginName').value.trim();
  const pin  = getPin('loginPinRow');

  if (!name)          { showError('loginError', 'Escribe tu nombre.'); return; }
  if (pin.length < 4) { showError('loginError', 'Introduce los 4 dígitos de tu PIN.'); return; }

  const btn = document.getElementById('loginBtn');
  btn.textContent = 'Entrando...';
  btn.disabled = true;

  try {
    const data = await API.login(name, pin, '');
    await enterApp(name, data);
  } catch (err) {
    showError('loginError', 'Nombre o PIN incorrecto. ¿Es tu primera vez? Usa "Soy nuevo".');
  } finally {
    btn.textContent = 'Entrar';
    btn.disabled = false;
  }
}

// ── Registro alumno nuevo ─────────────────────
async function doRegister() {
  const name   = document.getElementById('registerName').value.trim();
  const course = document.getElementById('registerCourse').value;
  const pin    = getPin('registerPinRow');
  const pin2   = getPin('registerPinRow2');

  if (!name)          { showError('registerError', 'Escribe tu nombre completo.'); return; }
  if (!course)        { showError('registerError', 'Selecciona tu curso.'); return; }
  if (pin.length < 4) { showError('registerError', 'Elige un PIN de 4 dígitos.'); return; }
  if (pin !== pin2)   { showError('registerError', 'Los dos PINs no coinciden. Inténtalo de nuevo.'); return; }

  const btn = document.getElementById('registerBtn');
  btn.textContent = 'Creando perfil...';
  btn.disabled = true;

  try {
    const age = estimateAge(course);
    await API.register(name, pin, course, age);
    const data = await API.login(name, pin, course);
    await enterApp(name, data, course);
  } catch (err) {
    if (err.message && err.message.includes('ya existe')) {
      showError('registerError', 'Ya existe un alumno con ese nombre. Prueba a añadir tu apellido.');
    } else {
      showError('registerError', 'No se pudo crear el perfil. Inténtalo de nuevo.');
    }
  } finally {
    btn.textContent = 'Crear mi perfil';
    btn.disabled = false;
  }
}

// ── Entrar a la app ───────────────────────────
async function enterApp(name, data, course) {
  AppState.student = { name, course };

  document.getElementById('sidebarName').textContent   = name;
  document.getElementById('sidebarCourse').textContent =
    `${course || ''} · ${document.getElementById('subjectSelect').value}`;

  // Ocultar todas las pantallas de auth
  ['screenSelector','screenLogin','screenRegister'].forEach(s => {
    const el = document.getElementById(s);
    if (el) el.style.display = 'none';
  });
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('appShell').style.display    = 'flex';

  const isNew = !course; // Si no tiene curso guardado, es acceso recurrente
  const welcome = isNew
    ? `¡Hola, ${name}! ¿Sobre qué te gustaría aprender hoy?`
    : `¡Bienvenido, ${name}! Estoy listo para ayudarte. ¿Por dónde empezamos?`;

  await Chat.init(welcome);
  buildFileTypeGrid();
}

// ── Utilidades ────────────────────────────────
function showError(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}

function estimateAge(course) {
  const map = {
    '1.º ESO':12,'2.º ESO':13,'3.º ESO':14,'4.º ESO':15,
    '1.º Bachillerato':16,'2.º Bachillerato':17,
    '1.º DAM':18,'2.º DAM':19,'1.º DAW':18,'2.º DAW':19,
    '1.º SMR':18,'2.º SMR':19,
  };
  return map[course] || 16;
}

function showPanel(name, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('panel-' + name);
  if (panel) panel.classList.add('active');
  if (btn)   btn.classList.add('active');
  if (name === 'portfolio') Portfolio.load();
}

async function changeSubject() {
  const subject = document.getElementById('subjectSelect').value;
  Chat.subject = subject;
  Chat.clear();
  document.getElementById('sidebarCourse').textContent =
    `${AppState.student?.course || ''} · ${subject}`;
  try {
    const conv = await API.startConversation(subject);
    Chat.conversationId = conv.conversation_id;
  } catch (e) {}
  Chat.addMessage('assistant',
    `Cambiando a <strong>${subject}</strong>. ¿Con qué necesitas ayuda?`
  );
}

function buildFileTypeGrid() {
  const types = [
    { ext:'py',   name:'Python',     color:'#3B6D11' },
    { ext:'html', name:'HTML',       color:'#993C1D' },
    { ext:'css',  name:'CSS',        color:'#185FA5' },
    { ext:'js',   name:'JavaScript', color:'#854F0B' },
    { ext:'md',   name:'Markdown',   color:'#534AB7' },
    { ext:'json', name:'JSON',       color:'#0F6E56' },
  ];
  const grid = document.getElementById('fileTypeGrid');
  if (!grid) return;
  grid.innerHTML = types.map(t => `
    <button class="file-type-btn" onclick="startFileCreation('${t.ext}')">
      <span style="font-size:26px;color:${t.color};display:block;margin-bottom:6px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="26" height="26">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
      </span>
      <div class="ext-label">.${t.ext}</div>
      <div class="ext-desc">${t.name}</div>
    </button>`).join('');
}

function startFileCreation(fileType) {
  showPanel('chat', document.querySelector('[data-panel=chat]'));
  Chat.pendingFileType = fileType;
  Chat.addMessage('assistant',
    `Vamos a crear un archivo <strong>.${fileType}</strong>. ` +
    `Antes de generarlo, te haré unas preguntas para comprobar que entiendes el tema. ` +
    `¿Sobre qué quieres que sea el archivo?`
  );
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
