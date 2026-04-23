let globalStats = null;
let charts = {};
let tableData = [];
let currentView = 'date';
let fichierActif = null;
let fichierActifNom = null;
let pendingMappingData = null;

// ── NAVIGATION ──
function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn,.mobile-nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('section-' + name).classList.add('active');
  document.querySelectorAll(`.nav-btn[onclick*="'${name}'"],.mobile-nav-btn[onclick*="'${name}'"]`).forEach(b => b.classList.add('active'));
  if (name === 'historique')  loadHistorique();
  if (name === 'alertes')     loadAlertes();
  if (name === 'previsions')  loadPrevisions();
  if (name === 'clients')     loadClients();
  if (name === 'vendeurs')    loadVendeurs();
  if (name === 'saisie')      loadSaisieHistory();
  if (name === 'carte')       loadCarte();
}

function toggleMobileNav() {
  document.getElementById('mobile-nav').classList.toggle('open');
  document.getElementById('hamburger').classList.toggle('open');
}
function closeMobileNav() {
  document.getElementById('mobile-nav').classList.remove('open');
  document.getElementById('hamburger').classList.remove('open');
}
document.addEventListener('click', e => {
  const nav = document.getElementById('mobile-nav');
  const burger = document.getElementById('hamburger');
  if (nav && nav.classList.contains('open') && !nav.contains(e.target) && !burger.contains(e.target)) closeMobileNav();
});

// ── DRAG & DROP ──
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('drag-over'); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); });
fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });

// ── UPLOAD ──
async function handleFile(file) {
  const pw = document.getElementById('progress-wrap');
  const pf = document.getElementById('progress-fill');
  const pt = document.getElementById('progress-text');
  pw.style.display = 'block';
  pt.textContent = 'Lecture de "' + file.name + '"...';
  let pct = 0;
  const iv = setInterval(() => { pct = Math.min(pct + 15, 90); pf.style.width = pct + '%'; }, 100);
  const form = new FormData();
  form.append('file', file);
  try {
    const res  = await fetch('/upload', { method: 'POST', body: form });
    const data = await res.json();
    clearInterval(iv);
    pf.style.width = '100%';
    setTimeout(() => { pw.style.display = 'none'; pf.style.width = '0%'; }, 400);
    if (!res.ok || data.error) { showToast('Erreur : ' + (data.error||'Inconnue'), 'error'); return; }
    if (data.need_mapping) {
      pendingMappingData = data;
      afficherMapping(data);
    }
  } catch (e) {
    clearInterval(iv);
    showToast('Erreur serveur', 'error');
  }
}

// ── MAPPING ──
const CHAMPS_LABELS = {
  '':             '-- Ignorer cette colonne --',
  'date':         'Date',
  'produit':      'Produit *',
  'quantite':     'Quantite *',
  'prix':         'Prix de vente *',
  'categorie':    'Categorie',
  'cout':         "Cout d'achat",
  'ville':        'Ville',
  'vendeur':      'Vendeur',
  'client':       'Client',
  'mode_paiement':'Mode Paiement',
  'statut':       'Statut',
};

function afficherMapping(data) {
  // Apercu
  document.getElementById('mapping-rows-count').textContent = data.rows + ' lignes detectees';
  const cols = data.colonnes;
  document.getElementById('apercu-head').innerHTML =
    '<tr>' + cols.map(c => `<th style="white-space:nowrap">${c}</th>`).join('') + '</tr>';
  document.getElementById('apercu-body').innerHTML =
    data.apercu.map(row =>
      '<tr>' + cols.map(c => `<td style="white-space:nowrap;max-width:100px;overflow:hidden;text-overflow:ellipsis">${row[c]||'—'}</td>`).join('') + '</tr>'
    ).join('');

  // Mapping selects
  const grid = document.getElementById('mapping-grid');
  grid.innerHTML = cols.map(col => {
    const val  = data.mapping_auto[col] || '';
    const isR  = ['produit','quantite','prix'].includes(val);
    const bc   = val ? (isR ? '#059669' : '#2563eb') : '#dde1ea';
    const opts = Object.entries(CHAMPS_LABELS).map(([v,l]) =>
      `<option value="${v}" ${val===v?'selected':''}>${l}</option>`).join('');
    const prev = data.apercu[0] ? String(data.apercu[0][col]||'').substring(0,20) : '';
    return `<div style="display:flex;flex-direction:column;gap:5px">
      <div style="display:flex;justify-content:space-between">
        <span style="font-size:11px;font-weight:700;color:#475569">${col}</span>
        <span style="font-size:10px;color:#94a3b8">ex: ${prev}</span>
      </div>
      <select data-col="${col}" style="background:#f8fafc;border:2px solid ${bc};color:#1a1f2e;padding:9px 12px;border-radius:8px;font-family:'Syne',sans-serif;font-size:13px;outline:none;transition:border-color 0.2s"
        onchange="this.style.borderColor=this.value?(['produit','quantite','prix'].includes(this.value)?'#059669':'#2563eb'):'#dde1ea'">
        ${opts}
      </select>
    </div>`;
  }).join('');

  document.getElementById('mapping-error').style.display = 'none';
  showSection('mapping');
}

