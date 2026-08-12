import { loadFoods, byCategory, foodById, groupMembers } from './data.js';
import { searchFoods } from './search.js';
import { listItem, matchHint, displayName, detailScreen, esc } from './render.js';

const shell = document.getElementById('shell');
const title = document.getElementById('title');
const subtitle = document.getElementById('subtitle');
const searchBox = document.getElementById('searchBox');
const input = document.getElementById('q');
const clearBtn = document.getElementById('clear');
const screen = document.getElementById('screen');

const CATEGORIES = [
  ['🥬', '채소'], ['🍎', '과일'], ['🍚', '밥·면·빵'],
  ['🍲', '국·찌개'], ['🍖', '고기·생선'], ['🍪', '간식·음료'],
];

let bundle = null;
// 상세에서 뒤로 갈 때 온 곳으로 되돌아가야 한다.
// 검색으로 왔으면 그 검색 결과로, 카테고리로 왔으면 그 카테고리로.
// showDetail 은 이 값을 건드리지 않는다 — 조리법 항목을 눌러 상세끼리
// 이동해도 원래 온 곳을 잊으면 안 된다.
let lastScreen = { kind: 'home' };   // {kind:'home'} | {kind:'list', query} | {kind:'category', name}

// ── 즐겨찾기 (localStorage 를 못 쓰면 조용히 비활성) ──
const FAV_KEY = 'diabetes-food:recent';

function readRecent() {
  try {
    return JSON.parse(localStorage.getItem(FAV_KEY) ?? '[]');
  } catch { return []; }
}

function pushRecent(id) {
  try {
    const list = [id, ...readRecent().filter(x => x !== id)].slice(0, 8);
    localStorage.setItem(FAV_KEY, JSON.stringify(list));
  } catch { /* 사파리 프라이빗 모드 등 — 기능만 조용히 빠진다 */ }
}

// ── 검색창 셸: 앱 시작 시 한 번만 붙이고 다시 그리지 않는다.
// 화면을 바꿀 때마다 input 을 새로 만들면 한글 조합 중이던 상태가 사라진다. ──
function mountShell() {
  input.addEventListener('input', () => {
    const q = input.value.trim();
    if (q) showList(q);
    else showHome();
  });
  clearBtn.addEventListener('click', () => {
    showHome();
    input.focus();
  });
}

function wireItems() {
  screen.querySelectorAll('.item[data-id]').forEach(el =>
    el.addEventListener('click', () => showDetail(el.dataset.id)));
}

// ── 첫 화면 ──
function showHome() {
  shell.classList.remove('hidden', 'compact');
  searchBox.classList.remove('hidden');
  clearBtn.classList.add('hidden');
  subtitle.classList.remove('hidden');
  title.textContent = '이거 먹어도 돼요?';
  input.value = '';
  lastScreen = { kind: 'home' };

  const recent = readRecent()
    .map(id => bundle.foods.find(f => f.id === id))
    .filter(Boolean);

  screen.innerHTML = `
    ${recent.length ? `
    <section class="sec">
      <h2 class="sec-h">자주 찾는 것</h2>
      <div class="chips">
        ${recent.map(f => `
          <button class="chip" data-id="${esc(f.id)}">
            <span class="d" style="background:var(--${f.verdict.level})"></span>${esc(f.display ?? f.name)}
          </button>`).join('')}
      </div>
    </section>` : ''}
    <section class="sec">
      <h2 class="sec-h">눌러서 찾기</h2>
      <div class="grid">
        ${CATEGORIES.map(([e, name]) => `
          <button class="cat" data-cat="${esc(name)}">
            <span class="e" aria-hidden="true">${e}</span>${esc(name)}
          </button>`).join('')}
      </div>
    </section>
    <p class="disclaimer">
      참고용입니다. 치료나 식단은 담당 의사·영양사와 상의하세요.
    </p>`;

  screen.querySelectorAll('[data-id]').forEach(el =>
    el.addEventListener('click', () => showDetail(el.dataset.id)));
  screen.querySelectorAll('[data-cat]').forEach(el =>
    el.addEventListener('click', () => showCategory(el.dataset.cat)));

  window.scrollTo(0, 0);
}

