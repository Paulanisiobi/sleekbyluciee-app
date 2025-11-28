from flask import Blueprint, request, abort, jsonify, render_template_string
import os
import time
try:
    from db import get_conn
    from psycopg2.extras import RealDictCursor
except Exception:
    # During tests we may monkeypatch get_conn; keep placeholders
    def get_conn():
        raise RuntimeError('DB not available')
    RealDictCursor = None

admin_bp = Blueprint('admin', __name__)

ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')


def _auth_token_from_request():
    auth = request.headers.get('Authorization')
    if auth and auth.lower().startswith('bearer '):
        return auth.split(None, 1)[1]
    return request.headers.get('X-Admin-Token') or request.args.get('token')


def check_admin():
    if not ADMIN_TOKEN:
        return True
    token = _auth_token_from_request()
    return token == ADMIN_TOKEN


@admin_bp.before_request
def require_admin():
    if request.path.startswith('/admin') and not check_admin():
        abort(403)


# Simple in-memory rate limiter: allow N requests per WINDOW secs per IP
RATE_LIMIT_N = int(os.environ.get('ADMIN_RATE_LIMIT_N', '60'))
RATE_LIMIT_WINDOW = int(os.environ.get('ADMIN_RATE_LIMIT_WINDOW', '60'))
_rate_store = {}


@admin_bp.before_request
def admin_rate_limit():
    # only apply to JSON/admin API endpoints
    if request.path.startswith('/admin') and request.path.endswith('.json'):
        ip = request.remote_addr or 'local'
        now = int(time.time())
        bucket = _rate_store.get(ip, {'ts': now, 'count': 0})
        if now - bucket['ts'] > RATE_LIMIT_WINDOW:
            bucket = {'ts': now, 'count': 0}
        bucket['count'] += 1
        _rate_store[ip] = bucket
        if bucket['count'] > RATE_LIMIT_N:
            return jsonify({'error': 'rate_limited'}), 429


LIST_HTML = '''
<!doctype html>
<title>Dead Jobs</title>
<h1>Dead Jobs</h1>
<form id="search" onsubmit="event.preventDefault(); load(1);">Search: <input id="q" name="q"/> <button type="submit">Go</button></form>
<div id="list">Loading...</div>
<div id="pager"></div>
<script>
const perPage = 10;
async function load(page=1){
  const q = document.getElementById('q').value;
  const r = await fetch(`/admin/dead_letters.json?limit=${perPage}&page=${page}${q?('&q='+encodeURIComponent(q)) : ''}`);
  const data = await r.json();
  const el = document.getElementById('list');
  if(!data.items.length){ el.innerHTML = '<p>No dead jobs</p>'; document.getElementById('pager').innerHTML=''; return }
  let html = '<table border=1><tr><th>ID</th><th>Attempts</th><th>Created</th><th>Action</th></tr>'
  for(const j of data.items){
    html += `<tr><td><a href="/admin/dead_letters/${j.id}">${j.id}</a></td><td>${j.attempts}</td><td>${j.created_at}</td><td><button onclick="requeue('${j.id}')">Requeue</button></td></tr>`
  }
  html += '</table>'
  el.innerHTML = html
  // pager
  const pager = document.getElementById('pager');
  let phtml = '';
  for(let i=1;i<=Math.max(1, Math.ceil(data.total/perPage));i++){
    if(i===page) phtml += `<strong>${i}</strong> `; else phtml += `<button onclick="load(${i})">${i}</button> `
  }
  pager.innerHTML = phtml
}
async function requeue(id){
  if(!confirm('Requeue '+id+'?')) return;
  const token = new URLSearchParams(window.location.search).get('token');
  const headers = token ? {'Authorization': 'Bearer '+token} : {};
  const r = await fetch('/admin/dead_letters/'+id+'/requeue', {method:'POST', headers: headers});
  if(r.ok) { alert('Requeued'); load() }
  else { alert('Failed'); }
}
load();
</script>
'''


@admin_bp.route('/dead_letters')
def dead_letters_page():
    return render_template_string(LIST_HTML)


@admin_bp.route('/dead_letters.json')
def dead_letters_json():
    per_page = int(request.args.get('limit', 100))
    page = int(request.args.get('page', 1))
    q = request.args.get('q')
    if per_page <= 0:
        per_page = 100
    if page <= 0:
        page = 1
    offset = (page - 1) * per_page
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            total = None
            # Try to get a reliable total via COUNT(); if the cursor returns an
            # unexpected structure (e.g. tests using DummyCursor), fall back to
            # computing length from the selected rows below.
            try:
                if q:
                    like = f"%{q}%"
                    cur.execute("SELECT count(*) FROM measurement_jobs WHERE status='dead' AND (id::text ILIKE %s OR payload::text ILIKE %s)", (like, like))
                else:
                    cur.execute("SELECT count(*) FROM measurement_jobs WHERE status='dead'")
                cnt_row = cur.fetchone()
                if isinstance(cnt_row, dict) and 'count' in cnt_row:
                    total = int(cnt_row['count'])
                elif isinstance(cnt_row, (list, tuple)) and len(cnt_row) > 0:
                    total = int(cnt_row[0])
            except Exception:
                total = None

            # Now fetch the actual page of rows
            if q:
                like = f"%{q}%"
                cur.execute("SELECT id, created_at, attempts, last_error, payload FROM measurement_jobs WHERE status='dead' AND (id::text ILIKE %s OR payload::text ILIKE %s) ORDER BY created_at DESC LIMIT %s OFFSET %s", (like, like, per_page, offset))
            else:
                cur.execute("SELECT id, created_at, attempts, last_error, payload FROM measurement_jobs WHERE status='dead' ORDER BY created_at DESC LIMIT %s OFFSET %s", (per_page, offset))
            rows = cur.fetchall()
            if total is None:
                try:
                    total = int(getattr(cur, 'rowcount', len(rows)))
                except Exception:
                    total = len(rows)
            return jsonify({'items': rows, 'total': int(total)})
    finally:
        conn.close()


@admin_bp.route('/dead_letters/<job_id>')
def dead_letter_show(job_id):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM measurement_jobs WHERE id=%s", (job_id,))
            row = cur.fetchone()
            if not row:
                abort(404)
            csrf_note = ''
            if ADMIN_TOKEN:
                csrf_note = '<p>Form submissions require the admin token (hidden input named token) or Authorization Bearer header.</p>'
            return render_template_string('<h1>Job {{id}}</h1>'+csrf_note+'<pre>{{job|tojson(indent=2)}}</pre><form method="post" action="/admin/dead_letters/{{id}}/requeue"><input type="hidden" name="token" value="{{token}}"/><button type="submit">Requeue</button></form>', id=job_id, job=row, token=(ADMIN_TOKEN or ''))
    finally:
        conn.close()


@admin_bp.route('/dead_letters/<job_id>/requeue', methods=['POST'])
def dead_letter_requeue(job_id):
    token = _auth_token_from_request()
    if ADMIN_TOKEN:
        form_token = request.form.get('token')
        if token != ADMIN_TOKEN and form_token != ADMIN_TOKEN:
            return jsonify({'error': 'unauthorized'}), 403

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE measurement_jobs SET status='queued', attempts=0, last_error=NULL WHERE id=%s", (job_id,))
            conn.commit()
            if cur.rowcount == 0:
                return jsonify({'updated': 0}), 404
            return jsonify({'updated': cur.rowcount})
    finally:
        conn.close()
