import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeQuery, chosungOf, isChosungOnly, searchFoods } from '../search.js';

const make = (name, chosung, alias = [], group = null) => ({
  id: name,
  name,
  group,
  search: { norm: name.replace(/[\s,·()]/g, ''), chosung, alias }
});

const FOODS = [
  make('고구마, 삶은 것', 'ㄱㄱㅁㅅㅇㄱ', ['삶은고구마']),
  make('고구마, 찐 것', 'ㄱㄱㅁㅉㄱ', ['찐고구마']),
  make('군고구마', 'ㄱㄱㄱㅁ'),
  make('고구마말랭이', 'ㄱㄱㅁㅁㄹㅇ'),
  make('고구마순 나물', 'ㄱㄱㅁㅅㄴㅁ'),
  make('감자, 삶은 것', 'ㄱㅈㅅㅇㄱ', ['삶은감자']),
  make('사과', 'ㅅㄱ'),
];

test('초성 추출', () => {
  assert.equal(chosungOf('고구마'), 'ㄱㄱㅁ');
  assert.equal(chosungOf('찐 고구마'), 'ㅉㄱㄱㅁ');
  assert.equal(chosungOf('된장찌개'), 'ㄷㅈㅉㄱ');
});

test('질의 정규화 — 공백과 구두점 제거', () => {
  assert.equal(normalizeQuery('찐 고구마'), '찐고구마');
  assert.equal(normalizeQuery('고구마, 삶은 것'), '고구마삶은것');
  assert.equal(normalizeQuery('  사과  '), '사과');
});

test('초성만으로 이루어진 질의 판별', () => {
  assert.equal(isChosungOnly('ㄱㄱㅁ'), true);
  assert.equal(isChosungOnly('고구마'), false);
  assert.equal(isChosungOnly('ㄱ고'), false);
  assert.equal(isChosungOnly(''), false);
});

test('부분 일치 — 끝까지 안 쳐도 나온다', () => {
  const names = searchFoods('고구', FOODS).map(r => r.food.name);
  assert.ok(names.includes('고구마, 삶은 것'));
  assert.ok(names.includes('군고구마'));
  assert.ok(!names.includes('사과'));
});

test('초성 검색', () => {
  const results = searchFoods('ㄱㄱㅁ', FOODS);
  const names = results.map(r => r.food.name);
  assert.ok(names.includes('고구마, 삶은 것'));
  assert.ok(names.includes('고구마말랭이'));
  assert.equal(results[0].kind, 'chosung');
});

test('띄어쓰기를 무시한다', () => {
  const a = searchFoods('찐고구마', FOODS).map(r => r.food.name);
  const b = searchFoods('찐 고구마', FOODS).map(r => r.food.name);
  assert.deepEqual(a, b);
  assert.ok(a.includes('고구마, 찐 것'));
});

test('별칭으로도 찾는다', () => {
  const names = searchFoods('삶은고구마', FOODS).map(r => r.food.name);
  assert.ok(names.includes('고구마, 삶은 것'));
});

test('오타 한 글자를 허용한다', () => {
  const results = searchFoods('고구미', FOODS);
  const names = results.map(r => r.food.name);
  assert.ok(names.some(n => n.includes('고구마')));
  assert.ok(results.every(r => r.kind === 'fuzzy'));
});

test('정확 일치가 맨 앞에 온다', () => {
  const results = searchFoods('군고구마', FOODS);
  assert.equal(results[0].food.name, '군고구마');
  assert.equal(results[0].kind, 'exact');
});

test('접두 일치가 부분 일치보다 앞선다', () => {
  // '고구마, 삶은 것' 은 '고구마' 로 시작(접두), '군고구마' 는 중간에 포함(부분).
  // 이름 길이와 무관하게 접두가 항상 먼저다.
  const results = searchFoods('고구마', FOODS);
  const idx = n => results.findIndex(r => r.food.name === n);
  assert.ok(idx('고구마, 삶은 것') < idx('군고구마'));
});

test('같은 등급 안에서는 이름이 짧은 것이 먼저', () => {
  // 둘 다 접두 일치다. 이때만 길이가 순서를 가른다.
  const results = searchFoods('고구마', FOODS);
  const idx = n => results.findIndex(r => r.food.name === n);
  assert.ok(idx('고구마말랭이') < idx('고구마, 삶은 것'));
});

test('빈 질의는 빈 결과', () => {
  assert.deepEqual(searchFoods('', FOODS), []);
  assert.deepEqual(searchFoods('   ', FOODS), []);
});

test('결과 개수를 제한한다', () => {
  assert.equal(searchFoods('고구', FOODS, 2).length, 2);
});

test('한 글자 질의에는 오타 보정을 하지 않는다', () => {
  // '배' 는 어디에도 없다. q.length >= 2 가드가 없으면 한 글자는
  // 모든 음식의 첫 글자와 편집거리 1 안에 들어 전부 fuzzy 로 걸린다.
  assert.deepEqual(searchFoods('배', FOODS), []);
});

test('대표 이름이 질의와 같으면 파생 음식보다 앞선다', () => {
  const foods = [
    { id:'고구마밥', name:'고구마밥', group:null,
      search:{ norm:'고구마밥', chosung:'ㄱㄱㅁㅂ', alias:[] } },
    { id:'고구마_찐것', name:'고구마_찐것', group:'고구마',
      search:{ norm:'고구마찐것', chosung:'ㄱㄱㅁㅉㄱ', alias:['찐고구마'] } },
  ];
  const r = searchFoods('고구마', foods);
  assert.equal(r[0].food.id, '고구마_찐것');
  assert.equal(r[0].kind, 'group');
});
