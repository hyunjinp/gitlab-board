const state = {
  projectIds: [],
  issues: [],
  assigneeSummary: {},
  chart: null,
};

function toast(message) {
  alert(message);
}

function getProjectIds() {
  const value = document.getElementById('project-ids').value;
  state.projectIds = value.split(',').map((v) => v.trim()).filter(Boolean).map(Number);
  return state.projectIds;
}

async function saveConfig() {
  const server = document.getElementById('server-url').value.trim();
  const token = document.getElementById('api-token').value.trim();
  if (!server || !token) {
    toast('서버와 토큰을 모두 입력하세요');
    return;
  }
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gitlab_server: server, api_token: token }),
  });
  if (res.ok) {
    toast('설정이 저장되었습니다');
  } else {
    toast('설정 저장에 실패했습니다');
  }
}

async function loadConfig() {
  const res = await fetch('/api/config');
  if (!res.ok) {
    toast('저장된 설정이 없습니다');
    return;
  }
  const data = await res.json();
  document.getElementById('server-url').value = data.gitlab_server;
  document.getElementById('api-token').value = data.api_token;
}

async function syncRepos() {
  const projectIds = getProjectIds();
  if (!projectIds.length) {
    toast('프로젝트 ID를 입력하세요');
    return;
  }
  const params = new URLSearchParams();
  projectIds.forEach((id) => params.append('project_ids', id));
  const res = await fetch(`/api/repos?${params.toString()}`, { method: 'POST' });
  if (!res.ok) {
    toast('레포지토리 동기화 실패');
    return;
  }
  const repos = await res.json();
  document.getElementById('repo-list').innerText = repos.map((r) => `${r.name} (${r.id})`).join(', ');
}

function buildQueryParams() {
  const projectIds = getProjectIds();
  const params = new URLSearchParams();
  params.set('project_ids', projectIds.join(','));
  const q = document.getElementById('search-text').value.trim();
  const author = document.getElementById('search-author').value.trim();
  const assignee = document.getElementById('search-assignee').value.trim();
  const label = document.getElementById('search-label').value.trim();
  const category = document.getElementById('search-category').value.trim();
  const note = document.getElementById('search-note').value.trim();
  if (q) params.set('query', q);
  if (author) params.set('author', author);
  if (assignee) params.set('assignee', assignee);
  if (label) params.set('label', label);
  if (category) params.set('category', category);
  if (note) params.set('note', note);
  return params;
}

function renderIssues() {
  const tbody = document.querySelector('#issue-table tbody');
  tbody.innerHTML = '';
  state.issues.forEach((issue) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="checkbox" data-id="${issue.id}"></td>
      <td>${issue.project_id}</td>
      <td>${issue.iid}</td>
      <td>${issue.title}</td>
      <td>${issue.author ?? ''}</td>
      <td>${issue.assignee ?? ''}</td>
      <td>${(issue.labels || []).map(l => `<span class="badge">${l}</span>`).join('')}</td>
      <td>${issue.state}</td>
      <td><input class="category-input" data-id="${issue.id}" value="${issue.category ?? ''}"></td>
      <td>
        <textarea class="note-input" data-id="${issue.id}" rows="2">${issue.note ?? ''}</textarea>
        <div class="actions-inline"><button data-action="save-note" data-id="${issue.id}">저장</button></div>
      </td>
      <td><a href="${issue.web_url}" target="_blank">열기</a></td>`;
    tbody.appendChild(tr);
  });
  document.getElementById('assignee-summary').innerText =
    Object.entries(state.assigneeSummary).map(([k, v]) => `${k}: ${v}건`).join(' / ');
}

async function fetchIssues(applyFilter = false) {
  const projectIds = getProjectIds();
  if (!projectIds.length) {
    toast('프로젝트 ID를 입력하세요');
    return;
  }
  const params = applyFilter ? buildQueryParams() : new URLSearchParams({ project_ids: projectIds.join(',') });
  const res = await fetch(`/api/issues?${params.toString()}`);
  if (!res.ok) {
    toast('이슈 조회 실패');
    return;
  }
  const data = await res.json();
  state.issues = data.issues;
  state.assigneeSummary = data.assignee_summary;
  renderIssues();
}

async function refreshIssues() {
  const projectIds = getProjectIds();
  if (!projectIds.length) {
    toast('프로젝트 ID를 입력하세요');
    return;
  }
  const res = await fetch('/api/issues/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_ids: projectIds, fetch_newer_only: true })
  });
  if (!res.ok) {
    toast('새 이슈를 불러오지 못했습니다');
    return;
  }
  const data = await res.json();
  state.issues = data.issues;
  state.assigneeSummary = data.assignee_summary;
  renderIssues();
}

async function saveIssueFields(issueId) {
  const category = document.querySelector(`input.category-input[data-id="${issueId}"]`).value;
  const note = document.querySelector(`textarea.note-input[data-id="${issueId}"]`).value;
  const res = await fetch(`/api/issues/${issueId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category, note }),
  });
  if (res.ok) {
    toast('저장되었습니다');
  } else {
    toast('저장 실패');
  }
}

