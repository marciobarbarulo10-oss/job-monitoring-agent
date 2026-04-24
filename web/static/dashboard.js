// dashboard.js — Job Agent v2.0 Frontend Logic

// ── STATE ─────────────────────────────────────────────────────────────────────
const State = {
  vagasPage: 1,
  vagasFilter: '',
  vagasGrade: '',
  vagasSearch: '',
  vagasFonte: '',
  vagasTotal: 0,
  searchTimer: null,
  activeTab: 'pipeline',
};

const LIMIT = 20;

const STATUS_LABELS = {
  nova: 'Nova', aplicada: 'Aplicada', em_analise: 'Em Analise',
  entrevista: 'Entrevista', rejeitada: 'Rejeitada', encerrada: 'Encerrada',
  suspeita: 'Suspeita', cv_gerado: 'CV Gerado', proposta: 'Proposta',
};

// ── UTILS ─────────────────────────────────────────────────────────────────────
function scoreClass(s) {
  if (s >= 9) return 'score-a';
  if (s >= 7) return 'score-b';
  if (s >= 5) return 'score-c';
  if (s >= 3) return 'score-d';
  return 'score-f';
}

function gradeClass(g) {
  const m = { A: 'grade-a', B: 'grade-b', C: 'grade-c', D: 'grade-d', F: 'grade-f' };
  return m[g] || '';
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showToast(msg, err = false, duration = 4000) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (err ? ' err' : '');
  setTimeout(() => { t.className = 'toast'; }, duration);
}

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function postJSON(url, body = {}) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

// ── TABS ──────────────────────────────────────────────────────────────────────
function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

  const btn = document.querySelector(`[data-tab="${tabName}"]`);
  const panel = document.getElementById(`tab-${tabName}`);
  if (btn) btn.classList.add('active');
  if (panel) panel.classList.add('active');

  State.activeTab = tabName;

  if (tabName === 'cvs') loadCVs();
  if (tabName === 'feedback') loadFeedback();
  if (tabName === 'mercado') loadMercado();
  if (tabName === 'config') loadConfig();
}

// ── METRICS ───────────────────────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const d = await fetchJSON('/api/stats');
    document.getElementById('m-total').textContent      = d.total;
    document.getElementById('m-novas').textContent      = d.novas;
    document.getElementById('m-analise').textContent    = d.em_analise;
    document.getElementById('m-entrevista').textContent = d.entrevista;
    document.getElementById('m-conv').textContent       = d.taxa_conversao + '%';
    document.getElementById('m-score').textContent      = d.media_score;
    document.getElementById('m-score-sub').textContent  = d.pct_acima_6 + '% acima de 6';
    document.getElementById('m-encerradas').textContent = d.encerradas;
    document.getElementById('m-cvs').textContent        = d.cvs_gerados;
    document.getElementById('m-early').textContent      = d.early_applicant;
    document.getElementById('last-update').textContent  = 'Atualizado: ' + d.atualizado_em;

    // Em Processo card com breakdown
    const emp = d.em_processo || {};
    document.getElementById('m-aplicadas').textContent = emp.total ?? d.aplicadas;
    const empSub = document.getElementById('m-aplicadas-sub');
    if (empSub && emp.breakdown) {
      const b = emp.breakdown;
      const parts = [];
      if (b.aplicada)  parts.push(b.aplicada + ' aplic');
      if (b.entrevista) parts.push(b.entrevista + ' entrev');
      if (b.proposta)   parts.push(b.proposta + ' prop');
      empSub.textContent = parts.length ? parts.join(' · ') : 'em andamento';
    }

    const badge = document.getElementById('badge-novas');
    if (d.novas > 0) { badge.textContent = d.novas + ' novas'; badge.classList.add('show'); }
    else badge.classList.remove('show');

    const cycleBadge = document.getElementById('badge-cycle');
    cycleBadge.style.display = d.cycle_running ? 'inline' : 'none';

    renderBannerAcao(d.acoes_hoje || []);
  } catch (e) { console.error('loadMetrics:', e); }
}

function renderBannerAcao(acoes) {
  const banner = document.getElementById('banner-acao');
  const lista  = document.getElementById('acoes-lista');
  if (!banner || !lista) return;
  if (!acoes || !acoes.length) { banner.style.display = 'none'; return; }
  lista.innerHTML = acoes.map(a => `
    <div class="acao-item">
      <span style="font-size:13px">${esc(a.texto)}</span>
      <button class="btn-sm" onclick="setFilterDirect('${esc(a.filtro)}')" style="flex-shrink:0">${esc(a.acao)}</button>
    </div>`).join('');
  banner.style.display = 'block';
}

function setFilterDirect(status) {
  const btn = document.querySelector(`.filter-btn[onclick*="'${status}'"]`)
           || document.querySelector('.filter-btn');
  setFilter(status, btn);
}

// ── PIPELINE ──────────────────────────────────────────────────────────────────
async function loadPipeline() {
  try {
    const d = await fetchJSON('/api/pipeline');
    for (const [k, v] of Object.entries(d)) {
      const el = document.getElementById('ps-' + k);
      if (el) el.textContent = v;
    }
  } catch (e) { console.error('loadPipeline:', e); }
}

