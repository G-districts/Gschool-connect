
// Locks teacher.html to a specific class session.
// Filters API responses to only include the session's students.
// Reroutes control changes to per-session endpoints where possible.
(function(){
  const SID = window.__SESSION_ID__;
  let SESSION_STUDENTS = new Set();
  const BASE = '';

  async function getSession() {
    const r = await fetch(`/api/sessions/${encodeURIComponent(SID)}`);
    const j = await r.json();
    const arr = (j.session && j.session.students) || [];
    SESSION_STUDENTS = new Set(arr);
    annotateUI(j.session);
  }

  function annotateUI(sess){
    // Small badge so teachers know which session they're on
    try {
      const hdr = document.querySelector('header, .header, nav') || document.body;
      const badge = document.createElement('div');
      badge.style.cssText = "position:fixed;right:12px;bottom:12px;background:#111827;color:#fff;padding:8px 12px;border-radius:10px;font:12px/1.2 system-ui";
      badge.textContent = `Session: ${sess?.name || SID}`;
      document.body.appendChild(badge);
    } catch(e){}
  }

  // Helper: shallow student-filter for common payload shapes
  function filterPayload(data){
    try {
      // Arrays of students
      if (Array.isArray(data)) {
        return data.filter(x => {
          const id = x?.id || x?.email || x?.student || x?.user;
          return id ? SESSION_STUDENTS.has(id) : true;
        });
      }
      // Objects with .students / .presence / .items etc.
      if (data && typeof data === 'object') {
        const out = Array.isArray(data) ? [] : { ...data };
        for (const k of Object.keys(data)) {
          const v = data[k];
          if (Array.isArray(v)) {
            out[k] = filterPayload(v);
          } else if (v && typeof v === 'object') {
            out[k] = filterPayload(v);
          } else {
            out[k] = v;
          }
        }
        return out;
      }
    } catch(e){ console.warn('filterPayload error', e); }
    return data;
  }

  // Monkey-patch fetch to filter GET responses for certain endpoints
  const _fetch = window.fetch.bind(window);
  window.fetch = async function(input, init){
    try {
      const url = (typeof input === 'string') ? input : (input?.url || '');
      const method = (init?.method || 'GET').toUpperCase();

      // Intercept POST bodies that include student arrays; restrict to session
      if (method === 'POST' || method === 'PUT') {
        if (init && init.body && typeof init.body === 'string' && init.headers && /application\/json/i.test(init.headers['Content-Type']||init.headers['content-type']||'')) {
          try {
            const body = JSON.parse(init.body);
            if (Array.isArray(body.students)) {
              body.students = body.students.filter(s => SESSION_STUDENTS.has(s));
              init.body = JSON.stringify(body);
            }
          } catch(e){}
        }
      }

      init=init||{};init.headers=init.headers||{};init.headers['X-Session-ID']=SID;
      const res = await _fetch(input, init);
      // Filter only for selected endpoints
      const watch = [/\/api\/presence\b/, /\/api\/commands\b/, /\/api\/timeline\b/, /\/api\/heartbeat\b/, /\/api\/offtask\b/];
      if (method === 'GET' && watch.some(rx => rx.test(url))) {
        const clone = res.clone();
        let data;
        try { data = await clone.json(); } catch(e){ return res; }
        const filtered = filterPayload(data);
        const blob = new Blob([JSON.stringify(filtered)], { type: 'application/json' });
        const newRes = new Response(blob, {
          status: res.status,
          statusText: res.statusText,
          headers: res.headers
        });
        return newRes;
      }
      return res;
    } catch(e){
      return _fetch(input, init);
    }
  };

  // On load
  document.addEventListener('DOMContentLoaded', getSession);
})();
