import { loadFoods, byCategory } from './data.js';
import { searchFoods } from './search.js';

const app = document.getElementById('app');
const CATEGORIES = [
  ['🥬', '채소'], ['🍎', '과일'], ['🍚', '밥·면·빵'],
  ['🍲', '국·찌개'], ['🍖', '고기·생선'], ['🍪', '간식·음료'],
];
const LEVEL_LABEL = { green: '좋음', amber: '주의', red: '피하기' };

let bundle = null;

const esc = s => String(s).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

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

// ── 첫 화면 ──
function showHome() {
  const recent = readRecent()
    .map(id => bundle.foods.find(f => f.id === id))
    .filter(Boolean);

  app.innerHTML = `
    <header class="brand">
      <h1>이거 먹어도 돼요?</h1>
      <p>당뇨 음식 찾기</p>
    </header>
    <div class="search">
      <span class="ic" aria-hidden="true">🔍</span>
      <input id="q" type="search" inputmode="search" autocomplete="off"
             placeholder="음식 이름을 쳐보세요" aria-label="음식 검색">
    </div>
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

  const input = document.getElementById('q');
  input.addEventListener('input', () => {
    const q = input.value.trim();
    if (q) showList(q);
  });
  app.querySelectorAll('[data-id]').forEach(el =>
    el.addEventListener('click', () => showDetail(el.dataset.id)));
  app.querySelectorAll('[data-cat]').forEach(el =>
    el.addEventListener('click', () => showCategory(el.dataset.cat)));
}

// Task 10, 11 에서 채운다.
function showList(query) { console.log('showList', query); }
function showCategory(cat) { console.log('showCategory', cat); }
function showDetail(id) { console.log('showDetail', id); }

// ── 시작 ──
async function start() {
  try {
    bundle = await loadFoods();
    showHome();
  } catch (err) {
    app.innerHTML = `
      <div class="empty">
        <h2>자료를 불러오지 못했어요</h2>
        <p>인터넷 연결을 확인해 주세요.</p>
        <button class="btn" id="retry">다시 시도</button>
      </div>`;
    document.getElementById('retry').addEventListener('click', start);
  }
}

start();
