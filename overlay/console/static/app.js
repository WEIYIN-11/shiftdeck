/* shiftdeck 主控台前端：送出請求、輪詢 agent 狀態、列出專案。
   狀態訊息刻意分「有 agent 在接」「沒有 agent」兩種，不讓人對著轉圈猜。 */

const $ = (id) => document.getElementById(id);
const POLL_MS = 2000;
const STALE_MS = 15000;      // 狀態超過這麼久沒更新，就當作沒有 agent 在跑

let picked = [];

/* ------------------------------------------------------------ 檔案挑選 */
const drop = $('drop');
const input = $('materials');

$('browse').addEventListener('click', () => input.click());
input.addEventListener('change', () => addFiles(input.files));

['dragenter', 'dragover'].forEach((ev) =>
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((ev) =>
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', (e) => addFiles(e.dataTransfer.files));

function addFiles(list) {
  for (const f of list) {
    if (!picked.some((p) => p.name === f.name && p.size === f.size)) picked.push(f);
  }
  renderFiles();
}

function renderFiles() {
  $('filelist').innerHTML = picked.map((f, i) =>
    `<li><span>${escapeHtml(f.name)}</span>
       <button type="button" class="link" data-i="${i}">移除</button></li>`).join('');
  $('filelist').querySelectorAll('button').forEach((b) =>
    b.addEventListener('click', () => { picked.splice(+b.dataset.i, 1); renderFiles(); }));
}

/* ------------------------------------------------------------ 送出表單 */
$('new-deck').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  form.delete('materials');
  picked.forEach((f) => form.append('materials', f));

  const fb = $('feedback');
  $('submit').disabled = true;
  fb.className = 'feedback';
  fb.textContent = '送出中…';

  try {
    const res = await fetch('/api/new-deck', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '送出失敗');
    fb.className = 'feedback ok';
    fb.textContent = `已送出，等 agent 接手（${data.request.id}）`;
    e.target.reset();
    picked = [];
    renderFiles();
    refresh();
  } catch (err) {
    fb.className = 'feedback err';
    fb.textContent = err.message;
  } finally {
    $('submit').disabled = false;
  }
});

/* ------------------------------------------------------------ 狀態輪詢 */
async function refresh() {
  let data;
  try {
    data = await (await fetch('/api/state')).json();
  } catch {
    setAgent('idle', '主控台連不上', '伺服器可能已經關掉了');
    return;
  }

  const st = data.status || {};
  const fresh = st.updated_at && (Date.now() - Date.parse(st.updated_at) < STALE_MS);

  if (st.busy && fresh) {
    setAgent('busy', st.text || 'AI 正在處理', st.project ? `專案：${st.project}` : '');
  } else if (data.queue.length && !fresh) {
    setAgent('waiting', '等待 agent 接手',
             `有 ${data.queue.length} 筆請求排著，agent 那邊還沒開始等`);
  } else if (fresh) {
    setAgent('idle', st.text || '待命中', '在這裡按任何按鈕，agent 都會接手');
  } else {
    setAgent('idle', '沒有 agent 在等', '請在對話框叫它一聲，或跑 agent.py wait');
  }

  const bar = st.progress != null && st.busy && fresh;
  $('bar-wrap').hidden = !bar;
  if (bar) $('bar').style.width = `${Math.round(st.progress * 100)}%`;

  $('queue').innerHTML = (data.queue || []).map((q) => `
    <div class="q-item ${q.state}">
      <span class="q-kind">${q.state === 'claimed' ? '處理中' : '排隊中'}</span>
      ${kindLabel(q.kind)}${q.project ? ` · ${escapeHtml(q.project)}` : ''}
    </div>`).join('');

  renderProjects(data.projects || []);
}

function setAgent(kind, title, note) {
  $('agent-dot').className = `agent-dot ${kind}`;
  $('agent-title').textContent = title;
  $('agent-note').textContent = note || '';
}

function kindLabel(kind) {
  return { new_deck: '開新簡報', regen_page: '重畫一頁',
           apply_edits: '套用修改', export: '匯出' }[kind] || kind;
}

function renderProjects(rows) {
  if (!rows.length) {
    $('projects').innerHTML = '<p class="empty">還沒有專案。上面填一份，按「開始製作」。</p>';
    return;
  }
  $('projects').innerHTML = rows.map((p) => `
    <div class="proj">
      <div>
        <div class="proj-name">${escapeHtml(p.name)}</div>
        <div class="proj-meta">${p.pages} 頁${p.export ? ` · 已匯出 ${escapeHtml(p.export)}` : ' · 尚未匯出'}</div>
      </div>
      <div class="proj-tail">
        ${p.pending_regen ? '<span class="badge wait">有一頁等著重畫</span>'
                          : (p.export ? '<span class="badge done">可以下載</span>' : '')}
      </div>
    </div>`).join('');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

refresh();
setInterval(refresh, POLL_MS);
