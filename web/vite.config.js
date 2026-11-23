import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const backend = process.env.RECIPE_BOX_BACKEND || 'http://127.0.0.1:5000';
const backendPaths = [
    '^/(?:api|auth|photos|static)(?:/|$)',
    '^/(?:manifest\\.webmanifest|service-worker\\.js|offline)(?:\\?|$)',
];

export default defineConfig({
    server: {
        fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] },
        proxy: Object.fromEntries(backendPaths.map(path => [path, { target: backend, changeOrigin: true }])),
    },
});
