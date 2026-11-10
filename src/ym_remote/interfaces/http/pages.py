MANIFEST = {
    "id": "/",
    "scope": "/",
    "name": "YM Remote",
    "short_name": "YM Remote",
    "description": "Пульт Яндекс Музыки",
    "start_url": "/?source=pwa",
    "display": "standalone",
    "display_override": ["standalone", "browser"],
    "background_color": "#000000",
    "theme_color": "#000000",
    "orientation": "portrait",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
}

OPEN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#000000">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="YM Remote">
  <meta name="mobile-web-app-capable" content="yes">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <title>YM Remote</title>
  <meta http-equiv="refresh" content="0;url=/">
  <script>location.replace('/');</script>
</head>
<body style="margin:0;background:#000;color:#fff;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh">
  <p><a href="/" style="color:#ffcc00;text-decoration:none;font-size:1.1rem">Открыть пульт</a></p>
</body>
</html>
"""

SERVICE_WORKER = """self.addEventListener('install', (event) => {
  self.skipWaiting();
});
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
self.addEventListener('notificationclick', (event) => {
  const action = event.action;
  const cmd = action === 'prev' || action === 'play_pause' || action === 'next' ? action : '';
  if (!cmd) event.notification.close();
  event.waitUntil((async () => {
    const list = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    if (list.length > 0) {
      const target = list.find((client) => client.focused) || list[0];
      if (cmd) {
        target.postMessage({ type: 'shade_command', command: cmd });
      } else if ('focus' in target) {
        await target.focus();
      }
      return;
    }
    const url = cmd ? '/?source=pwa&shade=' + cmd : '/?source=pwa';
    if (self.clients.openWindow) {
      await self.clients.openWindow(url);
    }
  })());
});
"""
