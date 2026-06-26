"""Ingress web UI: status panel plus manual Pull / Push / Resolve actions."""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from logger import RING

log = logging.getLogger("web")

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Git Sync</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
         background: #f5f6f8; color: #1c1c1c; }
  @media (prefers-color-scheme: dark) {
    body { background: #111418; color: #e8e8e8; }
    .card { background: #1c2026 !important; }
    .log { background: #0c0e11 !important; color: #c8d0d8 !important; }
    .k { color: #8aa0b4 !important; }
  }
  header { background: #03a9f4; color: #fff; padding: 16px 20px; font-size: 20px;
           font-weight: 600; display: flex; align-items: center; gap: 10px; }
  main { max-width: 820px; margin: 0 auto; padding: 16px; }
  .card { background: #fff; border-radius: 12px; padding: 16px 18px; margin: 14px 0;
          box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  h2 { font-size: 15px; margin: 0 0 12px; text-transform: uppercase;
       letter-spacing: .04em; opacity: .7; }
  .grid { display: grid; grid-template-columns: 140px 1fr; gap: 6px 12px; font-size: 14px; }
  .k { color: #555; }
  .pill { display: inline-block; padding: 2px 10px; border-radius: 999px;
          font-size: 12px; font-weight: 600; }
  .ok { background: #e6f4ea; color: #137333; }
  .warn { background: #fef7e0; color: #b06000; }
  .err { background: #fce8e6; color: #c5221f; }
  .muted { background: #eceff1; color: #546e7a; }
  button { font-size: 14px; font-weight: 600; padding: 10px 16px; border: 0;
           border-radius: 8px; cursor: pointer; color: #fff; background: #03a9f4; }
  button.secondary { background: #607d8b; }
  button.danger { background: #c5221f; }
  button:disabled { opacity: .5; cursor: default; }
  .row { display: flex; gap: 10px; flex-wrap: wrap; }
  .banner { border-left: 4px solid #b06000; background: #fef7e0; color: #6b4900;
            padding: 12px 14px; border-radius: 8px; margin-bottom: 12px; font-size: 14px; }
  .log { background: #1c2026; color: #c8d0d8; border-radius: 8px; padding: 12px;
         font-family: ui-monospace, Menlo, monospace; font-size: 12px; line-height: 1.5;
         max-height: 320px; overflow: auto; white-space: pre-wrap; }
  .toast { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
           background: #323232; color: #fff; padding: 10px 18px; border-radius: 8px;
           font-size: 14px; opacity: 0; transition: opacity .2s; pointer-events: none; }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
<header>&#128260; Git Sync</header>
<main>
  <div id="resolve" class="card" style="display:none">
    <div class="banner" id="resolveText"></div>
    <div class="row">
      <button class="secondary" onclick="act('resolve','pull')">&#11015; Restore from remote (remote wins)</button>
      <button class="danger" onclick="act('resolve','push')">&#11014; Push local (local wins)</button>
    </div>
  </div>

  <div id="conflict" class="card" style="display:none">
    <div class="banner" id="conflictText"></div>
    <div style="font-size:13px;margin:0 0 10px">
      <b>Conflicting files:</b>
      <div id="conflictFiles" style="font-family:ui-monospace,Menlo,monospace;
        font-size:12px;margin-top:6px;white-space:pre-wrap"></div>
    </div>
    <div class="row">
      <button class="danger" onclick="resolveConflict('local')">&#11014; Keep my version (local wins)</button>
      <button class="secondary" onclick="resolveConflict('remote')">&#11015; Use remote version (remote wins)</button>
    </div>
  </div>

  <div class="card">
    <h2>Status</h2>
    <div class="grid">
      <div class="k">State</div><div id="s_state">&mdash;</div>
      <div class="k">Branch</div><div id="s_branch">&mdash;</div>
      <div class="k">Remote</div><div id="s_remote" style="word-break:break-all">&mdash;</div>
      <div class="k">Working tree</div><div id="s_dirty">&mdash;</div>
      <div class="k">Ahead / Behind</div><div id="s_ab">&mdash;</div>
      <div class="k">Last commit</div><div id="s_commit">&mdash;</div>
      <div class="k">Last pull</div><div id="s_pull">&mdash;</div>
      <div class="k">Last push</div><div id="s_push">&mdash;</div>
      <div class="k">Auto pull</div><div id="s_apull">&mdash;</div>
      <div class="k">Auto push</div><div id="s_apush">&mdash;</div>
      <div class="k">Last error</div><div id="s_err">&mdash;</div>
    </div>
  </div>

  <div class="card">
    <h2>SSH deploy key</h2>
    <p style="font-size:13px;opacity:.75;margin:0 0 8px">
      Add this <b>public</b> key to your repository as a deploy key with
      <b>write access</b> (GitHub: Settings &rarr; Deploy keys &rarr; Add).
      The private key never leaves this app.
    </p>
    <div class="grid" style="margin-bottom:10px">
      <div class="k">Type</div><div id="k_type">&mdash;</div>
      <div class="k">Fingerprint</div><div id="k_fp" style="word-break:break-all">&mdash;</div>
      <div class="k">Source</div><div id="k_src">&mdash;</div>
    </div>
    <textarea id="k_pub" readonly rows="3" style="width:100%;box-sizing:border-box;
      font-family:ui-monospace,Menlo,monospace;font-size:12px;border-radius:8px;
      padding:8px"></textarea>
    <div class="row" style="margin-top:10px;align-items:center">
      <button class="secondary" onclick="copyKey()">&#128203; Copy public key</button>
      <button onclick="connectRepo()">&#128279; Connect / retry</button>
    </div>
    <div class="row" style="margin-top:10px;align-items:center">
      <select id="k_newtype" style="padding:8px;border-radius:8px">
        <option value="ed25519">ed25519 (recommended)</option>
        <option value="rsa">rsa (4096)</option>
      </select>
      <input id="k_newname" placeholder="key name / comment"
        style="padding:8px;border-radius:8px;border:1px solid #ccc;flex:1;min-width:160px">
      <button class="danger" onclick="genKey()">&#9851; Regenerate key</button>
    </div>
  </div>

  <div class="card">
    <h2>Manual actions</h2>
    <div class="row">
      <button id="b_pull" onclick="act('pull')">&#11015; Pull now</button>
      <button id="b_push" onclick="act('push')">&#11014; Push now</button>
    </div>
  </div>

  <div class="card">
    <h2>Backup filters (.gitignore)</h2>
    <p style="font-size:13px;opacity:.75;margin:0 0 8px">
      Files matching these patterns are <b>not</b> backed up. This file is yours —
      the app seeds it once and only changes it when you save here.
    </p>
    <div class="row" style="margin-bottom:8px;align-items:center">
      <input id="gi_add" placeholder="add a pattern, e.g. *.bak or media/"
        onkeydown="if(event.key==='Enter')addPattern()"
        style="padding:8px;border-radius:8px;border:1px solid #ccc;flex:1;min-width:180px">
      <button class="secondary" onclick="addPattern()">&#10133; Add</button>
    </div>
    <textarea id="gi_text" rows="10" spellcheck="false" style="width:100%;box-sizing:border-box;
      font-family:ui-monospace,Menlo,monospace;font-size:12px;border-radius:8px;padding:8px"></textarea>
    <div class="row" style="margin-top:10px;align-items:center">
      <button onclick="saveGitignore()">&#128190; Save .gitignore</button>
      <button class="secondary" onclick="loadGitignore()">&#8635; Reload</button>
    </div>
  </div>

  <div class="card">
    <h2>Recent log</h2>
    <div class="log" id="log">loading&hellip;</div>
  </div>
</main>
<div class="toast" id="toast"></div>
<script>
function pill(cls, text){ return '<span class="pill '+cls+'">'+text+'</span>'; }
function fmt(v){ return v ? v : '&mdash;'; }

async function refresh(){
  try {
    const s = await (await fetch('./api/status', {cache:'no-store'})).json();
    let stateHtml;
    if (s.paused) stateHtml = pill('warn','Paused — needs resolution');
    else if (s.last_error) stateHtml = pill('err','Error');
    else if (s.busy) stateHtml = pill('muted', s.busy + '…');
    else if (!s.initialized) stateHtml = pill('err','Not initialised');
    else stateHtml = pill('ok','Idle');
    document.getElementById('s_state').innerHTML = stateHtml;
    document.getElementById('s_branch').textContent = fmtTxt(s.branch);
    document.getElementById('s_remote').textContent = fmtTxt(s.remote);
    document.getElementById('s_dirty').innerHTML = s.dirty
        ? pill('warn','Uncommitted changes') : pill('ok','Clean');
    document.getElementById('s_ab').textContent = (s.ahead||0)+' ahead, '+(s.behind||0)+' behind';
    document.getElementById('s_commit').textContent = fmtTxt(s.last_commit);
    document.getElementById('s_pull').textContent = fmtTxt(s.last_pull);
    document.getElementById('s_push').textContent = fmtTxt(s.last_push);
    document.getElementById('s_apull').textContent = s.auto_pull
        ? ('on, every '+s.pull_interval+'s') : 'off';
    document.getElementById('s_apush').textContent = s.auto_push
        ? ('on, debounce '+s.push_debounce+'s') : 'off';
    const errEl = document.getElementById('s_err');
    errEl.innerHTML = s.last_error ? pill('err', escapeHtml(s.last_error)) : '&mdash;';

    const cf = document.getElementById('conflict');
    if (s.conflict){ cf.style.display='block';
      document.getElementById('conflictText').textContent = s.pause_reason;
      document.getElementById('conflictFiles').textContent =
        (s.conflict_files||[]).join('\\n') || '(none reported)'; }
    else cf.style.display='none';

    const rv = document.getElementById('resolve');
    if (s.paused && !s.conflict){ rv.style.display='block';
      document.getElementById('resolveText').textContent = s.pause_reason; }
    else rv.style.display='none';

    document.getElementById('k_type').textContent = fmtTxt(s.key_type);
    document.getElementById('k_fp').textContent = fmtTxt(s.key_fingerprint);
    document.getElementById('k_src').textContent = fmtTxt(s.key_source);
    const pub = document.getElementById('k_pub');
    if (document.activeElement !== pub) pub.value = s.public_key || '';

    const busy = !!s.busy;
    document.getElementById('b_pull').disabled = busy;
    document.getElementById('b_push').disabled = busy;
  } catch(e){ /* ignore transient errors */ }
}

function copyKey(){
  const pub = document.getElementById('k_pub');
  if (!pub.value){ toast('No key yet'); return; }
  navigator.clipboard.writeText(pub.value).then(
    ()=> toast('Public key copied'),
    ()=> { pub.select(); document.execCommand('copy'); toast('Public key copied'); }
  );
}
function connectRepo(){ act('connect'); }
async function resolveConflict(strategy){
  const msg = strategy === 'local'
    ? 'Keep your LOCAL version and overwrite the remote?'
    : 'Discard local changes and take the REMOTE version?';
  if (!confirm(msg)) return;
  toast('Resolving conflict: ' + strategy + '…');
  try {
    await fetch('./api/conflict', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({strategy:strategy})});
  } catch(e){ toast('Request failed'); }
  setTimeout(()=>{ refresh(); refreshLog(); }, 700);
}
async function genKey(){
  if (!confirm('Regenerate the SSH key? You must add the NEW public key to your '
      + 'repository before sync will work again.')) return;
  const type = document.getElementById('k_newtype').value;
  const comment = document.getElementById('k_newname').value;
  toast('Generating key…');
  try {
    await fetch('./api/genkey', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({type:type, comment:comment})});
  } catch(e){ toast('Request failed'); }
  setTimeout(()=>{ refresh(); refreshLog(); }, 800);
}
function fmtTxt(v){ return v ? v : '—'; }
function escapeHtml(s){ return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

async function refreshLog(){
  try {
    const d = await (await fetch('./api/log', {cache:'no-store'})).json();
    const el = document.getElementById('log');
    el.textContent = (d.lines||[]).join('\\n');
    el.scrollTop = el.scrollHeight;
  } catch(e){}
}
async function loadGitignore(){
  try {
    const d = await (await fetch('./api/gitignore', {cache:'no-store'})).json();
    const ta = document.getElementById('gi_text');
    if (document.activeElement !== ta) ta.value = d.content || '';
  } catch(e){}
}
function addPattern(){
  const inp = document.getElementById('gi_add');
  const ta = document.getElementById('gi_text');
  const p = inp.value.trim();
  if (!p) return;
  if (ta.value && !ta.value.endsWith('\\n')) ta.value += '\\n';
  ta.value += p + '\\n';
  inp.value = '';
  ta.scrollTop = ta.scrollHeight;
}
async function saveGitignore(){
  const content = document.getElementById('gi_text').value;
  toast('Saving .gitignore…');
  try {
    await fetch('./api/gitignore', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({content:content})});
    toast('.gitignore saved');
  } catch(e){ toast('Request failed'); }
  setTimeout(()=>{ loadGitignore(); refresh(); refreshLog(); }, 500);
}
async function act(name, action){
  toast(action ? (name+': '+action) : (name+'…'));
  try {
    await fetch('./api/'+name, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(action ? {action:action} : {})});
  } catch(e){ toast('Request failed'); }
  setTimeout(()=>{ refresh(); refreshLog(); }, 600);
}
let toastTimer;
function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=> t.classList.remove('show'), 2500);
}
refresh(); refreshLog(); loadGitignore();
setInterval(refresh, 3000);
setInterval(refreshLog, 4000);
</script>
</body>
</html>
"""


def make_handler(gs):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default stderr logging
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                pass

        def _path(self):
            return self.path.split("?", 1)[0].rstrip("/")

        def do_GET(self):
            path = self._path()
            if path == "" or path.endswith("/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif path.endswith("/api/status"):
                self._send(200, json.dumps(gs.status()))
            elif path.endswith("/api/log"):
                self._send(200, json.dumps({"lines": list(RING)}))
            elif path.endswith("/api/gitignore"):
                self._send(200, json.dumps({"content": gs.read_gitignore()}))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            path = self._path()
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                payload = {}

            def background(fn, *args):
                threading.Thread(target=fn, args=args, daemon=True).start()

            if path.endswith("/api/pull"):
                background(gs.pull)
            elif path.endswith("/api/push"):
                background(gs.push, payload.get("message"))
            elif path.endswith("/api/resolve"):
                background(gs.resolve, payload.get("action", ""))
            elif path.endswith("/api/conflict"):
                background(gs.resolve_conflict, payload.get("strategy", ""))
            elif path.endswith("/api/resume"):
                gs.resume()
            elif path.endswith("/api/connect"):
                background(gs.connect)
            elif path.endswith("/api/genkey"):
                background(gs.generate_key,
                          payload.get("type"), payload.get("comment"))
            elif path.endswith("/api/gitignore"):
                gs.save_gitignore(payload.get("content", ""))
            else:
                self._send(404, json.dumps({"error": "not found"}))
                return
            self._send(200, json.dumps({"ok": True}))

    return Handler


def start_web(gs, port=8099):
    server = ThreadingHTTPServer(("0.0.0.0", int(port)), make_handler(gs))
    log.info("Ingress web UI listening on port %s", port)
    server.serve_forever()
