// 화면 이동을 브라우저 방문 기록(history)에 태운다.
//
// 폰의 뒤로가기 버튼은 "방문 기록을 하나 물린다"는 동작이다. 화면을 바꿀 때
// 기록을 쌓아두지 않으면 뒤로가기가 앱 자체를 끄고, 화면 맨 위의 '‹' 버튼을
// 찾아 눌러야만 뒤로 갈 수 있다. 그래서 화면을 바꿀 때마다 기록을 하나 쌓고,
// 뒤로가기가 알려주는 popstate 에서 그 상태를 다시 그린다.
//
// 주소(URL)는 건드리지 않는다. 기록만 쌓으면 목적은 달성되고, 주소를 바꾸면
// 그 주소로 새로고침했을 때 GitHub Pages 가 404 를 내기 때문이다.
//
// 상태 모양:
//   {kind:'home'} | {kind:'list', query} | {kind:'category', name} | {kind:'detail', id}
// 여기에 이 모듈이 세 가지를 얹는다.
//   depth   — 첫 화면에서 몇 걸음 들어왔는지
//   back    — 뒤로가기 버튼에 쓸 "돌아갈 곳" 이름
//   scrollY — 떠날 때의 스크롤 위치 (돌아오면 보던 자리로)
//
// history 와 scrollY 를 인자로 받는 것은 테스트 때문이다. 브라우저 없이
// 가짜 history 를 넣고 기록이 어떻게 쌓이는지 확인한다.

const SEARCH = 'list';

export function createNav({ history, render, scrollY = () => 0, label = () => null }) {
  const now = () => history.state ?? null;
  const paint = entry => render(entry, entry.scrollY ?? 0);

  // 앱이 뜰 때 한 번. 지금 기록 칸에 첫 화면을 새겨 넣는다(쌓지 않는다) —
  // 여기서 쌓으면 첫 화면에서 뒤로가기를 눌러도 앱이 안 닫혀서 갇힌다.
  function start(state) {
    const entry = { ...state, depth: 0, back: null };
    history.replaceState(entry, '');
    paint(entry);
  }

  function go(state) {
    const from = now();

    // 검색은 한 글자 칠 때마다 화면이 바뀐다. 그때마다 기록을 쌓으면
    // 뒤로가기를 글자 수만큼 눌러야 한다. 검색 화면끼리는 갈아끼운다.
    if (from?.kind === SEARCH && state.kind === SEARCH) {
      const entry = { ...state, depth: from.depth, back: from.back };
      history.replaceState(entry, '');
      paint(entry);
      return;
    }

    // 검색어를 지워 첫 화면으로 돌아가는 것은 '뒤로'와 같은 동작이다.
    // 기록을 새로 쌓으면 뒤로가기가 방금 지운 검색어로 되돌아간다.
    if (from?.kind === SEARCH && state.kind === 'home' && from.depth > 0) {
      history.back();                       // popstate 가 첫 화면을 그린다
      return;
    }

    // 떠나기 전에 보던 자리를 지금 칸에 적어둔다. 돌아오면 그 자리로 간다.
    if (from) history.replaceState({ ...from, scrollY: scrollY() }, '');

    const entry = { ...state, depth: (from?.depth ?? 0) + 1, back: label(from) };
    history.pushState(entry, '');
    paint(entry);
  }

  function back() {
    history.back();
  }

  // popstate 에서 부른다. 기록이 비어 있거나(다른 페이지에서 넘어옴)
  // 우리 것이 아니면 첫 화면으로 떨어뜨린다.
  function restore(state) {
    paint(state?.kind ? state : { kind: 'home', depth: 0, back: null });
  }

  return { start, go, back, restore };
}
