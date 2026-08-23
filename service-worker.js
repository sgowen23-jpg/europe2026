const CACHE_VERSION = 'hatzing26-v5';
const RUNTIME_CACHE = CACHE_VERSION + '-runtime';
const CORE_ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png',
  './favicon-32.png'
];

// Cross-origin hosts we runtime-cache (cache-first) so the app works fully offline:
// - flagcdn.com          → country flag images
// - fonts.googleapis.com → the Google Fonts stylesheet
// - fonts.gstatic.com    → the actual font files the stylesheet points to
const RUNTIME_HOSTS = ['flagcdn.com', 'fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_VERSION && k !== RUNTIME_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Network-first for the HTML page, with a timeout fallback to cache.
async function networkFirst(req) {
  const cache = await caches.open(CACHE_VERSION);
  try {
    const network = fetch(req);
    // If the network is slow/flaky, fall back to cache after 4s.
    const res = await Promise.race([
      network,
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 4000))
    ]);
    cache.put('./index.html', res.clone());
    return res;
  } catch {
    return (await cache.match('./index.html')) || (await cache.match(req)) || Response.error();
  }
}

// Cache-first for stable assets (icons, manifest, flags, fonts).
async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    cache.put(req, res.clone());
    return res;
  } catch {
    return cached || Response.error();
  }
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // The itinerary page itself: NETWORK-FIRST so content updates flow through
  // automatically whenever online. Falls back to the cached page when offline.
  if (req.mode === 'navigate') {
    event.respondWith(networkFirst(req));
    return;
  }

  // Cross-origin flags + Google Fonts: cache-first (stable, needed offline).
  if (RUNTIME_HOSTS.includes(url.hostname)) {
    event.respondWith(cacheFirst(req, RUNTIME_CACHE));
    return;
  }

  // Same-origin static assets (icons, manifest): cache-first.
  event.respondWith(cacheFirst(req, CACHE_VERSION));
});
