// Basic Service Worker
const CACHE_NAME = 'groweasy-invoice-v3';

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll([
          '/',
          '/static/css/invoice.min.css',
          '/static/css/bootstrap.min.css',
          '/static/js/groweasy_toast.min.js',
          '/static/js/bootstrap.bundle.min.js',
          '/static/js/form_items.js',
          '/static/img/favicon.ico',
          '/static/img/favicon-192.png',
          '/static/manifest.json'
        ]).catch(error => {
          console.log('Cache addAll failed:', error);
        });
      })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      })
  );
});