const shell = "recipe-box-offline-v1";
const scope = new URL(self.registration.scope);
const offline = new URL("offline", scope).href;

self.addEventListener("install", event => {
    event.waitUntil(caches.open(shell).then(cache => cache.add(offline)));
});

self.addEventListener("activate", event => {
    event.waitUntil(caches.keys().then(keys => Promise.all(
        keys.filter(key => key.startsWith("recipe-box-offline-") && key !== shell)
            .map(key => caches.delete(key))
    )));
});

self.addEventListener("fetch", event => {
    if (event.request.mode !== "navigate" || event.request.method !== "GET") return;
    const target = new URL(event.request.url);
    if (target.origin !== scope.origin || !target.pathname.startsWith(scope.pathname)) return;
    event.respondWith(fetch(event.request).catch(async () =>
        (await caches.match(offline)) || Response.error()));
});