// ── TOP VAGAS ─────────────────────────────────────────────────────────────────
async function loadTopVagas() {
  try {
    const vagas = await fetchJSON('/api/top-vagas');
    const el = document.getElementById('top-vagas-list');

    if (!vagas.length) {
      el.innerHTML = '<p class="empty-msg">Nenhuma vaga com score alto ainda.</p>';
      return;
    }

    el.innerHTML = vagas.map((v, i) => {
      const rank = i + 1;
      const kws = v.keywords.slice(0, 4).map(k => `<span class="tv-kw">${esc(k)}</span>`).join('');
      const earlyBadge = v.is_early ? '<span class="badge-early">JANELA</span>' : '';
      const gradeBadge = v.score_grade ? `<span class="grade-badge ${gradeClass(v.score_grade)}">${v.score_grade}</span>` : '';
      return `
        <div class="top-vaga">
          <div class="tv-rank rank-${rank <= 3 ? rank : 'n'}">${rank}</div>
          <div class="tv-info">
            <div class="tv-titulo">${esc(v.titulo)} ${earlyBadge}</div>
            <div class="tv-empresa">${esc(v.empresa)} &mdash; ${esc(v.localizacao)}</div>
            <div class="tv-kws">${kws}</div>
          </div>
          <div class="tv-right">
            <span class="score-badge ${scoreClass(v.score)}">${v.score} ${gradeBadge}</span>
            <div class="tv-actions">
              <a href="${esc(v.url)}" target="_blank" class="btn-sm btn-link">Abrir</a>
              <button class="btn-sm btn-apply" ${v.aplicada ? 'disabled' : ''} onclick="marcarAplicada(${v.id}, this)">
                ${v.aplicada ? 'Aplicada' : 'Aplicar'}
              </button>
              <button class="btn-sm" onclick="gerarCV(${v.id}, this)">CV</button>
            </div>
          </div>
        </div>`;
    }).join('');
  } catch (e) { console.error('loadTopVagas:', e); }
}

// ── VAGAS TABLE ───────────────────────────────────────────────────────────────
async function loadVagas() {
  try {
    const url = `/api/vagas?page=${State.vagasPage}&limit=${LIMIT}&status=${State.vagasFilter}&grade=${State.vagasGrade}&q=${encodeURIComponent(State.vagasSearch)}&fonte=${encodeURIComponent(State.vagasFonte)}`;
    const data = await fetchJSON(url);
    State.vagasTotal = data.total;

    const tbody = document.getElementById('vagas-tbody');
    tbody.innerHTML = data.vagas.map(v => {
      const earlyBadge = v.is_early ? '<span class="badge-early">JANELA</span>' : '';
      const suspBadge  = v.status === 'suspeita' ? '<span class="badge-susp">SUSPEITA</span>' : '';
      const methodTag  = v.score_method === 'semantic' ? '<sup title="Score semantico">AI</sup>' : '';
      const favLabel   = v.favorited ? '★' : '☆';
      const favExtra   = v.favorited ? ' fav-ativo on' : '';
      const favTitle   = v.favorited ? 'Remover favorito' : 'Favoritar';
      const dataCell   = v.data_aplicacao
        ? `<span title="Aplicada em">${esc(v.data_aplicacao)}</span>`
        : esc(v.data_encontrada);
      const ignoreBtn  = !v.aplicada && !v.ignored
        ? `<button class="btn-sm btn-ignore" onclick="ignorarVaga(${v.id}, ${JSON.stringify(v.titulo)})">Ignorar</button>`
        : '';
      const restoreBtn = v.ignored
        ? `<button class="btn-sm" onclick="restaurarVaga(${v.id})" title="Restaurar para Novas">↩</button>`
        : '';
      return `
        <tr id="job-row-${v.id}" class="${v.status === 'suspeita' ? 'row-suspicious' : ''}">
          <td>
            <span class="score-badge ${scoreClass(v.score)}">${v.score}${methodTag}</span>
            ${v.score_grade ? `<span class="grade-badge ${gradeClass(v.score_grade)}">${v.score_grade}</span>` : ''}
          </td>
          <td class="col-titulo" title="${esc(v.titulo)}">${esc(v.titulo)} ${earlyBadge} ${suspBadge}</td>
          <td>${esc(v.empresa)}</td>
          <td class="col-loc">${esc(v.localizacao)}</td>
          <td><span class="fonte-tag">${esc(v.fonte)}</span></td>
          <td>
            <select class="status-select" onchange="updateStatus(${v.id}, this.value)">
              ${Object.entries(STATUS_LABELS).map(([k, l]) =>
                `<option value="${k}" ${v.status === k ? 'selected' : ''}>${l}</option>`
              ).join('')}
            </select>
          </td>
          <td>${dataCell}</td>
          <td class="col-acoes">
            <a href="${esc(v.url)}" target="_blank" class="btn-sm btn-link">Abrir</a>
            <button class="btn-sm btn-assist" onclick="openAssistente(${v.id}, '${esc(v.titulo)}', '${esc(v.empresa)}', '${esc(v.fonte)}', '${esc(v.url)}')">Assistente</button>
            <button class="btn-sm btn-fav${favExtra}" id="fav-${v.id}" title="${favTitle}" onclick="toggleFavorito(${v.id}, this)">${favLabel}</button>
            ${ignoreBtn}${restoreBtn}
            <button class="btn-sm" onclick="gerarCV(${v.id}, this)">CV</button>
            <button class="btn-sm btn-feedback" onclick="openFeedbackModal(${v.id}, '${esc(v.titulo)}')">FB</button>
          </td>
        </tr>`;
    }).join('') || '<tr><td colspan="8" class="empty-row">Nenhuma vaga encontrada</td></tr>';

    const totalPages = Math.ceil(State.vagasTotal / LIMIT) || 1;
    document.getElementById('page-info').textContent = `Pag ${State.vagasPage} de ${totalPages} (${State.vagasTotal})`;
    document.getElementById('btn-prev').disabled = State.vagasPage <= 1;
    document.getElementById('btn-next').disabled = State.vagasPage >= totalPages;
  } catch (e) { console.error('loadVagas:', e); }
}

