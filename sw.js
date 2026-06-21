/* Ganjoor PWA service worker
 * Strategy:
 *   - Precache app shell (index, manifest, icons) on install
 *   - Precache cross-origin runtime bundles (React, ReactDOM, Tailwind,
 *     Google Fonts CSS) on install — opaque-response opportunistic
 *     caching is too unreliable. See Gotcha #9 in CLAUDE.md.
 *   - data/*.json: NOT intercepted. Persistence happens in the app
 *     layer via IndexedDB (see Gotcha #10). The SW returning data from
 *     Cache Storage worked correctly but on iOS Safari ~17K entries
 *     made PWA cold-start take 8+ s while WebKit indexed the namespace.
 *   - Everything else (font WOFFs, etc.): cache-first with network
 *     fallback. The runtime cacheFirst handler accepts opaque responses
 *     so future cross-origin additions are cached opportunistically.
 *
 * Cache naming convention:
 *   - SHELL_CACHE and RUNTIME bump together when index.html or the
 *     pinned CDN versions change.
 *   - No DATA_CACHE in this version. Legacy ganjoor-data-v* caches
 *     from older versions are deleted on activate to reclaim space.
 */
const SHELL_CACHE = 'ganjoor-shell-v20';
const RUNTIME     = 'ganjoor-runtime-v20';

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
  'https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&family=Estedad:wght@400;500;700&display=swap',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL_CACHE);
    await Promise.allSettled(SHELL.map((u) => shell.add(u)));
    // CDN urls: <script> tags have no crossorigin attribute, so fetches
    // are no-cors and the response is opaque (status 0, ok=false).
    // cache.add() rejects opaque responses, so we do fetch + put manually.
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
    // Anything not in the keep-list goes — including the legacy
    // ganjoor-data-v* caches from before the IDB migration, which
    // reclaims ~300 MB and unblocks iOS cold-start performance.
    await Promise.all(names.map((n) => {
      if (![SHELL_CACHE, RUNTIME].includes(n)) return caches.delete(n);
    }));
    await self.clients.claim();
  })());
});

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

  // Same-origin data/*.json: do NOT intercept. The app layer reads
  // these from IndexedDB when offline-saved and falls back to network
  // otherwise. Routing them through Cache Storage made iOS cold-start
  // scale linearly with cache entry count (8+ s at 17K entries).
  if (url.origin === self.location.origin && /\/data\/.+\.json(?:$|\?)/.test(url.pathname)) {
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
