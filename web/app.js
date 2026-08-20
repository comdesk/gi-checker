import { loadFoods, byCategory, foodById, groupMembers } from './data.js';
import { searchFoods } from './search.js';
import { listItem, matchHint, displayName, detailScreen, esc } from './render.js';
import { createNav } from './nav.js';
import { shareUrl, parseShareHash, shareText } from './share.js';

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

// 화면 이동은 전부 nav 를 거친다. 직접 그리는 함수를 부르면 방문 기록이
// 안 쌓여서 폰의 뒤로가기 버튼이 앱을 꺼버린다.
let nav = null;

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
    nav.go(q ? { kind: 'list', query: q } : { kind: 'home' });
  });
  clearBtn.addEventListener('click', () => {
    nav.go({ kind: 'home' });
    input.focus();
  });
}

// 검색창에 글자를 되돌려 넣는다. 사용자가 치고 있는 중이면 건드리지 않는다 —
// 한글은 조합 중인 글자가 input.value 안에 들어 있어서, 같은 값을 다시 써도
// 조합이 끊긴다.
function syncInput(text) {
  if (input.value.trim() !== text) input.value = text;
}

function wireItems() {
  screen.querySelectorAll('[data-id]').forEach(el =>
    el.addEventListener('click', () => nav.go({ kind: 'detail', id: el.dataset.id })));
}

// ── 첫 화면 ──
function paintHome() {
  shell.classList.remove('hidden', 'compact');
  searchBox.classList.remove('hidden');
  clearBtn.classList.add('hidden');
  subtitle.classList.remove('hidden');
  title.textContent = '이거 먹어도 돼요?';
  syncInput('');

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

  wireItems();
  screen.querySelectorAll('[data-cat]').forEach(el =>
    el.addEventListener('click', () => nav.go({ kind: 'category', name: el.dataset.cat })));
}

// ── 검색 결과 목록 ──
function paintList(query) {
  shell.classList.remove('hidden');
  shell.classList.add('compact');
  searchBox.classList.remove('hidden');
  clearBtn.classList.remove('hidden');
  subtitle.classList.add('hidden');
  title.textContent = '이거 먹어도 돼요?';
  syncInput(query);

  const hits = searchFoods(query, bundle.foods, 50);

  if (hits.length === 0) {
    screen.innerHTML = `
      <div class="empty">
        <h2>"${esc(query)}" 을(를) 못 찾았어요</h2>
        <p>이름을 조금 줄여서 쳐보세요.<br>예: "된장찌개" → "된장"</p>
        <button class="btn" id="tohome">카테고리에서 찾기</button>
      </div>`;
    document.getElementById('tohome')
      .addEventListener('click', () => nav.go({ kind: 'home' }));
    return;
  }

  const hint = matchHint(hits[0].kind, hits[0].food);
  screen.innerHTML = (hint ? `<p class="hint">${hint}</p>` : '')
    + `<p class="cnt">${hits.length}개</p>`
    + `<div class="list">${hits.map(h => listItem(h.food)).join('')}</div>`;

  wireItems();
}

// ── 카테고리 목록 ──
function paintCategory(category, backLabel) {
  shell.classList.add('hidden');
  searchBox.classList.add('hidden');

  const foods = byCategory(bundle, category)
    .sort((a, b) => {
      const [x, y] = [displayName(a), displayName(b)];
      return x.length - y.length || x.localeCompare(y, 'ko');
    })
    .slice(0, 200);

  screen.innerHTML = `
    <button class="nav" id="back"><span class="back">‹</span> ${esc(backLabel ?? '처음으로')}</button>
    <header class="brand" style="padding-top:0"><h1>${esc(category)}</h1></header>
    <p class="cnt">${foods.length}개</p>
    <div class="list">${foods.map(listItem).join('')}</div>`;

  document.getElementById('back').addEventListener('click', () => nav.back());
  wireItems();
}

// ── 상세 화면 ──
function paintDetail(id, backLabel) {
  const food = foodById(bundle, id);
  if (!food) { paintHome(); return; }

  pushRecent(id);
  shell.classList.add('hidden');          // 상세에서는 검색창을 감춘다
  searchBox.classList.add('hidden');      // DOM 에서 제거하지 않는다 (조합 상태 보존)
  screen.innerHTML = detailScreen(food, groupMembers(bundle, food), backLabel);

  // 화면 위의 '‹' 버튼과 폰의 뒤로가기 버튼은 같은 동작이어야 한다.
  // 둘이 다른 곳으로 가면 어느 쪽을 눌렀는지에 따라 결과가 달라진다.
  document.getElementById('back').addEventListener('click', () => nav.back());
  screen.querySelectorAll('.way[data-id]').forEach(el =>
    el.addEventListener('click', () => nav.go({ kind: 'detail', id: el.dataset.id })));

  // 공유. 폰의 공유 시트를 여는 내장 기능이 있을 때만 버튼을 보인다
  // (데스크톱 구형 브라우저 등에서는 조용히 빠진다 — 즐겨찾기와 같은 원칙).
  const share = document.getElementById('share');
  if (navigator.share) {
    share.hidden = false;
    share.addEventListener('click', () => {
      navigator.share({
        text: shareText(food),
        url: shareUrl(location.origin + location.pathname, food.id),
      }).catch(() => { /* 공유 시트를 그냥 닫은 것 — 오류가 아니다 */ });
    });
  }
}

// nav 가 상태 하나를 넘겨주면 그 화면을 그린다. 방문 기록은 nav 가 관리하므로
// 여기서는 그리기만 한다.
function paint(state, scrollY) {
  if (state.kind === 'list') paintList(state.query);
  else if (state.kind === 'category') paintCategory(state.name, state.back);
  else if (state.kind === 'detail') paintDetail(state.id, state.back);
  else paintHome();
  window.scrollTo(0, scrollY);
}

// 뒤로가기 버튼에 쓸 "돌아갈 곳" 이름.
function labelOf(state) {
  if (!state) return null;
  if (state.kind === 'list') return '검색으로';
  if (state.kind === 'category') return state.name;
  if (state.kind === 'detail') {
    const food = foodById(bundle, state.id);
    return food ? displayName(food) : '뒤로';
  }
  return '처음으로';
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

    // 스크롤 복원은 우리가 한다. 브라우저에 맡기면 화면을 다 그리기 전에
    // 옛 위치로 튀어서 엉뚱한 자리에 멈춘다.
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

    nav = createNav({
      history,
      render: paint,
      scrollY: () => window.scrollY,
      label: labelOf,
    });
    window.addEventListener('popstate', e => nav.restore(e.state));

    mountShell();

    // 공유 링크(#f=음식id)로 들어왔으면 그 음식 화면을 바로 연다.
    // 해시는 읽자마자 지운다 — 이 앱의 주소는 언제나 하나라는 원칙(nav.js)은
    // 그대로 두고, 해시는 들어올 때 한 번 쓰는 입장권으로만 쓴다.
    // 첫 화면을 깔고 그 위에 얹으므로 받은 사람의 뒤로가기는 첫 화면으로 간다.
    const sharedId = parseShareHash(location.hash);
    if (location.hash) history.replaceState(null, '', location.pathname + location.search);
    nav.start({ kind: 'home' });
    if (sharedId && foodById(bundle, sharedId)) nav.go({ kind: 'detail', id: sharedId });

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
