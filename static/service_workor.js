const CACHE_NAME = "v1";
const urlsToCache = [
  "/",
  "/static/css/styles.css", // Add your CSS file paths
  "/static/js/scripts.js", // Add your JS file paths
  "/manifest.json",
  "/static/images/android-chrome-192x192.png",
  "/static/images/android-chrome-512x512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
