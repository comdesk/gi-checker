import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const CSS = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');

/** 선택자에 딸린 선언 블록을 꺼낸다. 없으면 null.
 *
 * 줄 앞에 고정해서 찾는다. 그냥 문자열로 찾으면 '.nut-group' 이
 * '.nut .nut-group' 안에서도 걸려 엉뚱한 블록을 집는다. */
function block(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const m = CSS.match(new RegExp(`(?:^|\\n)\\s*${escaped}\\s*\\{([^}]*)\\}`));
  return m ? m[1] : null;
}

// ── 명시성 함정 ────────────────────────────────────────────
// 영양성분 상자(.nut-group)는 .nut 안의 div 라서 ".nut div"(0,1,1) 규칙에
// 걸린다. ".nut-group"(0,1,0)에 적은 것은 전부 진다. 이 함정에 두 번 걸렸다 —
// 처음엔 display 가 flex 로 눌렸고, 다음엔 좌우 padding 이 0 으로 눌려
// 글씨가 테두리에 붙었다. 그때 CSS 를 고쳐도 화면이 안 바뀌어서 원인을
// 찾는 데 시간이 걸렸다. 세 번째가 없도록 못 박는다.

test('.nut div 규칙이 여전히 존재한다 — 이 테스트의 전제다', () => {
  const rows = block('.nut div');
  assert.ok(rows, '.nut div 규칙이 사라졌다. 이 파일의 전제를 다시 확인하라');
  assert.ok(/padding\s*:/.test(rows), '.nut div 에 padding 이 없다면 함정도 없다');
});

test('영양성분 상자의 여백은 .nut div 를 이기는 자리에 있다', () => {
  const strong = block('.nut .nut-group');
  assert.ok(strong, '.nut .nut-group 규칙이 없다');
  assert.ok(/padding\s*:/.test(strong),
    '좌우 여백이 .nut .nut-group 에 없다 — .nut div 에 눌려 화면에 안 먹는다');
  assert.ok(/display\s*:\s*block/.test(strong),
    'display:block 이 없으면 상자가 flex 로 눌린다');
});

test('약한 자리(.nut-group)에는 여백을 적지 않는다', () => {
  const weak = block('.nut-group');
  assert.ok(weak, '.nut-group 규칙이 없다');
  assert.ok(!/padding\s*:/.test(weak),
    '.nut-group 에 적은 padding 은 .nut div 에 져서 조용히 무시된다');
});

// ── 검색창 ─────────────────────────────────────────────────

test('브라우저가 그리는 지우기 버튼을 끈다', () => {
  // input type="search" 는 브라우저가 자기 ✕ 를 하나 더 그린다.
  // 우리 .clear 버튼과 나란히 두 개가 됐었다.
  assert.ok(CSS.includes('::-webkit-search-cancel-button'), '크롬·사파리 것이 남아 있다');
  assert.ok(CSS.includes('::-ms-clear'), '엣지 것이 남아 있다');
});
