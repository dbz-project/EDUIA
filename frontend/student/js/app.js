/**
 * app.js v7 — Fix botones inaccesibles por overlay de carga
 */

const AppState = { student: null };

document.addEventListener('DOMContentLoaded', () => {
  setupPinInputs('loginPinRow');
  setupPinInputs('registerPinRow');
  setupPinInputs('registerPinRow2');

  // Mostrar carga
  const ls = document.getElementById('loadingScreen');
  if (ls) { ls.style.display = 'flex'; ls.style.zIndex = '999'; }

  startHealthChecks();
});

async function startHealthChecks() {
  await sleep(1000);
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch('http://127.0.0.1:8765/health');
      if (res.ok) {
        const data = await res.json();
        if (data.ready === true) { showAuth(); return; }
      }
    } catch (e) {}
    await sleep(2000);
  }
  showError('errorScreen');
}

function showAuth() {
  // Ocultar loading completamente — incluyendo pointer-events
  const ls = document.getElementById('loadingScreen');
  if (ls) {
    ls.style.display = 'none';
    ls.style.pointerEvents = 'none';
    ls.style.zIndex = '-1';
  }
  const login = document.getElementById('loginScreen');
  if (login) {
    login.style.display = 'block';
    login.style.zIndex = '100';
    login.style.pointerEvents = 'all';
  }
  showScreen('screenSelector');
}

function showError(id) {
  const ls = document.getElementById('loadingScreen');
  if (ls) { ls.style.display = 'none'; ls.style.pointerEvents = 'none'; }
  const el = document.getElementById(id);
  if (el) { el.style.display = 'flex'; el.style.zIndex = '200'; }
}

async function retryConnection() {
  const es = document.getElementById('errorScreen');
  if (es) es.style.display = 'none';
  const ls = document.getElementById('loadingScreen');
  if (ls) { ls.style.display = 'flex'; ls.style.zIndex = '999'; ls.style.pointerEvents = 'all'; }
  await startHealthChecks();
}

function showScreen(id) {
  ['screenSelector','screenLogin','screenRegister'].forEach(s => {
    const el = document.getElementById(s);
    if (!el) return;
    if (s === id) {
      el.style.display = 'flex';
      el.style.pointerEvents = 'all';
      el.style.zIndex = '10';
    } else {
      el.style.display = 'none';
      el.style.pointerEvents = 'none';
    }
  });
  document.querySelectorAll('.login-error').forEach(e => e.style.display = 'none');
}

function setupPinInputs(rowId) {
  const container = document.getElementById(rowId);
  if (!container) return;
  const pins = container.querySelectorAll('.pin-digit');
  pins.forEach((input, i) => {
    input.addEventListener('input', () => {
      input.value = input.value.replace(/\D/g,'');
      if (input.value && i < pins.length - 1) pins[i+1].focus();
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !input.value && i > 0) pins[i-1].focus();
      if (e.key === 'Enter') { if (rowId === 'loginPinRow') doLogin(); else doRegister(); }
    });
    input.addEventListener('paste', e => {
      const pasted = e.clipboardData.getData('text').replace(/\D/g,'').slice(0,4);
      pasted.split('').forEach((d,j) => { if (pins[j]) pins[j].value = d; });
      e.preventDefault();
    });
  });
}

function getPin(rowId) {
  const c = document.getElementById(rowId);
  if (!c) return '';
  return [...c.querySelectorAll('.pin-digit')].map(i => i.value).join('');
}