async function confirmerMapping() {
  const mapping = {};
  const used    = new Set();
  const errEl   = document.getElementById('mapping-error');
  let hasError  = false;

  document.querySelectorAll('#mapping-grid select').forEach(sel => {
    const col = sel.dataset.col;
    const val = sel.value;
    if (val) {
      if (used.has(val)) { errEl.textContent = 'Le champ "' + val + '" est utilise plusieurs fois.'; errEl.style.display = 'block'; hasError = true; return; }
      mapping[col] = val;
      used.add(val);
    }
  });
  if (hasError) return;

  const requis = ['quantite','prix'];
  const manquants = requis.filter(r => !used.has(r));
  if (manquants.length) { errEl.textContent = 'Champs obligatoires manquants : ' + manquants.join(', '); errEl.style.display = 'block'; return; }
  errEl.style.display = 'none';

  showToast('Analyse en cours...', 'success');
  const res  = await fetch('/confirmer_mapping', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mapping}) });
  const data = await res.json();
  if (!res.ok || data.error) { showToast('Erreur : '+(data.error||'Inconnue'), 'error'); return; }
  globalStats     = data.stats;
  fichierActif    = data.fichier_id;
  fichierActifNom = data.filename || 'fichier importe';
  pendingMappingData = null;
  activateDashboard(data.stats);
  showToast(data.rows + ' lignes importees !', 'success');
}

// ── ENABLE NAV ──
function enableNav() {
  ['nav-dashboard','nav-data','nav-comp','nav-alertes','nav-prev','nav-clients','nav-vendeurs','nav-carte'].forEach(id => { const el = document.getElementById(id); if (el) el.disabled = false; });
  const ez = document.getElementById('export-zone'); if (ez) ez.style.display = 'flex';
  ['mob-dashboard','mob-alertes','mob-comp','mob-data','mob-prev','mob-clients','mob-vendeurs','mob-carte'].forEach(id => { const el = document.getElementById(id); if (el) el.disabled = false; });
  const me = document.getElementById('mob-export'); if (me) me.style.display = 'flex';
}

function activateDashboard(stats) {
  enableNav(); updateFichierBar();
  populateFilters(stats); renderKPIs(stats.kpis);
  renderAllCharts(stats); tableData = stats.raw; renderTable(tableData);
  showSection('dashboard');
}

function updateFichierBar() {
  const bar = document.getElementById('fichier-actif-bar');
  const nom = document.getElementById('fichier-actif-nom');
  if (bar && fichierActifNom) { bar.style.display = 'flex'; nom.textContent = fichierActifNom; }
}

