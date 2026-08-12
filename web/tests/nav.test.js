import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createNav } from '../nav.js';

// 브라우저 없이 기록이 어떻게 쌓이는지 보려고 만든 가짜 history.
// 진짜 브라우저에서 back() 은 비동기지만, 여기서는 바로 popstate 를 부른다.
// 확인하려는 것은 "기록이 몇 개 쌓였고 뒤로 가면 어디로 가는가" 이므로
// 타이밍은 상관없다.
function fakeHistory() {
  const entries = [];
  let i = -1;
  const h = {
    exited: false,
    onpop: () => {},
    get state() { return i >= 0 ? entries[i] : null; },
    get entries() { return entries; },
    get index() { return i; },
    pushState(s) { entries.splice(i + 1); entries.push(s); i = entries.length - 1; },
    replaceState(s) { if (i < 0) { entries.push(s); i = 0; } else entries[i] = s; },
    back() {
      if (i > 0) { i -= 1; h.onpop(entries[i]); }
      else { h.exited = true; }          // 진짜 브라우저였다면 앱이 닫힌다
    },
  };
  return h;
}

// 화면 이름을 뒤로가기 버튼 라벨로 쓴다 (app.js 가 하는 일의 축소판)
const label = s => {
  if (!s) return null;
  if (s.kind === 'home') return '처음으로';
  if (s.kind === 'list') return '검색으로';
  if (s.kind === 'category') return s.name;
  return s.id;
};

function setup({ scrollY = () => 0 } = {}) {
  const history = fakeHistory();
  const painted = [];
  const nav = createNav({
    history,
    scrollY,
    label,
    render: (state, y) => painted.push({ ...state, at: y }),
  });
  history.onpop = s => nav.restore(s);
  nav.start({ kind: 'home' });
  return { history, nav, painted, last: () => painted[painted.length - 1] };
}

test('첫 화면은 기록을 쌓지 않는다 — 쌓으면 뒤로가기로 앱이 안 닫혀 갇힌다', () => {
  const { history } = setup();
  assert.equal(history.entries.length, 1);
  history.back();
  assert.equal(history.exited, true);
});

test('상세로 들어가면 기록이 하나 쌓이고 뒤로가기로 되돌아온다', () => {
  const { history, nav, last } = setup();
  nav.go({ kind: 'detail', id: 'A' });

  assert.equal(history.entries.length, 2);
  assert.equal(last().kind, 'detail');

  history.back();
  assert.equal(history.exited, false, '앱이 닫히면 안 된다');
  assert.equal(last().kind, 'home');
});

test('검색어를 여러 글자 쳐도 기록은 하나만 쌓인다', () => {
  const { history, nav, last } = setup();
  for (const q of ['고', '고구', '고구마']) nav.go({ kind: 'list', query: q });

  assert.equal(history.entries.length, 2, '글자 수만큼 뒤로가기를 누르게 하면 안 된다');
  assert.equal(last().query, '고구마');

  history.back();
  assert.equal(last().kind, 'home');
});

test('검색어를 지우면 기록이 늘지 않고 첫 화면으로 돌아간다', () => {
  const { history, nav, last } = setup();
  nav.go({ kind: 'list', query: '고구마' });
  nav.go({ kind: 'home' });                    // ✕ 를 누르거나 글자를 다 지운 경우

  assert.equal(last().kind, 'home');
  assert.equal(history.index, 0,
    '첫 화면으로 되돌아간 것이지 새 화면으로 간 것이 아니다');
  history.back();
  assert.equal(history.exited, true);
});

test('검색 → 상세 → 뒤로 하면 검색 결과가 그대로 남는다', () => {
  const { history, nav, last } = setup();
  nav.go({ kind: 'list', query: '고구마' });
  nav.go({ kind: 'detail', id: 'A' });

  history.back();
  assert.equal(last().kind, 'list');
  assert.equal(last().query, '고구마');
});

test('상세에서 상세로 옮겨가도 한 걸음씩 되짚어 나온다', () => {
  const { history, nav, last } = setup();
  nav.go({ kind: 'category', name: '채소' });
  nav.go({ kind: 'detail', id: 'A' });
  nav.go({ kind: 'detail', id: 'B' });         // 조리법 비교에서 옆 항목으로

  history.back();
  assert.equal(last().id, 'A');
  history.back();
  assert.equal(last().kind, 'category');
  history.back();
  assert.equal(last().kind, 'home');
});

test('뒤로 돌아오면 보던 자리로 스크롤이 복원된다', () => {
  let y = 0;
  const { history, nav, last } = setup({ scrollY: () => y });
  nav.go({ kind: 'category', name: '채소' });
  y = 840;                                     // 목록을 한참 내려서 본 상태
  nav.go({ kind: 'detail', id: 'A' });

  assert.equal(last().at, 0, '새 화면은 맨 위에서 시작한다');
  history.back();
  assert.equal(last().at, 840);
});

test('뒤로가기 버튼에는 돌아갈 곳 이름이 붙는다', () => {
  const { nav, last } = setup();
  nav.go({ kind: 'category', name: '채소' });
  assert.equal(last().back, '처음으로');
  nav.go({ kind: 'detail', id: 'A' });
  assert.equal(last().back, '채소');
});

test('남의 기록에서 넘어와 popstate 가 비어 있으면 첫 화면을 그린다', () => {
  const { nav, last } = setup();
  nav.restore(null);
  assert.equal(last().kind, 'home');
});
