/* 청약패스 서비스 워커 — 웹 푸시 알림만 처리한다 (기능: web_push).
   화면·데이터를 캐시하지 않는다 (fetch 처리 없음). 알림을 켤 때만 등록된다. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || '청약패스', {
    body: d.body || '새 소식이 있어요.',
    icon: 'icon-192.png',
    tag: d.tag || 'cp',
    data: { url: d.url || '/' },
    lang: 'ko',
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || '/', self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    const w = list.find(c => new URL(c.url).origin === self.location.origin);
    if (w) { w.postMessage({ type: 'cp-open', url }); return w.focus(); }
    return self.clients.openWindow(url);
  }));
});
