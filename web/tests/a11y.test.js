// 접근성 검사(2026-08)에서 나온 문제들을 못 박는다.
// 사용자는 60대다 — 대비와 스크린리더는 이 앱에서 장식이 아니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as render from '../render.js';

const CSS = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
const HTML = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

const NUT = { kcal: 100, carb: 20, sugar: 1, fiber: 1, fat: 0.1, sodium: 5 };
const base = (overrides) => ({
  id: 'x', name: '테스트', display: '테스트', group: null, method: null,
  category: '채소',
  serving: { label: '100g 기준', grams: null, isPackage: false },
  nutrients: NUT,
  perServing: null,
  gi: { value: null, kind: 'none', basis: null },
  verdict: { level: 'green', reason: 'nutrient' },
  source: null, caution: null,
  ...overrides,
});
const amber = (overrides) => base({
  gi: { value: 65, kind: 'measured', basis: null },
  verdict: { level: 'amber', reason: 'gi' },
  ...overrides,
});

// ── 색 대비 (WCAG AA: 일반 글자 4.5:1) ─────────────────────
// 실측: --amber(#d99a1f)는 흰 바탕에서 2.4:1 — 목록의 '주의' 글자가
// 제일 안 보이는 글자였다. 글자 색으로 쓰는 토큰만 검사한다.
// 점·배지·배경으로만 쓰는 --amber 자체는 글자가 아니므로 여기 없다.

function luminance(hex) {
  const [r, g, b] = [0, 2, 4]
    .map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrastOnWhite = hex => 1.05 / (luminance(hex) + 0.05);
function token(name) {
  const m = CSS.match(new RegExp(`--${name}:\\s*#([0-9a-fA-F]{6})`));
  assert.ok(m, `styles.css 에 --${name} 토큰이 없다`);
  return m[1];
}

test('글자로 쓰는 색은 전부 흰 바탕에서 4.5:1 을 넘는다', () => {
  for (const name of ['ink', 'ink2', 'ink3',
    'green-ink', 'amber-ink', 'red-ink', 'unknown-ink']) {
    const ratio = contrastOnWhite(token(name));
    assert.ok(ratio >= 4.5,
      `--${name} 이 ${ratio.toFixed(2)}:1 — 60대 눈에는 더 안 보인다`);
  }
});

// ── 신호등 글자는 진한 -ink 색으로 ────────────────────────
// 연한 --amber 로 '주의' 를 쓰면 위 대비 검사를 통과 못 한다.
// 숫자(gn)는 원래 -ink 였는데 글자(gl)만 연한 색이었다.

test('목록의 신호등 글자는 -ink 색을 쓴다', () => {
  const html = render.listItem(amber());
  assert.ok(html.includes('"gl" style="color:var(--amber-ink)"'), html);
});

test('조리법 비교의 신호등 글자도 -ink 색을 쓴다', () => {
  const me = amber({ method: '굽기' });
  const other = amber({ id: 'y', method: '찌기' });
  const html = render.waysList(me, [me, other]);
  assert.ok(html.includes('"s" style="color:var(--amber-ink)"'), html);
});

// ── 스크린리더 ─────────────────────────────────────────────

test('뒤로가기의 ‹ 기호는 스크린리더에게 숨긴다', () => {
  // 목록의 › (.arw) 는 처음부터 숨겼는데 이쪽만 빠져 있었다.
  const html = render.detailScreen(base(), null);
  assert.ok(html.includes('<span class="back" aria-hidden="true">'), html);
});

test('GI 눈금 막대와 숫자는 스크린리더에게 숨긴다', () => {
  // 값은 이미 "GI 지수 65" 로 읽힌다. 눈금의 0 55 70 100 까지 읽으면
  // 맥락 없는 숫자 나열이 된다.
  const html = render.giMeter(amber());
  assert.ok(html.includes('<div class="track" aria-hidden="true">'), html);
  assert.ok(html.includes('<div class="scale" aria-hidden="true">'), html);
});

test('상세 제목은 포커스를 받을 수 있다', () => {
  // 화면을 갈아끼우면 포커스가 body 로 떨어진다(실기기에서 확인).
  // 앱이 제목에 포커스를 옮겨야 "바뀌었다 + 어디로 왔다"가 전달된다.
  const html = render.detailScreen(base(), null);
  assert.ok(html.includes('<h1 class="name" tabindex="-1">'), html);
});

test('자주 찾는 것 칩에도 신호등이 글자로 있다', () => {
  // 목록·상세는 색 옆에 글자가 있는데 칩만 색 점뿐이었다.
  // 눈에는 지금처럼 점만 보이고, 리더에게만 수준이 읽힌다.
  const html = render.chipItem(base());
  assert.ok(html.includes('data-id="x"'), html);
  assert.ok(html.includes('<span class="sr-only">좋음</span>'), html);
});

test('숨김 글자용 .sr-only 가 정의되어 있다', () => {
  assert.ok(/\.sr-only\s*\{[^}]*position:absolute[^}]*\}/.test(CSS),
    '.sr-only 가 없으면 숨김 글자가 화면에 그대로 보인다');
});

test('앱 전체를 라이브 영역으로 만들지 않는다', () => {
  // aria-live 가 #app 에 있으면 화면이 바뀔 때마다 새 내용 전부를,
  // 검색은 한 글자마다 결과 50개를 처음부터 다시 낭독한다.
  assert.ok(!HTML.includes('aria-live'), 'aria-live 는 앱 전체가 아니라 좁은 알림 영역에');
});

test('검색 결과 개수를 알릴 좁은 알림 영역이 있다', () => {
  // 검색 중에는 포커스가 입력창에 남으므로(옮기면 타이핑이 끊긴다)
  // 결과가 바뀐 것은 role="status" 로만 전달된다.
  assert.ok(/id="status"[^>]*role="status"|role="status"[^>]*id="status"/.test(HTML),
    'role="status" 알림 영역이 없으면 검색 결과 변화가 리더에게 조용하다');
});
