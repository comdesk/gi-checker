// 음식 데이터 → HTML 문자열. DOM 이벤트는 여기서 다루지 않는다.

// 'unknown' 은 신호등의 네 번째 색이 아니라 '신호등을 켤 수 없음' 이다.
// 원본에 당류·식이섬유가 비어 있어 최선의 경우와 최악의 경우가 서로 다른
// 답이 나오는 음식(전체의 3.5%, 대부분 말린 나물·약차)이다. 찍어서 맞히는
// 것보다 모른다고 말하는 편이 낫다 — 당뇨 환자가 이 화면을 보고 먹는다.
export const LEVEL_LABEL = { green: '좋음', amber: '주의', red: '피하기', unknown: '모름' };

export const REASON_LINE = {
  'low-carb': '탄수화물이 적어 혈당에 거의 영향 없어요',
  'gi+sweet': '지방과 당분이 함께 많습니다',
  'nutrient+sweet': '당분이 많습니다',
  // GI 는 '얼마나 빨리 오르나'지 '얼마나 오르나'가 아니다. 자장면은 GI 46 으로
  // 낮지만 한 그릇에 탄수화물이 175g — 쌀밥 세 공기다.
  serving: '한 번에 드시는 양이 많습니다',
  insufficient: '영양성분 정보가 모자라 판단할 수 없어요',
};

export const LEVEL_LINE = {
  green: '드셔도 좋아요',
  amber: '조금만 드세요',
  red: '혈당을 빠르게 올립니다',
  unknown: '영양성분 정보가 모자라 판단할 수 없어요',
};

export const PILL_TEXT = {
  green: '좋음', amber: '주의', red: '드시지 마세요', unknown: '알 수 없음',
};