// ── FILTRES ──
function populateFilters(stats) {
  const vs = document.getElementById('f-ville'); const vp = document.getElementById('f-produit');
  if (vs) { vs.innerHTML = '<option value="">Toutes</option>'; (stats.villes||[]).forEach(v => vs.innerHTML += `<option value="${v}">${v}</option>`); }
  if (vp) { vp.innerHTML = '<option value="">Tous</option>'; (stats.produits||[]).forEach(p => vp.innerHTML += `<option value="${p}">${p}</option>`); }
}
async function applyFilters() {
  const params = new URLSearchParams();
  const dd = document.getElementById('f-date-debut').value;
  const df = document.getElementById('f-date-fin').value;
  const v  = document.getElementById('f-ville').value;
  const p  = document.getElementById('f-produit').value;
  if (fichierActif) params.append('fichier_id', fichierActif);
  if (dd) params.append('date_debut', dd); if (df) params.append('date_fin', df);
  if (v)  params.append('ville', v);       if (p)  params.append('produit', p);
  const res = await fetch('/stats?' + params.toString());
  if (!res.ok) { showToast('Aucun resultat', 'error'); return; }
  const data = await res.json();
  renderKPIs(data.kpis); renderAllCharts(data); tableData = data.raw; renderTable(tableData);
}
function resetFilters() {
  ['f-date-debut','f-date-fin'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  ['f-ville','f-produit'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  if (globalStats) { renderKPIs(globalStats.kpis); renderAllCharts(globalStats); tableData = globalStats.raw; renderTable(tableData); }
}

// ── KPIs ──
function renderKPIs(kpis) {
  const fmt = n => new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const defs = [
    {icon:'CA',  label:"Chiffre d'Affaires", value:fmt(kpis.total_ca)+' FCFA',          color:'#2563eb'},
    {icon:'BEN', label:'Benefice Total',      value:fmt(kpis.total_benefice)+' FCFA',    color:'#059669'},
    {icon:'QTE', label:'Unites Vendues',      value:fmt(kpis.total_ventes),              color:'#7c3aed'},
    {icon:'TRX', label:'Transactions',        value:fmt(kpis.nb_transactions),           color:'#d97706'},
    {icon:'MGE', label:'Marge',               value:(kpis.marge_pct||0).toFixed(1)+'%', color:'#0891b2'},
    {icon:'TOP', label:'Top Produit',         value:kpis.top_produit,                    color:'#dc2626'},
  ];
  const grid = document.getElementById('kpis-grid'); if (!grid) return;
  grid.innerHTML = defs.map(k => `
    <div class="kpi-card" style="--kpi-color:${k.color}">
      <div class="kpi-badge" style="background:${k.color}18;color:${k.color}">${k.icon}</div>
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value">${k.value}</div>
    </div>`).join('');
}

// ── CHARTS ──
const PAL = ['#2563eb','#7c3aed','#059669','#d97706','#dc2626','#0891b2','#65a30d','#ea580c','#9333ea','#db2777'];
function destroyChart(id) { if (charts[id]) { charts[id].destroy(); delete charts[id]; } }

function renderAllCharts(stats) {
  renderEvolutionChart(stats, currentView);
  renderProduitChart(stats);
  renderVilleChart(stats);
  renderCAProduitChart(stats);
}

function chartOpts(label, gridX=false) {
  return { responsive:true, plugins:{ legend:{display:false}, tooltip:{ callbacks:{label:ctx=>' '+new Intl.NumberFormat('fr-FR').format(Math.round(ctx.parsed.y??ctx.parsed))+(label.includes('CA')||label.includes('Benefice')?' FCFA':'')}, backgroundColor:'white', borderColor:'#e2e8f0', borderWidth:1, titleColor:'#1a1f2e', bodyColor:'#64748b', padding:12, cornerRadius:8 } }, scales:{ x:{grid:{color:gridX?'#f1f5f9':'transparent'}, ticks:{color:'#94a3b8',font:{family:'Syne',size:10},maxRotation:35}, border:{color:'#e2e8f0'}}, y:{grid:{color:'#f1f5f9'}, ticks:{color:'#94a3b8',font:{family:'Space Mono',size:10}, callback:v=>new Intl.NumberFormat('fr-FR',{notation:'compact'}).format(v)}, border:{color:'#e2e8f0'}} } };
}

function renderEvolutionChart(stats, view) {
  destroyChart('evolution');
  const data = view==='date' ? stats.par_date : stats.par_mois;
  const labels = data.map(d => d[view==='date'?'date':'mois']);
  const values = data.map(d => d.ca);
  const ctx = document.getElementById('chart-evolution').getContext('2d');
  const grad = ctx.createLinearGradient(0,0,0,260); grad.addColorStop(0,'rgba(37,99,235,0.15)'); grad.addColorStop(1,'rgba(37,99,235,0)');
  charts['evolution'] = new Chart(ctx, { type:'line', data:{ labels, datasets:[{ label:'CA', data:values, borderColor:'#2563eb', backgroundColor:grad, borderWidth:2, pointRadius:3, tension:0.4, fill:true }] }, options:chartOpts('CA (FCFA)') });
}
function renderProduitChart(stats) {
  destroyChart('produits');
  const top = stats.par_produit.slice(0,8);
  const ctx = document.getElementById('chart-produits').getContext('2d');
  charts['produits'] = new Chart(ctx, { type:'bar', data:{ labels:top.map(p=>p.produit), datasets:[{ label:'Quantite', data:top.map(p=>p.quantite), backgroundColor:top.map((_,i)=>PAL[i%PAL.length]+'22'), borderColor:top.map((_,i)=>PAL[i%PAL.length]), borderWidth:2, borderRadius:6 }] }, options:chartOpts('Quantite',true) });
}
function renderVilleChart(stats) {
  destroyChart('villes');
  const ctx = document.getElementById('chart-villes').getContext('2d');
  charts['villes'] = new Chart(ctx, { type:'doughnut', data:{ labels:stats.par_ville.map(v=>v.ville), datasets:[{ data:stats.par_ville.map(v=>v.ca), backgroundColor:stats.par_ville.map((_,i)=>PAL[i%PAL.length]), borderColor:'white', borderWidth:3, hoverOffset:6 }] }, options:{ responsive:true, plugins:{ legend:{position:'bottom',labels:{color:'#64748b',font:{family:'Syne',size:11},padding:12}}, tooltip:{callbacks:{label:ctx=>' '+new Intl.NumberFormat('fr-FR').format(ctx.parsed)+' FCFA'}} } } });
}
function renderCAProduitChart(stats) {
  destroyChart('ca-produit');
  const ctx = document.getElementById('chart-ca-produit').getContext('2d');
  charts['ca-produit'] = new Chart(ctx, { type:'bar', data:{ labels:stats.par_produit.map(p=>p.produit), datasets:[{ label:'CA', data:stats.par_produit.map(p=>p.ca), backgroundColor:stats.par_produit.map((_,i)=>PAL[i%PAL.length]+'22'), borderColor:stats.par_produit.map((_,i)=>PAL[i%PAL.length]), borderWidth:2, borderRadius:6 }] }, options:{...chartOpts('CA (FCFA)',true), indexAxis:'y'} });
}
function switchView(type, btn) {
  currentView = type;
  document.querySelectorAll('.ctrl-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderEvolutionChart(globalStats, type);
}

// ── VENDEURS ──
let vendeursData = [];
async function loadVendeurs() {
  const url = '/vendeurs'+(fichierActif?'?fichier_id='+fichierActif:'');
  const res = await fetch(url); const data = await res.json();
  vendeursData = data;
  const fmt = n => new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const total_ca = data.reduce((s,v)=>s+v.ca_total,0);
  const top_v    = data.length ? data[0].vendeur : '—';
  const COLORS   = ['#2563eb','#7c3aed','#059669','#d97706','#dc2626'];
  document.getElementById('vendeurs-kpis').innerHTML = `
    <div class="kpi-card" style="--kpi-color:#2563eb"><div class="kpi-badge" style="background:#2563eb18;color:#2563eb">NB</div><div class="kpi-label">Nb Vendeurs</div><div class="kpi-value">${data.length}</div></div>
    <div class="kpi-card" style="--kpi-color:#059669"><div class="kpi-badge" style="background:#05996918;color:#059669">CA</div><div class="kpi-label">CA Total</div><div class="kpi-value">${fmt(total_ca)} FCFA</div></div>
    <div class="kpi-card" style="--kpi-color:#7c3aed"><div class="kpi-badge" style="background:#7c3aed18;color:#7c3aed">BEN</div><div class="kpi-label">Benefice Total</div><div class="kpi-value">${fmt(data.reduce((s,v)=>s+v.benefice,0))} FCFA</div></div>
    <div class="kpi-card" style="--kpi-color:#d97706"><div class="kpi-badge" style="background:#d9770618;color:#d97706">TOP</div><div class="kpi-label">Meilleur Vendeur</div><div class="kpi-value" style="font-size:15px">${top_v}</div></div>`;
  destroyChart('vendeur-ca'); destroyChart('vendeur-ben');
  const ctx1 = document.getElementById('chart-vendeur-ca').getContext('2d');
  charts['vendeur-ca'] = new Chart(ctx1, { type:'bar', data:{ labels:data.map(v=>v.vendeur), datasets:[{ label:'CA', data:data.map(v=>v.ca_total), backgroundColor:data.map((_,i)=>COLORS[i%COLORS.length]+'22'), borderColor:data.map((_,i)=>COLORS[i%COLORS.length]), borderWidth:2, borderRadius:6 }] }, options:chartOpts('CA (FCFA)',true) });
  const ctx2 = document.getElementById('chart-vendeur-ben').getContext('2d');
  charts['vendeur-ben'] = new Chart(ctx2, { type:'bar', data:{ labels:data.map(v=>v.vendeur), datasets:[{ label:'Benefice', data:data.map(v=>v.benefice), backgroundColor:data.map((_,i)=>COLORS[i%COLORS.length]+'22'), borderColor:data.map((_,i)=>COLORS[i%COLORS.length]), borderWidth:2, borderRadius:6 }] }, options:chartOpts('Benefice (FCFA)',true) });
  const body = document.getElementById('vendeurs-body');
  if (!data.length) { body.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:30px">Aucun vendeur detecte</td></tr>'; return; }
  body.innerHTML = data.map((v,i) => `
    <tr><td><div style="display:flex;align-items:center;gap:10px">
      <div style="width:32px;height:32px;border-radius:50%;background:${COLORS[i%COLORS.length]};display:grid;place-items:center;color:white;font-weight:800;font-size:13px">${v.vendeur.charAt(0)}</div>
      <strong>${v.vendeur}</strong></div></td>
      <td>${fmt(v.nb_ventes)}</td><td class="montant">${fmt(v.ca_total)} FCFA</td>
      <td style="color:#059669;font-family:'Space Mono',monospace;font-size:12px;font-weight:700">${fmt(v.benefice)} FCFA</td>
      <td>${fmt(v.panier_moyen)} FCFA</td><td>${fmt(v.nb_clients)}</td><td>${fmt(v.qte_totale)}</td>
    </tr>`).join('');
}

// ── CLIENTS ──
let clientsData = [];
let clientsSortDir = {};
async function loadClients() {
  const url = '/clients'+(fichierActif?'?fichier_id='+fichierActif:'');
  const res = await fetch(url); const data = await res.json();
  clientsData = data; renderClientsKPIs(data); renderClientsTable(data);
  document.getElementById('client-detail').style.display = 'none';
}
function renderClientsKPIs(data) {
  const fmt = n => new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const total_ca   = data.reduce((s,c)=>s+c.ca_total,0);
  const panier_moy = data.length ? data.reduce((s,c)=>s+c.panier_moyen,0)/data.length : 0;
  document.getElementById('clients-kpis').innerHTML = `
    <div class="kpi-card" style="--kpi-color:#2563eb"><div class="kpi-badge" style="background:#2563eb18;color:#2563eb">NB</div><div class="kpi-label">Total Clients</div><div class="kpi-value">${data.length}</div></div>
    <div class="kpi-card" style="--kpi-color:#059669"><div class="kpi-badge" style="background:#05996918;color:#059669">CA</div><div class="kpi-label">CA Total</div><div class="kpi-value">${fmt(total_ca)} FCFA</div></div>
    <div class="kpi-card" style="--kpi-color:#d97706"><div class="kpi-badge" style="background:#d9770618;color:#d97706">MOY</div><div class="kpi-label">Panier Moyen</div><div class="kpi-value">${fmt(panier_moy)} FCFA</div></div>
    <div class="kpi-card" style="--kpi-color:#dc2626"><div class="kpi-badge" style="background:#dc262618;color:#dc2626">TOP</div><div class="kpi-label">Meilleur Client</div><div class="kpi-value" style="font-size:14px">${data.length?data[0].client:'—'}</div></div>`;
}
function renderClientsTable(data) {
  const fmt = n => new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const body = document.getElementById('clients-body');
  if (!data.length) { body.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:30px">Aucun client detecte</td></tr>'; return; }
  body.innerHTML = data.map((c,i) => {
    const cls = i===0?'gold':i===1?'silver':i===2?'bronze':'normal';
    return `<tr>
      <td><div style="display:flex;align-items:center;gap:10px"><span class="client-rang ${cls}">${i+1}</span><strong>${c.client}</strong></div></td>
      <td>${c.nb_achats}</td><td class="montant">${fmt(c.ca_total)} FCFA</td>
      <td>${fmt(c.panier_moyen)} FCFA</td>
      <td style="color:#059669;font-family:'Space Mono',monospace;font-size:12px;font-weight:700">${fmt(c.benefice)} FCFA</td>
      <td style="color:var(--text-dim);font-size:12px">${c.derniere_date||'—'}</td>
      <td><button class="btn-detail" onclick="voirClient('${c.client.replace(/'/g,"\\'")}')">Voir</button></td>
    </tr>`;
  }).join('');
}
function filterClients() {
  const q = document.getElementById('client-search').value.toLowerCase();
  renderClientsTable(clientsData.filter(c => c.client.toLowerCase().includes(q)));
}
function sortClients(col) {
  const keys = ['client','nb_achats','ca_total','panier_moyen','benefice','derniere_date'];
  const key  = keys[col]; clientsSortDir[key] = !clientsSortDir[key];
  renderClientsTable([...clientsData].sort((a,b) => { const va=isNaN(a[key])?String(a[key]):Number(a[key]); const vb=isNaN(b[key])?String(b[key]):Number(b[key]); return clientsSortDir[key]?(va<vb?-1:va>vb?1:0):(va>vb?-1:va<vb?1:0); }));
}
async function voirClient(nom) {
  const url = '/clients/'+encodeURIComponent(nom)+'/achats'+(fichierActif?'?fichier_id='+fichierActif:'');
  const res = await fetch(url); const data = await res.json();
  const fmt = n => new Intl.NumberFormat('fr-FR').format(Math.round(n));
  document.getElementById('client-detail-nom').textContent = 'Historique de ' + nom;
  document.getElementById('client-detail').style.display = 'block';
  document.getElementById('client-detail').scrollIntoView({behavior:'smooth'});
  const sb = s => { if(!s||s==='N/A') return '<span class="badge-statut default">—</span>'; const sl=s.toLowerCase(); const cls=sl.includes('pay')?'paye':sl.includes('att')?'attente':sl.includes('ann')?'annule':'default'; return `<span class="badge-statut ${cls}">${s}</span>`; };
  document.getElementById('client-achats-body').innerHTML = data.map(row => `
    <tr><td>${row.date||'—'}</td><td><strong>${row.produit||'—'}</strong></td>
    <td><span class="badge-ville">${row.categorie||'—'}</span></td>
    <td>${fmt(row.quantite)}</td><td>${fmt(row.prix)} FCFA</td>
    <td class="montant">${fmt(row.montant)} FCFA</td>
    <td>${row.ville||'—'}</td><td>${row.mode_paiement||'—'}</td><td>${sb(row.statut)}</td></tr>`).join('');
}

// ── ALERTES ──
function toggleObjectifForm() { const f=document.getElementById('objectif-form'); f.style.display=f.style.display==='none'?'block':'none'; if(f.style.display==='block') loadObjectifs(); }
async function loadObjectifs() { const res=await fetch('/objectifs'); const d=await res.json(); document.getElementById('obj-ca').value=d.ca_mensuel||''; document.getElementById('obj-baisse').value=d.seuil_baisse||20; document.getElementById('obj-faible').value=d.seuil_produit_faible||3; }
async function saveObjectifs() {
  const res=await fetch('/objectifs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ca_mensuel:parseFloat(document.getElementById('obj-ca').value)||0,seuil_baisse:parseFloat(document.getElementById('obj-baisse').value)||20,seuil_produit_faible:parseInt(document.getElementById('obj-faible').value)||3})});
  if(res.ok){showToast('Objectifs sauvegardes !','success');document.getElementById('objectif-form').style.display='none';loadAlertes();}
}
async function loadAlertes() {
  const res=await fetch('/alertes'); const alertes=await res.json();
  const container=document.getElementById('alertes-list');
  if(!alertes.length){container.innerHTML='<div class="no-alerts">Aucune alerte — tout va bien !</div>';return;}
  container.innerHTML=alertes.map((a,i)=>`<div class="alert-card ${a.type}" style="animation-delay:${i*0.07}s"><div class="alert-icon-box ${a.type}">${a.icon}</div><div><div class="alert-titre">${a.titre}</div><div class="alert-message">${a.message}</div></div></div>`).join('');
}

// ── FACTURATION ──
let lignesCount = 0;

document.addEventListener('DOMContentLoaded', () => {
  const d = document.getElementById('f-date');
  if (d) d.value = new Date().toISOString().split('T')[0];
  ajouterLigne(); // Ajouter une premiere ligne vide
});

function ajouterLigne() {
  lignesCount++;
  const id = 'ligne-' + lignesCount;
  const div = document.createElement('div');
  div.className = 'ligne-produit';
  div.id = id;
  div.innerHTML = `
    <input type="text" placeholder="Produit *" class="form-input-field l-produit" style="font-size:13px"/>
    <input type="text" placeholder="Categorie" class="form-input-field l-categorie" style="font-size:13px"/>
    <input type="number" placeholder="Qte" class="form-input-field l-quantite" value="1" min="1" oninput="calculerTotal()" style="font-size:13px"/>
    <input type="number" placeholder="Prix FCFA" class="form-input-field l-prix" oninput="calculerTotal()" style="font-size:13px"/>
    <input type="number" placeholder="Cout FCFA" class="form-input-field l-cout" style="font-size:13px"/>
    <button class="btn-remove-ligne" onclick="supprimerLigne('${id}')">×</button>`;
  document.getElementById('lignes-container').appendChild(div);
}

function supprimerLigne(id) {
  const el = document.getElementById(id);
  if (el && document.querySelectorAll('.ligne-produit').length > 1) {
    el.remove(); calculerTotal();
  } else {
    showToast('Il faut au moins un produit', 'error');
  }
}

function calculerTotal() {
  let total = 0;
  document.querySelectorAll('.ligne-produit').forEach(ligne => {
    const q = parseFloat(ligne.querySelector('.l-quantite')?.value || 0);
    const p = parseFloat(ligne.querySelector('.l-prix')?.value || 0);
    total += q * p;
  });
  const el = document.getElementById('total-facture');
  if (el) el.textContent = new Intl.NumberFormat('fr-FR').format(Math.round(total)) + ' FCFA';
}

async function creerFacture() {
  const client = document.getElementById('f-client')?.value.trim();
  if (!client) { showToast('Le nom du client est obligatoire', 'error'); return; }

  const lignes = [];
  let hasError = false;
  document.querySelectorAll('.ligne-produit').forEach(ligne => {
    const produit  = ligne.querySelector('.l-produit')?.value.trim();
    const quantite = parseFloat(ligne.querySelector('.l-quantite')?.value || 0);
    const prix     = parseFloat(ligne.querySelector('.l-prix')?.value || 0);
    const cout     = parseFloat(ligne.querySelector('.l-cout')?.value || 0);
    const categorie = ligne.querySelector('.l-categorie')?.value.trim() || 'N/A';
    if (!produit || !prix) { hasError = true; return; }
    lignes.push({ produit, categorie, quantite, prix, cout });
  });

  if (hasError || !lignes.length) { showToast('Remplis Produit et Prix pour chaque ligne', 'error'); return; }

  const payload = {
    date:          document.getElementById('f-date')?.value,
    client,
    ville:         document.getElementById('f-ville')?.value || 'N/A',
    vendeur:       document.getElementById('f-vendeur')?.value || 'N/A',
    mode_paiement: document.getElementById('f-paiement')?.value,
    statut:        document.getElementById('f-statut')?.value,
    lignes,
  };

  const res  = await fetch('/factures/creer', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const data = await res.json();

  if (data.success) {
    showToast('Facture ' + data.numero + ' creee !', 'success');
    const s = document.getElementById('facture-success');
    if (s) { s.textContent = 'Facture ' + data.numero + ' creee avec succes !'; s.style.display = 'block'; setTimeout(() => s.style.display = 'none', 4000); }
    resetFacture();
    loadFactures();
    // Proposer de telecharger le PDF
    setTimeout(() => { if (confirm('Telecharger la facture PDF ' + data.numero + ' ?')) window.open('/factures/' + data.fichier_id + '/pdf'); }, 500);
  } else {
    showToast('Erreur : ' + (data.error || 'Inconnue'), 'error');
  }
}

function resetFacture() {
  document.getElementById('f-client').value  = '';
  document.getElementById('f-ville').value   = '';
  document.getElementById('f-vendeur').value = '';
  document.getElementById('f-date').value    = new Date().toISOString().split('T')[0];
  document.getElementById('lignes-container').innerHTML = '';
  lignesCount = 0;
  ajouterLigne();
  calculerTotal();
}

async function loadFactures() {
  const res  = await fetch('/factures');
  const data = await res.json();
  const container = document.getElementById('factures-list');
  if (!container) return;

  if (!data.length) {
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim)">Aucune facture creee</div>';
    return;
  }

  const fmt = n => new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const sb  = s => {
    if (!s) return '';
    const sl  = s.toLowerCase();
    const cls = sl.includes('pay') ? 'paye' : sl.includes('att') ? 'attente' : 'annule';
    return `<span class="badge-statut ${cls}">${s}</span>`;
  };

  container.innerHTML = data.map(f => `
    <div class="facture-card">
      <div class="facture-header">
        <span class="facture-num">${f.numero}</span>
        <span class="facture-total">${fmt(f.total)} FCFA</span>
      </div>
      <div class="facture-meta">
        Client : <strong>${f.client}</strong> &nbsp;·&nbsp;
        Date : ${f.date} &nbsp;·&nbsp;
        ${f.nb_articles} article(s) &nbsp;·&nbsp;
        ${sb(f.statut)}
      </div>
      <div class="facture-actions">
        <button class="btn-facture-pdf" onclick="window.open('/factures/${f.id}/pdf')">Telecharger PDF</button>
        <button class="btn-facture-del" onclick="deleteFacture(${f.id}, '${f.numero}')">Supprimer</button>
      </div>
    </div>`).join('');
}

async function deleteFacture(id, num) {
  if (!confirm('Supprimer la facture ' + num + ' ?')) return;
  const res = await fetch('/factures/' + id + '/delete', { method: 'DELETE' });
  if (res.ok) { showToast('Facture supprimee', 'success'); loadFactures(); }
}

function loadSaisieHistory() { loadFactures(); }

// ── PREVISIONS ──
async function loadPrevisions() {
  const errEl=document.getElementById('prev-error'); const contEl=document.getElementById('prev-content');
  if(!errEl||!contEl)return;
  errEl.style.display='none'; contEl.style.display='none';
  let res; try{res=await fetch('/previsions'+(fichierActif?'?fichier_id='+fichierActif:''));}catch(e){errEl.textContent='Erreur de connexion';errEl.style.display='block';return;}
  if(!res.ok){let msg='Erreur';try{const d=await res.json();msg=d.error||msg;}catch(e){}errEl.textContent=msg;errEl.style.display='block';return;}
  const data=await res.json(); if(data.error){errEl.textContent=data.error;errEl.style.display='block';return;}
  contEl.style.display='block';
  const fmt=n=>new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const fmtSign=n=>(n>=0?'+':'')+n.toFixed(1)+'%';
  const pm=data.previsions.ca[0]||0; const dr=data.historique.ca[data.historique.ca.length-1]||0;
  const dp=dr>0?((pm-dr)/dr*100):0;
  const tc=data.tendance==='hausse'?'#059669':data.tendance==='baisse'?'#dc2626':'#d97706';
  document.getElementById('prev-kpis').innerHTML=`
    <div class="prev-kpi-card" style="--prev-color:#2563eb"><div class="prev-kpi-label">Prochain mois prevu</div><div class="prev-kpi-value">${fmt(pm)} FCFA</div><div class="prev-kpi-sub">${data.previsions.mois[0]}</div></div>
    <div class="prev-kpi-card" style="--prev-color:${tc}"><div class="prev-kpi-label">Tendance</div><div class="prev-kpi-value"><span class="tendance-badge ${data.tendance}">${data.tendance.toUpperCase()}</span></div><div class="prev-kpi-sub">${fmtSign(data.variation)} sur la periode</div></div>
    <div class="prev-kpi-card" style="--prev-color:#059669"><div class="prev-kpi-label">Meilleur mois</div><div class="prev-kpi-value">${data.meilleur_mois}</div></div>
    <div class="prev-kpi-card" style="--prev-color:#d97706"><div class="prev-kpi-label">Croissance prevue</div><div class="prev-kpi-value">${fmtSign(dp)}</div></div>`;
  destroyChart('previsions');
  const allM=[...data.historique.mois,...data.previsions.mois]; const hl=data.historique.mois.length;
  const caH=[...data.historique.ca,...Array(data.previsions.mois.length).fill(null)];
  const caP=[...Array(hl-1).fill(null),data.historique.ca[hl-1],...data.previsions.ca];
  const ctx=document.getElementById('chart-previsions').getContext('2d');
  const grad=ctx.createLinearGradient(0,0,0,280); grad.addColorStop(0,'rgba(37,99,235,0.15)'); grad.addColorStop(1,'rgba(37,99,235,0)');
  charts['previsions']=new Chart(ctx,{type:'line',data:{labels:allM,datasets:[
    {label:'Historique',data:caH,borderColor:'#2563eb',backgroundColor:grad,borderWidth:2,pointRadius:4,tension:0.4,fill:true,spanGaps:false},
    {label:'Prevision',data:caP,borderColor:'#059669',backgroundColor:'transparent',borderWidth:2,borderDash:[8,4],pointBackgroundColor:'#059669',pointRadius:5,pointStyle:'triangle',tension:0.4,spanGaps:false}
  ]},options:{responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>' '+new Intl.NumberFormat('fr-FR').format(Math.round(ctx.parsed.y))+' FCFA'},backgroundColor:'white',borderColor:'#e2e8f0',borderWidth:1,titleColor:'#1a1f2e',bodyColor:'#64748b',padding:12,cornerRadius:8}},scales:{x:{grid:{color:'transparent'},ticks:{color:'#94a3b8',font:{family:'Syne',size:10}},border:{color:'#e2e8f0'}},y:{grid:{color:'#f1f5f9'},ticks:{color:'#94a3b8',font:{family:'Space Mono',size:10},callback:v=>new Intl.NumberFormat('fr-FR',{notation:'compact'}).format(v)},border:{color:'#e2e8f0'}}}}});
  destroyChart('prev-benefice');
  const ctx2=document.getElementById('chart-prev-benefice').getContext('2d');
  const grad2=ctx2.createLinearGradient(0,0,0,240); grad2.addColorStop(0,'rgba(5,150,105,0.15)'); grad2.addColorStop(1,'rgba(5,150,105,0)');
  charts['prev-benefice']=new Chart(ctx2,{type:'line',data:{labels:data.historique.mois,datasets:[{label:'Benefice',data:data.historique.benefice,borderColor:'#059669',backgroundColor:grad2,borderWidth:2,pointRadius:3,tension:0.4,fill:true}]},options:chartOpts('Benefice (FCFA)')});
  destroyChart('prev-qte');
  const ctx3=document.getElementById('chart-prev-qte').getContext('2d');
  charts['prev-qte']=new Chart(ctx3,{type:'bar',data:{labels:data.historique.mois,datasets:[{label:'Quantite',data:data.historique.quantite,backgroundColor:data.historique.mois.map((_,i)=>PAL[i%PAL.length]+'22'),borderColor:data.historique.mois.map((_,i)=>PAL[i%PAL.length]),borderWidth:2,borderRadius:6}]},options:chartOpts('Quantite',true)});
}

// ── CARTE ──
async function loadCarte() {
  const url='/carte'+(fichierActif?'?fichier_id='+fichierActif:'');
  const res=await fetch(url); const data=await res.json();
  if(!data.length)return;
  const fmt=n=>new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const COLORS=['#2563eb','#7c3aed','#059669','#d97706','#dc2626','#0891b2','#65a30d','#ea580c'];
  const total_ca=data.reduce((s,v)=>s+v.ca,0);
  document.getElementById('carte-kpis').innerHTML=`
    <div class="kpi-card" style="--kpi-color:#2563eb"><div class="kpi-badge" style="background:#2563eb18;color:#2563eb">NB</div><div class="kpi-label">Nb Villes</div><div class="kpi-value">${data.length}</div></div>
    <div class="kpi-card" style="--kpi-color:#059669"><div class="kpi-badge" style="background:#05996918;color:#059669">CA</div><div class="kpi-label">CA Total</div><div class="kpi-value">${fmt(total_ca)} FCFA</div></div>
    <div class="kpi-card" style="--kpi-color:#7c3aed"><div class="kpi-badge" style="background:#7c3aed18;color:#7c3aed">QTE</div><div class="kpi-label">Unites Totales</div><div class="kpi-value">${fmt(data.reduce((s,v)=>s+v.quantite,0))}</div></div>
    <div class="kpi-card" style="--kpi-color:#d97706"><div class="kpi-badge" style="background:#d9770618;color:#d97706">TOP</div><div class="kpi-label">Meilleure Ville</div><div class="kpi-value" style="font-size:15px">${data[0]?data[0].ville:'—'}</div></div>`;
  destroyChart('carte-ca'); destroyChart('carte-pie');
  const ctx1=document.getElementById('chart-carte-ca').getContext('2d');
  charts['carte-ca']=new Chart(ctx1,{type:'bar',data:{labels:data.map(v=>v.ville),datasets:[{label:'CA',data:data.map(v=>v.ca),backgroundColor:data.map((_,i)=>COLORS[i%COLORS.length]+'22'),borderColor:data.map((_,i)=>COLORS[i%COLORS.length]),borderWidth:2,borderRadius:6}]},options:chartOpts('CA (FCFA)',true)});
  const ctx2=document.getElementById('chart-carte-pie').getContext('2d');
  charts['carte-pie']=new Chart(ctx2,{type:'doughnut',data:{labels:data.map(v=>v.ville),datasets:[{data:data.map(v=>v.ca),backgroundColor:data.map((_,i)=>COLORS[i%COLORS.length]),borderColor:'white',borderWidth:3,hoverOffset:6}]},options:{responsive:true,plugins:{legend:{position:'bottom',labels:{color:'#64748b',font:{family:'Syne',size:11},padding:12}},tooltip:{callbacks:{label:ctx=>' '+new Intl.NumberFormat('fr-FR').format(ctx.parsed)+' FCFA ('+data[ctx.dataIndex].pct+'%)'}}}}});
  document.getElementById('carte-villes').innerHTML=data.map((v,i)=>`
    <div class="carte-ville-card">
      <div class="ville-dot" style="background:${COLORS[i%COLORS.length]}"></div>
      <div class="ville-info" style="flex:1">
        <strong>${v.ville}</strong><span>${fmt(v.ca)} FCFA — ${v.pct}%</span>
        <div class="ville-bar-wrap"><div class="ville-bar" style="width:${v.pct}%;background:${COLORS[i%COLORS.length]}"></div></div>
        <span style="font-size:10px;color:#94a3b8">${fmt(v.quantite)} unites • ${v.nb_transactions} ventes</span>
      </div>
    </div>`).join('');
}

// ── HISTORIQUE ──
async function loadHistorique() {
  const res=await fetch('/historique'); const data=await res.json();
  const body=document.getElementById('hist-body');
  if(!data.length){body.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:30px">Aucun fichier importe</td></tr>';return;}
  body.innerHTML=data.map(f=>`
    <tr class="${fichierActif===f.id?'row-active':''}">
      <td style="color:var(--text-faint)">#${f.id}</td><td><strong>${f.nom}</strong></td>
      <td>${new Intl.NumberFormat('fr-FR').format(f.nb_lignes)} lignes</td>
      <td>${f.importe_le}</td><td><span class="badge-ville">${f.user}</span></td>
      <td><button class="btn-afficher ${fichierActif===f.id?'active':''}" onclick="afficherFichier(${f.id},'${f.nom}')">${fichierActif===f.id?'Affiche':'Afficher'}</button></td>
      <td><button class="btn-delete" onclick="deleteFichier(${f.id})">Supprimer</button></td>
    </tr>`).join('');
}
async function afficherFichier(id, nom) {
  const res=await fetch('/stats?fichier_id='+id); if(!res.ok){showToast('Aucune donnee','error');return;}
  const data=await res.json(); fichierActif=id; fichierActifNom=nom; globalStats=data;
  enableNav(); updateFichierBar(); populateFilters(data); renderKPIs(data.kpis);
  renderAllCharts(data); tableData=data.raw; renderTable(tableData);
  showToast('Affichage : '+nom,'success'); loadHistorique(); showSection('dashboard');
}
async function deleteFichier(id) {
  if(!confirm('Supprimer ce fichier ?'))return;
  const res=await fetch('/historique/delete/'+id,{method:'DELETE'});
  if(res.ok){if(fichierActif===id){fichierActif=null;fichierActifNom=null;const b=document.getElementById('fichier-actif-bar');if(b)b.style.display='none';}showToast('Fichier supprime','success');loadHistorique();}
}

// ── COMPARER ──
async function doComparer() {
  const p1d=document.getElementById('p1-debut').value; const p1f=document.getElementById('p1-fin').value;
  const p2d=document.getElementById('p2-debut').value; const p2f=document.getElementById('p2-fin').value;
  if(!p1d||!p1f||!p2d||!p2f){showToast('Remplis toutes les dates','error');return;}
  const res=await fetch('/comparer?p1_debut='+p1d+'&p1_fin='+p1f+'&p2_debut='+p2d+'&p2_fin='+p2f);
  if(!res.ok){showToast('Donnees insuffisantes','error');return;}
  const data=await res.json();
  const fmt=n=>new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const dc=(val,label,v1,v2)=>`<div class="compare-card"><h4>${label}</h4><div class="delta-val ${val>=0?'up':'down'}">${val>=0?'+':''}${val}%</div><div style="margin-top:10px"><div class="period-val">${v1}</div><div class="period-label">P1 : ${data.periode1.label}</div><div class="period-val" style="margin-top:4px">${v2}</div><div class="period-label">P2 : ${data.periode2.label}</div></div></div>`;
  const k1=data.periode1.kpis; const k2=data.periode2.kpis;
  document.getElementById('compare-result').innerHTML=`<div class="compare-result-grid">
    ${dc(data.delta.ca,"CA",fmt(k1.total_ca)+' FCFA',fmt(k2.total_ca)+' FCFA')}
    ${dc(data.delta.benefice,'Benefice',fmt(k1.total_benefice)+' FCFA',fmt(k2.total_benefice)+' FCFA')}
    ${dc(data.delta.ventes,'Unites',fmt(k1.total_ventes),fmt(k2.total_ventes))}
    ${dc(data.delta.transactions,'Transactions',fmt(k1.nb_transactions),fmt(k2.nb_transactions))}
  </div>`;
}

// ── TABLE ──
function renderTable(data) {
  const fmt=n=>new Intl.NumberFormat('fr-FR').format(Math.round(n));
  const body=document.getElementById('table-body'); if(!body)return;
  body.innerHTML=data.map(row=>`<tr>
    <td>${row.date||'—'}</td><td><strong>${row.produit||'—'}</strong></td>
    <td>${fmt(row.quantite)}</td><td>${fmt(row.prix)} FCFA</td>
    <td><span class="badge-ville">${row.ville||'—'}</span></td>
    <td class="montant">${fmt(row.montant)} FCFA</td></tr>`).join('');
}
function filterTable(){const q=document.getElementById('search-input').value.toLowerCase();renderTable(tableData.filter(r=>Object.values(r).some(v=>String(v).toLowerCase().includes(q))));}
let sortDir={};
function sortTable(col){const keys=['date','produit','quantite','prix','ville','montant'];const key=keys[col];sortDir[key]=!sortDir[key];const sorted=[...tableData].sort((a,b)=>{const va=isNaN(a[key])?String(a[key]):Number(a[key]);const vb=isNaN(b[key])?String(b[key]):Number(b[key]);return sortDir[key]?(va<vb?-1:va>vb?1:0):(va>vb?-1:va<vb?1:0);});renderTable(sorted);}

// ── EXPORTS ──
function exportPDF(){showToast('Generation PDF...','success');window.location.href='/export/pdf'+(fichierActif?'?fichier_id='+fichierActif:'');}
function exportExcel(){showToast('Generation Excel...','success');window.location.href='/export/excel'+(fichierActif?'?fichier_id='+fichierActif:'');}

// ── TOAST ──
let toastTimer;
function showToast(msg,type='success'){const t=document.getElementById('toast');t.textContent=msg;t.className='toast show '+type;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{t.className='toast';},3500);}