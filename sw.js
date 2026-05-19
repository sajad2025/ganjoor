/* Ganjoor PWA service worker
 * Strategy:
 *   - Precache app shell (index, manifest, icons) on install
 *   - data/*.json: stale-while-revalidate
 *   - everything else (fonts, CDN scripts): cache-first with network fallback
 */
const SHELL_CACHE = 'ganjoor-shell-v3';
const DATA_CACHE  = 'ganjoor-data-v3';
const RUNTIME     = 'ganjoor-runtime-v3';

const SHELL = [
  './',
  './index.html',
  './manifest.json',
  './favicon.png',
  './apple-touch-icon.png',
  './icon-192.png',
  './icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const c = await caches.open(SHELL_CACHE);
    await Promise.allSettled(SHELL.map((u) => c.add(u)));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.map((n) => {
      if (![SHELL_CACHE, DATA_CACHE, RUNTIME].includes(n)) return caches.delete(n);
    }));
    await self.clients.claim();
  })());
});

function isData(url) { return /\/data\/.+\.json(?:$|\?)/.test(url.pathname); }
function isShell(url) {
  return SHELL.some((s) => url.pathname.endsWith(s.replace('./', '/')) || url.pathname.endsWith(s.slice(1)));
}

async function staleWhileRevalidate(cacheName, request) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request).then((resp) => {
    if (resp && resp.ok) cache.put(request, resp.clone());
    return resp;
  }).catch(() => null);
  return cached || (await network) || new Response('Offline.', { status: 503 });
}

async function cacheFirst(cacheName, request) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const resp = await fetch(request);
    if (resp && resp.ok) cache.put(request, resp.clone());
    return resp;
  } catch {
    return cached || new Response('Offline.', { status: 503 });
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // Same-origin data/*.json: stale-while-revalidate
  if (url.origin === self.location.origin && isData(url)) {
    event.respondWith(staleWhileRevalidate(DATA_CACHE, request));
    return;
  }

  // Same-origin shell files: cache-first
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(SHELL_CACHE, request));
    return;
  }

  // Cross-origin (fonts, CDN scripts): cache-first runtime
  event.respondWith(cacheFirst(RUNTIME, request));
});
