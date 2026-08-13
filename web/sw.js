// 오프라인 캐싱. 첫 실행 한 번만 네트워크가 필요하고 그 뒤로는 없어도 열린다.
//
// 이 앱은 서버가 없고 데이터가 파일 하나(foods.json 2.6MB)라 통째로 캐싱할 수
// 있다. 그래서 호스팅이 죽어도, 지하철에서도, 비행기에서도 그대로 동작한다.
//
// VERSION 은 bundle.py 가 빌드할 때마다 고쳐 쓴다. 이 파일의 내용이 바뀌어야
// 브라우저가 새 서비스워커를 설치하기 때문이다 — 손으로 올리는 것을 잊으면
// 사용자는 영영 옛날 버전을 보게 된다.
const VERSION = '2026-08-13+7817045b';
const CACHE = `meogeodo-${VERSION}`;

// 앱이 도는 데 필요한 전부. 하나라도 빠지면 오프라인에서 깨진다.
const ASSETS = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './data.js',
  './render.js',
  './search.js',
  './nav.js',
  './foods.json',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './apple-touch-icon.png',
];

self.addEventListener('install', event => {
  // 하나라도 실패하면 설치를 통째로 실패시킨다. 반쯤 캐싱된 상태가 제일 나쁘다 —
  // 앱은 열리는데 데이터만 없는 화면이 된다.
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name !== CACHE) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

// skipWaiting 은 일부러 쓰지 않는다. 쓰면 앱을 보고 있는 도중에 새 버전이
// 넘겨받아 옛 화면과 새 코드가 섞인다. 다음에 앱을 다시 열 때 바뀌는 편이 안전하다.

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  // 남의 주소는 건드리지 않는다 (이 앱은 외부를 부르지 않지만 방어적으로).
  if (new URL(request.url).origin !== self.location.origin) return;

  event.respondWith((async () => {
    const cached = await caches.match(request, { ignoreSearch: true });
    if (cached) return cached;
    try {
      return await fetch(request);
    } catch (err) {
      // 주소창으로 들어온 요청은 첫 화면으로 돌려준다.
      // (안 그러면 오프라인에서 브라우저 기본 오류 화면이 뜬다)
      if (request.mode === 'navigate') {
        const fallback = await caches.match('./index.html');
        if (fallback) return fallback;
      }
      throw err;
    }
  })());
});
