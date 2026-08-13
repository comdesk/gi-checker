// 눈으로 확인하는 용도. 테스트가 아니라 실제 번들로 그려보는 스크립트다.
//   node web/tests/render_check.mjs
import { readFileSync } from 'node:fs';
import { detailScreen } from '../render.js';

const bundle = JSON.parse(readFileSync(new URL('../foods.json', import.meta.url), 'utf8'));

const want = ['생 사과', '생 상추', '배추김치', '삶은 국수',
              '생 삼겹살', '삼겹살', '생 소고기', '구운 고등어', '생 달걀',
              '말린 아몬드', '볶은 땅콩', '생 굴', '말린 북어'];

// 식이섬유 표가 실제로 무엇에 붙었는지 한눈에 본다 — 이 표의 쓸모는
// '같은 값이면 이쪽' 이라 비교가 되어야 의미가 있다.
const fiber = bundle.foods
  .filter(f => f.exchange?.fiberRich && !['red', 'unknown'].includes(f.verdict.level))
  .map(f => f.display);
console.log(`[식이섬유 표가 붙은 것 ${fiber.length}건]`);
console.log('  ' + fiber.join(', ') + '\n');
const text = t => t.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

for (const name of want) {
  const f = bundle.foods.find(x => x.display === name);
  if (!f) { console.log(`(없음) ${name}`); continue; }
  const html = detailScreen(f, null, '검색으로');
  const box = html.match(/<div class="portion">[\s\S]*?<\/div>/);
  console.log(`\n== ${name}  [${f.verdict.level}]`);
  console.log('   ' + (box ? text(box[0]) : '(분량 상자 없음)'));
}
