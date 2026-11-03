const $ = selector => document.querySelector(selector);
let token = '';
let checkingStatus = false;
let busy = false;
let uploading = false;
let maxUploadMb = null;
let importSignature = '';
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...options.headers, 'X-Local-Token': token}});
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? t(body.detail) : t('Cerere invalidă. Verifică datele introduse.'));
  return body;
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
async function status() {
  if (checkingStatus) return;
  checkingStatus = true;
  try {
    const data = await api('/api/status', {signal: AbortSignal.timeout(10000)});
    token = data.token;
    maxUploadMb = data.max_upload_mb;
    $('#upload-limit').textContent = `PDF, Markdown, TXT · max. ${maxUploadMb} MiB / ${language === 'en' ? 'file' : 'fișier'}`;
    $('#connection').textContent = t({ready: '● OLLAMA CONECTAT', models_missing: '◌ MODELE LIPSĂ', offline: '◌ OLLAMA OPRIT'}[data.ollama]);
    $('#models').textContent = `${data.chat_model} / ${data.embed_model}`;
    $('#setup').hidden = data.ollama === 'ready';
  } catch (error) {
    $('#connection').textContent = language === 'en' ? '◌ STATUS UNAVAILABLE' : '◌ STARE INDISPONIBILĂ';
    $('#setup').hidden = false;
  } finally { checkingStatus = false; }
}
async function documents() {
  const docs = await api('/api/documents');
  $('#documents').replaceChildren();
  $('#count').textContent = docs.length;
  if (!docs.length) $('#documents').append(element('p', t('Niciun document importat.'), 'muted'));
  for (const doc of docs) {
    const row = element('div', undefined, 'doc');
    const info = element('div');
    info.append(element('strong', doc.name), element('small', `${doc.chunks} ${language === 'en' ? 'chunks' : 'fragmente'} · ${doc.created_at} UTC`));
    const remove = element('button', '×');
    remove.setAttribute('aria-label', `${language === 'en' ? 'Delete' : 'Șterge'} ${doc.name}`);
    remove.addEventListener('click', async () => {
      if (busy || !confirm(language === 'en' ? `Delete “${doc.name}” from the local index?` : `Ștergi documentul „${doc.name}” din indexul local?`)) return;
      remove.disabled = true;
      try { await api(`/api/documents/${doc.id}`, {method: 'DELETE'}); await documents(); }
      catch (error) { $('#upload-status').textContent = t(error.message); remove.disabled = false; }
    });
    row.append(info, remove);
    $('#documents').append(row);
  }
}
async function refreshImports() {
  const jobs = await api('/api/imports');
  $('#imports').replaceChildren();
  for (const job of jobs.slice(-5).reverse()) {
    const row = element('div', undefined, 'import-job');
    const labels = language === 'en'
      ? {queued: 'Queued', running: 'Indexing', completed: 'Completed', failed: 'Failed'}
      : {queued: 'În așteptare', running: 'Indexare', completed: 'Finalizat', failed: 'Eșuat'};
    row.append(element('strong', job.name), element('p', `${labels[job.state]} · ${job.chunks_done} ${language === 'en' ? 'chunks' : 'fragmente'}`));
    if (job.state === 'running' || job.state === 'queued') {
      const progress = element('progress');
      progress.setAttribute('aria-label', language === 'en' ? 'Indexing progress' : 'Progres indexare');
      if (job.pages_total) {
        progress.max = job.pages_total;
        progress.value = job.pages_done;
        row.append(element('small', `${job.pages_done} / ${job.pages_total} ${language === 'en' ? 'pages read' : 'pagini citite'}`));
      }
      row.append(progress);
      if (job.phase === 'saving') row.append(element('small', language === 'en' ? 'Saving index…' : 'Salvare index…'));
    }
    if (job.error) row.append(element('small', t(job.error), 'error'));
    if (job.result?.duplicate) row.append(element('small', t('deja indexat')));
    $('#imports').append(row);
  }
  const signature = jobs.filter(job => job.state === 'completed').map(job => job.id).join(',');
  if (signature !== importSignature) { importSignature = signature; await documents(); }
  return jobs;
}
async function waitImport(id) {
  while (true) {
    const job = (await refreshImports()).find(job => job.id === id);
    if (!job) throw new Error(language === 'en' ? 'Import not found. The server may have restarted.' : 'Import inexistent. Serverul poate fi repornit.');
    if (job.state === 'failed') throw new Error(t(job.error));
    if (job.state === 'completed') return job.result;
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
}
$('#files').addEventListener('change', async event => {
  if (busy || uploading) return;
  uploading = true;
  const files = [...event.target.files];
  event.target.disabled = true;
  const results = [];
  try {
    for (const file of files) {
      $('#upload-status').textContent = `${language === 'en' ? 'Indexing' : 'Indexare'}: ${file.name}…`;
      if (maxUploadMb === null) throw new Error(language === 'en' ? 'Reload the page to load upload limits.' : 'Reîncarcă pagina pentru limitele de upload.');
      if (file.size > maxUploadMb * 1024 * 1024) { results.push(`${file.name}: ${language === 'en' ? 'exceeds' : 'depășește'} ${maxUploadMb} MiB.`); continue; }
      const data = new FormData(); data.append('file', file);
      try {
        const accepted = await api('/api/documents', {method: 'POST', body: data});
        const result = await waitImport(accepted.job_id);
        results.push(`${file.name}: ${result.duplicate ? t('deja indexat') : `${result.chunks} ${language === 'en' ? 'chunks indexed' : 'fragmente indexate'}`}.`);
      } catch (error) { results.push(`${file.name}: ${t(error.message)}`); }
    }
    await documents();
    $('#upload-status').textContent = results.join(' ');
  } catch (error) { $('#upload-status').textContent = t(error.message); }
  finally { event.target.value = ''; uploading = false; event.target.disabled = busy; }
});
function message(role, text) {
  const node = element('article', undefined, `message ${role}`);
  node.append(element('h3', t(role === 'user' ? 'TU / ÎNTREBARE' : 'OpsAtlas / RĂSPUNS')), element('pre', text));
  $('#conversation').append(node);
  return node;
}
$('#ask').addEventListener('submit', async event => {
  event.preventDefault();
  const question = $('#question').value.trim();
  if (busy || !question) return;
  busy = true; $('#language').disabled = true; $('#send').disabled = true; $('#files').disabled = true;
  $('#empty').hidden = true;
  message('user', question); $('#question').value = '';
  const reply = message('assistant', t('Caut în documente și pregătesc răspunsul…'));
  try {
    const data = await api('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question})});
    reply.querySelector('pre').textContent = data.sources.length ? data.answer : t(data.answer);
    if (data.citations_valid === false) reply.append(element('p', t('Modelul nu a furnizat citări valide pentru toate referințele. Verifică fragmentele de mai jos.'), 'warning'));
    if (data.sources.length) {
      const list = element('div', undefined, 'sources');
      data.sources.forEach((source, index) => {
        const item = element('details');
        const summary = element('summary');
        const render = () => { summary.textContent = `[${index + 1}] ${source.name} · ${language === 'en' ? 'page' : 'pagina'} ${source.page} · ${language === 'en' ? 'similarity' : 'similaritate'} ${source.score.toFixed(2)}`; };
        render();
        document.addEventListener('languagechange', render);
        item.append(summary, element('p', source.text));
        list.append(item);
      });
      reply.append(list);
    }
  } catch (error) { reply.querySelector('pre').textContent = t(error.message); reply.classList.add('error'); }
  finally { busy = false; $('#language').disabled = false; $('#send').disabled = false; $('#files').disabled = uploading; $('#question').focus(); }
});
document.querySelectorAll('.suggestions button').forEach(button => button.addEventListener('click', () => { $('#question').value = button.textContent; $('#question').focus(); }));
document.addEventListener('languagechange', async () => {
  document.querySelectorAll('.message').forEach(node => {
    node.querySelector('h3').textContent = t(node.classList.contains('user') ? 'TU / ÎNTREBARE' : 'OpsAtlas / RĂSPUNS');
    const warning = node.querySelector('.warning');
    if (warning) warning.textContent = t('Modelul nu a furnizat citări valide pentru toate referințele. Verifică fragmentele de mai jos.');
  });
  $('#upload-status').textContent = '';
  await status();
  try { await documents(); } catch (error) { $('#upload-status').textContent = t(error.message); }
  try { await refreshImports(); } catch (error) { $('#upload-status').textContent = t(error.message); }
});
$('#refresh').addEventListener('click', status);
async function init() {
  await status();
  async function monitorStatus() {
    await status();
    setTimeout(monitorStatus, 5000);
  }
  setTimeout(monitorStatus, 5000);
  try { await documents(); } catch (error) { $('#upload-status').textContent = t(error.message); }
  async function monitor() {
    if (!uploading) {
      try { await refreshImports(); } catch (error) { $('#upload-status').textContent = t(error.message); }
    }
    setTimeout(monitor, 2000);
  }
  monitor();
}
init();
