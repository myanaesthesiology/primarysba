const CACHE_VERSION = 'primary-revision-gate01-v1';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './firebase-config.js',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_VERSION).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);

  // Firebase discussions are deliberately online-only. Never satisfy Firebase SDK/API
  // requests from the app cache; an offline failure must not block the core SBA shell.
  const firebaseOnlineOnly = /(^|\.)gstatic\.com$|(^|\.)googleapis\.com$|(^|\.)firebaseio\.com$|(^|\.)firebaseapp\.com$|(^|\.)firebasestorage\.app$/.test(url.hostname);
  if (firebaseOnlineOnly) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Other cross-origin resources remain online-first with opportunistic caching.
  if (url.origin !== self.location.origin) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then(cache => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Navigation requests fall back to the cached question bank shell when offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_VERSION).then(cache => cache.put('./index.html', copy));
          return response;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  // Same-origin static assets: cache first, then network and cache.
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE_VERSION).then(cache => cache.put(event.request, copy));
      }
      return response;
    }))
  );
});
