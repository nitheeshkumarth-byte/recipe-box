if ("serviceWorker" in navigator && window.isSecureContext) {
    const worker = document.querySelector('meta[name="recipe-service-worker"]');
    if (worker) navigator.serviceWorker.register(worker.content).catch(() => {});
}
