/* team-umc 거버넌스 대시보드 — 클라이언트. design.md §4·§5.
   렉 0 원칙: 10초 클라 폴링 + diff 패치(전체 리렌더 금지). */

const POLL_MS = 10000;
const $ = (id) => document.getElementById(id);

let lastDecisionIds = new Set();   // 입장 애니메이션용(새 결정만)
let lastSnapshot = null;
let currentDetail = null;
// 섹션별 직전 렌더 시그니처. 동일하면 DOM을 건드리지 않는다(전체 리렌더 금지 →
// 포커스·hover 보존·페인트 폭주 방지. design.md §2.4·§5).
const sig = { reminders: null, teams: null, feed: null, news: null };
function changed(key, data) {
  const s = JSON.stringify(data);
  if (sig[key] === s) return false;
  sig[key] = s;
  return true;
}

function relTime(tsNs) {
  if (!tsNs) return "";
  const ms = Number(tsNs) / 1e6;
  const diff = Date.now() - ms;
  if (diff < 0) return "방금";
  const m = Math.floor(diff / 60000);
  if (m < 1) return "방금";
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  return `${Math.floor(h / 24)}일 전`;
}

function esc(s) {
  // 텍스트 노드 직렬화는 따옴표를 이스케이프하지 않으므로, 속성 컨텍스트(class·data-*)
  // 주입을 막기 위해 따옴표까지 명시적으로 처리한다(XSS 방어).
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ── 미리알림 스트립 (회사 전체 umc만; 팀별은 각 팀 카드로 이동) ── */
function renderReminders(reminders) {
  const company = (reminders || []).filter(r => r.list === "umc");
  if (!changed("reminders", company)) return;
  const el = $("reminders-strip");
  if (!company.length) {
    el.innerHTML = '<span class="empty-note">미리알림 캐시 없음 — ↻ 미리알림으로 불러오세요.</span>';
    return;
  }
  el.innerHTML = company.map(r => {
    const zero = (r.open || 0) === 0;
    return `<span class="rem-chip ${zero ? "zero" : ""}">
      <span class="open-dot"></span>
      <span class="name">${esc(r.list)}</span>
      <span class="count">${r.open}/${r.total}</span>
    </span>`;
  }).join("");
}

/* ── 팀 카드 ── */
function renderTeams(teams) {
  if (!changed("teams", teams)) return;
  const el = $("team-grid");
  el.innerHTML = teams.map(t => {
    const teamClass = String(t.name || "").replace(/[^a-zA-Z0-9_-]/g, "");
    const members = (t.members || []).map(m =>
      `<span class="worker-chip">${esc(m)}</span>`).join("");
    const dec = t.latest_decision
      ? `<div class="tc-decision" data-decision="${esc(t.latest_decision.id)}" tabindex="0" role="button">
           <span>${esc(t.latest_decision.subject).slice(0, 60)}</span>
           <span class="arrow">▸</span>
         </div>`
      : `<div class="tc-decision empty">최근 결정 없음</div>`;
    const verdict = t.verdict
      ? `<span class="verdict-badge ${esc(t.verdict.result)}">${t.verdict.result === "PASS" ? "✓" : "⚑"} ${esc(t.verdict.result)}${t.verdict.count > 1 ? " ×" + t.verdict.count : ""}</span>`
      : "";
    // 사용자 요청: 각 팀 카드에 자기 팀 미리알림 목록 표시.
    const rem = t.reminder;
    const remHtml = rem
      ? (rem.open == null
          ? `<div class="tc-reminder zero"><span class="open-dot"></span><span class="name">${esc(rem.list)}</span><span class="count">—</span></div>`
          : `<div class="tc-reminder ${rem.open === 0 ? "zero" : ""}"><span class="open-dot"></span><span class="name">${esc(rem.list)}</span><span class="count">${rem.open}/${rem.total} open</span></div>`)
      : "";
    return `<div class="team-card">
      <div class="tc-head">
        <span class="team-ring team-${esc(teamClass)}"></span>
        <span class="tc-name">${esc(t.name)}</span>
      </div>
      <div class="tc-lead">팀장 · ${esc(t.lead)}</div>
      <div class="tc-stats">
        <div class="tc-stat ${t.team_skill_added_recent ? "added" : ""}">
          <div class="v">＋${t.team_skill_added_recent}</div><div class="k">스킬 추가</div>
        </div>
        <div class="tc-stat ${t.agent_added_recent ? "added" : ""}">
          <div class="v">＋${t.agent_added_recent}</div><div class="k">에이전트 추가</div>
        </div>
        <div class="tc-stat">
          <div class="v">${(t.members || []).length}</div><div class="k">워커</div>
        </div>
      </div>
      <div class="tc-members">${members}</div>
      ${remHtml}
      ${dec}
      ${verdict}
    </div>`;
  }).join("");
  el.querySelectorAll("[data-decision]").forEach(node => {
    const open = () => openDetail(node.getAttribute("data-decision"));
    node.addEventListener("click", open);
    node.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  });
}

/* ── 결정 피드 (dirty-check: 데이터 동일하면 DOM 미변경; 새 항목만 입장) ── */
function renderFeed(decisions) {
  if (!changed("feed", decisions)) return;
  const el = $("decision-feed");
  if (!decisions || !decisions.length) {
    el.innerHTML = '<div class="empty-note">조용합니다 — 새 팀장 결정이 없습니다.</div>';
    lastDecisionIds = new Set();
    return;
  }
  const newIds = new Set(decisions.map(d => d.id));
  el.innerHTML = decisions.map(d => {
    const result = d.verdict && d.verdict.result;
    const flag = result === "FAIL" || result === "PARTIAL";
    const isNew = !lastDecisionIds.has(d.id) && lastDecisionIds.size > 0;
    // 색만으로 구분하지 않도록 ⚑ 아이콘 + 상태 레이블 병행(design.md §4.4·§7).
    const flagMark = flag
      ? `<span class="feed-flag" aria-hidden="true">⚑</span><span class="feed-flag-label">${esc(result)}</span>`
      : "";
    const aria = flag ? ` aria-label="${esc(result)}: ${esc(d.subject)}"` : "";
    return `<div class="feed-row ${flag ? "flag" : ""} ${isNew ? "enter" : ""}"
                 tabindex="0" data-decision="${esc(d.id)}"${aria}>
      <span class="dot"></span>
      ${flagMark}
      <span class="from">${esc(d.from)}</span>
      <span class="subject">${esc(d.subject)}</span>
      <span class="time">${relTime(d.ts_ns)}</span>
    </div>`;
  }).join("");
  el.querySelectorAll("[data-decision]").forEach(node => {
    const open = () => openDetail(node.getAttribute("data-decision"));
    node.addEventListener("click", open);
    node.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
  });
  lastDecisionIds = newIds;
}

/* ── 소식 ── */
const NEWS_GLYPH = {
  team_skill_added: "＋", agent_added: "＋", worker_skill_updated: "↻", promotion_signal: "★",
};
function newsText(n) {
  if (n.kind === "team_skill_added") return `<span class="nteam">${esc(n.team)}</span> 팀스킬 <strong>${esc(n.name)}</strong> 추가`;
  if (n.kind === "agent_added") return `<span class="nteam">${esc(n.team)}</span> 에이전트 <strong>${esc(n.name)}</strong> 추가`;
  if (n.kind === "worker_skill_updated") return `<span class="nteam">${esc(n.team)}/${esc(n.worker)}</span> 스킬 <strong>${esc(n.name)}</strong> ${n.new ? "신규" : "업데이트"}`;
  if (n.kind === "promotion_signal") return `승격 신호 · ${esc(n.detail)}`;
  return esc(n.kind);
}
function newsExplain(n) {
  if (n.kind === "team_skill_added") return `${n.team} 팀이 공용 스킬 '${n.name}'을 새로 추가했습니다.`;
  if (n.kind === "agent_added") return `${n.team} 팀에 새 에이전트 '${n.name}'이 추가되었습니다.`;
  if (n.kind === "worker_skill_updated") return `${n.team}/${n.worker}의 워커 스킬 '${n.name}'이 ${n.new ? "새로 생성" : "업데이트"}되었습니다.`;
  if (n.kind === "promotion_signal") return `승격 후보 신호: ${n.detail || ""}`;
  return n.kind;
}
function renderNews(news) {
  if (!changed("news", news)) return;
  const el = $("news-list");
  if (!news || !news.length) {
    el.innerHTML = '<div class="empty-note">새 스킬·에이전트 변화가 없습니다.</div>';
    return;
  }
  el.innerHTML = news.map((n, i) =>
    `<span class="news-chip ${esc(n.kind)}" data-news="${i}" tabindex="0" role="button" title="${esc(newsExplain(n))}">
       <span class="glyph">${NEWS_GLYPH[n.kind] || "•"}</span>
       <span>${newsText(n)}</span>
     </span>`).join("");
  // 클릭 시 무엇이 바뀌었는지 1줄 설명(design.md §4.5).
  el.querySelectorAll("[data-news]").forEach(node => {
    const idx = Number(node.getAttribute("data-news"));
    const show = () => window.alert(newsExplain(news[idx]));
    node.addEventListener("click", show);
    node.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(); } });
  });
}

