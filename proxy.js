const http = require('http');

const PORT = 8080; // Unified gateway port
const SIDECAR_URL = 'http://127.0.0.1:8081';
const MEMOS_URL = 'http://127.0.0.1:9099';

const server = http.createServer((req, res) => {
  const url = req.url;
  // Match Caddyfile logic: /admin/*, /health, /webhooks/* -> Sidecar API
  const isSidecar = url.startsWith('/admin/') || url === '/health' || url.startsWith('/webhooks/');
  const target = isSidecar ? SIDECAR_URL : MEMOS_URL;
  
  const targetUrl = new URL(target + url);
  
  const proxyReq = http.request({
    hostname: targetUrl.hostname,
    port: targetUrl.port,
    path: targetUrl.pathname + targetUrl.search,
    method: req.method,
    headers: req.headers
  }, (proxyRes) => {
    // Write headers and pipe response body back
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });
  
  proxyReq.on('error', (err) => {
    console.error(`Proxy error for ${req.method} ${url}:`, err.message);
    res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end(`网关错误 (Bad Gateway): ${err.message}`);
  });
  
  // Pipe request body to target
  req.pipe(proxyReq);
});

// Enable keepAlive for connection efficiency
server.keepAliveTimeout = 60000;

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[Unified Gateway] Listening on http://localhost:${PORT}`);
  console.log(`  -> Routing Memos to ${MEMOS_URL}`);
  console.log(`  -> Routing Sidecar to ${SIDECAR_URL}`);
});
