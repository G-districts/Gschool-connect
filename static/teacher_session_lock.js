
(function(){
  const SID = window.__SESSION_ID__ || '';
  const _fetch = window.fetch.bind(window);
  window.fetch = async function(input, init){
    init = init || {};
    init.headers = init.headers || {};
    if (!init.headers['X-Session-ID'] && !init.headers['x-session-id']) {
      init.headers['X-Session-ID'] = SID;
    }
    return _fetch(input, init);
  };
  document.addEventListener('DOMContentLoaded', ()=>{
    const b = document.createElement('div');
    b.textContent = 'Session: ' + SID;
    b.style.cssText = 'position:fixed;right:12px;bottom:12px;background:#111827;color:#fff;padding:8px 12px;border-radius:10px;font:12px/1.2 system-ui;z-index:2147483647';
    document.body.appendChild(b);
  });
})();
