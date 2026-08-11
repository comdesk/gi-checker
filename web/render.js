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

const GI_TAG = { measured: '실측', estimated: '추정' };

/** 0~100 눈금. 초록 0-55, 노랑 56-69, 빨강 70-100 구간에 현재 값을 찍는다. */
export function giMeter(food) {
  const { level } = food.verdict;
  const { value, kind, basis } = food.gi;

  if (value == null) {
    const message = kind === 'na'
      ? '탄수화물이 적어 GI 가 성립하지 않습니다'
      : 'GI 자료가 없어 영양성분으로 판정했습니다';
    return `<div class="gi-box">
      <div class="gi-top"><span class="gi-l">GI 지수</span>
        <span class="gi-v"><span class="gi-n" style="color:var(--ink3)">—</span></span></div>
      <p class="gi-none">${message}</p></div>`;
  }

  const pos = Math.max(0, Math.min(100, value));
  const tag = GI_TAG[kind] ?? '';
  const basisText = kind === 'estimated' && basis ? ` · ${esc(basis)}` : '';

  return `<div class="gi-box">
    <div class="gi-top">
      <span class="gi-l">GI 지수</span>
      <span class="gi-v">
        <span class="gi-n" style="color:var(--${level}-ink)">${kind === 'estimated' ? '약 ' : ''}${value}</span>
        <span class="gi-tag">${tag}${basisText}</span>
      </span>
    </div>
    <div class="track">
      <i style="width:55%;background:var(--green-soft)"></i>
      <i style="width:15%;background:var(--amber-soft)"></i>
      <i style="width:30%;background:var(--red-soft)"></i>
      <span class="mark" style="left:${pos}%;border-color:var(--${level})"></span>
    </div>
    <div class="scale"><span>0</span><span>55</span><span>70</span><span>100</span></div>
  </div>`;
}

/**
 * 조리법 비교. 조리법마다 대표 하나씩만 골라 보여준다.
 *
 * 그룹은 GI 오름차순이라 앞에서 자르면 가장 나쁜 선택지가 늘 빠진다.
 * 그리고 품종만 다른 중복(분질/점질 찐것)이 칸을 다 먹는다.
 * 이 기능의 목적은 "조리법에 따라 얼마나 달라지나" 를 보여주는 것이므로
 * 조리법 단위로 접어서 보여준다.
 */
function pickByMethod(food, members) {
  const seen = new Map();   // method -> 대표 레코드
  for (const m of members) {
    const key = m.method ?? '기타';
    // 지금 보고 있는 항목이 있으면 그것을 대표로 삼는다
    if (!seen.has(key) || m.id === food.id) seen.set(key, m);
  }
  const out = [...seen.values()];
  // GI 오름차순, GI 없는 것은 뒤로
  out.sort((a, b) => {
    const av = a.gi.value, bv = b.gi.value;
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return av - bv;
  });
  return out;
}

/** 조리법 비교. 항목이 2개 미만이면 섹션을 내보내지 않는다. */
export function waysList(food, members) {
  if (!members) return '';

  let rows = pickByMethod(food, members);
  if (rows.length < 2) return '';          // 비교할 게 없으면 섹션을 안 낸다

  if (rows.length > 5) {
    const must = new Set([food.id, rows[rows.length - 1].id]);   // 현재 항목 + 최악
    const keep = rows.filter(r => must.has(r.id));
    for (const r of rows) {
      if (keep.length >= 5) break;
      if (!must.has(r.id)) keep.push(r);
    }
    // 다시 GI 순으로 정렬해 표시 순서를 유지한다
    rows = keep.sort((a, b) => rows.indexOf(a) - rows.indexOf(b));
  }

  const heading = food.verdict.level === 'red'
    ? `같은 ${esc(food.group)}라도 이렇게 드세요`
    : '조리법에 따라 이렇게 달라져요';

  const wayRows = rows.map(m => {
    const level = m.verdict.level;
    const isNow = m.id === food.id;
    const label = esc(m.method ?? displayName(m));
    const gi = m.gi.value == null
      ? `<span class="g" style="color:var(--ink3);font-size:15px">—</span>`
      : `<span class="g" style="color:var(--${level}-ink)">${m.gi.value}</span>`;
    return `<button class="way${isNow ? ' now' : ''}" data-id="${esc(m.id)}">
      <span class="d" style="background:var(--${level})"></span>
      <span class="w">${label}${isNow ? '<span class="badge">지금 보는 것</span>' : ''}</span>
      ${gi}
      <span class="s" style="color:var(--${level})">${LEVEL_LABEL[level]}</span>
    </button>`;
  }).join('');

  return `<section class="sec">
    <h2 class="sec-h">${heading}</h2>
    <div class="ways">${wayRows}</div>
  </section>`;
}

