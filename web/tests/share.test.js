import { test } from 'node:test';
import assert from 'node:assert/strict';
import { shareUrl, parseShareHash, shareText } from '../share.js';
import { detailScreen } from '../render.js';

// 공유 기능. 링크를 받은 폰에서 그 음식 화면이 바로 열려야 하고(딥링크),
// 공유 문구는 카톡 미리보기 카드가 못 전하는 정보(어느 음식, 무슨 판정)를
// 대신 전해야 한다.

const NUT = { kcal: 100, carb: 20, sugar: 1, fiber: 1, fat: 0.1, sodium: 5 };

const base = (overrides) => ({
  id: '복숭아-백도-생것', name: '복숭아', display: '복숭아', group: null,
  method: null, category: '과일',
  serving: { label: '100g 기준', grams: null, isPackage: false },
  nutrients: NUT,
  perServing: null,
  gi: { value: 56, kind: 'measured', basis: null },
  verdict: { level: 'amber', reason: 'gi' },
  source: null, caution: null,
  ...overrides,
});

// ── 주소 만들기 / 읽기 ──
// id 는 '멥쌀-쌀눈-생것' 같은 한글 슬러그다. 주소에 그대로 넣으면 문자 앱마다
// 링크 인식이 갈려서 인코딩해 넣는다. 만들기와 읽기는 서로 되돌릴 수 있어야 한다.

test('만든 주소를 다시 읽으면 같은 id 가 나온다', () => {
  const url = shareUrl('https://comdesk.github.io/gi-checker/', '멥쌀-쌀눈-생것');
  const hash = new URL(url).hash;
  assert.equal(parseShareHash(hash), '멥쌀-쌀눈-생것');
});

test('주소의 한글 id 는 인코딩되어 있다', () => {
  const url = shareUrl('https://comdesk.github.io/gi-checker/', '복숭아-백도-생것');
  assert.ok(!url.includes('복숭아'), url);
  assert.ok(url.startsWith('https://comdesk.github.io/gi-checker/#f='), url);
});

test('공유 해시가 아니면 null 이다', () => {
  assert.equal(parseShareHash(''), null);
  assert.equal(parseShareHash('#'), null);
  assert.equal(parseShareHash('#뭔가다른것'), null);
  assert.equal(parseShareHash(undefined), null);
});

test('망가진 인코딩은 앱을 죽이지 않고 null 이 된다', () => {
  // decodeURIComponent('%') 는 예외를 던진다. 남이 손으로 고친 링크로
  // 들어와도 첫 화면이 떠야지 흰 화면이 뜨면 안 된다.
  assert.equal(parseShareHash('#f=%'), null);
  assert.equal(parseShareHash('#f='), null);
});

// ── 공유 문구 ──
// 카드가 모든 음식에서 똑같이 뜨므로(정적 사이트의 한계) 문구가 판정을 전한다.

test('공유 문구에 이름·신호등·이유가 다 들어간다', () => {
  const text = shareText(base());
  assert.ok(text.includes('복숭아'), text);
  assert.ok(text.includes('주의'), text);
  assert.ok(text.includes('🟡'), text);
});

test('빨강은 드시지 마세요 라고 말한다', () => {
  const text = shareText(base({
    verdict: { level: 'red', reason: 'gi' },
    gi: { value: 92, kind: 'measured', basis: null },
  }));
  assert.ok(text.includes('🔴'), text);
  assert.ok(text.includes('드시지 마세요'), text);
});

test('술의 공유 문구도 탄수화물이 적다는 말을 하지 않는다', () => {
  const text = shareText(base({
    display: '소주',
    verdict: { level: 'amber', reason: 'alcohol' },
    gi: { value: null, kind: 'na', basis: null },
  }));
  assert.ok(text.includes('소주'), text);
  assert.ok(!text.includes('탄수화물이 적어'), text);
});

// ── 상세 화면의 공유 버튼 ──

test('상세 화면에 공유 버튼이 있다', () => {
  const html = detailScreen(base(), null);
  assert.ok(html.includes('id="share"'), html);
  assert.ok(html.includes('공유'), html);
});