/* ── 디테일 패널 ── */
function openDetail(id) {
  if (!lastSnapshot) return;
  const d = (lastSnapshot.decisions || []).find(x => x.id === id);
  if (!d) return;
  currentDetail = d;
  $("dp-title").textContent = d.subject || "(제목 없음)";
  const meta = [`from: ${d.from}`, d.to_team ? `to_team: ${d.to_team}` : null,
                d.work_ref ? `work_ref: ${d.work_ref}` : null,
                d.verdict ? `verdict: ${JSON.stringify(d.verdict)}` : null]
    .filter(Boolean).join("  ·  ");
  $("dp-meta").textContent = meta;
  $("dp-body").textContent = d.body || "(본문 없음)";
  // 체크백 폼 프리필: 목록 드롭다운 채우고, 기본 목록의 작업을 로드.
  fillListDropdown();
  $("cb-note").value = `[${d.from}] ${d.subject}`;
  $("cb-complete").checked = false;
  $("cb-result").innerHTML = "";
  $("cb-result").className = "";
  loadTasksForList($("cb-list").value);
  $("detail-overlay").classList.add("open");
  $("detail-panel").classList.add("open");
}

// 체크백: 목록 드롭다운을 현재 스냅샷의 미리알림 목록으로 채운다.
function fillListDropdown() {
  const sel = $("cb-list");
  const lists = [];
  if (lastSnapshot) {
    (lastSnapshot.reminders || []).forEach(r => lists.push(r.list));
    (lastSnapshot.teams || []).forEach(t => { if (t.reminder && t.reminder.list) lists.push(t.reminder.list); });
  }
  const uniq = [...new Set(lists)];
  if (!uniq.length) uniq.push("umc");
  const cur = sel.value;
  sel.innerHTML = uniq.map(l => `<option value="${esc(l)}">${esc(l)}</option>`).join("");
  if (uniq.includes(cur)) sel.value = cur;
}

