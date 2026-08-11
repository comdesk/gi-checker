// 검색 매칭. DOM을 건드리지 않는 순수 함수만 둔다.
// 브라우저(<script type="module">)와 node --test 양쪽에서 그대로 쓴다.

const CHOSUNG = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
const HANGUL_BASE = 0xac00;
const HANGUL_LAST = 0xd7a3;
const JUNG_JONG = 588;

const RANK = { exact: 0, prefix: 1, substring: 2, chosung: 3, fuzzy: 4 };

export function normalizeQuery(text) {
  return String(text ?? '').replace(/[\s,·()[\]/\-_.]+/g, '').toLowerCase();
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

function matchKind(query, food) {
  const fields = haystacks(food);
  if (fields.some(h => h === query)) return 'exact';
  if (fields.some(h => h.startsWith(query))) return 'prefix';
  if (fields.some(h => h.includes(query))) return 'substring';
  return null;
}

export function searchFoods(query, foods, limit = 50) {
  const q = normalizeQuery(query);
  if (!q) return [];

  const hits = [];

  if (isChosungOnly(q)) {
    for (const food of foods) {
      if ((food.search.chosung ?? '').includes(q)) hits.push({ food, kind: 'chosung' });
    }
  } else {
    for (const food of foods) {
      const kind = matchKind(q, food);
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
