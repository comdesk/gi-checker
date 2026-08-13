// 눈으로 확인하는 용도. 테스트가 아니라 실제 번들로 그려보는 스크립트다.
//   node web/tests/render_check.mjs
import { readFileSync } from 'node:fs';
import { detailScreen } from '../render.js';

const bundle = JSON.parse(readFileSync(new URL('../foods.json', import.meta.url), 'utf8'));

const want = ['생 사과', '생 수박', '생 단감', '생 연시', '말린 곶감',
              '멥쌀밥 백미', '생 마늘', '생 앵두', '우유'];
const text = t => t.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

for (const name of want) {
  const f = bundle.foods.find(x => x.display === name);
  if (!f) { console.log(`(없음) ${name}`); continue; }
  const html = detailScreen(f, null, '검색으로');
  const box = html.match(/<div class="portion">[\s\S]*?<\/div>/);
  console.log(`\n== ${name}  [${f.verdict.level}]`);
  console.log('   ' + (box ? text(box[0]) : '(분량 상자 없음)'));
}