// 선택한 목록의 작업을 불러와 작업 드롭다운에 채운다(정확 매칭 위해 id를 value로).
async function loadTasksForList(listName) {
  const taskSel = $("cb-task");
  if (!listName) { taskSel.innerHTML = '<option value="">— 목록을 먼저 고르세요 —</option>'; return; }
  taskSel.innerHTML = '<option value="">불러오는 중…</option>';
  try {
    const r = await fetch("/api/reminder-tasks?list=" + encodeURIComponent(listName));
    const data = await r.json();
    const tasks = (data.tasks || []).filter(t => !t.completed);
    if (!tasks.length) { taskSel.innerHTML = '<option value="">(열린 작업 없음)</option>'; return; }
    taskSel.innerHTML = '<option value="">— 작업 선택 —</option>' +
      tasks.map(t => `<option value="${esc(t.id)}" data-name="${esc(t.name)}">${esc(t.name)}</option>`).join("");
  } catch (e) {
    taskSel.innerHTML = '<option value="">불러오기 실패</option>';
  }
}
function closeDetail() {
  $("detail-overlay").classList.remove("open");
  $("detail-panel").classList.remove("open");
  currentDetail = null;
}

/* ── 미리알림 체크백(쓰기) — 확인 다이얼로그 후 실행 ── */
async function submitCheckback() {
  const list = $("cb-list").value.trim();
  const taskSel = $("cb-task");
  const taskId = taskSel.value.trim();
  const taskOpt = taskSel.options[taskSel.selectedIndex];
  const taskName = taskOpt ? (taskOpt.getAttribute("data-name") || taskOpt.textContent) : "";
  const note = $("cb-note").value.trim();
  const complete = $("cb-complete").checked;
  const resEl = $("cb-result");
  if (!list || !taskId) {
    resEl.className = "cb-result err"; resEl.textContent = "목록과 대상 작업을 선택하세요.";
    return;
  }
  if (!note && !complete) {
    resEl.className = "cb-result err"; resEl.textContent = "노트를 쓰거나 완료 표시 중 하나는 필요합니다.";
    return;
  }
  const confirmMsg = `미리알림에 기록합니다.\n\n목록: ${list}\n작업: ${taskName}\n노트: ${note || "(없음)"}\n완료표시: ${complete ? "예" : "아니오"}\n\n실데이터가 변경됩니다. 진행할까요?`;
  if (!window.confirm(confirmMsg)) return;
  const btn = $("cb-submit");
  btn.disabled = true; btn.textContent = "기록 중...";
  try {
    const r = await fetch("/api/checkback", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ list, task_id: taskId, task_name: taskName, note, complete }),
    });
    const data = await r.json();
    if (data.ok) {
      resEl.className = "cb-result ok"; resEl.textContent = "✓ 미리알림에 기록되었습니다.";
      poll(true); // 백로그 카운트 갱신
    } else {
      resEl.className = "cb-result err";
      resEl.textContent = "실패: " + (data.error || JSON.stringify(data.results || ""));
    }
  } catch (e) {
    resEl.className = "cb-result err"; resEl.textContent = "요청 실패: " + e.message;
  } finally {
    btn.disabled = false; btn.textContent = "백로그에 기록";
  }
}