// ── 검색 결과 목록 ──
function showList(query) {
  shell.classList.remove('hidden');
  shell.classList.add('compact');
  searchBox.classList.remove('hidden');
  clearBtn.classList.remove('hidden');
  subtitle.classList.add('hidden');
  title.textContent = '이거 먹어도 돼요?';
  lastScreen = { kind: 'list', query };

  const hits = searchFoods(query, bundle.foods, 50);

  if (hits.length === 0) {
    screen.innerHTML = `
      <div class="empty">
        <h2>"${esc(query)}" 을(를) 못 찾았어요</h2>
        <p>이름을 조금 줄여서 쳐보세요.<br>예: "된장찌개" → "된장"</p>
        <button class="btn" id="tohome">카테고리에서 찾기</button>
      </div>`;
    document.getElementById('tohome').addEventListener('click', () => showHome());
    window.scrollTo(0, 0);
    return;
  }

  const hint = matchHint(hits[0].kind, hits[0].food);
  screen.innerHTML = (hint ? `<p class="hint">${hint}</p>` : '')
    + `<p class="cnt">${hits.length}개</p>`
    + `<div class="list">${hits.map(h => listItem(h.food)).join('')}</div>`;

  wireItems();
  window.scrollTo(0, 0);
}

// ── 카테고리 목록 ──
function showCategory(category) {
  shell.classList.add('hidden');
  searchBox.classList.add('hidden');
  lastScreen = { kind: 'category', name: category };

  const foods = byCategory(bundle, category)
    .sort((a, b) => {
      const [x, y] = [displayName(a), displayName(b)];
      return x.length - y.length || x.localeCompare(y, 'ko');
    })
    .slice(0, 200);

  screen.innerHTML = `
    <button class="nav" id="back"><span class="back">‹</span> 처음으로</button>
    <header class="brand" style="padding-top:0"><h1>${esc(category)}</h1></header>
    <p class="cnt">${foods.length}개</p>
    <div class="list">${foods.map(listItem).join('')}</div>`;

  document.getElementById('back').addEventListener('click', () => showHome());
  wireItems();
  window.scrollTo(0, 0);
}

// ── 상세 화면 ──
function showDetail(id) {
  const food = foodById(bundle, id);
  if (!food) { showHome(); return; }

  pushRecent(id);
  shell.classList.add('hidden');          // 상세에서는 검색창을 감춘다
  searchBox.classList.add('hidden');      // DOM 에서 제거하지 않는다 (조합 상태 보존)
  screen.innerHTML = detailScreen(food, groupMembers(bundle, food));
  window.scrollTo(0, 0);

  document.getElementById('back').addEventListener('click', () => {
    if (lastScreen.kind === 'list') showList(lastScreen.query);
    else if (lastScreen.kind === 'category') showCategory(lastScreen.name);
    else showHome();
  });
  screen.querySelectorAll('.way[data-id]').forEach(el =>
    el.addEventListener('click', () => showDetail(el.dataset.id)));
}

// ── 오프라인 ──
// 서비스워커 등록은 앱이 뜬 뒤에 한다. 등록이 실패해도(사파리 프라이빗 모드,
// http 로 연 경우 등) 앱은 그냥 온라인 전용으로 동작하면 되므로 조용히 넘긴다.
function registerOffline() {
  if (!('serviceWorker' in navigator)) return;
  // 상대 경로여야 한다 — GitHub Pages 는 /저장소이름/ 아래에 얹힌다.
  navigator.serviceWorker.register('sw.js').catch(() => {});
}

// ── 시작 ──
async function start() {
  try {
    bundle = await loadFoods();
    mountShell();
    showHome();
    registerOffline();
  } catch (err) {
    screen.innerHTML = `
      <div class="empty">
        <h2>자료를 불러오지 못했어요</h2>
        <p>인터넷 연결을 확인해 주세요.</p>
        <button class="btn" id="retry">다시 시도</button>
      </div>`;
    document.getElementById('retry').addEventListener('click', start);
  }
}

start();
