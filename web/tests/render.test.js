import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detailScreen, listItem, nutrientTable } from '../render.js';

// Task 11B Step 3: '100g 기준' 은 분량이 아니라 영양성분의 기준량이므로
// '보통 한 번에' 문구를 달면 안 된다. 실제 분량(grams)이 있을 때만 단다.
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

test('100g 기준 뿐이고 실제 분량을 모르면 보통 한 번에 줄이 없다', () => {
  const html = detailScreen(base(), null);
  assert.ok(!html.includes('보통 한 번에'), html);
});

test('실제 분량(grams)이 있으면 보통 한 번에 줄이 있다', () => {
  const food = base({
    serving: { label: '292ml', grams: 292, isPackage: false },
  });
  const html = detailScreen(food, null);
  assert.ok(html.includes('보통 한 번에'), html);
  assert.ok(html.includes('292ml'), html);
});

test('포장 전체(isPackage)면 grams 가 있어도 보통 한 번에 줄이 없다', () => {
  const food = base({
    serving: { label: '1500g', grams: 1500, isPackage: true },
  });
  const html = detailScreen(food, null);
  assert.ok(!html.includes('보통 한 번에'), html);
});

test('빨강 등급이면 실제 분량이 있어도 보통 한 번에 줄이 없다', () => {
  const food = base({
    serving: { label: '292ml', grams: 292, isPackage: false },
    verdict: { level: 'red', reason: 'nutrient' },
  });
  const html = detailScreen(food, null);
  assert.ok(!html.includes('보통 한 번에'), html);
});

// Task 11C: 답이 같은 품종을 한 줄로 합친 대표 레코드는 영양성분을 펼쳤을 때
// 어떤 품종이 합쳐졌는지 보여줘야 한다.
test('variants 가 2개 이상이면 영양성분 안에 품종 목록이 보인다', () => {
  const food = base({ display: '찐 감자', variants: ['대지', '수미', '자색'] });
  const html = nutrientTable(food);
  assert.ok(html.includes('품종 3종 · 대지, 수미, 자색'), html);
});

test('variants 가 없으면 품종 줄이 안 나온다', () => {
  const html = nutrientTable(base());
  assert.ok(!html.includes('품종'), html);
});

test('목록 화면(listItem)에는 품종 줄이 나오지 않는다 — 목록은 이미 빽빽하다', () => {
  const food = base({ variants: ['대지', '수미', '자색'] });
  const html = listItem(food);
  assert.ok(!html.includes('품종'), html);
});

// ── 판단할 수 없는 음식(unknown) ────────────────────────────────
// 원본에 당류·식이섬유가 없어 최선/최악의 판정이 갈리는 경우다.
// 신호등의 네 번째 색이 아니라 '신호등을 켤 수 없음' 이다.

const unsure = (overrides = {}) => base({
  display: '당밀 가공당',
  nutrients: { kcal: 274, carb: 68.2, sugar: null, fiber: null, fat: null, sodium: 10 },
  verdict: { level: 'unknown', reason: 'insufficient' },
  ...overrides,
});

test('판단할 수 없으면 좋다 나쁘다 말하지 않는다', () => {
  const html = detailScreen(unsure(), null);
  assert.ok(html.includes('알 수 없음'), html);
  for (const lie of ['드셔도 좋아요', '조금만 드세요', '드시지 마세요', '혈당을 빠르게 올립니다']) {
    assert.ok(!html.includes(lie), `unknown 인데 "${lie}" 가 나왔다`);
  }
});

test('판단할 수 없는 이유로 어떤 값이 없는지 밝힌다', () => {
  const html = detailScreen(unsure(), null);
  assert.ok(html.includes('당류'), html);
  assert.ok(html.includes('식이섬유'), html);
  assert.ok(html.includes('68.2g'), '아는 값(탄수화물)은 보여줘야 한다');
});

test('판단할 수 없으면 권장량을 말하지 않는다', () => {
  const html = detailScreen(
    unsure({ serving: { label: '200g', grams: 200, isPackage: false } }), null);
  assert.ok(!html.includes('보통 한 번에'), '판단 못 하면서 먹는 양을 말하면 판단한 것처럼 읽힌다');
});

test('모르는 영양성분을 0으로 표시하지 않는다', () => {
  const html = nutrientTable(unsure());
  assert.ok(html.includes('정보 없음'), html);
  assert.ok(!/당류<\/span><span[^>]*>0g/.test(html), '모르는 값을 0g 이라고 하면 거짓말이다');
});

test('물려받은 값은 추정이라고 밝힌다', () => {
  const html = nutrientTable(base({
    nutrients: { kcal: 340, carb: 78, sugar: 58.1, fiber: 17.8, fat: 1, sodium: 5 },
    estimated: ['fiber', 'sugar'],
  }));
  assert.ok(html.includes('추정'), html);
  assert.ok(html.includes('실제와 다를 수 있습니다'), html);
});

test('측정값만 있으면 추정 표시가 없다', () => {
  const html = nutrientTable(base({ estimated: [] }));
  assert.ok(!html.includes('추정'), html);
});

test('목록에서도 unknown 이 색으로 오해되지 않는다', () => {
  const html = listItem(unsure());
  assert.ok(html.includes('var(--unknown)'), html);
  assert.ok(html.includes('모름'), html);
});

test('판단 못 한 음식에 판정했다고 말하지 않는다', () => {
  const html = detailScreen(unsure(), null);
  assert.ok(!html.includes('영양성분으로 판정했습니다'),
    '판단할 수 없다고 해놓고 판정했다고 하면 모순이다');
});

test('그룹 키가 아니라 사람이 부르는 이름을 보여준다', () => {
  // 키 '호박 단호박' 은 다른 그룹과 겹치지 않기 위한 것이다.
  // 뒤로가기 버튼과 조리법 비교 제목에 그대로 나오면 안 된다.
  const food = base({
    display: '찐 단호박', group: '호박 단호박', groupLabel: '단호박',
    method: '찌기', verdict: { level: 'red', reason: 'gi' },
  });
  const html = detailScreen(food, [food, base({ id: 'y', method: '생것' })]);
  assert.ok(html.includes('단호박'), html);
  assert.ok(!html.includes('호박 단호박'), '그룹 키가 화면에 새어나왔다');
});

test('groupLabel 이 없으면 group 을 그대로 쓴다', () => {
  const food = base({ group: '고구마', method: '찌기' });
  const html = detailScreen(food, [food, base({ id: 'y', method: '생것' })]);
  assert.ok(html.includes('고구마'), html);
});
