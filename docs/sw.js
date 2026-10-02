/* 청약패스 서비스 워커 — 웹 푸시 알림만 처리한다 (기능: web_push).
   화면·데이터를 캐시하지 않는다 (fetch 처리 없음). 알림을 켤 때만 등록된다.
   받은 알림함 (기능: push_inbox): 받은 알림을 이 기기 IndexedDB(cp-inbox)에 최근 30개까지 두고, 안 읽은 수를 앱 아이콘 배지로 표시한다.
   화면(알림 탭)이 읽음 처리와 배지 지우기를 한다. 알림 서버로는 아무것도 보내지 않는다. */
const INBOX_MAX = 30;
function inboxDB(){
  return new Promise((ok, no) => { const r = indexedDB.open('cp-inbox', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('items', { keyPath: 'id', autoIncrement: true });
    r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error); });
}
async function inboxAdd(item){
  try {
    const db = await inboxDB();
    const all = await new Promise((ok, no) => { const t = db.transaction('items', 'readwrite'), st = t.objectStore('items');
      st.add(item); const g = st.getAll(); t.oncomplete = () => ok(g.result || []); t.onerror = () => no(t.error); });
    const old = all.sort((a, b) => b.id - a.id).slice(INBOX_MAX);
    if (old.length) await new Promise(ok => { const t = db.transaction('items', 'readwrite'); old.forEach(x => t.objectStore('items').delete(x.id)); t.oncomplete = ok; t.onerror = ok; });
    const unread = all.filter(x => !x.read).length;
    if (self.navigator.setAppBadge) await self.navigator.setAppBadge(unread).catch(() => {});
    const list = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    list.forEach(c => c.postMessage({ type: 'cp-inbox' }));
  } catch (x) { /* 알림함 저장에 실패해도 알림은 그대로 보인다 */ }
}
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : '' }; }
  const title = d.title || '청약패스', body = d.body || '새 소식이 있어요.', url = d.url || '/';
  e.waitUntil(Promise.all([
    self.registration.showNotification(title, { body, icon: 'icon-192.png', tag: d.tag || 'cp', data: { url, at: Date.now() }, lang: 'ko' }),
    inboxAdd({ title, body, url, at: Date.now(), read: false }),
  ]));
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
