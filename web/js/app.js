/**
 * SENAMHI Extractor SaaS — Frontend Application
 * SPA with interactive dropdowns, charts, map, dark/light mode.
 */
(function () {
  'use strict';

  // ── Configuration ──
  const API_BASE = '/api';
  let currentView = 'dashboard';
  let chartInstances = {};
  let stationMap = null;
  let mapMarkers = [];

  // ── State ──
  const state = {
    stations: [],
    filterOptions: {},
    extractionTasks: [],
    files: [],
    systemStatus: {},
    stationsWithData: [],
  };

  // ── DOM refs ──
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ═══════════════════════════════════════════════════
  //  INIT
  // ═══════════════════════════════════════════════════
  async function init() {
    setupNavigation();
    setupThemeToggle();
    setupExtractionModeToggle();
    setupStationFilters();
    setupDataViewer();
    setupHistoryCleanup();
    await loadAllData();
  }

  async function loadAllData() {
    await Promise.all([
      loadStations(),
      loadStationsWithData(),
      loadFilterOptions(),
      loadSystemStatus(),
      loadFiles(),
      loadExtractionHistory(),
    ]);
    updateDashboard();
  }

  // ── Auto-refresh every 15 seconds ──
  setInterval(autoRefresh, 15000);

  async function autoRefresh() {
    try {
      const oldFileCount = state.files.length;
      const oldTaskCount = state.extractionTasks.length;
      await Promise.all([
        loadSystemStatus(),
        loadFiles(),
        loadExtractionHistory(),
        loadStationsWithData(),
      ]);
      // Only re-render if in the relevant view
      if (state.files.length !== oldFileCount) {
        renderFilesTable();
        populateStationSelects();
      }
      if (currentView === 'dashboard') updateDashboard();
      if (state.extractionTasks.length !== oldTaskCount) {
        renderExtractionHistory();
      }
    } catch (e) {
      // silent
    }
  }

  async function loadStationsWithData() {
    const data = await apiGet('/stations/with-data');
    if (data) state.stationsWithData = data.stations_with_data || [];
  }

  // ═══════════════════════════════════════════════════
  //  API HELPERS
  // ═══════════════════════════════════════════════════
  async function apiGet(path) {
    try {
      const res = await fetch(API_BASE + path);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error(`API GET ${path}:`, err);
      return null;
    }
  }

  async function apiPost(path, body) {
    try {
      const res = await fetch(API_BASE + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      console.error(`API POST ${path}:`, err);
      throw err;
    }
  }

  async function apiDelete(path) {
    try {
      const res = await fetch(API_BASE + path, { method: 'DELETE' });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.error || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      console.error(`API DELETE ${path}:`, err);
      throw err;
    }
  }

  function setupHistoryCleanup() {
    ['#clearRecentExtractions', '#clearExtractionStatus', '#clearExtractionHistory'].forEach((selector) => {
      const btn = $(selector);
      if (!btn) return;
      btn.addEventListener('click', clearExtractionHistory);
    });
  }

  async function clearExtractionHistory() {
    const active = state.extractionTasks.some(t => t.status === 'pending' || t.status === 'running');
    const msg = active
      ? 'Hay extracciones pendientes o en ejecución. Se borrarán solo completadas y fallidas.'
      : 'Se borrará el historial de extracciones completadas y fallidas.';
    if (!confirm(`${msg}\n\nLos archivos CSV descargados no se eliminarán.`)) return;

    try {
      const result = await apiDelete('/extractions/tasks');
      showToast(`Historial limpiado: ${result.deleted || 0} registros`, 'success');
      await Promise.all([loadExtractionHistory(), loadSystemStatus()]);
      updateDashboard();
      renderExtractionHistory();
    } catch (err) {
      showToast(`Error limpiando historial: ${err.message}`, 'error');
    }
  }

  async function loadStations(type, status, search) {
    let params = new URLSearchParams();
    if (type) params.set('type', type);
    if (status) params.set('status', status);
    if (search) params.set('search', search);
    const qs = params.toString() ? '?' + params.toString() : '';
    const data = await apiGet('/stations' + qs);
    if (data) {
      state.stations = data.stations || [];
      renderStationTable();
      populateStationSelects();
    }
  }

  async function loadFilterOptions() {
    const data = await apiGet('/stations/filters');
    if (data) state.filterOptions = data;
  }

  async function loadSystemStatus() {
    const data = await apiGet('/system/status');
    if (data) state.systemStatus = data;
  }

  async function loadFiles() {
    const data = await apiGet('/files');
    if (data) {
      state.files = data.files || [];
      renderFilesTable();
    }
  }

  async function loadExtractionHistory() {
    const data = await apiGet('/extractions/tasks?limit=50');
    if (data) {
      state.extractionTasks = data;
      renderExtractionHistory();
    }
  }

  // ═══════════════════════════════════════════════════
  //  NAVIGATION & UI
  // ═══════════════════════════════════════════════════
  function setupNavigation() {
    const btns = $$('.nav-btn');
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        navigateTo(view);
      });
    });
  }

  function navigateTo(view) {
    currentView = view;
    // Update nav buttons
    $$('.nav-btn').forEach(b => b.classList.remove('active'));
    const activeBtn = $(`.nav-btn[data-view="${view}"]`);
    if (activeBtn) activeBtn.classList.add('active');

    // Switch views
    $$('.view').forEach(v => v.classList.remove('active'));
    const viewEl = $(`#view-${view}`);
    if (viewEl) viewEl.classList.add('active');

    // Update title
    const titles = {
      dashboard: 'Dashboard',
      stations: 'Catálogo de Estaciones',
      extraction: 'Extracción de Datos',
      'data-viewer': 'Visualización de Datos',
      files: 'Archivos Generados',
      map: 'Mapa de Estaciones',
    };
    const titleEl = $('#viewTitle');
    if (titleEl) titleEl.textContent = titles[view] || view;

    // Init map if needed
    if (view === 'map' && !stationMap) {
      setTimeout(initMap, 100);
    }
    if (view === 'map' && stationMap) {
      setTimeout(() => stationMap.invalidateSize(), 100);
    }
    if (view === 'dashboard') {
      updateDashboard();
    }
    // Auto-refresh stations list + selector when entering viewer
    if (view === 'data-viewer') {
      loadStationsWithData().then(() => populateStationSelects());
    }
    if (view === 'files') {
      loadFiles().then(() => renderFilesTable());
    }
  }

  function setupThemeToggle() {
    const toggle = $('#themeToggle');
    if (!toggle) return;
    const icon = toggle.querySelector('.theme-icon');
    toggle.addEventListener('click', () => {
      const html = document.documentElement;
      const current = html.getAttribute('data-theme');
      const next = current === 'light' ? 'dark' : 'light';
      html.setAttribute('data-theme', next);
      icon.textContent = next === 'light' ? '☀️' : '🌙';
      localStorage.setItem('senamhi-theme', next);
      // Update map tiles if visible
      updateMapTheme(next);
    });
    // Load saved preference
    const saved = localStorage.getItem('senamhi-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    icon.textContent = saved === 'light' ? '☀️' : '🌙';
  }

  function setupExtractionModeToggle() {
    const modeSelect = $('#extractionMode');
    const monthParams = $('#modeMonthParams');
    const yearParams = $('#modeYearParams');
    const periodParams = $('#modePeriodParams');
    if (!modeSelect) return;

    modeSelect.addEventListener('change', () => {
      const mode = modeSelect.value;
      monthParams.style.display = mode === 'month' ? 'flex' : 'none';
      yearParams.style.display = mode === 'year' ? 'flex' : 'none';
      periodParams.style.display = mode === 'period' ? 'flex' : 'none';
    });
  }

  function setupStationFilters() {
    const searchEl = $('#stationSearch');
    const typeEl = $('#stationTypeFilter');
    const statusEl = $('#stationStatusFilter');

    const filter = () => {
      loadStations(
        typeEl?.value || null,
        statusEl?.value || null,
        searchEl?.value || null
      );
    };

    if (searchEl) searchEl.addEventListener('input', debounce(filter, 300));
    if (typeEl) typeEl.addEventListener('change', filter);
    if (statusEl) statusEl.addEventListener('change', filter);
  }

  function setupDataViewer() {
    const loadBtn = $('#loadDataPreview');
    if (loadBtn) {
      loadBtn.addEventListener('click', loadDataPreview);
    }
    const startExtBtn = $('#startExtraction');
    if (startExtBtn) {
      startExtBtn.addEventListener('click', startExtraction);
    }
    const openFolderBtn = $('#openDataFolder');
    if (openFolderBtn) {
      openFolderBtn.addEventListener('click', () => {
        fetch(API_BASE + '/files/open-folder')
          .then(r => r.json())
          .then(d => {
            if (d && d.path) {
              showToast('📂 Abriendo: ' + d.path, 'info');
            }
          })
          .catch(() => showToast('No se pudo abrir la carpeta', 'error'));
      });
    }
  }

  // ═══════════════════════════════════════════════════
  //  STATION TABLE
  // ═══════════════════════════════════════════════════
  function renderStationTable() {
    const tbody = $('#stationTableBody');
    const countEl = $('#stationCount');
    if (!tbody) return;
    if (countEl) countEl.textContent = state.stations.length;

    if (state.stations.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No se encontraron estaciones</td></tr>';
      return;
    }

    const typeLabels = { M: '🌡️ Meteorológica', H: '💧 Hidrológica' };
    const statusLabels = { REAL: '🟢 Real', DIFERIDO: '🟡 Diferido', AUTOMATICA: '🔵 Auto' };

    tbody.innerHTML = state.stations.map(s => {
      const hasData = state.stationsWithData.includes(s.name.replace(/ /g, ''));
      const dataIcon = hasData ? '📊' : '⬇️';
      const dataTitle = hasData ? 'Ver datos descargados' : 'Sin datos — Extraer primero';
      return `
      <tr>
        <td><code style="background:var(--bg-hover);padding:2px 8px;border-radius:4px;font-size:0.8rem;">${esc(s.code)}</code></td>
        <td><strong>${esc(s.name)}</strong>${hasData ? ' <span style="font-size:0.7rem;color:var(--success);">✓ datos</span>' : ''}</td>
        <td>${typeLabels[s.station_type] || s.station_type}</td>
        <td><span class="badge">${esc(s.category)}</span></td>
        <td>${statusLabels[s.status] || s.status}</td>
        <td style="font-size:0.8rem;color:var(--text-muted)">${s.latitude.toFixed(4)}, ${s.longitude.toFixed(4)}</td>
        <td>
          <button class="btn btn-sm btn-outline" data-preview="${esc(s.code)}" title="${dataTitle}">
            ${dataIcon} ${hasData ? 'Ver' : 'Extraer'}
          </button>
        </td>
      </tr>
    `;
    }).join('');

    // Wire preview buttons — go to viewer if data exists, else go to extraction
    tbody.querySelectorAll('[data-preview]').forEach(btn => {
      btn.addEventListener('click', () => {
        const code = btn.dataset.preview;
        const station = state.stations.find(s => s.code === code);
        const cleanName = station ? station.name.replace(/ /g, '') : '';
        const hasData = state.stationsWithData.includes(cleanName);
        if (hasData) {
          const dataStation = $('#dataViewerStation');
          if (dataStation) dataStation.value = code;
          navigateTo('data-viewer');
          setTimeout(() => loadDataPreview(), 200);
        } else {
          showToast('Sin datos descargados. Ve a Extracción para obtener datos de esta estación.', 'warning');
          navigateTo('extraction');
          const extStation = $('#extractionStation');
          if (extStation) extStation.value = code;
        }
      });
    });
  }

  function populateStationSelects() {
    // Extraction: all stations
    const extSel = $('#extractionStation');
    if (extSel) {
      const currentVal = extSel.value;
      extSel.innerHTML = '<option value="">-- Seleccionar estación --</option>' +
        state.stations.map(s =>
          `<option value="${esc(s.code)}">${esc(s.name)} (${esc(s.code)})</option>`
        ).join('');
      if (currentVal) extSel.value = currentVal;
    }

    // Data viewer: only stations that have CSV data
    const dvSel = $('#dataViewerStation');
    if (dvSel) {
      const currentVal = dvSel.value;
      const withData = state.stations.filter(s =>
        state.stationsWithData.includes(s.name.replace(/ /g, ''))
      );
      dvSel.innerHTML = withData.length === 0
        ? '<option value="">-- No hay datos descargados aun --</option>'
        : '<option value="">-- Seleccionar estación --</option>' +
          withData.map(s =>
            `<option value="${esc(s.code)}">${esc(s.name)} (${esc(s.code)})</option>`
          ).join('');
      if (currentVal) dvSel.value = currentVal;
    }
  }

  // ═══════════════════════════════════════════════════
  //  DASHBOARD
  // ═══════════════════════════════════════════════════
  function updateDashboard() {
    const ss = state.systemStatus;
    if ($('#kpiStations')) $('#kpiStations').textContent = ss.stations_count || state.stations.length || '--';
    if ($('#kpiExtractions')) $('#kpiExtractions').textContent = ss.total_extractions || state.extractionTasks.length || '--';
    if ($('#kpiCompleted')) {
      const completed = state.extractionTasks.filter(t => t.status === 'completed').length;
      $('#kpiCompleted').textContent = completed || '--';
    }
    if ($('#kpiDbSize')) $('#kpiDbSize').textContent = (ss.database_size_mb || 0).toFixed(1) + ' MB';

    // Render recent extractions
    renderRecentExtractions();
    // Render charts
    renderStationDistributionChart();
    renderExtractionStatusChart();
    // Render files summary
    renderFilesSummary();
  }

  function renderRecentExtractions() {
    const el = $('#recentExtractions');
    if (!el) return;
    const tasks = state.extractionTasks.slice(0, 8);
    if (tasks.length === 0) {
      el.innerHTML = '<p class="text-muted">No hay extracciones registradas aún.</p>';
      return;
    }
    const statusBadges = {
      completed: '<span class="status-badge status-completed">✅ Completado</span>',
      pending: '<span class="status-badge status-pending">⏳ Pendiente</span>',
      running: '<span class="status-badge status-running">🔄 Ejecutando</span>',
      failed: '<span class="status-badge status-failed">❌ Fallido</span>',
    };
    el.innerHTML = tasks.map(t => {
      const date = t.created_at ? new Date(t.created_at).toLocaleString('es-PE') : '--';
      return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);">
          <div>
            <strong>${esc(t.station_name || 'Estación ' + t.station_id)}</strong>
            <span style="color:var(--text-muted);font-size:0.8rem;"> · ${t.mode} · ${t.year || ''}${t.month ? '-' + t.month : ''}${t.end_year ? ' a ' + t.end_year : ''}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:0.75rem;color:var(--text-muted);">${date}</span>
            ${statusBadges[t.status] || t.status}
          </div>
        </div>
      `;
    }).join('');
  }

  function renderStationDistributionChart() {
    const canvas = $('#stationChart');
    if (!canvas) return;

    // Count by type
    const typeCounts = { M: 0, H: 0 };
    state.stations.forEach(s => {
      typeCounts[s.station_type] = (typeCounts[s.station_type] || 0) + 1;
    });

    destroyChart('stationChart');
    chartInstances['stationChart'] = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Meteorológicas', 'Hidrológicas'],
        datasets: [{
          data: [typeCounts.M, typeCounts.H],
          backgroundColor: ['#3b82f6', '#22c55e'],
          borderColor: 'var(--bg-card)',
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom', labels: { color: '#9aa0b0', padding: 16 } }
        },
      },
    });
  }

  function renderExtractionStatusChart() {
    const canvas = $('#extractionStatusChart');
    if (!canvas) return;
    const statusCounts = { completed: 0, pending: 0, running: 0, failed: 0 };
    state.extractionTasks.forEach(t => {
      if (statusCounts[t.status] !== undefined) statusCounts[t.status]++;
    });

    destroyChart('extractionStatusChart');
    chartInstances['extractionStatusChart'] = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: ['Completadas', 'Pendientes', 'Ejecutando', 'Fallidas'],
        datasets: [{
          data: [statusCounts.completed, statusCounts.pending, statusCounts.running, statusCounts.failed],
          backgroundColor: ['#22c55e', '#f59e0b', '#06b6d4', '#ef4444'],
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { color: '#9aa0b0' } },
          x: { ticks: { color: '#9aa0b0' } },
        },
      },
    });
  }

  function renderFilesSummary() {
    const el = $('#filesSummary');
    if (!el) return;
    if (state.files.length === 0) {
      el.innerHTML = '<p class="text-muted">No hay archivos generados.</p>';
      return;
    }
    const totalRows = state.files.reduce((sum, f) => sum + f.rows, 0);
    const totalSize = state.files.reduce((sum, f) => sum + f.size_mb, 0);
    el.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:12px;">
        <div style="display:flex;justify-content:space-between;">
          <span style="color:var(--text-secondary)">Archivos totales</span>
          <strong>${state.files.length}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;">
          <span style="color:var(--text-secondary)">Filas totales</span>
          <strong>${totalRows.toLocaleString()}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;">
          <span style="color:var(--text-secondary)">Tamaño total</span>
          <strong>${totalSize.toFixed(1)} MB</strong>
        </div>
        <hr style="border-color:var(--border)">
        <div style="font-size:0.8rem;color:var(--text-muted);">
          📁 ${new Set(state.files.map(f => f.station)).size} estaciones con datos
        </div>
        <button class="btn btn-sm btn-outline open-folder-btn" style="margin-top:8px;width:100%;">
          📂 Abrir carpeta de datos en Explorer
        </button>
      </div>
    `;
    // Wire the button after HTML is injected
    el.querySelector('.open-folder-btn')?.addEventListener('click', () => {
      fetch(API_BASE + '/files/open-folder').then(r => r.json()).then(d => {
        if (d && d.path) showToast('📂 Carpeta: ' + d.path, 'info');
      });
    });
  }

  function renderFilesTable() {
    const tbody = $('#filesTableBody');
    const countEl = $('#fileCount');
    if (!tbody) return;
    if (countEl) countEl.textContent = state.files.length;
    if (state.files.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No hay archivos generados</td></tr>';
      return;
    }
    tbody.innerHTML = state.files.map(f => `
      <tr>
        <td><strong>${esc(f.station)}</strong></td>
        <td>${esc(f.filename)}</td>
        <td>${f.size_mb.toFixed(1)} MB</td>
        <td>${f.rows.toLocaleString()}</td>
        <td>
          <button class="btn btn-sm btn-outline" data-download="${esc(f.station)}/${esc(f.filename)}">⬇️ Descargar</button>
          <button class="btn btn-sm btn-danger" data-delete="${esc(f.station)}/${esc(f.filename)}" style="margin-left:4px;">🗑️</button>
        </td>
      </tr>
    `).join('');

    tbody.querySelectorAll('[data-download]').forEach(btn => {
      btn.addEventListener('click', () => {
        const path = btn.dataset.download;
        window.open(`${API_BASE}/files/download/${path}`, '_blank');
      });
    });

    tbody.querySelectorAll('[data-delete]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const path = btn.dataset.delete;
        if (!confirm(`¿Eliminar ${path}?`)) return;
        try {
          const res = await fetch(`${API_BASE}/files/${path}`, { method: 'DELETE' });
          if (res.ok) {
            showToast(`🗑️ Archivo eliminado: ${path}`, 'success');
            await loadFiles();
            await loadStationsWithData();
            populateStationSelects();
            renderFilesTable();
            updateDashboard();
          } else {
            const err = await res.json().catch(() => ({}));
            showToast(`❌ Error: ${err.error || 'No se pudo eliminar'}`, 'error');
          }
        } catch (e) {
          showToast(`❌ Error: ${e.message}`, 'error');
        }
      });
    });
  }

  // ═══════════════════════════════════════════════════
  //  EXTRACTION
  // ═══════════════════════════════════════════════════
  async function startExtraction() {
    const stationCode = $('#extractionStation')?.value;
    const mode = $('#extractionMode')?.value;
    if (!stationCode || !mode) {
      showToast('Selecciona una estación y un modo de consulta', 'warning');
      return;
    }

    const body = {
      station_code: stationCode,
      mode: mode,
      consolidated: $('#extConsolidated')?.checked ?? true,
    };

    if (mode === 'month') {
      body.year = parseInt($('#extYear')?.value || '2024');
      body.month = parseInt($('#extMonth')?.value || '1');
    } else if (mode === 'year') {
      body.year = parseInt($('#extYearY')?.value || '2024');
    } else if (mode === 'period') {
      body.year = parseInt($('#extStartYear')?.value || '2020');
      body.end_year = parseInt($('#extEndYear')?.value || '2025');
    }

    try {
      showToast('⏳ Iniciando extracción (esto puede tomar 30-90s)...', 'info');
      const result = await apiPost('/extractions', body);
      const taskId = result.id;
      showToast(`🔄 Extrayendo ${result.station_name}...`, 'info');

      // Poll task status until it finishes
      let finished = false;
      for (let i = 0; i < 30; i++) {
        await sleep(4000);
        const task = await apiGet(`/extractions/${taskId}`);
        if (!task) break;
        if (task.status === 'completed') {
          showToast(`✅ ¡Completado! ${task.record_count?.toLocaleString() || 0} registros descargados de ${task.station_name}`, 'success');
          finished = true;
          break;
        }
        if (task.status === 'failed') {
          showToast(`❌ Fallido: ${(task.error_detail || 'Error desconocido').substring(0, 100)}`, 'error');
          finished = true;
          break;
        }
        // Update progress toast
        if (i === 5) showToast('⏳ Aún trabajando... el scraping puede tomar hasta 2 minutos', 'info');
      }
      if (!finished) {
        showToast('⏳ La extracción sigue en proceso. Recarga la página en un momento.', 'warning');
      }

      // Reload ALL data to refresh every view
      await Promise.all([
        loadExtractionHistory(),
        loadFiles(),
        loadSystemStatus(),
        loadStationsWithData(),
      ]);
      populateStationSelects();
      renderFilesTable();
      updateDashboard();
    } catch (err) {
      showToast(`❌ Error: ${err.message}`, 'error');
    }
  }

  function renderExtractionHistory() {
    const el = $('#extractionHistory');
    if (!el) return;
    const tasks = state.extractionTasks.slice(0, 20);
    if (tasks.length === 0) {
      el.innerHTML = '<p class="text-muted">No hay extracciones registradas.</p>';
      return;
    }
    const statusBadges = {
      completed: '<span class="status-badge status-completed">✅ Completado</span>',
      pending: '<span class="status-badge status-pending">⏳ Pendiente</span>',
      running: '<span class="status-badge status-running">🔄 Ejecutando</span>',
      failed: '<span class="status-badge status-failed">❌ Fallido</span>',
    };
    el.innerHTML = `<div class="table-scroll"><table class="data-table">
      <thead><tr><th>Estación</th><th>Modo</th><th>Año</th><th>Registros</th><th>Estado</th><th>Fecha</th></tr></thead>
      <tbody>${tasks.map(t => {
        const date = t.created_at ? new Date(t.created_at).toLocaleString('es-PE') : '--';
        return `<tr>
          <td><strong>${esc(t.station_name)}</strong></td>
          <td>${esc(t.mode)}</td>
          <td>${t.year || ''}${t.month ? '-' + String(t.month).padStart(2,'0') : ''}${t.end_year ? ' a ' + t.end_year : ''}</td>
          <td>${(t.record_count || 0).toLocaleString()}</td>
          <td>${statusBadges[t.status] || t.status}</td>
          <td style="font-size:0.75rem;color:var(--text-muted);">${date}</td>
        </tr>`;
      }).join('')}</tbody></table></div>`;
  }

  // ═══════════════════════════════════════════════════
  //  DATA VIEWER
  // ═══════════════════════════════════════════════════
  async function loadDataPreview() {
    const code = $('#dataViewerStation')?.value;
    if (!code) {
      showToast('Selecciona una estación', 'warning');
      return;
    }

    try {
      const previewData = await apiGet(`/stations/${code}/data/preview`);
      if (!previewData || !previewData.headers || previewData.row_count === 0) {
        $('#dataPreviewInfo').innerHTML = '<p class="text-muted">No hay datos disponibles para esta estación.</p>';
        $('#dataPreviewHead').innerHTML = '';
        $('#dataPreviewBody').innerHTML = '';
        destroyChart('timeSeriesChart');
        return;
      }

      $('#dataPreviewInfo').innerHTML = `
        <strong>${esc(previewData.station_name)}</strong> ·
        ${previewData.row_count.toLocaleString()} registros ·
        ${previewData.date_range || ''}
      `;

      // Render data table
      $('#dataPreviewHead').innerHTML = '<tr>' + previewData.headers.map(h => `<th>${esc(h)}</th>`).join('') + '</tr>';
      $('#dataPreviewBody').innerHTML = (previewData.sample_rows || []).map(row =>
        '<tr>' + row.map(cell => `<td>${esc(String(cell))}</td>`).join('') + '</tr>'
      ).join('');

      // Query full data for chart
      const queryData = await apiPost(`/stations/${code}/data/query`, {
        station_code: code,
        limit: 2000,
        offset: 0,
      });

      if (queryData && queryData.rows && queryData.rows.length > 0) {
        renderTimeSeriesChart(queryData);
      }
    } catch (err) {
      showToast(`Error cargando datos: ${err.message}`, 'error');
    }
  }

  function renderTimeSeriesChart(data) {
    const canvas = $('#timeSeriesChart');
    if (!canvas || !data.rows || data.rows.length === 0) return;

    // Find numeric columns (skip Año, Mes, Día, Hora)
    const numCols = data.headers.filter((h, i) => {
      if (['Año', 'Mes', 'Día', 'Hora'].includes(h)) return false;
      // Check if values are numeric
      const sample = data.rows.slice(0, 10);
      return sample.some(r => r[h] !== undefined && r[h] !== 'S/D' && !isNaN(parseFloat(r[h])));
    });

    if (numCols.length === 0) return;

    // Prepare labels (dates)
    const labels = data.rows.map(r => {
      const y = r['Año'] || '';
      const m = (r['Mes'] || '').toString().padStart(2, '0');
      const d = (r['Día'] || '').toString().padStart(2, '0');
      return `${y}-${m}-${d}`;
    });

    // Show only every Nth label
    const step = Math.max(1, Math.floor(labels.length / 20));
    const displayLabels = labels.map((l, i) => i % step === 0 ? l : '');

    const colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
    const datasets = numCols.map((col, i) => ({
      label: col,
      data: data.rows.map(r => {
        const v = r[col];
        if (v === 'S/D' || v === undefined || v === null) return null;
        const n = parseFloat(v);
        return isNaN(n) ? null : n;
      }),
      borderColor: colors[i % colors.length],
      backgroundColor: colors[i % colors.length] + '20',
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.1,
      spanGaps: false,
    }));

    destroyChart('timeSeriesChart');
    chartInstances['timeSeriesChart'] = new Chart(canvas, {
      type: 'line',
      data: { labels: displayLabels, datasets },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { color: '#9aa0b0', usePointStyle: true, padding: 16 } },
          tooltip: {
            callbacks: {
              title: (items) => labels[items[0].dataIndex] || '',
            }
          },
        },
        scales: {
          y: { ticks: { color: '#9aa0b0' }, grid: { color: 'var(--border)' } },
          x: { ticks: { color: '#9aa0b0', maxTicksLimit: 15 }, grid: { display: false } },
        },
      },
    });
  }

  function destroyChart(name) {
    if (chartInstances[name]) {
      chartInstances[name].destroy();
      chartInstances[name] = null;
    }
  }

  // ═══════════════════════════════════════════════════
  //  MAP
  // ═══════════════════════════════════════════════════
  function initMap() {
    const mapEl = $('#stationMap');
    if (!mapEl) return;

    stationMap = L.map('stationMap').setView([-11.5, -76.5], 7);

    updateMapTheme(document.documentElement.getAttribute('data-theme'));

    // Add markers
    state.stations.forEach(s => {
      const typeEmoji = s.station_type === 'M' ? '🌡️' : '💧';
      const color = s.station_type === 'M' ? '#3b82f6' : '#22c55e';
      const marker = L.circleMarker([s.latitude, s.longitude], {
        radius: 6,
        fillColor: color,
        color: '#fff',
        weight: 1.5,
        fillOpacity: 0.85,
      }).addTo(stationMap);

      marker.bindPopup(`
        <div class="map-popup">
          <strong>${typeEmoji} ${esc(s.name)}</strong><br>
          <span style="font-size:0.8rem;">Código: ${esc(s.code)}</span><br>
          <span style="font-size:0.75rem;color:#666;">${esc(s.category)} · ${esc(s.status)}</span><br>
          <span style="font-size:0.75rem;">(${s.latitude.toFixed(4)}, ${s.longitude.toFixed(4)})</span>
        </div>
      `);
      mapMarkers.push(marker);
    });

    // Fit bounds
    if (state.stations.length > 0) {
      const bounds = L.latLngBounds(state.stations.map(s => [s.latitude, s.longitude]));
      stationMap.fitBounds(bounds, { padding: [30, 30] });
    }
  }

  function updateMapTheme(theme) {
    if (!stationMap) return;
    // Remove existing tile layer
    stationMap.eachLayer(layer => {
      if (layer instanceof L.TileLayer) {
        stationMap.removeLayer(layer);
      }
    });

    const tileUrl = theme === 'light'
      ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

    L.tileLayer(tileUrl, {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
    }).addTo(stationMap);
  }

  // ═══════════════════════════════════════════════════
  //  TOASTS
  // ═══════════════════════════════════════════════════
  function showToast(message, type = 'info') {
    const container = $('#toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = '0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // ═══════════════════════════════════════════════════
  //  UTILITIES
  // ═══════════════════════════════════════════════════
  function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function debounce(fn, ms) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }

  // Check API status periodically
  async function checkApiStatus() {
    const statusEl = $('.status-dot');
    try {
      const res = await fetch(API_BASE + '/health');
      if (res.ok && statusEl) {
        statusEl.classList.remove('offline');
      }
    } catch {
      if (statusEl) statusEl.classList.add('offline');
    }
  }

  // ═══════════════════════════════════════════════════
  //  BOOT
  // ═══════════════════════════════════════════════════
  init();
  setInterval(checkApiStatus, 30000);
  checkApiStatus();

  // Poll extraction status periodically when on extraction view
  setInterval(() => {
    if (currentView === 'extraction' || currentView === 'dashboard') {
      loadExtractionHistory();
    }
  }, 10000);

})();