/* ── 자동화 제어판 ── */
let autoRoster = [];
function renderAutomation(data) {
  const cfg = data.config || {};
  autoRoster = data.roster || [];
  $("auto-enabled").checked = !!cfg.enabled;
  $("auto-interval").value = cfg.interval_min || 10;
  $("auto-dryrun").checked = cfg.dry_run !== false;
  // 상태 배지
  const stateEl = $("auto-state");
  stateEl.textContent = cfg.enabled
    ? `켜짐 · ${cfg.interval_min}분마다 · ${cfg.dry_run !== false ? "dry-run" : "실제 실행"}`
    : "꺼짐";
  stateEl.className = "auto-state " + (cfg.enabled ? "on" : "off");
  // 타깃 체크박스(로스터)
  const tg = $("auto-targets");
  const sel = new Set(cfg.targets || []);
  tg.innerHTML = autoRoster.map(name =>
    `<label class="target-chip ${sel.has(name) ? "sel" : ""}">
       <input type="checkbox" value="${esc(name)}" ${sel.has(name) ? "checked" : ""}>
       ${esc(name)}
     </label>`).join("");
  // 메타: 마지막/다음 발화
  const meta = [];
  if (cfg.last_tick_ts_ns) meta.push(`마지막 발화 ${relTime(cfg.last_tick_ts_ns)}`);
  else meta.push("아직 발화 없음");
  if (cfg.enabled && cfg.next_tick_ts_ns) {
    const ms = Number(cfg.next_tick_ts_ns) / 1e6 - Date.now();
    meta.push(ms > 0 ? `다음 발화 ~${Math.max(1, Math.round(ms / 60000))}분 후` : "곧 발화");
  }
  $("auto-meta").textContent = meta.join("  ·  ");
  // 로그
  const log = data.log || [];
  $("auto-log").innerHTML = log.length
    ? log.slice().reverse().map(e =>
        `<div class="log-row"><span class="lt">${relTime(e.ts_ns)}</span>
         <span class="li">${esc(e.identity)}</span>
         <span class="lm">${esc(e.mode)}${e.ok ? "" : " ✗"}</span>
         <span class="ln">${esc(e.note || "")}</span></div>`).join("")
    : '<div class="empty-note">발화 기록 없음</div>';
}