/** 신호등과 무관한 별도 경고. 있을 때만 눈에 띄게 보여준다. */
export function cautionBlock(food) {
  if (!food.caution) return '';
  return `<div class="caution" role="note">
    <span class="caution-ic" aria-hidden="true">⚠</span>
    <p>${esc(food.caution)}</p>
  </div>`;
}

const NUT_ROWS = [
  ['열량', 'kcal', 'kcal'],
  ['탄수화물', 'carb', 'g'],
  ['당류', 'sugar', 'g'],
  ['식이섬유', 'fiber', 'g'],
  ['지방', 'fat', 'g'],
  ['나트륨', 'sodium', 'mg'],
];

function nutRows(n) {
  return NUT_ROWS.map(([label, key, unit]) => {
    // null 은 '모름'이다. 0 으로 표시하면 거짓말이 된다.
    const v = n[key];
    const shown = v == null ? '정보 없음' : `${v}${unit}`;
    const dim = v == null ? ' style="color:var(--ink3);font-weight:600"' : '';
    return `<div><span>${label}</span><span${dim}>${shown}</span></div>`;
  }).join('');
}

/**
 * 영양성분. 100g 기준과 실제 분량 기준을 **상자로 갈라서** 보여준다.
 * 두 기준을 섞어 보여주면 사용자가 몇 배씩 잘못 읽는다 (실제로 겪은 문제).
 */
export function nutrientTable(food) {
  const base = food.serving.label.endsWith('기준') ? food.serving.label : '100g 기준';
  let body = `<div class="nut-group">
      <p class="nut-h">${esc(base)}</p>
      ${nutRows(food.nutrients)}
    </div>`;

  if (food.perServing) {
    body += `<div class="nut-group">
      <p class="nut-h">한 번에 먹는 양 ${esc(food.serving.label)} 기준</p>
      ${nutRows(food.perServing)}
    </div>`;
  } else if (food.serving.isPackage) {
    body += `<p class="nut-note">포장 전체 ${esc(food.serving.label)} 기준이라
      한 사람이 한 번에 먹는 양이 아닙니다.</p>`;
  }

  const origin = [];
  if (food.display && food.display !== food.name) origin.push(`원본 ${esc(food.name)}`);
  if (food.source) origin.push(`출처 ${esc(food.source)}`);
  if (origin.length) body += `<p class="nut-src">${origin.join(' · ')}</p>`;

  return `<details class="more">
    <summary>영양성분 자세히 보기 ⌄</summary>
    <div class="nut">${body}</div>
  </details>`;
}

export function detailScreen(food, members) {
  const level = food.verdict.level;
  // 빨강에는 권장량 줄을 내보내지 않는다 (설계 5.2).
  const servingLine = level === 'red' || food.serving.isPackage ? ''
    : `<p class="fact">보통 한 번에 <b>${esc(food.serving.label)}</b></p>`;

  return `
    <button class="nav" id="back"><span class="back">‹</span> ${esc(food.group ?? '검색으로')}</button>
    <div class="accent" style="background:var(--${level})"></div>
    <div class="head">
      <h1 class="name">${esc(displayName(food))}</h1>
      <span class="pill" style="background:var(--${level}-tint);
            border-color:var(--${level}-soft);color:var(--${level}-ink)">
        <span class="dot" style="background:var(--${level})"></span>${PILL_TEXT[level]}
      </span>
      <p class="say">${verdictLine(food)}</p>
    </div>
    ${cautionBlock(food)}
    ${giMeter(food)}
    ${waysList(food, members)}
    ${servingLine}
    ${nutrientTable(food)}`;
}
