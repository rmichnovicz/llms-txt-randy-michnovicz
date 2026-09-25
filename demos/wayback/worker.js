// Generated snapshot data is prepended by scripts/wayback_demo.py.
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (!['GET', 'HEAD'].includes(request.method)) return new Response('Read-only historical replay', {status: 405});
    const provenance = JSON.stringify(SNAPSHOT.metadata, null, 2);
    const routes = {
      '/site/': [SNAPSHOT.html, 'text/html; charset=utf-8'],
      '/robots.txt': [`User-agent: *\nAllow: /site/\nDisallow: /\nSitemap: ${url.origin}/sitemap.xml\n`, 'text/plain'],
      '/sitemap.xml': [`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>${url.origin}/site/</loc></url></urlset>`, 'application/xml'],
      '/provenance.json': [provenance, 'application/json'],
      '/': [`<!doctype html><meta name="viewport" content="width=device-width"><title>Brief historical replay</title><style>body{font:18px/1.6 system-ui;max-width:720px;margin:50px auto;padding:20px}a{color:#493398}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Historical replay</h1><p>A single HTML5 Boilerplate homepage captured by the Wayback Machine. This is an independent Brief demo, not the original website.</p><p>Active capture: <strong>${SNAPSHOT.metadata.timestamp}</strong></p><p><a href="/site/">Open the replay page</a> · <a href="${SNAPSHOT.metadata.capture_url}">Original archive</a> · <a href="/provenance.json">Capture provenance</a></p><p>Submit <code>${url.origin}/site/</code> to Brief. Switch captures using the deployment command, then choose Check now.</p>`, 'text/html; charset=utf-8'],
    };
    const route = routes[url.pathname];
    if (!route) return new Response('This resource was not captured. Unavailable is not evidence of deletion.', {status: 503, headers: {'Cache-Control': 'no-store'}});
    const [body, type] = route;
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body));
    const etag = '"' + [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2,'0')).join('') + '"';
    const headers = {'Content-Type':type,'Cache-Control':'public, max-age=0, must-revalidate','ETag':etag,'X-Replay-Capture':SNAPSHOT.metadata.timestamp,'X-Robots-Tag':'noindex','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"};
    if ((request.headers.get('If-None-Match') || '').split(',').map(s => s.trim().replace(/^W\//, '')).some(value => value === etag || value === '*')) return new Response(null, {status:304, headers});
    return new Response(request.method === 'HEAD' ? null : body, {headers});
  }
};