async function loadAutomation() {
  try {
    const r = await fetch("/api/automation");
    const data = await r.json();
    if (data.ok) renderAutomation(data);
  } catch (e) { /* 무시 — live dot이 연결상태 표시 */ }
}

async function saveAutomation() {
  const targets = [...$("auto-targets").querySelectorAll("input:checked")].map(i => i.value);
  const body = {
    enabled: $("auto-enabled").checked,
    interval_min: Number($("auto-interval").value) || 10,
    dry_run: $("auto-dryrun").checked,
    targets,
  };
  if (body.enabled && !body.dry_run) {
    if (!window.confirm(`자동화를 실제 실행 모드로 켭니다.\n\n${body.interval_min}분마다 [${targets.join(", ")}]을(를) 헤드리스 claude로 깨웁니다.\n토큰을 소비합니다. 진행할까요?`)) return;
  }
  const btn = $("auto-save");
  btn.disabled = true; btn.textContent = "적용 중…";
  try {
    const r = await fetch("/api/automation", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (data.ok) renderAutomation({ config: data.config, roster: autoRoster, log: [] });
    await loadAutomation();
  } catch (e) {
    $("auto-meta").textContent = "저장 실패: " + e.message;
  } finally {
    btn.disabled = false; btn.textContent = "적용";
  }
}

/* ── 폴링 ── */
async function poll(forceReminders = false) {
  try {
    const url = "/api/snapshot" + (forceReminders ? "?reminders=1" : "");
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const snap = await r.json();
    lastSnapshot = snap;
    renderReminders(snap.reminders);
    renderTeams(snap.teams);
    renderFeed(snap.decisions);
    renderNews(snap.news);
    $("live-dot").className = "live-dot on";
  } catch (e) {
    $("live-dot").className = "live-dot off";
  }
}

/* ── 부트 ── */
$("dp-close").addEventListener("click", closeDetail);
$("detail-overlay").addEventListener("click", closeDetail);
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDetail(); });
$("refresh-rem").addEventListener("click", () => poll(true));
$("live-dot").addEventListener("click", () => poll(false));  // §4.1 수동 새로고침
$("cb-list").addEventListener("change", () => loadTasksForList($("cb-list").value));
$("cb-submit").addEventListener("click", submitCheckback);
$("auto-save").addEventListener("click", saveAutomation);
$("auto-targets").addEventListener("change", e => {
  const chip = e.target.closest(".target-chip");
  if (chip) chip.classList.toggle("sel", e.target.checked);
});

poll(false);              // first paint
poll(true);               // refresh reminders
loadAutomation();            // 자동화 상태 로드
setInterval(() => poll(false), POLL_MS);  // 이후 10초 폴링(캐시 미리알림 → 렉 0)
setInterval(loadAutomation, 30000);       // 자동화 상태는 30초마다 갱신(발화 로그 반영)