// 그룹 키는 다른 그룹과 겹치지 않기 위한 것('호박 단호박')이고,
// 사람에게 보여줄 이름은 따로 있다('단호박').
export const groupName = food => food.groupLabel ?? food.group;

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
  // 양념이 붙었다는 사실은 목록에서부터 보여야 한다 — 탄수화물이 왜 높은지가
  // 조리법이 아니라 양념 때문일 수 있다.
  const season = food.seasoning ? ` · ${esc(food.seasoning)}` : '';
  return `${serving} · ${kind}${season}`;
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
    // 판정 자체를 못 한 음식에 '영양성분으로 판정했습니다' 라고 하면
    // 바로 위 '판단할 수 없습니다' 와 정면으로 어긋난다.
    const message = level === 'unknown'
      ? 'GI 자료도 없습니다'
      : kind === 'na'
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
  const seen = new Map();   // 조리법+양념 -> 대표 레코드
  for (const m of members) {
    // 양념 여부를 키에 넣는다. '굽기' 한 칸에 구운것(0.1g)과
    // 조미하여 구운것(26.6g)을 같이 넣으면 앱이 둘 중 하나만 골라
    // "오징어는 구우면 안 된다" 또는 "구워도 괜찮다" 중 아무 말이나 하게 된다.
    //
    // 구분자는 '\0' 이스케이프로 적는다. 예전에는 널 문자를 파일에 그대로
    // 박아뒀는데, 그러면 git 이 이 파일을 통째로 바이너리로 보고 diff 를 아예
    // 안 보여준다("Bin 16117 -> 17337 bytes"). 동작은 같고 리뷰만 가능해진다.
    const key = `${m.method ?? '기타'}\0${m.seasoning ?? ''}`;
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
    ? `같은 ${esc(groupName(food))}라도 이렇게 드세요`
    : '조리법에 따라 이렇게 달라져요';

  const wayRows = rows.map(m => {
    const level = m.verdict.level;
    const isNow = m.id === food.id;
    // 양념 여부를 조리법 옆에 붙인다. '굽기' 와 '굽기 · 양념' 이 나란히 보여야
    // 탄수화물 차이가 조리법 탓이 아니라 양념 탓이라는 것이 읽힌다.
    const label = esc(m.method ?? displayName(m))
      + (m.seasoning ? ` <span class="seasontag">${esc(m.seasoning)}</span>` : '');
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

/**
 * 양념이 되어 있다는 고지.
 *
 * 같은 재료·같은 조리법이라도 양념이 붙으면 완전히 다른 음식이다.
 * 조미 오징어는 탄수화물 26.6g, 그냥 구운 오징어는 0.1g 이다. 그 26g 은
 * 오징어가 아니라 양념이다. 이것을 말해주지 않으면 사용자는 "오징어는
 * 구우면 안 되는구나" 라고 잘못 배운다.
 */
export function seasoningBlock(food) {
  if (!food.seasoning) return '';
  const carb = food.nutrients.carb;
  const amount = carb == null ? '' :
    ` 탄수화물 <b>${carb}g</b> 가운데 상당 부분이 양념일 수 있습니다.`;
  return `<div class="season">
    <span class="season-ic" aria-hidden="true">🥄</span>
    <p><b>${esc(food.seasoning)}이 되어 있습니다.</b>${amount}
    양념하지 않은 같은 음식과는 다릅니다.</p>
  </div>`;
}

/**
 * 한 번에 먹어도 되는 양 (대한당뇨병학회 식품교환표 1교환단위량).
 *
 * 이 앱은 지금까지 '먹어도 되나' 만 답했다. 당뇨에서는 그것으로 부족하다 —
 * 사과가 초록이라고 세 개를 드시면 초록인 의미가 없다.
 *
 * 빨강·알 수 없음에는 내보내지 않는다. '드시지 마세요' 바로 아래에 '한 번에
 * 15g' 이라고 적으면 먹어도 된다는 말로 읽힌다 (설계 5.2 의 권장량 줄과 같은
 * 원칙). 판정을 못 한 음식에 분량을 말하는 것도 판정한 것처럼 읽힌다.
 */
export function portionBlock(food) {
  const ex = food.exchange;
  if (!ex) return '';
  const level = food.verdict.level;
  if (level === 'red' || level === 'unknown') return '';

  const eyeball = ex.eyeball ? ` <span class="portion-e">${esc(ex.eyeball)}</span>` : '';
  // 식품군마다 하고 싶은 말이 다르다. 과일·우유는 하루 횟수, 채소는
  // '충분히 드셔도 좋습니다' — 채소에 분량만 띄우면 없는 제한이 생긴다.
  const advice = ex.advice ? `${esc(ex.advice)} · ` : '';
  // 1교환단위에 식이섬유가 2.5g 이상인 식품. 지침이 '식이섬유가 높은 통곡물을
  // 우선하여 선택한다' 고 하는 그 기준이라, 같은 값이면 이쪽이 낫다는 뜻이다.
  const fiber = ex.fiberRich
    ? '<p class="portion-fiber">식이섬유가 많은 편입니다</p>' : '';
  return `<div class="portion">
    <p class="portion-h">한 번에 이만큼</p>
    <p class="portion-v"><b>${ex.grams}${esc(ex.unit ?? 'g')}</b>${eyeball}</p>
    ${fiber}
    <p class="portion-sub">${advice}대한당뇨병학회 식품교환표 기준</p>
  </div>`;
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

function nutRows(n, estimated = []) {
  return NUT_ROWS.map(([label, key, unit]) => {
    // null 은 '모름'이다. 0 으로 표시하면 거짓말이 된다.
    const v = n[key];
    const shown = v == null ? '정보 없음' : `${v}${unit}`;
    const dim = v == null ? ' style="color:var(--ink3);font-weight:600"' : '';
    // 물려받은 값은 측정값이 아니다. 같은 값으로 보이게 두면 안 된다.
    const mark = estimated.includes(key) ? '<span class="est">추정</span>' : '';
    return `<div><span>${label}${mark}</span><span${dim}>${shown}</span></div>`;
  }).join('');
}

const MISSING_LABEL = { sugar: '당류', fiber: '식이섬유', fat: '지방' };

/**
 * 신호등을 켤 수 없을 때 그 이유를 밝힌다.
 *
 * '알 수 없음' 만 띄워놓고 왜인지 말하지 않으면 사용자는 앱이 고장난 줄 안다.
 * 어떤 값이 없어서 판단이 갈렸는지까지 말해야 스스로 판단할 여지가 생긴다.
 */
export function unknownBlock(food) {
  if (food.verdict.level !== 'unknown') return '';
  const missing = ['sugar', 'fiber', 'fat']
    .filter(k => food.nutrients[k] == null)
    .map(k => MISSING_LABEL[k]);
  const what = missing.length ? `${missing.join('·')} 정보가 없습니다.` : '';
  return `<div class="unsure">
    <p><b>${what}</b> 그래서 이 음식이 혈당을 얼마나 올리는지
    좋게도 나쁘게도 단정할 수 없습니다. 찍어서 알려드리지 않겠습니다.</p>
    <p class="unsure-sub">아래 영양성분에서 아는 값은 확인하실 수 있습니다.
    탄수화물이 <b>${food.nutrients.carb}g</b> 입니다.</p>
  </div>`;
}

/**
 * 영양성분. 100g 기준과 실제 분량 기준을 **상자로 갈라서** 보여준다.
 * 두 기준을 섞어 보여주면 사용자가 몇 배씩 잘못 읽는다 (실제로 겪은 문제).
 */
export function nutrientTable(food) {
  const base = food.serving.label.endsWith('기준') ? food.serving.label : '100g 기준';
  const est = food.estimated ?? [];
  let body = `<div class="nut-group">
      <p class="nut-h">${esc(base)}</p>
      ${nutRows(food.nutrients, est)}
    </div>`;

  if (food.perServing) {
    body += `<div class="nut-group">
      <p class="nut-h">한 번에 먹는 양 ${esc(food.serving.label)} 기준</p>
      ${nutRows(food.perServing, est)}
    </div>`;
  } else if (food.serving.isPackage) {
    body += `<p class="nut-note">포장 전체 ${esc(food.serving.label)} 기준이라
      한 사람이 한 번에 먹는 양이 아닙니다.</p>`;
  }

  const origin = [];
  if (food.display && food.display !== food.name) origin.push(`원본 ${esc(food.name)}`);
  if (food.source) origin.push(`출처 ${esc(food.source)}`);
  if (food.variants && food.variants.length > 1) {
    origin.push(`품종 ${food.variants.length}종 · ${food.variants.map(esc).join(', ')}`);
  }
  if (est.length) {
    const names = est.map(k => MISSING_LABEL[k]).filter(Boolean).join('·');
    body += `<p class="nut-note">${names}는 원본에 값이 없어 같은 종류 음식에서
      추정한 값입니다. 실제와 다를 수 있습니다.</p>`;
  }
  if (origin.length) body += `<p class="nut-src">${origin.join(' · ')}</p>`;

  // 화살표는 글자가 아니라 아이콘이다. '⌄' 글자는 글꼴마다 세로 위치가 달라
  // 글씨와 어긋나 보였다. 펼치면 CSS 가 180도 돌린다.
  return `<details class="more">
    <summary>영양성분 자세히 보기<svg class="chev" viewBox="0 0 24 24"
      aria-hidden="true"><path d="M6 9.5 12 15.5 18 9.5"/></svg></summary>
    <div class="nut">${body}</div>
  </details>`;
}

// backLabel 은 뒤로가기가 데려다줄 화면의 이름이다. 앱이 방문 기록에서
// 꺼내 넘겨준다 — 이 화면이 스스로 알 수 있는 값이 아니다.
export function detailScreen(food, members, backLabel = null) {
  const level = food.verdict.level;
  // 빨강에는 권장량 줄을 내보내지 않는다 (설계 5.2).
  // 실제 분량을 아는 음식만 '한 번에' 라고 말할 수 있다.
  // '100g 기준' 은 분량이 아니라 영양성분의 기준량이므로 그 줄을 내지 않는다
  // (영양성분 상자 제목이 이미 기준을 밝힌다).
  const hasRealPortion = food.serving.grams && !food.serving.isPackage;
  // 판단할 수 없는 음식에 권장량을 말하면 판단한 것처럼 읽힌다.
  const hideServing = level === 'red' || level === 'unknown' || !hasRealPortion;
  const servingLine = hideServing ? ''
    : `<p class="fact">보통 한 번에 <b>${esc(food.serving.label)}</b></p>`;

  return `
    <button class="nav" id="back"><span class="back">‹</span> ${esc(backLabel ?? '뒤로')}</button>
    <div class="accent" style="background:var(--${level})"></div>
    <div class="head">
      <h1 class="name">${esc(displayName(food))}</h1>
      <span class="pill" style="background:var(--${level}-tint);
            border-color:var(--${level}-soft);color:var(--${level}-ink)">
        <span class="dot" style="background:var(--${level})"></span>${PILL_TEXT[level]}
      </span>
      <p class="say">${verdictLine(food)}</p>
    </div>
    ${unknownBlock(food)}
    ${portionBlock(food)}
    ${seasoningBlock(food)}
    ${cautionBlock(food)}
    ${giMeter(food)}
    ${waysList(food, members)}
    ${servingLine}
    ${nutrientTable(food)}`;
}
