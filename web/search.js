// 검색 매칭. DOM을 건드리지 않는 순수 함수만 둔다.
// 브라우저(<script type="module">)와 node --test 양쪽에서 그대로 쓴다.

const CHOSUNG = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const HANGUL_BASE = 0xac00;
const HANGUL_LAST = 0xd7a3;
const JUNG_JONG = 588;

const RANK = {
  exact: 0, group: 1, prefix: 2, substring: 3, words: 4, split: 5,
  chosung: 6, fuzzy: 7,
};

// 붙여 친 질의를 둘로 쪼갤 때 각 조각의 최소 길이.
// 한 글자까지 허용하면 '조' 같은 조각이 거의 모든 음식에 걸린다.
const MIN_PIECE = 2;

export function normalizeQuery(text) {
  return String(text ?? '').replace(/[\s,·()[\]/\-_.]+/g, '').toLowerCase();
}

/**
 * 질의를 낱말로 쪼갠다. 낱말 하나하나는 normalizeQuery 와 같은 규칙으로 씻는다.
 *
 * 사람은 이름을 통째로 외워서 치지 않는다. '조미 오징어' 라고 치면
 * '오징어 조미하여 구운것' 이 나와야 하는데, 붙여서 '조미오징어' 로 만들어
 * 부분 일치를 보면 순서가 뒤집혀 있어 못 찾는다.
 */
export function queryWords(text) {
  return String(text ?? '')
    .split(/[\s,·()[\]/\-_.]+/)
    .map(w => normalizeQuery(w))
    .filter(w => w.length > 0);
}

/**
 * 붙여 친 질의를 둘로 쪼갠 후보들. '조미오징어' -> [['조미','오징어'], ...]
 *
 * 한국어는 띄어쓰기를 잘 안 한다. '조미 오징어' 는 낱말 검색으로 찾아지지만
 * '조미오징어' 는 그대로 이어붙인 이름이 없어서 못 찾는다. 어디서 끊어야
 * 할지는 알 수 없으니 가능한 자리를 전부 시도한다 — 질의가 짧아서 몇 개 안 된다.
 */
export function querySplits(query) {
  const out = [];
  for (let i = MIN_PIECE; i <= query.length - MIN_PIECE; i++) {
    out.push([query.slice(0, i), query.slice(i)]);
  }
  return out;
}

export function chosungOf(text) {
  let out = '';
  for (const ch of String(text ?? '')) {
    const code = ch.codePointAt(0);
    if (code >= HANGUL_BASE && code <= HANGUL_LAST) {
      out += CHOSUNG[Math.floor((code - HANGUL_BASE) / JUNG_JONG)];
    } else if (!/\s/.test(ch)) {
      out += ch;
    }
  }
  return out;
}

export function isChosungOnly(text) {
  const t = normalizeQuery(text);
  return t.length > 0 && [...t].every(ch => CHOSUNG.includes(ch));
}

// 편집 거리가 1 이하인지. 전체 거리를 계산하지 않고 한 번만 어긋나는지 본다.
function withinOneEdit(a, b) {
  if (Math.abs(a.length - b.length) > 1) return false;
  const [short, long] = a.length <= b.length ? [a, b] : [b, a];
  let i = 0, j = 0, edits = 0;
  while (i < short.length && j < long.length) {
    if (short[i] === long[j]) { i++; j++; continue; }
    if (++edits > 1) return false;
    if (short.length === long.length) i++;
    j++;
  }
  return edits + (long.length - j) + (short.length - i) <= 1;
}

function haystacks(food) {
  return [food.search.norm, ...(food.search.alias ?? [])];
}

function matchKind(query, words, splits, food) {
  const fields = haystacks(food);
  if (fields.some(h => h === query)) return 'exact';
  // 질의가 이 음식의 대표 이름과 정확히 같으면 '그 음식 자체'다.
  // '고구마' 검색 시 '찐 고구마'(group=고구마)가 '고구마밥'(group=null)보다 앞선다.
  //
  // groupLabel 도 같이 본다. 그룹 키는 다른 그룹과 겹치지 않으려고 길어지지만
  // ('호박 단호박') 사람이 치는 말은 짧은 쪽이다('단호박') — 키만 보면
  // '단호박' 검색에서 '생 단호박' 이 '단호박찜' 보다 뒤로 밀린다.
  if ((food.group && normalizeQuery(food.group) === query)
      || (food.groupLabel && normalizeQuery(food.groupLabel) === query)) {
    return 'group';
  }
  if (fields.some(h => h.startsWith(query))) return 'prefix';
  if (fields.some(h => h.includes(query))) return 'substring';
  // 낱말이 순서와 상관없이 전부 들어 있으면 찾은 것으로 본다.
  // '조미 오징어' -> '오징어 조미하여 구운것'.
  // 한 낱말짜리 질의는 위 부분 일치와 결과가 같으므로 건너뛴다.
  if (words.length >= 2 && fields.some(h => words.every(w => h.includes(w)))) {
    return 'words';
  }
  // 띄어쓰기 없이 친 경우. '조미오징어' 를 '조미'+'오징어' 로 끊어 본다.
  if (splits.length
      && fields.some(h => splits.some(([a, b]) => h.includes(a) && h.includes(b)))) {
    return 'split';
  }
  return null;
}

export function searchFoods(query, foods, limit = 50) {
  const q = normalizeQuery(query);
  const words = queryWords(query);
  if (!q) return [];
  // 낱말을 이미 띄어 쳤으면 쪼갤 필요가 없다.
  const splits = words.length >= 2 ? [] : querySplits(q);

  const hits = [];

  if (isChosungOnly(q)) {
    for (const food of foods) {
      if ((food.search.chosung ?? '').includes(q)) hits.push({ food, kind: 'chosung' });
    }
  } else {
    for (const food of foods) {
      const kind = matchKind(q, words, splits, food);
      if (kind) hits.push({ food, kind });
    }
    // 아무것도 못 찾았을 때만 오타 보정으로 내려간다. 두 글자 이상일 때만.
    if (hits.length === 0 && q.length >= 2) {
      for (const food of foods) {
        const hay = haystacks(food);
        const near = hay.some(h => {
          if (withinOneEdit(q, h)) return true;
          // 긴 이름 안의 같은 길이 구간과 비교한다: '고구미' vs '고구마말랭이'
          for (let i = 0; i + q.length <= h.length; i++) {
            if (withinOneEdit(q, h.slice(i, i + q.length))) return true;
          }
          return false;
        });
        if (near) hits.push({ food, kind: 'fuzzy' });
      }
    }
  }

  hits.sort((a, b) => {
    const byRank = RANK[a.kind] - RANK[b.kind];
    if (byRank !== 0) return byRank;
    const byLength = a.food.name.length - b.food.name.length;
    if (byLength !== 0) return byLength;
    return a.food.name.localeCompare(b.food.name, 'ko');
  });

  return hits.slice(0, limit);
}