async function closeSelectedIssues() {
  const checked = Array.from(document.querySelectorAll('#issue-table input[type="checkbox"]:checked'))
    .map((cb) => Number(cb.getAttribute('data-id')));
  if (!checked.length) {
    toast('선택된 이슈가 없습니다');
    return;
  }
  const res = await fetch('/api/issues/bulk-close', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue_ids: checked }),
  });
  if (res.ok) {
    toast('선택한 이슈를 닫았습니다');
    fetchIssues(true);
  } else {
    toast('이슈 close 실패');
  }
}

async function exportIssues() {
  const params = buildQueryParams();
  const url = `/api/issues/export?${params.toString()}`;
  window.open(url, '_blank');
}

async function loadCommitStats() {
  const projectIds = getProjectIds();
  if (!projectIds.length) {
    return;
  }
  const params = new URLSearchParams({ project_ids: projectIds.join(',') });
  const res = await fetch(`/api/commit-stats?${params.toString()}`);
  if (!res.ok) {
    toast('커밋 통계를 가져오지 못했습니다');
    return;
  }
  const data = await res.json();
  renderCommitChart(data.stats);
}

function renderCommitChart(stats) {
  const grouped = {};
  stats.forEach((row) => {
    if (!grouped[row.author]) grouped[row.author] = {};
    grouped[row.author][row.week] = row;
  });
  const weeks = Array.from(new Set(stats.map((s) => s.week))).sort();
  const datasets = Object.entries(grouped).map(([author, values]) => ({
    label: author,
    data: weeks.map((w) => values[w]?.commits || 0),
    borderWidth: 2,
    fill: false,
  }));
  const ctx = document.getElementById('commit-chart').getContext('2d');
  if (state.chart) state.chart.destroy();
  state.chart = new Chart(ctx, {
    type: 'line',
    data: { labels: weeks, datasets },
    options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
  });
}

function bindEvents() {
  document.getElementById('save-config').addEventListener('click', saveConfig);
  document.getElementById('load-config').addEventListener('click', loadConfig);
  document.getElementById('sync-repos').addEventListener('click', async () => {
    await syncRepos();
    fetchIssues();
    loadCommitStats();
  });
  document.getElementById('refresh-issues').addEventListener('click', () => {
    refreshIssues();
    loadCommitStats();
  });
  document.getElementById('apply-filter').addEventListener('click', () => fetchIssues(true));
  document.getElementById('close-selected').addEventListener('click', closeSelectedIssues);
  document.getElementById('export-issues').addEventListener('click', exportIssues);
  document.getElementById('select-all').addEventListener('change', (e) => {
    document.querySelectorAll('#issue-table tbody input[type="checkbox"]').forEach((cb) => {
      cb.checked = e.target.checked;
    });
  });
  document.querySelector('#issue-table tbody').addEventListener('click', (e) => {
    const target = e.target;
    if (target.dataset.action === 'save-note') {
      const id = Number(target.dataset.id);
      saveIssueFields(id);
    }
  });
}

bindEvents();