async function doLogin() {
  const name = document.getElementById('loginName').value.trim();
  const pin  = getPin('loginPinRow');
  if (!name)          { showErr('loginError', 'Escribe tu nombre.'); return; }
  if (pin.length < 4) { showErr('loginError', 'Introduce los 4 dígitos de tu PIN.'); return; }

  const btn = document.getElementById('loginBtn');
  btn.textContent = 'Entrando...'; btn.disabled = true;
  try {
    const res = await fetch('http://127.0.0.1:8765/auth/login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name, credential: pin, role:'student', course:''}),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    API.token = data.token;
    await enterApp(name, '');
  } catch {
    showErr('loginError','Nombre o PIN incorrecto. ¿Primera vez? Usa "Soy nuevo".');
  } finally { btn.textContent = 'Entrar'; btn.disabled = false; }
}

async function doRegister() {
  const name   = document.getElementById('registerName').value.trim();
  const course = document.getElementById('registerCourse').value;
  const pin    = getPin('registerPinRow');
  const pin2   = getPin('registerPinRow2');

  if (!name)          { showErr('registerError','Escribe tu nombre completo.'); return; }
  if (!course)        { showErr('registerError','Selecciona tu curso.'); return; }
  if (pin.length < 4) { showErr('registerError','Elige un PIN de 4 dígitos.'); return; }
  if (pin !== pin2)   { showErr('registerError','Los dos PINs no coinciden.'); return; }

  const btn = document.getElementById('registerBtn');
  btn.textContent = 'Creando perfil...'; btn.disabled = true;
  try {
    const r1 = await fetch('http://127.0.0.1:8765/auth/register/student', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, pin, course, age: estimateAge(course)}),
    });
    if (!r1.ok) { const e = await r1.json(); throw new Error(e.detail||'error'); }

    const r2 = await fetch('http://127.0.0.1:8765/auth/login', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, credential:pin, role:'student', course}),
    });
    if (!r2.ok) throw new Error('login fallido');
    const data = await r2.json();
    API.token = data.token;
    await enterApp(name, course);
  } catch (err) {
    const msg = err.message?.includes('ya existe')
      ? 'Ya existe un alumno con ese nombre. Añade tu apellido.'
      : 'No se pudo crear el perfil. Inténtalo de nuevo.';
    showErr('registerError', msg);
  } finally { btn.textContent = 'Crear mi perfil'; btn.disabled = false; }
}

async function enterApp(name, course) {
  AppState.student = { name, course };
  document.getElementById('sidebarName').textContent = name;
  document.getElementById('sidebarCourse').textContent =
    `${course||''} · ${document.getElementById('subjectSelect')?.value||'Programación'}`;
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('appShell').style.display = 'flex';
  const welcome = course
    ? `¡Hola, ${name}! ¿Sobre qué te gustaría aprender hoy?`
    : `Bienvenido de nuevo, ${name}. ¿Con qué continuamos?`;
  if (typeof Chat !== 'undefined') await Chat.init(welcome);
  buildFileTypeGrid();
}

function showErr(id, msg) {
  const el = document.getElementById(id);
  if (el) { el.textContent = msg; el.style.display = 'block'; }
}

function estimateAge(course) {
  const m = {'1.º ESO':12,'2.º ESO':13,'3.º ESO':14,'4.º ESO':15,
    '1.º Bachillerato':16,'2.º Bachillerato':17,'1.º DAM':18,'2.º DAM':19,
    '1.º DAW':18,'2.º DAW':19,'1.º SMR':18,'2.º SMR':19};
  return m[course]||16;
}

function showPanel(name, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('panel-'+name);
  if (panel) panel.classList.add('active');
  if (btn)   btn.classList.add('active');
  if (name==='portfolio' && typeof Portfolio!=='undefined') Portfolio.load();
}

async function changeSubject() {
  const subject = document.getElementById('subjectSelect').value;
  if (typeof Chat==='undefined') return;
  Chat.subject = subject; Chat.clear();
  document.getElementById('sidebarCourse').textContent =
    `${AppState.student?.course||''} · ${subject}`;
  try { const c = await API.startConversation(subject); Chat.conversationId=c.conversation_id; } catch(e){}
  Chat.addMessage('assistant',`Cambiando a <strong>${subject}</strong>. ¿Con qué necesitas ayuda?`);
}

function buildFileTypeGrid() {
  const types = [
    {ext:'py',name:'Python',color:'#3B6D11'},{ext:'html',name:'HTML',color:'#993C1D'},
    {ext:'css',name:'CSS',color:'#185FA5'},{ext:'js',name:'JavaScript',color:'#854F0B'},
    {ext:'md',name:'Markdown',color:'#534AB7'},{ext:'json',name:'JSON',color:'#0F6E56'},
  ];
  const grid = document.getElementById('fileTypeGrid');
  if (!grid) return;
  grid.innerHTML = types.map(t=>`
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
  if (typeof Chat!=='undefined') {
    Chat.pendingFileType = fileType;
    Chat.addMessage('assistant',
      `Vamos a crear un archivo <strong>.${fileType}</strong>. ` +
      `Antes, te haré unas preguntas rápidas. ¿Sobre qué quieres que sea?`);
  }
}

function sleep(ms) { return new Promise(r=>setTimeout(r,ms)); }
