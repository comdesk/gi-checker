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

test('펼치기 화살표는 글자가 아니라 아이콘이다', () => {
  // '⌄' 글자는 글꼴마다 세로 위치가 달라 글씨와 어긋나 보였다.
  // 펼침 여부에 따른 회전은 CSS(details[open] .chev)가 한다.
  const html = nutrientTable(base());
  assert.ok(html.includes('class="chev"'), html);
  assert.ok(!html.includes('⌄'), '글자 화살표가 남아 있다');
  assert.ok(html.includes('aria-hidden="true"'), '읽어주기에서 빠져야 한다');
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

// ── 한 번에 먹어도 되는 양 (식품교환표 1교환단위량) ──────────────
// 앱이 '먹어도 되나' 만 답하면 부족하다 — 사과가 초록이라고 세 개를 드시면
// 초록인 의미가 없다. 다만 '드시지 마세요' 아래에 분량을 적으면 먹어도
// 된다는 말로 읽히므로 빨강·알 수 없음에는 내보내지 않는다.

const APPLE = { grams: 80, eyeball: '중 1/3개', foodGroup: '과일군', advice: '하루 1~2번' };

test('1회 분량이 있으면 한 번에 이만큼 상자가 나온다', () => {
  const html = detailScreen(base({ exchange: APPLE }), null);
  assert.ok(html.includes('한 번에 이만큼'), html);
  assert.ok(html.includes('80g'), html);
  assert.ok(html.includes('중 1/3개'), html);
  assert.ok(html.includes('하루 1~2번'), html);
  assert.ok(html.includes('대한당뇨병학회 식품교환표'), html);
});

test('1회 분량 자료가 없으면 상자가 없다', () => {
  const html = detailScreen(base(), null);
  assert.ok(!html.includes('한 번에 이만큼'), html);
});

test('빨강이면 1회 분량을 말하지 않는다 — 먹어도 된다는 말로 읽힌다', () => {
  const food = base({ exchange: APPLE, verdict: { level: 'red', reason: 'gi' } });
  const html = detailScreen(food, null);
  assert.ok(!html.includes('한 번에 이만큼'), html);
});

test('판단할 수 없으면 1회 분량을 말하지 않는다', () => {
  const food = base({
    exchange: APPLE, verdict: { level: 'unknown', reason: 'insufficient' },
  });
  const html = detailScreen(food, null);
  assert.ok(!html.includes('한 번에 이만큼'), html);
});

test('목측량과 한 줄 조언은 없어도 상자가 나온다', () => {
  const food = base({ exchange: { grams: 150, foodGroup: '과일군' } });
  const html = detailScreen(food, null);
  assert.ok(html.includes('한 번에 이만큼'), html);
  assert.ok(html.includes('150g'), html);
  assert.ok(!html.includes('하루'), html);
});

test('식이섬유가 많으면 그렇다고 알려준다', () => {
  const food = base({ exchange: { ...APPLE, fiberRich: true } });
  const html = detailScreen(food, null);
  assert.ok(html.includes('식이섬유가 많은 편입니다'), html);
});

test('식이섬유 표시가 없으면 그 줄도 없다', () => {
  const html = detailScreen(base({ exchange: APPLE }), null);
  assert.ok(!html.includes('식이섬유가 많은'), html);
});

test('빨강이면 식이섬유가 많아도 상자째 안 나온다', () => {
  // '드시지 마세요' 아래에 권장 문구가 붙으면 앞뒤가 맞지 않는다.
  const food = base({
    exchange: { ...APPLE, fiberRich: true },
    verdict: { level: 'red', reason: 'gi' },
  });
  const html = detailScreen(food, null);
  assert.ok(!html.includes('식이섬유가 많은'), html);
});

test('채소는 분량과 함께 충분히 드시라는 말을 같이 한다', () => {
  // 채소에 분량만 덩그러니 띄우면 있지도 않은 제한을 만든다.
  const food = base({
    exchange: { grams: 70, foodGroup: '채소군', advice: '채소는 충분히 드셔도 좋습니다' },
  });
  const html = detailScreen(food, null);
  assert.ok(html.includes('70g'), html);
  assert.ok(html.includes('충분히 드셔도 좋습니다'), html);
});

test('단위가 있으면 그것을 쓴다 — 우유는 g 이 아니라 mL 다', () => {
  const food = base({
    exchange: { grams: 200, eyeball: '1컵', foodGroup: '우유군', unit: 'mL' },
  });
  const html = detailScreen(food, null);
  assert.ok(html.includes('200mL'), html);
  assert.ok(!html.includes('200g'), html);
});

test('1회 분량은 영양성분의 100g 기준과 다른 자리에 나온다', () => {
  // 두 숫자를 같은 상자에 섞으면 몇 배씩 잘못 읽는다 (실제로 겪은 문제).
  const html = detailScreen(base({ exchange: APPLE }), null);
  assert.ok(html.indexOf('한 번에 이만큼') < html.indexOf('영양성분 자세히 보기'), html);
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
  const food = base({
    group: '고구마', method: '찌기', verdict: { level: 'red', reason: 'gi' },
  });
  const html = detailScreen(food, [food, base({ id: 'y', method: '생것' })]);
  assert.ok(html.includes('고구마'), html);
});

// 뒤로가기 버튼은 "돌아갈 곳"을 말해야 한다. 예전에는 그룹 이름을 붙였는데,
// 실제로 돌아가는 곳은 그룹이 아니라 직전 화면(검색 결과·카테고리·다른 상세)이라
// 이름과 동작이 어긋났다. 이제 앱이 방문 기록에서 꺼내 넘겨준다.
test('뒤로가기 버튼에 앱이 넘겨준 이름이 붙는다', () => {
  const html = detailScreen(base({ group: '고구마' }), null, '채소');
  assert.match(html, /id="back"[^]*?채소/);
  assert.ok(!/id="back"[^]*?고구마/.test(html), '그룹 이름은 돌아갈 곳이 아니다');
});

test('돌아갈 곳 이름이 없으면 그냥 뒤로라고 한다', () => {
  const html = detailScreen(base(), null);
  assert.match(html, /id="back"[^]*?뒤로/);
});

// ── 양념 고지 ────────────────────────────────────────────────
// 조미 오징어 26.6g / 그냥 구운 오징어 0.1g. 그 26g 은 오징어가 아니라 양념이다.

const seasoned = (o = {}) => base({
  id: 's', display: '조미하여 구운 오징어', group: '오징어류 육', method: '굽기',
  seasoning: '양념',
  nutrients: { kcal: 200, carb: 26.6, sugar: 12, fiber: 0.5, fat: 2, sodium: 900 },
  verdict: { level: 'red', reason: 'nutrient' },
  ...o,
});
const plain = (o = {}) => base({
  id: 'p', display: '구운 오징어', group: '오징어류 육', method: '굽기',
  nutrients: { kcal: 100, carb: 0.1, sugar: 0, fiber: 0, fat: 1, sodium: 300 },
  verdict: { level: 'green', reason: 'low-carb' },
  ...o,
});

test('양념이 되어 있으면 상세에서 밝힌다', () => {
  const html = detailScreen(seasoned(), null);
  assert.ok(html.includes('양념이 되어 있습니다'), html);
  assert.ok(html.includes('26.6g'), '얼마가 양념 몫일 수 있는지 말해야 한다');
});

test('양념 안 한 것에는 고지가 없다', () => {
  assert.ok(!detailScreen(plain(), null).includes('양념이 되어 있습니다'));
});

test('조리법 비교에서 양념한 것과 안 한 것이 같은 칸에 묻히지 않는다', () => {
  const members = [plain(), seasoned()];
  const html = detailScreen(seasoned(), members);
  // 굽기 두 줄이 다 나와야 한다 — 하나만 나오면 앱이 둘 중 하나를 임의로 고른 것이다
  assert.equal((html.match(/굽기/g) ?? []).length, 2, html);
  // 비교 줄은 GI 와 신호등을 보여준다. 두 답이 다 보여야 비교가 된다.
  assert.ok(html.includes('좋음'), '양념 안 한 것의 답이 보여야 비교가 된다');
  assert.ok(html.includes('피하기'), html);
});

test('목록에서도 양념 여부가 보인다', () => {
  assert.ok(listItem(seasoned()).includes('양념'));
  assert.ok(!listItem(plain()).includes('양념'));
});
