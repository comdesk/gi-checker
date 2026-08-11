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
