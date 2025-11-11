
const $ = (q)=>document.querySelector(q);
const api = (p, opt)=>fetch(p, opt).then(r=>r.json());

async function loadStudents() {
  const res = await api('/api/students');
  const sel = $('#sess_students');
  sel.innerHTML = '';
  (res.students || []).forEach(s=>{
    const opt = document.createElement('option');
    opt.value = s.id || s.email;
    opt.textContent = `${s.name || s.email} (${s.email || s.id})`;
    sel.appendChild(opt);
  });
  // students table
  const tbl = (res.students || []).map(s=>`• ${s.name || s.email} <span class="subtle">[${s.email || s.id}]</span>`).join('<br>');
  $('#students_table').innerHTML = tbl || 'No students yet.';
}

function getSelectedStudents() {
  const el = $('#sess_students');
  return Array.from(el.selectedOptions).map(o=>o.value);
}

function readWeeklySchedule() {
  const days = $('#sched_days').value.trim();
  const start = $('#sched_start').value || '';
  const end = $('#sched_end').value || '';
  if (!days || !start || !end) return [];
  const arr = days.split(',').map(d=>parseInt(d.trim())).filter(n=>!isNaN(n));
  return [{ type: 'weekly', days: arr, start, end, timezone: 'America/Los_Angeles' }];
}

async function loadSessions() {
  const res = await api('/api/sessions');
  const activeSet = new Set(res.active || []);
  const list = $('#sessions_list');
  list.innerHTML = '';
  (res.sessions || []).forEach(s=>{
    const li = document.createElement('li');
    li.className = 'item';
    const active = activeSet.has(s.id);
    li.innerHTML = `
      <div>
        <div><strong>${s.name}</strong> <span class="small subtle">(${s.teacher||'—'})</span></div>
        <div class="small">${(s.students||[]).length} student(s) • Allowlist: <span class="subtle">${(s.controls?.allowlist||[]).length}</span> • Focus: <span class="subtle">${!!(s.controls?.focusMode)}</span> • Exam: <span class="subtle">${!!(s.controls?.examMode)}</span></div>
      </div>
      <div>
        <span class="pill ${active? 'ok':'off'}">${active? 'Active':'Inactive'}</span>
        <button data-id="${s.id}" class="btn ${active? 'secondary':'ghost'} startstop">${active? 'End':'Start'}</button>
        <button data-id="${s.id}" class="btn ghost edit">Edit</button>
        <input type="checkbox" class="bulk" data-id="${s.id}" title="Select for bulk start/end">
      </div>
    `;
    list.appendChild(li);
  });
}

function formToSession() {
  return {
    id: $('#sess_id').value.trim() || undefined,
    name: $('#sess_name').value.trim(),
    teacher: $('#sess_teacher').value.trim(),
    students: getSelectedStudents(),
    controls: {
      focusMode: $('#sess_focus').checked,
      allowlist: ($('#sess_allowlist').value || '').split('\n').map(s=>s.trim()).filter(Boolean),
      examMode: $('#sess_exam').checked,
      examUrl: $('#sess_examurl').value.trim()
    },
    schedule: { entries: readWeeklySchedule() }
  };
}

function sessionToForm(s) {
  $('#sess_id').value = s.id || '';
  $('#sess_name').value = s.name || '';
  $('#sess_teacher').value = s.teacher || '';
  // select students
  const sel = $('#sess_students');
  const values = new Set((s.students||[]));
  Array.from(sel.options).forEach(o=> o.selected = values.has(o.value));
  // controls
  $('#sess_focus').checked = !!(s.controls?.focusMode);
  $('#sess_allowlist').value = (s.controls?.allowlist||[]).join('\\n');
  $('#sess_exam').checked = !!(s.controls?.examMode);
  $('#sess_examurl').value = s.controls?.examUrl || '';
  // schedule (weekly - first entry if present)
  const w = (s.schedule?.entries||[]).find(e=>e.type==='weekly');
  $('#sched_days').value = w ? (w.days||[]).join(',') : '';
  $('#sched_start').value = w ? (w.start||'') : '';
  $('#sched_end').value = w ? (w.end||'') : '';
}

async function init() {
  await loadStudents();
  await loadSessions();

  $('#refresh').addEventListener('click', async ()=>{
    await loadStudents(); await loadSessions();
  });

  $('#export').addEventListener('click', async ()=>{
    const [stud, sess] = await Promise.all([api('/api/students/export'), api('/api/sessions')]);
    const dump = JSON.stringify({ students: stud.students||[], sessions: sess.sessions||[], active: sess.active||[] }, null, 2);
    const blob = new Blob([dump], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'gschool_db.json'; a.click();
    URL.revokeObjectURL(url);
  });

  $('#add_student').addEventListener('click', async ()=>{
    const id = $('#student_id').value.trim();
    const name = $('#student_name').value.trim();
    if (!id) return alert('Enter student id/email.');
    await api('/api/students', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ id, name, email:id })});
    $('#student_id').value=''; $('#student_name').value='';
    await loadStudents();
  });

  $('#save_session').addEventListener('click', async ()=>{
    const s = formToSession();
    if (!s.name) return alert('Please enter a session name.');
    await api('/api/sessions', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(s)});
    await loadSessions();
    alert('Saved.');
  });

  $('#delete_session').addEventListener('click', async ()=>{
    const id = $('#sess_id').value.trim();
    if (!id) return alert('Enter Session ID to delete (or click Edit on one).');
    if (!confirm('Delete this session?')) return;
    const res = await api('/api/sessions/'+encodeURIComponent(id), { method:'DELETE' });
    if (!res.ok) alert(res.error||'Delete failed');
    await loadSessions();
  });

  $('#reset_form').addEventListener('click', ()=>{
    sessionToForm({id:'',name:'',teacher:'',students:[],controls:{allowlist:[]},schedule:{entries:[]}});
  });

  // Delegate clicks for Start/End/Edit and bulk select
  $('#sessions_list').addEventListener('click', async (e)=>{
    const btn = e.target.closest('button');
    if (!btn) return;
    const id = btn.dataset.id;
    if (btn.classList.contains('startstop')) {
      // determine current label
      if (btn.textContent==='Start') {
        await api(`/api/sessions/${encodeURIComponent(id)}/start`, {method:'POST'});
      } else {
        await api(`/api/sessions/${encodeURIComponent(id)}/end`, {method:'POST'});
      }
      await loadSessions();
    } else if (btn.classList.contains('edit')) {
      const detail = await api(`/api/sessions/${encodeURIComponent(id)}`);
      if (detail.ok) sessionToForm(detail.session);
    }
  });

  $('#start_selected').addEventListener('click', async ()=>{
    const ids = Array.from(document.querySelectorAll('.bulk:checked')).map(c=>c.dataset.id);
    for (const id of ids) await api(`/api/sessions/${encodeURIComponent(id)}/start`, {method:'POST'});
    await loadSessions();
  });
  $('#end_selected').addEventListener('click', async ()=>{
    const ids = Array.from(document.querySelectorAll('.bulk:checked')).map(c=>c.dataset.id);
    for (const id of ids) await api(`/api/sessions/${encodeURIComponent(id)}/end`, {method:'POST'});
    await loadSessions();
  });
}

document.addEventListener('DOMContentLoaded', init);
