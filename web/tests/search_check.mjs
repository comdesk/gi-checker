// 부모님이 실제로 치실 말로 검색해본다. 테스트가 아니라 확인용 스크립트다.
//   node web/tests/search_check.mjs
import { readFileSync } from 'node:fs';
import { searchFoods } from '../search.js';

const bundle = JSON.parse(readFileSync(new URL('../foods.json', import.meta.url), 'utf8'));

const QUERIES = [
  // 고기 — 파는 이름
  '삼겹살', '목살', '항정살', '갈매기살', '차돌박이', '꽃등심', '앞다리살', '뒷다리살',
  '등심', '안심', '채끝', '갈비', '사태', '우둔', '설도', '살치살', '부채살',
  '닭가슴살', '닭다리', '닭날개', '닭목', '오리고기',
  // 생선·해산물
  '고등어', '갈치', '삼치', '조기', '광어', '동태', '북어', '멸치', '오징어',
  '새우', '굴', '홍합', '전복', '낙지', '주꾸미', '문어', '꼬막',
  // 자주 먹는 것
  '쌀밥', '현미밥', '잡곡밥', '식빵', '고구마', '감자', '사과', '배', '귤',
  '수박', '참외', '포도', '딸기', '바나나', '토마토', '두부', '달걀', '우유',
  '김치', '깍두기', '된장찌개', '김치찌개', '라면', '자장면', '떡볶이',
];

let missing = [];
for (const q of QUERIES) {
  const hits = searchFoods(q, bundle.foods, 5);
  const top = hits.slice(0, 3).map(h => h.food.display);
  if (!hits.length) { missing.push(q); console.log(`  ✗ ${q.padEnd(8)} 0건`); continue; }
  console.log(`    ${q.padEnd(8)} ${top.join(' / ')}`);
}
console.log(`\n0건인 검색어 ${missing.length}개: ${missing.join(', ') || '없음'}`);
