const CACHE_VERSION = 'cinema-v1';
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const IMAGE_CACHE = `${CACHE_VERSION}-images`;
const STATIC_CACHE = `${CACHE_VERSION}-static`;

const STATIC_ASSETS = [
    '/',
    '/static/css/main.css',
    '/static/js/main.js',
    '/static/js/theme.js',
    '/offline.html',
];

const CACHE_URLS = [
    /\.js$/,
    /\.css$/,
    /\.woff2?$/,
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch(err => {
                console.warn('Failed to cache some static assets:', err);
            });
        }).then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter(cacheName => cacheName.startsWith('cinema-') && !cacheName.startsWith(CACHE_VERSION))
                    .map(cacheName => caches.delete(cacheName))
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - network first for HTML, cache first for other assets
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip external requests
    if (!url.origin.includes(self.location.origin)) {
        return;
    }

    // Strategy 1: Network first for HTML documents
    if (request.headers.get('accept')?.includes('text/html')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    if (!response || response.status !== 200 || response.type === 'error') {
                        return response;
                    }
                    const responseToCache = response.clone();
                    caches.open(RUNTIME_CACHE).then(cache => {
                        cache.put(request, responseToCache);
                    });
                    return response;
                })
                .catch(() => {
                    return caches.match(request).then(response => {
                        return response || caches.match('/offline.html');
                    });
                })
        );
        return;
    }

    // Strategy 2: Cache first for images
    if (request.destination === 'image') {
        event.respondWith(
            caches.match(request).then(response => {
                return response || fetch(request).then(response => {
                    if (!response || response.status !== 200) {
                        return response;
                    }
                    const responseToCache = response.clone();
                    caches.open(IMAGE_CACHE).then(cache => {
                        cache.put(request, responseToCache);
                    });
                    return response;
                }).catch(() => {
                    return new Response(
                        '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100" fill="#f3f3f2"/><text x="50" y="50" text-anchor="middle" dy=".3em" fill="#999">No image</text></svg>',
                        { headers: { 'Content-Type': 'image/svg+xml' } }
                    );
                });
            })
        );
        return;
    }

    // Strategy 3: Cache first for static assets (CSS, JS, fonts)
    if (CACHE_URLS.some(pattern => pattern.test(url.pathname))) {
        event.respondWith(
            caches.match(request).then(response => {
                return response || fetch(request).then(response => {
                    if (!response || response.status !== 200) {
                        return response;
                    }
                    const responseToCache = response.clone();
                    caches.open(STATIC_CACHE).then(cache => {
                        cache.put(request, responseToCache);
                    });
                    return response;
                });
            })
        );
        return;
    }

    // Strategy 4: Stale while revalidate for API calls and other requests
    event.respondWith(
        caches.open(RUNTIME_CACHE).then(cache => {
            return fetch(request)
                .then(response => {
                    if (!response || response.status !== 200) {
                        return response;
                    }
                    cache.put(request, response.clone());
                    return response;
                })
                .catch(() => {
                    return cache.match(request);
                });
        })
    );
});

// Background sync for offline actions (future enhancement)
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-reviews') {
        event.waitUntil(syncReviews());
    }
});

async function syncReviews() {
    // Implementation for syncing reviews when online
    return Promise.resolve();
}
