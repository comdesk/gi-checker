// foods.json 로드와 조회. 네트워크 실패를 호출자가 구분할 수 있게 예외를 던진다.

let cache = null;

export async function loadFoods() {
  if (cache) return cache;
  const res = await fetch('foods.json', { cache: 'no-cache' });
  if (!res.ok) throw new Error(`foods.json 응답 ${res.status}`);
  cache = await res.json();
  return cache;
}

export function foodById(bundle, id) {
  return bundle.foods.find(f => f.id === id) ?? null;
}

export function groupMembers(bundle, food) {
  if (!food.group) return [];
  const ids = bundle.groups[food.group] ?? [];
  return ids.map(id => foodById(bundle, id)).filter(Boolean);
}

export function byCategory(bundle, category) {
  return bundle.foods.filter(f => f.category === category);
}
