// FiscMoney Service Worker - PWA Offline Shell & Fast Asset Cache
const CACHE_NAME = 'fiscmoney-cache-v1';
const STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/images/logo.png',
    '/static/images/favicon.png',
    '/static/images/icon-192.png',
    '/static/images/icon-512.png',
    '/static/manifest.json'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

// Network-first strategy for dynamic pages/API, Cache-first for static assets
self.addEventListener('fetch', (event) => {
    const requestUrl = new URL(event.request.url);

    // Skip non-GET or chrome-extension requests
    if (event.request.method !== 'GET' || requestUrl.protocol.startsWith('chrome-extension')) {
        return;
    }

    // Static assets: Cache First, fallback to Network
    if (requestUrl.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(event.request).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseToCache);
                        });
                    }
                    return networkResponse;
                });
            })
        );
        return;
    }

    // Dynamic Pages / Endpoints: Network First, fallback to cache if available
    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});
