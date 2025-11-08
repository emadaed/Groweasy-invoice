// Basic Service Worker
const CACHE_NAME = 'groweasy-invoice-v1';
const urlsToCache = [
  '/',
  '/static/css/invoice.css',
  '/static/js/groweasy_toast.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});