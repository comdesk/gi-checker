// 음식 데이터 → HTML 문자열. DOM 이벤트는 여기서 다루지 않는다.

export const LEVEL_LABEL = { green: '좋음', amber: '주의', red: '피하기' };

export const REASON_LINE = {
  'low-carb': '탄수화물이 적어 혈당에 거의 영향 없어요',
  'gi+sweet': '지방과 당분이 함께 많습니다',
  'nutrient+sweet': '당분이 많습니다',
};

export const LEVEL_LINE = {
  green: '드셔도 좋아요',
  amber: '조금만 드세요',
  red: '혈당을 빠르게 올립니다',
};

export const PILL_TEXT = { green: '좋음', amber: '주의', red: '드시지 마세요' };

export const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/** 배지 아래 한 줄. verdict.reason 에서 기계적으로 정한다 (설계 5.2). */
export function verdictLine(food) {
  const { level, reason } = food.verdict;
  if (REASON_LINE[reason]) return REASON_LINE[reason];
  if (reason === 'nutrient' && level === 'red') return '탄수화물이 많습니다';
  return LEVEL_LINE[level];
}

/** 목록 한 줄의 오른쪽 GI 칸. GI가 없어도 신호등 글자는 반드시 남는다. */
export function giCell(food) {
  const { level } = food.verdict;
  const value = food.gi.value;
  const num = value == null
    ? `<div class="gn" style="color:var(--ink3);font-size:20px">—</div>`
    : `<div class="gn" style="color:var(--${level}-ink)">${value}</div>`;
  return `<span class="gi">${num}
    <div class="gl" style="color:var(--${level})">${LEVEL_LABEL[level]}</div></span>`;
}

/** 목록 한 줄의 회색 보조 문구. */
export function subLine(food) {
  const serving = esc(food.serving.label);
  const kind = {
    measured: '실측',
    estimated: '추정',
    na: '탄수화물 적음',
    none: 'GI 자료없음',
  }[food.gi.kind];
  return `${serving} · ${kind}`;
}

/** 화면에 보이는 이름. 식약처 원본 표기 대신 사람이 쓰는 말을 쓴다. */
export function displayName(food) {
  return food.display ?? food.name;
}

export function listItem(food) {
  return `
    <button class="item" data-id="${esc(food.id)}">
      <span class="d" style="background:var(--${food.verdict.level})"></span>
      <span class="t">
        <div class="n">${esc(displayName(food))}</div>
        <div class="m">${subLine(food)}</div>
      </span>
      ${giCell(food)}
      <span class="arw" aria-hidden="true">›</span>
    </button>`;
}

/** 무엇으로 찾았는지 알려준다. 정확·접두·부분 일치면 알릴 것이 없다. */
export function matchHint(kind, food) {
  if (kind === 'chosung') return `초성으로 찾았어요 · "${esc(displayName(food))}"`;
  if (kind === 'fuzzy') return `비슷한 이름으로 찾았어요 · "${esc(displayName(food))}"`;
  return '';
}
