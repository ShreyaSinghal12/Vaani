// Minimal service worker. Needed so Android lets people install Vaani and
// pick it from the Share menu. We only cache the app shell; checks always go
// to the server.
var CACHE = "vaani-v1";
var SHELL = ["/", "/style.css", "/app.js", "/icon.svg", "/manifest.webmanifest"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }));
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }));
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.indexOf("/api/") === 0) return;
  e.respondWith(
    fetch(e.request).catch(function () { return caches.match(e.request, { ignoreSearch: true }); })
  );
});
