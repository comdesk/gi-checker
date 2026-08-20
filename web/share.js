// 공유. 주소 만들기·읽기와 공유 문구 — DOM 을 건드리지 않는 순수 함수만 둔다.
//
// 딥링크는 '#f=음식id' 다. # 뒤는 GitHub Pages 가 보지 않아 새로고침해도
// 404 가 없고(nav.js 가 주소를 안 바꾸는 이유가 그 404 였다), 서버 없이
// 링크 하나로 특정 음식 화면을 열 수 있는 유일한 자리다.
//
// 주소는 앱에 들어올 때 한 번만 읽고 바로 지운다. 화면 이동마다 주소를
// 바꾸는 방식으로 넓히지 않는다 — 방문 기록 관리(nav.js)와 주소 관리가
// 서로 얽히면 뒤로가기가 다시 어려워진다.

import { displayName, verdictLine, PILL_TEXT } from './render.js';

const PREFIX = '#f=';

// 신호등을 글자 없이도 알아볼 수 있게. 카톡 목록처럼 문구가 잘리는 곳에서도
// 색 동그라미 하나는 살아남는다.
const LEVEL_EMOJI = { green: '🟢', amber: '🟡', red: '🔴', unknown: '❓' };

/** 공유할 주소. id 는 한글 슬러그라 인코딩해 넣는다 — 문자 앱마다
 *  한글 주소의 링크 인식이 갈린다. */
export function shareUrl(baseUrl, id) {
  return `${baseUrl}${PREFIX}${encodeURIComponent(id)}`;
}

/** 주소에서 음식 id 를 꺼낸다. 공유 링크가 아니거나 망가졌으면 null —
 *  남이 손으로 고친 링크로 들어와도 흰 화면 대신 첫 화면이 떠야 한다. */
export function parseShareHash(hash) {
  if (!hash || !hash.startsWith(PREFIX)) return null;
  try {
    return decodeURIComponent(hash.slice(PREFIX.length)) || null;
  } catch {
    return null;
  }
}

/** 공유 문구. 미리보기 카드는 모든 음식에서 똑같이 뜨므로(정적 사이트라
 *  음식별 카드를 못 만든다) 어느 음식이 무슨 판정인지는 이 문구가 전한다. */
export function shareText(food) {
  const level = food.verdict.level;
  return `${displayName(food)} ${LEVEL_EMOJI[level]} ${PILL_TEXT[level]} — ${verdictLine(food)}`;
}
