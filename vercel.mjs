const backend = process.env.RECIPE_BOX_BACKEND;
if (!backend || !/^https:\/\/[a-z0-9.-]+$/i.test(backend)) {
    throw new Error('Set RECIPE_BOX_BACKEND to the HTTPS origin of your Render backend.');
}

const forwarded = [
    '/api/:path*', '/auth/:path*', '/photos/:path*', '/static/:path*',
    '/manifest.webmanifest', '/service-worker.js', '/offline', '/healthz', '/readyz',
];

export const config = {
    framework: null,
    installCommand: 'npm ci --prefix web',
    buildCommand: 'npm run --prefix web build',
    outputDirectory: 'web/dist',
    rewrites: [
        ...forwarded.map(source => ({ source, destination: `${backend}${source}` })),
        ...['/add', '/recipe/:id', '/edit/:id'].map(source => ({ source, destination: '/index.html' })),
    ],
    headers: [{ source: '/(.*)', headers: [{ key: 'X-Content-Type-Options', value: 'nosniff' }] }],
};
