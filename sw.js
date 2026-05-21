/* Ganjoor PWA service worker
 * Strategy:
 *   - Precache app shell (index, manifest, icons) on install
 *   - Precache cross-origin runtime bundles (React, ReactDOM, Tailwind,
 *     Babel, Google Fonts CSS) on install — these are required to boot
 *     the React app, so opaque-response opportunistic caching is too
 *     unreliable. See Gotcha #9 in CLAUDE.md.
 *   - data/*.json: stale-while-revalidate
 *   - everything else (font WOFFs, etc.): cache-first with network fallback
 *
 * Cache naming convention:
 *   - SHELL_CACHE and RUNTIME bump together when index.html or the
 *     pinned CDN versions change.
 *   - DATA_CACHE is pinned and must NOT be bumped with shell upgrades —
 *     it holds ~250 MB of user-saved poems from the OfflineCache feature.
 *     Only bump it if the on-disk JSON schema changes (it hasn't).
 */
const SHELL_CACHE = 'ganjoor-shell-v14';
const RUNTIME     = 'ganjoor-runtime-v14';
const DATA_CACHE  = 'ganjoor-data-v13';

const SHELL = [
  './',
  './index.html',
  './manifest.json',
  './favicon.png',
  './apple-touch-icon.png',
  './icon-192.png',
  './icon-512.png',
];

// Cross-origin runtime bundles required to render the app shell.
// Keep in sync with the <script> and <link> tags in index.html.
const CDN = [
  'https://cdn.tailwindcss.com/',
  'https://unpkg.com/react@18.2.0/umd/react.production.min.js',
  'https://unpkg.com/react-dom@18.2.0/umd/react-dom.production.min.js',
  'https://unpkg.com/@babel/standalone@7.24.0/babel.min.js',
  'https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&family=Estedad:wght@400;500;700&display=swap',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL_CACHE);
    await Promise.allSettled(SHELL.map((u) => shell.add(u)));
    // CDN urls: the <script> tags have no crossorigin attribute, so the
    // browser fetches them in no-cors mode and the response is opaque
    // (status 0, ok=false). cache.add() rejects opaque responses, so we
    // fetch + put manually. The opaque body is still replayable from the
    // cache, which is all we need to boot the app offline.
    const runtime = await caches.open(RUNTIME);
    await Promise.allSettled(CDN.map(async (u) => {
      try {
        const resp = await fetch(u, { mode: 'no-cors' });
        await runtime.put(u, resp);
      } catch {}
    }));
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
    // Cache OK responses AND opaque cross-origin responses (status 0,
    // ok=false, type='opaque'). Without the type='opaque' branch, every
    // <script src> / <link href> without a crossorigin attribute silently
    // fails to cache and the PWA boots to a white screen offline.
    if (resp && (resp.ok || resp.type === 'opaque')) cache.put(request, resp.clone());
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
