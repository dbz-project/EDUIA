/**
 * frontend/student/js/app.js
 * Fix: mostrar login cuando backend_alive=true, aunque fallback esté activo
 * Recomendación ChatGPT: "Backend responde → abrir login. No importa el motor."
 */

const AppState = { student: null, isReturning: false };

document.addEventListener('DOMContentLoaded', async () => {
  Loading.show('loadingScreen');
  setupPinInputs();
  await bootSequence();
});

// ── Arranque ──────────────────────────────────────
async function bootSequence() {
  // Reintentar durante 60s con backoff — da tiempo a Qwen y al fallback
  const delays = [2000, 3000, 5000, 5000, 10000, 10000, 15000, 10000];
  
  for (let i = 0; i < delays.length; i++) {
    await sleep(delays[i]);
    
    try {
      const health = await API.health();
      
      // ChatGPT: si el backend responde, abrir login.
      // No importa si es Qwen o fallback — ambos pueden atender conversaciones.
      if (health.ready === true) {
        Loading.hide('loadingScreen');
        showLoginScreen();
        return;
      }
    } catch (e) {
      // Backend aún arrancando — continuar esperando
      console.log(`Health check ${i+1}/${delays.length} fallido, reintentando...`);
    }
  }

  // Solo si el backend no responde en absoluto → mostrar error
  Loading.hide('loadingScreen');
  document.getElementById('errorScreen').style.display = 'flex';
}

async function retryConnection() {
  document.getElementById('errorScreen').style.display = 'none';
  Loading.show('loadingScreen');
  await bootSequence();
}

function showLoginScreen() {
  const savedName = localStorage.getItem('eduia_last_name');
  if (savedName) {
    AppState.isReturning = true;
    document.getElementById('loginTitle').textContent = '¡Qué bien verte de nuevo!';
    document.getElementById('loginSub').textContent   = 'Continúa aprendiendo donde lo dejaste.';
    document.getElementById('loginBtn').textContent   = 'Entrar';
    document.getElementById('loginName').value        = savedName;
    document.getElementById('courseField').style.display = 'none';
  } else {
    document.getElementById('loginBtn').textContent = 'Comenzar';
  }
  document.getElementById('loginScreen').style.display = 'flex';
}

// ── PIN ───────────────────────────────────────────
function setupPinInputs() {
  const pins = document.querySelectorAll('.pin-digit');
  pins.forEach((input, i) => {
    input.addEventListener('input', () => {
      input.value = input.value.replace(/\D/g,'');
      if (input.value && i < pins.length - 1) pins[i+1].focus();
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !input.value && i > 0) pins[i-1].focus();
      if (e.key === 'Enter') doLogin();
    });
    input.addEventListener('paste', e => {
      const pasted = e.clipboardData.getData('text').replace(/\D/g,'').slice(0,4);
      pasted.split('').forEach((d,j) => { if (pins[j]) pins[j].value = d; });
      if (pins[pasted.length-1]) pins[pasted.length-1].focus();
      e.preventDefault();
    });
  });
}

function getPin() {
  return [...document.querySelectorAll('.pin-digit')].map(i => i.value).join('');
}

// ── Login ─────────────────────────────────────────
async function doLogin() {
  const name   = document.getElementById('loginName').value.trim();
  const course = document.getElementById('loginCourse')?.value || '';
  const pin    = getPin();

  if (!name)          { showLoginError('Escribe tu nombre.'); return; }
  if (pin.length < 4) { showLoginError('Introduce los 4 dígitos de tu PIN.'); return; }
  if (!AppState.isReturning && !course) {
    showLoginError('Selecciona tu curso.'); return;
  }

  const btn = document.getElementById('loginBtn');
  btn.textContent = 'Entrando...';
  btn.disabled    = true;
  document.getElementById('loginError').style.display = 'none';

  try {
    let data;
    try {
      data = await API.login(name, pin, course);
    } catch (e) {
      if (e.message.includes('incorrectas')) throw e;
      const age = estimateAge(course);
      await API.register(name, pin, course, age);
      data = await API.login(name, pin, course);
    }

    localStorage.setItem('eduia_last_name', name);
    AppState.student = { name, course };

    document.getElementById('sidebarName').textContent   = name;
    document.getElementById('sidebarCourse').textContent =
      `${course} · ${document.getElementById('subjectSelect').value}`;

    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appShell').style.display    = 'flex';

    const welcomes = [
      `¡Hola, ${name}! ¿Sobre qué te gustaría aprender hoy?`,
      `Bienvenido de nuevo, ${name}. Estoy listo para ayudarte paso a paso.`,
      `Hola, ${name}. Cuéntame qué estás estudiando y empezamos.`,
    ];
    const welcome = AppState.isReturning ? welcomes[1] : welcomes[0];

    await Chat.init(welcome);
    buildFileTypeGrid();

  } catch (err) {
    showLoginError(err.message || 'Error al entrar. Inténtalo de nuevo.');
  } finally {
    btn.textContent = AppState.isReturning ? 'Entrar' : 'Comenzar';
    btn.disabled    = false;
  }
}

function showLoginError(msg) {
  const el = document.getElementById('loginError');
  el.textContent   = msg;
  el.style.display = 'block';
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

// ── Navegación ────────────────────────────────────
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

// ── Grid de tipos de archivo ──────────────────────
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
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.8" width="26" height="26">
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
