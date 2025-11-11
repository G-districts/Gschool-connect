
(function(){
  const sid = window.__SESSION_ID__;
  const $ = (q)=>document.querySelector(q);
  const api = (p,opt)=>fetch(p,opt).then(r=>r.json());

  function fillControls(sess){
    $('#sessionName').textContent = sess.name || sid;
    $('#ctl_focus').checked = !!(sess.controls?.focusMode);
    $('#ctl_allowlist').value = (sess.controls?.allowlist||[]).join('\n');
    $('#ctl_exam').checked = !!(sess.controls?.examMode);
    $('#ctl_examurl').value = sess.controls?.examUrl || '';
  }

  function fillStudents(sess){
    const ul = $('#studentsList');
    ul.innerHTML = '';
    (sess.students||[]).forEach(id=>{
      const li = document.createElement('li');
      li.className = 'item';
      li.innerHTML = `<span>${id}</span>`;
      ul.appendChild(li);
    });
    if (!(sess.students||[]).length){
      const li = document.createElement('li');
      li.className = 'item';
      li.textContent = 'No students assigned.';
      ul.appendChild(li);
    }
  }

  function setActive(isActive){
    const pill = $('#statusPill');
    pill.className = 'pill ' + (isActive ? 'ok' : 'off');
    pill.textContent = isActive ? 'Active' : 'Inactive';
  }

  async function load(){
    const res = await api(`/api/sessions/${encodeURIComponent(sid)}`);
    if (!res.ok){ alert(res.error||'Session not found'); return; }
    fillControls(res.session);
    fillStudents(res.session);
    setActive(!!res.active);
  }

  async function saveControls(){
    const body = {
      controls: {
        focusMode: $('#ctl_focus').checked,
        allowlist: $('#ctl_allowlist').value.split('\\n').map(s=>s.trim()).filter(Boolean),
        examMode: $('#ctl_exam').checked,
        examUrl: $('#ctl_examurl').value.trim()
      }
    };
    const res = await fetch(`/api/sessions/${encodeURIComponent(sid)}`, {
      method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
    }).then(r=>r.json());
    if (!res.ok) alert(res.error||'Save failed');
    else await load();
  }

  async function start(){ await fetch(`/api/sessions/${encodeURIComponent(sid)}/start`, {method:'POST'}); await load(); }
  async function end(){ await fetch(`/api/sessions/${encodeURIComponent(sid)}/end`, {method:'POST'}); await load(); }

  document.addEventListener('DOMContentLoaded', ()=>{
    $('#saveCtl').addEventListener('click', saveControls);
    $('#startBtn').addEventListener('click', start);
    $('#endBtn').addEventListener('click', end);
    load();
  });
})();