function setFilter(status, btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  State.vagasFilter = status;
  State.vagasPage = 1;
  loadVagas();
}

function setGradeFilter(grade, btn) {
  document.querySelectorAll('.grade-filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  State.vagasGrade = grade;
  State.vagasPage = 1;
  loadVagas();
}

function setFonteFilter(fonte, btn) {
  document.querySelectorAll('.fonte-filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  State.vagasFonte = fonte;
  State.vagasPage = 1;
  loadVagas();
}

function changePage(delta) {
  State.vagasPage += delta;
  loadVagas();
}

function debounceSearch() {
  clearTimeout(State.searchTimer);
  State.searchTimer = setTimeout(() => {
    State.vagasSearch = document.getElementById('search-vagas').value;
    State.vagasPage = 1;
    loadVagas();
  }, 350);
}

// ── CANDIDATURAS ──────────────────────────────────────────────────────────────
async function loadCandidaturas() {
  try {
    const data = await fetchJSON('/api/candidaturas');
    const tbody = document.getElementById('cand-tbody');
    tbody.innerHTML = data.map(c => `
      <tr>
        <td class="col-titulo" title="${esc(c.titulo)}">${esc(c.titulo)}</td>
        <td>${esc(c.empresa)}</td>
        <td>
          <select class="status-select" onchange="updateStatus(${c.id}, this.value)">
            ${Object.entries(STATUS_LABELS).map(([k, l]) =>
              `<option value="${k}" ${c.status === k ? 'selected' : ''}>${l}</option>`
            ).join('')}
          </select>
        </td>
        <td>${esc(c.data_aplicacao) || '—'}</td>
        <td>${esc(c.last_check) || '—'}</td>
        <td class="col-acoes">
          <a href="${esc(c.url)}" target="_blank" class="btn-sm btn-link">Abrir</a>
          <button class="btn-sm" onclick="openHistorico(${c.id})">Hist</button>
          <button class="btn-sm btn-feedback" onclick="openFeedbackModal(${c.id}, '${esc(c.titulo)}')">FB</button>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="6" class="empty-row">Nenhuma candidatura registrada</td></tr>';
  } catch (e) { console.error('loadCandidaturas:', e); }
}

// ── PERFIL ────────────────────────────────────────────────────────────────────
async function loadPerfil() {
  try {
    const [d, metrics] = await Promise.all([fetchJSON('/api/perfil'), fetchJSON('/api/stats')]);
    document.getElementById('p-score').textContent = metrics.media_score;
    document.getElementById('p-pct').textContent   = metrics.pct_acima_6 + '% das vagas com score acima de 6';
    document.getElementById('p-fortes').innerHTML  = d.fortes.map(k => `<span class="kw-tag kw-forte">${esc(k)}</span>`).join('');
    document.getElementById('p-medios').innerHTML  = d.medios.map(k => `<span class="kw-tag kw-medio">${esc(k)}</span>`).join('');

    const maxCount = Math.max(...d.top_keywords_vagas.map(x => x.count), 1);
    document.getElementById('p-demand').innerHTML = d.top_keywords_vagas.map(x => `
      <div class="kw-demand-item">
        <span class="kw-tag kw-demand">${esc(x.kw)}</span>
        <div class="kw-demand-bar-wrap"><div class="kw-demand-bar" style="width:${Math.round(x.count / maxCount * 100)}%"></div></div>
        <span class="kw-demand-count">${x.count}</span>
      </div>`).join('');
  } catch (e) { console.error('loadPerfil:', e); }
}

// ── CVs ───────────────────────────────────────────────────────────────────────
async function loadCVs() {
  try {
    const cvs = await fetchJSON('/api/cvs');
    const el = document.getElementById('cvs-list');

    if (!cvs.length) {
      el.innerHTML = '<p class="empty-msg">Nenhum CV gerado ainda. Clique em "CV" em qualquer vaga.</p>';
      return;
    }

    el.innerHTML = `
      <table>
        <thead><tr>
          <th>ID</th><th>Vaga</th><th>Empresa</th><th>Score</th><th>Gerado em</th><th>Arquivo</th><th>Acao</th>
        </tr></thead>
        <tbody>
          ${cvs.map(c => `
            <tr>
              <td>${c.id}</td>
              <td class="col-titulo">${esc(c.titulo)}</td>
              <td>${esc(c.empresa)}</td>
              <td><span class="score-badge ${scoreClass(c.score)}">${c.score}</span></td>
              <td>${(c.created_at || '').slice(0, 16)}</td>
              <td><span class="${c.exists ? 'badge-ok' : 'badge-missing'}">${c.exists ? 'OK' : 'AUSENTE'}</span></td>
              <td>
                ${c.exists ? `<a href="/api/cv/download/${c.id}" class="btn-sm btn-link">Download</a>` : '—'}
              </td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } catch (e) { console.error('loadCVs:', e); }
}

// ── FEEDBACK ──────────────────────────────────────────────────────────────────
async function loadFeedback() {
  try {
    const d = await fetchJSON('/api/feedback/summary');

    const por = d.por_outcome || {};
    document.getElementById('fb-total').textContent      = d.total_feedbacks || 0;
    document.getElementById('fb-entrevista').textContent = (por.entrevista?.count || 0) + ' (' + (d.taxa_entrevista || 0) + '%)';
    document.getElementById('fb-proposta').textContent   = (por.proposta?.count || 0) + ' (' + (d.taxa_proposta || 0) + '%)';
    document.getElementById('fb-rejeicao').textContent   = por.rejeicao?.count || 0;

    const tbody = document.getElementById('fb-tbody');
    const hist = d.historico || [];
    tbody.innerHTML = hist.map(h => `
      <tr>
        <td>${h.job_id}</td>
        <td class="col-titulo">${esc(h.titulo)}</td>
        <td>${esc(h.empresa)}</td>
        <td><span class="score-badge ${scoreClass(h.score || 0)}">${h.score || 0}</span></td>
        <td><span class="outcome-badge outcome-${h.outcome}">${h.outcome}</span></td>
        <td>${(h.data || '').slice(0, 10)}</td>
        <td>${esc(h.notes || '')}</td>
      </tr>`).join('') || '<tr><td colspan="7" class="empty-row">Nenhum feedback registrado</td></tr>';
  } catch (e) { console.error('loadFeedback:', e); }
}

async function calibrarScoring() {
  const btn = document.getElementById('btn-calibrar');
  btn.disabled = true;
  btn.textContent = 'Calibrando...';
  try {
    const r = await postJSON('/api/feedback/calibrate');
    if (r.status === 'calibrado') {
      showToast('Calibracao concluida! ' + (r.insight || ''));
      loadFeedback();
    } else {
      showToast(r.status === 'amostras_insuficientes'
        ? `Amostras insuficientes: ${r.amostras}/${r.minimo}`
        : r.erro || 'Erro na calibracao', true);
    }
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Recalibrar Agora';
  }
}

// ── MERCADO ───────────────────────────────────────────────────────────────────
async function loadMercado() {
  try {
    const report = await fetchJSON('/api/market/report');

    if (!report || !report.semana) {
      document.getElementById('mercado-content').innerHTML =
        '<p class="empty-msg">Nenhum relatorio gerado ainda. Clique em "Gerar Relatorio".</p>';
      return;
    }

    const topKws  = (report.top_keywords || []).slice(0, 12);
    const topEmp  = (report.top_empresas || []).slice(0, 10);
    const modal   = report.modalidade || {};
    const senior  = report.senioridade || {};
    const varSign = report.variacao_semana_pct >= 0 ? '+' : '';

    document.getElementById('mercado-content').innerHTML = `
      <div class="mercado-grid">
        <div class="panel">
          <div class="section-title">Resumo da Semana ${esc(report.semana)}</div>
          <div class="mercado-stats">
            <div class="mstat"><span class="mstat-val">${report.total_vagas}</span><span class="mstat-label">Vagas coletadas</span></div>
            <div class="mstat"><span class="mstat-val">${report.score_medio}</span><span class="mstat-label">Score medio</span></div>
            <div class="mstat"><span class="mstat-val ${report.variacao_semana_pct >= 0 ? 'var-pos' : 'var-neg'}">${varSign}${report.variacao_semana_pct}%</span><span class="mstat-label">vs semana anterior</span></div>
          </div>
        </div>

        <div class="panel">
          <div class="section-title">Top Keywords</div>
          <div class="kw-cloud">
            ${topKws.map(k => `<span class="kw-tag kw-demand" title="${k.count}x">${esc(k.keyword)}</span>`).join('')}
          </div>
        </div>

        <div class="panel">
          <div class="section-title">Top Empresas Contratando</div>
          ${topEmp.map((e, i) => `
            <div class="empresa-row">
              <span class="empresa-rank">${i + 1}</span>
              <span class="empresa-nome">${esc(e.empresa)}</span>
              <span class="empresa-count">${e.vagas} vagas</span>
            </div>`).join('')}
        </div>

        <div class="panel">
          <div class="section-title">Distribuicao por Modalidade</div>
          ${Object.entries(modal).map(([k, v]) => `
            <div class="dist-row">
              <span class="dist-label">${k.charAt(0).toUpperCase() + k.slice(1)}</span>
              <div class="dist-bar-wrap"><div class="dist-bar" style="width:${Math.round(v / (report.total_vagas || 1) * 100)}%"></div></div>
              <span class="dist-val">${v}</span>
            </div>`).join('')}
        </div>

        <div class="panel">
          <div class="section-title">Senioridade Demandada</div>
          ${Object.entries(senior).map(([k, v]) => `
            <div class="dist-row">
              <span class="dist-label">${k.charAt(0).toUpperCase() + k.slice(1)}</span>
              <div class="dist-bar-wrap"><div class="dist-bar dist-bar-2" style="width:${Math.round(v / (report.total_vagas || 1) * 100)}%"></div></div>
              <span class="dist-val">${v}</span>
            </div>`).join('')}
        </div>
      </div>`;
  } catch (e) { console.error('loadMercado:', e); }
}

async function gerarRelatorioMercado() {
  const btn = document.getElementById('btn-gerar-relatorio');
  btn.disabled = true;
  btn.textContent = 'Gerando...';
  try {
    await postJSON('/api/market/generate');
    showToast('Relatorio gerado!');
    loadMercado();
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Gerar Relatorio';
  }
}

// ── CONFIG ────────────────────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const [r, stats, cfg] = await Promise.all([
      fetchJSON('/api/config/profile'),
      fetchJSON('/api/stats'),
      fetchJSON('/api/config/settings'),
    ]);
    if (r.ok) document.getElementById('profile-editor').value = r.content;
    document.getElementById('cfg-cycle').textContent = stats.cycle_running ? 'Rodando' : 'Aguardando';
    if (cfg.ok) {
      const ms = document.getElementById('cfg-min-score');
      const ci = document.getElementById('cfg-interval');
      if (ms) ms.value = cfg.min_score_notify;
      if (ci) ci.value = cfg.check_interval_hours;
    }
  } catch (e) { console.error('loadConfig:', e); }

  try {
    const li = await fetchJSON('/api/profile/linkedin');
    if (li.ok && li.profile && li.profile.name) {
      _renderImportedProfile(li.profile, li.source || '', li.imported_at || '');
    }
  } catch (_) { /* sem perfil importado ainda */ }

  loadSchedulerStatus();
}

async function loadSchedulerStatus() {
  const el = document.getElementById('scheduler-jobs-list');
  if (!el) return;
  try {
    const d = await fetchJSON('/api/scheduler/status');
    el.innerHTML = d.jobs.map(j => `
      <div style="background:var(--bg2);border-radius:6px;padding:10px 14px;display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
        <div>
          <div style="font-size:13px;font-weight:600;color:var(--fg)">${esc(j.nome)}</div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px">${esc(j.descricao)}</div>
          <div style="font-size:11px;color:var(--accent);margin-top:4px">${esc(j.frequencia)}</div>
        </div>
        <div style="text-align:right;flex-shrink:0">
          <div style="font-size:10px;color:var(--muted)">Proxima execucao</div>
          <div style="font-size:12px;font-weight:600;color:var(--fg);white-space:nowrap">${esc(j.proxima_execucao)}</div>
        </div>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = '<div style="color:var(--muted);font-size:12px">Nao foi possivel carregar rotinas agendadas.</div>';
  }
}

async function saveProfile() {
  const content = document.getElementById('profile-editor').value;
  const btn = document.getElementById('btn-save-profile');
  btn.disabled = true;
  try {
    const r = await postJSON('/api/config/profile', { content });
    if (r.ok) showToast('Perfil salvo com sucesso!');
    else showToast(r.erro || 'Erro ao salvar', true);
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
  }
}

async function testarTelegram() {
  const btn = document.getElementById('btn-test-tg');
  btn.disabled = true;
  try {
    const r = await postJSON('/api/config/telegram-test');
    showToast(r.ok ? 'Telegram OK! Verifique seu chat.' : 'Falha no Telegram: ' + (r.erro || ''), !r.ok);
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
  }
}

async function executarManutencao() {
  const btn = document.getElementById('btn-manutencao');
  btn.disabled = true;
  btn.textContent = 'Executando...';
  try {
    const r = await postJSON('/api/maintenance');
    if (r.ok) {
      const rel = r.relatorio;
      showToast(`Manutencao OK: ${rel.duplicatas_removidas} dups removidas, ${rel.status_normalizados} status normalizados`);
    } else {
      showToast(r.erro || 'Erro na manutencao', true);
    }
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Executar Manutencao';
  }
}

// ── ASSISTENTE DE CANDIDATURA ─────────────────────────────────────────────────
let _assistJobId = null;

async function openAssistente(jobId, titulo, empresa, fonte, url) {
  _assistJobId = jobId;

  document.getElementById('assist-titulo').textContent = titulo;
  document.getElementById('assist-empresa').textContent = empresa;
  document.getElementById('assist-platform').textContent = fonte || '';
  document.getElementById('assist-platform').className = 'platform-badge platform-' + (fonte || '').toLowerCase();
  document.getElementById('assist-open-link').href = url || '#';
  document.getElementById('assist-pct').textContent = '...';
  document.getElementById('assist-bar').style.width = '0%';
  document.getElementById('assist-analysis').textContent = '';
  document.getElementById('assist-matched').innerHTML = '';
  document.getElementById('assist-missing').innerHTML = '';
  document.getElementById('assist-steps-section').style.display = 'none';
  document.getElementById('assist-fields-section').style.display = 'none';
  document.getElementById('assist-respostas').innerHTML = '<em style="color:var(--muted);font-size:12px">Carregando...</em>';

  document.getElementById('modal-assist').classList.add('show');

  try {
    const d = await fetchJSON(`/api/assist/${jobId}`);

    const exp = d.explanation || {};
    const pct = exp.match_pct || 0;
    document.getElementById('assist-pct').textContent = pct + '%';
    document.getElementById('assist-bar').style.width = pct + '%';
    document.getElementById('assist-analysis').textContent = exp.analysis || exp.recommendation || '';

    const matched = exp.matched || [];
    const missing = exp.missing || [];
    document.getElementById('assist-matched').innerHTML = matched.length
      ? '<div>' + matched.map(k => `<span class="kw-matched">${esc(k)}</span>`).join('') + '</div>'
      : '';
    document.getElementById('assist-missing').innerHTML = missing.length
      ? '<div>' + missing.map(k => `<span class="kw-missing">${esc(k)}</span>`).join('') + '</div>'
      : '';

    const assist = d.assist || {};

    const steps = assist.steps || [];
    if (steps.length) {
      document.getElementById('assist-steps').innerHTML = steps.map(s => `<li>${esc(s)}</li>`).join('');
      document.getElementById('assist-steps-section').style.display = '';
    }

    const fields = assist.prefill_fields || [];
    if (fields.length) {
      document.getElementById('assist-fields').innerHTML = fields.map((f, i) => {
        const fid = `assist-field-${i}`;
        const inputEl = f.type === 'textarea'
          ? `<textarea id="${fid}" class="prefill-value" readonly rows="3">${esc(f.value)}</textarea>`
          : `<input type="text" id="${fid}" class="prefill-value" readonly value="${esc(f.value)}">`;
        return `
          <div class="prefill-item">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px">
              <label class="prefill-label">${esc(f.label)}</label>
              <button class="btn-sm prefill-copy-btn" onclick="copiarCampo('${fid}', this)" title="Copiar">&#8855;</button>
            </div>
            ${inputEl}
            ${f.note ? `<div style="font-size:11px;color:var(--muted)">${esc(f.note)}</div>` : ''}
          </div>`;
      }).join('');
      document.getElementById('assist-fields-section').style.display = '';
    }

    const respostas = assist.respostas_comuns || [];
    document.getElementById('assist-respostas').innerHTML = respostas.length
      ? respostas.map((r, i) => {
          const rid = `assist-resp-${i}`;
          return `
            <div class="resposta-item" style="margin-bottom:10px">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px">
                <div style="font-size:12px;font-weight:600;color:var(--accent)">${esc(r.pergunta)}</div>
                <button class="btn-sm prefill-copy-btn" onclick="copiarCampo('${rid}', this)" title="Copiar">&#8855;</button>
              </div>
              <textarea id="${rid}" class="prefill-value" readonly rows="2" style="width:100%">${esc(r.resposta)}</textarea>
            </div>`;
        }).join('')
      : '<em style="color:var(--muted);font-size:12px">Nenhuma resposta sugerida disponivel.</em>';

  } catch (e) {
    document.getElementById('assist-respostas').innerHTML =
      `<em style="color:var(--red);font-size:12px">Erro ao carregar: ${esc(e.message)}</em>`;
  }
}

async function confirmarCandidatura() {
  if (!_assistJobId) return;
  const btn = document.getElementById('assist-apply-btn');
  btn.disabled = true;
  btn.textContent = 'Registrando...';
  try {
    const r = await postJSON(`/api/apply/${_assistJobId}`, { level: 2 });
    if (r.ok) {
      showToast('Candidatura registrada com sucesso!', false, 5000);
      closeModal();
      await refreshAll();
    } else {
      showToast(r.error || 'Erro ao registrar candidatura', true);
    }
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Confirmar Candidatura';
  }
}

// ── FAVORITO / IGNORAR ────────────────────────────────────────────────────────
async function toggleFavorito(jobId, btn) {
  try {
    const r = await fetch(`/api/vagas/${jobId}/favorite`, { method: 'POST' });
    if (!r.ok) { showToast('Erro ao favoritar', true); return; }
    const data = await r.json();
    const ativo = data.favorito === true;
    btn.classList.toggle('fav-ativo', ativo);
    btn.classList.toggle('on', ativo);
    btn.setAttribute('title', ativo ? 'Remover favorito' : 'Favoritar');
    btn.innerHTML = ativo ? '★' : '☆';
    showToast(ativo ? 'Vaga favoritada' : 'Favorito removido', false, 3000);
  } catch (e) { showToast('Erro: ' + e.message, true); }
}

function removerLinhaVaga(jobId) {
  const row = document.getElementById('job-row-' + jobId);
  if (row) row.remove();
  State.vagasTotal = Math.max(0, State.vagasTotal - 1);
}

async function ignorarVaga(jobId, titulo) {
  const confirmou = confirm(
    `Ignorar "${titulo || 'esta vaga'}"?\n\n` +
    `Ela sera movida para "Ignoradas" e nao aparecera mais.\n` +
    `Voce pode recupera-la depois se quiser.`
  );
  if (!confirmou) return;
  try {
    const r = await postJSON(`/api/vagas/${jobId}/ignore`);
    if (r.ok) {
      showToast('Vaga ignorada. Acesse "Ignoradas" para desfazer.', false, 5000);
      removerLinhaVaga(jobId);
      loadMetrics();
    }
  } catch (e) { showToast('Erro: ' + e.message, true); }
}

async function restaurarVaga(jobId) {
  try {
    const r = await postJSON(`/api/vagas/${jobId}/restore`);
    if (r.ok) {
      showToast('Vaga restaurada para Novas!');
      removerLinhaVaga(jobId);
      loadMetrics();
    } else showToast('Erro ao restaurar', true);
  } catch (e) { showToast('Erro: ' + e.message, true); }
}

function copiarCampo(inputId, btn) {
  const el = document.getElementById(inputId);
  const val = el ? (el.value || el.textContent || '') : '';
  navigator.clipboard.writeText(val).then(() => {
    const orig = btn.innerHTML;
    btn.innerHTML = '✓';
    btn.style.color = '#639922';
    setTimeout(() => { btn.innerHTML = orig; btn.style.color = ''; }, 2000);
  }).catch(() => showToast('Nao foi possivel copiar', true));
}

// ── LINKEDIN / PERFIL MANUAL ──────────────────────────────────────────────────
async function importarLinkedIn() {
  const url = (document.getElementById('li-url-input').value || '').trim();
  if (!url) { showToast('Informe a URL do perfil LinkedIn', true); return; }

  const btn = document.getElementById('btn-li-extract');
  btn.disabled = true;
  btn.textContent = 'Extraindo...';

  try {
    const r = await postJSON('/api/profile/linkedin', { url });
    if (r.ok) {
      showToast(r.message || 'Perfil importado!');
      _renderImportedProfile(r.profile, r.source || 'linkedin', r.imported_at || '');
    } else if (r.blocked) {
      showToast(r.sugestao || 'LinkedIn bloqueou o acesso automatico. Preencha manualmente.', true, 5000);
      const urlVal = (document.getElementById('li-url-input').value || '').trim();
      const slug = urlVal.replace(/\/+$/, '').split('/').pop() || '';
      setTimeout(() => {
        const form = document.getElementById('li-manual-form');
        form.classList.add('show');
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (slug) {
          const nameFromSlug = slug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
          const nameEl = document.getElementById('li-name');
          if (!nameEl.value) nameEl.value = nameFromSlug;
        }
      }, 1000);
    } else {
      showToast(r.error || 'Falha ao importar perfil', true);
    }
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Extrair Perfil';
  }
}

function toggleManualForm() {
  document.getElementById('li-manual-form').classList.toggle('show');
}

async function salvarManual() {
  const name     = document.getElementById('li-name').value.trim();
  const headline = document.getElementById('li-headline').value.trim();
  const location = document.getElementById('li-location').value.trim();
  const exp_years= parseInt(document.getElementById('li-exp').value) || 0;
  const skills   = document.getElementById('li-skills').value.trim();
  const idiomas  = (document.getElementById('li-idiomas')?.value || '').trim();
  const about    = document.getElementById('li-about').value.trim();

  if (!name) { showToast('Informe pelo menos seu nome', true); return; }

  try {
    const r = await postJSON('/api/profile/linkedin', {
      manual: { name, headline, location, exp_years, skills, idiomas, about }
    });
    if (r.ok) {
      showToast(r.message || 'Perfil salvo com sucesso!');
      _renderImportedProfile(r.profile, 'manual', '');
      document.getElementById('li-manual-form').classList.remove('show');
    } else {
      showToast(r.error || 'Erro ao salvar perfil', true);
    }
  } catch (e) { showToast('Erro: ' + e.message, true); }
}

function _renderImportedProfile(profile, source, importedAt) {
  if (!profile) return;
  const el = document.getElementById('li-imported');
  document.getElementById('li-imp-name').textContent = profile.name || '—';
  document.getElementById('li-imp-headline').textContent = profile.headline || '';
  const skills = Array.isArray(profile.skills)
    ? profile.skills.slice(0, 8).join(', ')
    : (typeof profile.skills === 'object' ? Object.values(profile.skills || {}).flat().slice(0, 8).join(', ') : '');
  document.getElementById('li-imp-skills').textContent = skills || '';
  document.getElementById('li-imp-date').textContent = `Fonte: ${source}${importedAt ? ' | ' + importedAt.slice(0, 16) : ''}`;
  el.style.display = 'block';
}

// ── EVOLUCAO ──────────────────────────────────────────────────────────────────
async function loadEvolution() {
  try {
    const data = await fetchJSON('/api/stats/evolution');
    const panel = document.getElementById('evo-panel');
    const chart = document.getElementById('evo-chart');
    if (!data.length) { panel.style.display = 'none'; return; }

    const maxApl = Math.max(...data.map(d => d.aplicadas), 1);
    chart.innerHTML = data.map(d => {
      const h = Math.round(d.aplicadas / maxApl * 80);
      const ph = d.aplicadas > 0 ? Math.round(d.positivas / d.aplicadas * 80) : 0;
      return `
        <div class="evo-col" title="${esc(d.semana)}: ${d.aplicadas} aplicadas, ${d.positivas} positivas">
          <div class="evo-bar-wrap" style="height:80px;display:flex;align-items:flex-end;gap:1px">
            <div class="evo-bar" style="height:${h}px;background:var(--accent);width:14px;border-radius:2px 2px 0 0"></div>
            <div class="evo-bar-pos" style="height:${ph}px;background:var(--green);width:8px;border-radius:2px 2px 0 0"></div>
          </div>
          <div class="evo-label" style="font-size:9px;color:var(--muted);text-align:center;margin-top:2px">${esc((d.semana || '').slice(5))}</div>
        </div>`;
    }).join('');
    panel.style.display = 'block';
  } catch (e) { console.error('loadEvolution:', e); }
}

// ── ACOES ─────────────────────────────────────────────────────────────────────
async function marcarAplicada(id, btn) {
  btn.disabled = true;
  try {
    const r = await postJSON('/api/marcar-aplicada', { id });
    if (r.ok) { showToast('Candidatura registrada!'); await refreshAll(); }
    else { showToast(r.erro || 'Erro ao marcar', true); btn.disabled = false; }
  } catch (e) {
    showToast('Erro: ' + e.message, true);
    btn.disabled = false;
  }
}

async function updateStatus(id, status) {
  try {
    const r = await postJSON('/api/atualizar-status', { id, status });
    if (r.ok) {
      showToast('Status: ' + (STATUS_LABELS[status] || status));
      loadMetrics(); loadPipeline(); loadCandidaturas();
    } else showToast(r.erro || 'Erro', true);
  } catch (e) { showToast('Erro: ' + e.message, true); }
}

async function gerarCV(jobId, btn) {
  btn.disabled = true;
  btn.textContent = '...';
  try {
    const r = await postJSON(`/api/cv/${jobId}`);
    if (r.ok) {
      showToast('CV gerado: ' + r.filename);
      if (State.activeTab === 'cvs') loadCVs();
    } else showToast(r.erro || 'Falha ao gerar CV', true);
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'CV';
  }
}

async function triggerCiclo() {
  const btn = document.getElementById('btn-trigger');
  btn.disabled = true;
  btn.textContent = 'Iniciando...';
  try {
    const r = await postJSON('/api/trigger');
    showToast(r.msg || (r.ok ? 'Ciclo iniciado!' : 'Erro'), !r.ok);
  } catch (e) {
    showToast('Erro: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Rodar Agora';
  }
}

// ── MODAL HISTÓRICO ───────────────────────────────────────────────────────────
async function openHistorico(id) {
  try {
    const d = await fetchJSON('/api/historico/' + id);
    document.getElementById('modal-titulo').textContent  = d.vaga.titulo || 'Vaga';
    document.getElementById('modal-empresa').textContent = d.vaga.empresa || '';
    document.getElementById('modal-timeline').innerHTML  = d.historico.length
      ? d.historico.map(h => `
          <div class="timeline-item">
            <div class="tl-dot"></div>
            <div class="tl-content">
              <div class="tl-ts">${esc(h.timestamp)}</div>
              <div class="tl-evt">${esc(h.status_old || '—')} &rarr; <strong>${esc(STATUS_LABELS[h.status_new] || h.status_new)}</strong></div>
              ${h.detalhes ? `<div class="tl-det">${esc(h.detalhes)}</div>` : ''}
            </div>
          </div>`).join('')
      : '<p class="empty-msg">Nenhum historico registrado.</p>';

    document.getElementById('modal-hist').classList.add('show');
  } catch (e) { console.error('openHistorico:', e); }
}

function closeModal() {
  document.getElementById('modal-hist').classList.remove('show');
  document.getElementById('modal-feedback').classList.remove('show');
  document.getElementById('modal-assist').classList.remove('show');
  _assistJobId = null;
}

// ── MODAL FEEDBACK ────────────────────────────────────────────────────────────
let _feedbackJobId = null;

function openFeedbackModal(jobId, titulo) {
  _feedbackJobId = jobId;
  document.getElementById('fb-modal-titulo').textContent = titulo;
  document.getElementById('fb-outcome').value = 'entrevista';
  document.getElementById('fb-notes').value = '';
  document.getElementById('modal-feedback').classList.add('show');
}

async function submitFeedback() {
  if (!_feedbackJobId) return;
  const outcome = document.getElementById('fb-outcome').value;
  const notes   = document.getElementById('fb-notes').value;

  try {
    const r = await postJSON(`/api/feedback/${_feedbackJobId}`, { outcome, notes });
    if (r.ok) {
      showToast('Feedback registrado!');
      closeModal();
      if (State.activeTab === 'feedback') loadFeedback();
    } else showToast(r.erro || 'Erro ao registrar', true);
  } catch (e) { showToast('Erro: ' + e.message, true); }
}

// ── REFRESH ───────────────────────────────────────────────────────────────────
async function salvarConfigNumerica() {
  const minScore = parseFloat(document.getElementById('cfg-min-score')?.value);
  const interval = parseInt(document.getElementById('cfg-interval')?.value);
  const btn = document.getElementById('btn-salvar-cfg');
  if (btn) { btn.disabled = true; btn.textContent = 'Salvando...'; }
  try {
    const body = {};
    if (!isNaN(minScore)) body.min_score_notify = minScore;
    if (!isNaN(interval)) body.check_interval_hours = interval;
    const r = await postJSON('/api/config/settings', body);
    if (r.ok) showToast(r.aviso || 'Configuracoes salvas!', false, 5000);
    else showToast(r.erro || 'Erro ao salvar', true);
  } catch (e) { showToast('Erro: ' + e.message, true); }
  finally { if (btn) { btn.disabled = false; btn.textContent = 'Salvar'; } }
}

async function refreshAll() {
  await Promise.all([
    loadMetrics(),
    loadPipeline(),
    loadTopVagas(),
    loadVagas(),
    loadCandidaturas(),
    loadPerfil(),
    loadEvolution(),
  ]);
}

// ── INIT ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Modal close on overlay click
  document.getElementById('modal-hist').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.getElementById('modal-feedback').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.getElementById('modal-assist').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });

  refreshAll();
  setInterval(refreshAll, 30000);
});
