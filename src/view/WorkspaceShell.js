// Presentation-only shell: panels, ribbon, dock, resizing and workspace preferences.
export class WorkspaceShell {
  constructor(root, { beforeResize = () => {} } = {}) {
    this.root = root; this.beforeResize = beforeResize; this.logs = [];
    this.state = { nav: true, inspector: true, dock: true, collapsed: false, navWidth: 228, inspectorWidth: 280, dockHeight: 142, ribbon: 'home', dockTab: 'measurements' };
    try {
      const saved = JSON.parse(localStorage.getItem('retopo-1:layout'));
      for (const key of ['nav', 'inspector', 'dock', 'collapsed']) if (typeof saved?.[key] === 'boolean') this.state[key] = saved[key];
      for (const [key, low, high] of [['navWidth', 180, 360], ['inspectorWidth', 240, 400], ['dockHeight', 110, 320]]) if (Number.isFinite(saved?.[key])) this.state[key] = Math.max(low, Math.min(high, saved[key]));
    } catch { /* Invalid workspace preferences do not affect the guide document. */ }
    this.compactPanels = { nav: false, inspector: false };
    this.bindTabs('[data-ribbon-tab]', 'ribbon', ['file', 'home', 'draw', 'view', 'retopology']);
    this.bindTabs('[data-dock-tab]', 'dockTab', ['measurements', 'history', 'log']);
    for (const key of ['nav', 'inspector', 'dock']) document.getElementById('toggle-' + key).onclick = () => {
      if (innerWidth < 780 && key !== 'dock') this.compactPanels[key] = !this.compactPanels[key];
      else this.state[key] = !this.state[key];
      this.apply();
    };
    document.getElementById('toggle-ribbon').onclick = () => { this.state.collapsed = !this.state.collapsed; this.apply(); };
    document.getElementById('clear-log').onclick = () => { this.logs = []; this.paintLog(); };
    document.getElementById('copy-log').onclick = async ({ currentTarget: button }) => {
      try { await navigator.clipboard.writeText(this.logText()); button.textContent = 'Copied'; } catch { button.textContent = 'Copy failed'; }
      clearTimeout(this.copyReset); this.copyReset = setTimeout(() => { button.textContent = 'Copy log'; }, 1500);
    };
    document.getElementById('save-log').onclick = () => {
      const url = URL.createObjectURL(new Blob([this.logText()], { type: 'text/plain' })), link = document.createElement('a');
      link.href = url; link.download = 'retopo-activity.txt'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    for (const splitter of root.querySelectorAll('[data-splitter]')) this.bindSplitter(splitter);
    addEventListener('resize', () => this.apply(false)); this.apply(false);
  }
  bindTabs(selector, key, choices) {
    const buttons = [...this.root.querySelectorAll(selector)];
    buttons.forEach((button, index) => {
      const value = choices[index];
      button.onclick = () => { this.state[key] = value; if (key === 'ribbon') this.state.collapsed = false; this.apply(); };
      button.onkeydown = event => {
        let next = index;
        if (event.key === 'ArrowRight') next = (index + 1) % buttons.length;
        else if (event.key === 'ArrowLeft') next = (index + buttons.length - 1) % buttons.length;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = buttons.length - 1;
        else return;
        event.preventDefault(); buttons[next].click(); buttons[next].focus();
      };
    });
  }
  bindSplitter(element) {
    const region = element.dataset.splitter, key = { west: 'navWidth', east: 'inspectorWidth', south: 'dockHeight' }[region];
    const limits = region === 'west' ? [180, 360] : region === 'east' ? [240, 400] : [110, 320];
    const update = value => { this.state[key] = Math.max(limits[0], Math.min(limits[1], value)); this.apply(); };
    let drag = null;
    element.onpointerdown = event => {
      if (event.button !== 0) return;
      event.preventDefault(); this.beforeResize(); element.focus(); drag = { id: event.pointerId, x: event.clientX, y: event.clientY, value: this.state[key] }; element.setPointerCapture(event.pointerId);
    };
    element.onpointermove = event => { if (drag?.id === event.pointerId) update(drag.value + (region === 'west' ? event.clientX - drag.x : region === 'east' ? drag.x - event.clientX : drag.y - event.clientY)); };
    const end = event => { if (drag?.id !== event.pointerId) return; if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId); drag = null; };
    element.onpointerup = end; element.onpointercancel = event => { if (drag) update(drag.value); end(event); };
    element.onlostpointercapture = () => { drag = null; };
    element.ondblclick = () => update(region === 'west' ? 228 : region === 'east' ? 280 : 142);
    element.onkeydown = event => {
      const negative = region === 'west' ? 'ArrowLeft' : region === 'east' ? 'ArrowRight' : 'ArrowDown';
      const positive = region === 'west' ? 'ArrowRight' : region === 'east' ? 'ArrowLeft' : 'ArrowUp';
      if (event.key === negative || event.key === positive) { event.preventDefault(); this.beforeResize(); update(this.state[key] + (event.key === positive ? 10 : -10)); }
    };
    element.setAttribute('aria-valuemin', limits[0]); element.setAttribute('aria-valuemax', limits[1]);
  }
  apply(persist = true) {
    const compact = innerWidth < 780, visible = key => compact && key !== 'dock' ? this.compactPanels[key] : this.state[key];
    this.root.classList.toggle('compact', compact);
    for (const key of ['nav', 'inspector', 'dock']) { this.root.classList.toggle(key + '-hidden', !visible(key)); document.getElementById('toggle-' + key).setAttribute('aria-pressed', String(visible(key))); }
    this.root.classList.toggle('ribbon-collapsed', this.state.collapsed);
    document.getElementById('toggle-ribbon').setAttribute('aria-expanded', String(!this.state.collapsed));
    for (const [key, variable] of [['navWidth', '--nav-width'], ['inspectorWidth', '--inspector-width'], ['dockHeight', '--dock-height']]) this.root.style.setProperty(variable, this.state[key] + 'px');
    for (const element of this.root.querySelectorAll('[data-splitter]')) element.setAttribute('aria-valuenow', this.state[{ west: 'navWidth', east: 'inspectorWidth', south: 'dockHeight' }[element.dataset.splitter]]);
    for (const button of this.root.querySelectorAll('[data-ribbon-tab]')) { const active = button.dataset.ribbonTab === this.state.ribbon; button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1; }
    for (const group of this.root.querySelectorAll('[data-ribbon-group]')) group.hidden = !group.dataset.ribbonGroup.split(' ').includes(this.state.ribbon);
    for (const button of this.root.querySelectorAll('[data-dock-tab]')) { const active = button.dataset.dockTab === this.state.dockTab; button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1; }
    for (const panel of this.root.querySelectorAll('[data-dock-panel]')) panel.hidden = panel.dataset.dockPanel !== this.state.dockTab;
    if (persist) { try { localStorage.setItem('retopo-1:layout', JSON.stringify(this.state)); } catch { /* Optional view preferences. */ } }
  }
  showLog() { this.state.dock = true; this.state.dockTab = 'log'; this.apply(); }
  logText() { return this.logs.map(e => `${e.time} ${e.level || (e.error ? 'error' : 'info')} ${e.message}`).join('\n') + '\n'; }
  addLog(message, error = false) { this.addLogs([{ message, error }]); }
  addLogs(entries) {
    for (const entry of entries) this.logs.push({ ...entry, time: entry.time === null ? '—' : new Date(entry.time === undefined ? Date.now() : entry.time * 1000).toLocaleTimeString('en-US', { hour12: false }) });
    if (this.logs.length > 1000) this.logs.splice(0, this.logs.length - 1000);
    this.paintLog();
    if (entries.length) document.getElementById('operationStatus').textContent = entries.at(-1).message;
  }
  paintLog() {
    const list = document.getElementById('logList'), panel = list.closest('.dock-panel');
    const atBottom = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 25; list.replaceChildren();
    for (const entry of this.logs) { const row = document.createElement('li'), time = document.createElement('time'), text = document.createElement('span'); row.classList.toggle('error', entry.error || entry.level === 'error'); row.classList.toggle('warning', entry.level === 'warning'); if (entry.jobId) row.dataset.jobId = entry.jobId; time.textContent = entry.time; text.textContent = entry.message; row.append(time, text); list.append(row); }
    if (atBottom) panel.scrollTop = panel.scrollHeight;
  }
  history(history) {
    const list = document.getElementById('historyList'); list.replaceChildren();
    [...history.undo, ...history.redo].forEach((label, i) => { const row = document.createElement('li'); row.textContent = `${i + 1}. ${label}`; row.classList.toggle('future', i >= history.index); if (i === history.index - 1) row.setAttribute('aria-current', 'step'); list.append(row); });
    if (!list.children.length) { const row = document.createElement('li'); row.textContent = 'Guide edits appear here. Selection and view changes stay out of history.'; row.className = 'empty'; list.append(row); }
  }
}
