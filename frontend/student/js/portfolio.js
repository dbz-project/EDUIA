/**
 * frontend/student/js/portfolio.js
 * Portfolio local del alumno — archivos generados con EduIA
 */

const Portfolio = {

  items: [],

  async load() {
    try {
      const data = await API.getPortfolio();
      this.items = data.items || [];
      this.render();
    } catch (e) {
      document.getElementById('portfolioGrid').innerHTML =
        '<p style="padding:20px;color:var(--text-3);font-size:13px;">No se pudo cargar el portfolio.</p>';
    }
  },

  render() {
    const grid = document.getElementById('portfolioGrid');
    const count = document.getElementById('portfolioCount');

    count.textContent = `${this.items.length} ${this.items.length === 1 ? 'archivo' : 'archivos'}`;

    if (this.items.length === 0) {
      grid.innerHTML = `
        <div style="grid-column:1/-1;padding:40px 20px;text-align:center;">
          <div style="font-size:13px;color:var(--text-3);line-height:1.7;">
            Aún no has creado ningún archivo.<br>
            Ve a <strong>Crear archivo</strong> para empezar.
          </div>
        </div>`;
      return;
    }

    grid.innerHTML = this.items.map(item => `
      <div class="file-card" onclick="Portfolio.openFile(${item.id})" role="button" tabindex="0">
        ${this.fileIcon(item.file_type)}
        <div class="file-name">${this.escapeHtml(item.filename)}</div>
        <div class="file-meta">${item.subject} · ${this.relativeDate(item.created_at)}</div>
        ${item.eval_passed
          ? `<div class="file-badge">
               <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="10" height="10"><polyline points="20 6 9 17 4 12"/></svg>
               Evaluación superada
             </div>`
          : ''}
      </div>`
    ).join('');
  },

  fileIcon(ext) {
    const colors = {
      py: '#3B6D11', html: '#993C1D', css: '#185FA5',
      js: '#854F0B', md: '#534AB7', json: '#0F6E56', txt: '#5F5E5A',
    };
    const color = colors[ext] || '#888780';
    return `
      <div class="file-ext-icon ${ext}" style="color:${color};margin-bottom:8px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="26" height="26">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <text x="7" y="18" font-size="5" fill="currentColor" stroke="none" font-weight="bold">.${ext}</text>
        </svg>
      </div>`;
  },

  async openFile(id) {
    try {
      const data = await API.getFileContent(id);
      // En Tauri esto abriría el archivo con el editor del sistema
      // Por ahora mostramos el contenido en el chat
      Chat.addMessage('assistant',
        `Aquí está el contenido de <strong>${data.filename}</strong>:<br><br>` +
        `<pre style="font-family:var(--font-mono);font-size:11px;white-space:pre-wrap;` +
        `background:rgba(0,0,0,0.04);padding:10px;border-radius:6px;overflow-x:auto;">` +
        `${this.escapeHtml(data.content)}</pre>`
      );
      showPanel('chat', document.querySelector('[data-panel=chat]'));
    } catch (e) {
      alert('No se pudo abrir el archivo.');
    }
  },

  relativeDate(isoStr) {
    const d = new Date(isoStr);
    const now = new Date();
    const diff = Math.floor((now - d) / 86400000);
    if (diff === 0) return 'hoy';
    if (diff === 1) return 'ayer';
    if (diff < 7) return `hace ${diff} días`;
    if (diff < 30) return `hace ${Math.floor(diff / 7)} semanas`;
    return `hace ${Math.floor(diff / 30)} meses`;
  },

  escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  },
};
