import http from 'http';
import fs from 'fs';
import path from 'path';

const PORT = 5180;
const ARTIFACT_DIR = process.env.ARTIFACT_DIR || './artifacts';

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  if (req.method === 'POST' && req.url === '/api/save-snapshot') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const { imageBase64, viewName } = JSON.parse(body);
        const data = imageBase64.replace(/^data:image\/\w+;base64,/, '');
        const buffer = Buffer.from(data, 'base64');
        const filename = viewName ? `snapshot_${viewName}.png` : 'live_preview.png';
        const filepath = path.join(ARTIFACT_DIR, filename);
        
        fs.writeFileSync(filepath, buffer);
        console.log(`[Visual Inspector] Successfully captured snapshot to: ${filepath}`);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', path: filepath }));
      } catch (err) {
        console.error('[Visual Inspector] Error saving snapshot:', err);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

server.listen(PORT, () => {
  console.log(`[Visual Inspector] Server running on http://localhost:${PORT}`);
});
