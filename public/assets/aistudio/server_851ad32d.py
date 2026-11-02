"""SERVER: the only file with sockets, threads and secrets. Wires api + db + ai_call + rounds + replay.
Environment: DATABASE_URL (Postgres), MODEL_API_KEY (Meta), BASETEN_API_KEY, ADMIN_TOKEN, PORT.
Run: python server.py     Needs: numpy, psycopg2-binary (Postgres only)"""
import json, os, threading, uuid, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from config import *
import ai_call, api, db, digest, prompts, replay as replay_mod, rounds, body as body_mod

DSN = os.environ.get("DATABASE_URL", "fighter.db")
JOBS, CACHE, LOCK = {}, {}, threading.Lock()
INFO = body_mod.build_spec(1).motor_info


def _ask(preset, effort, max_tokens):
    p = PROVIDERS[preset]; key = os.environ.get(p["key_env"], "")
    return lambda system, user: ai_call.call(p, system, user, effort, max_tokens, key)


def _job(kind, params, fn):
    jid = uuid.uuid4().hex[:8]; JOBS[jid] = dict(id=jid, kind=kind, status="running", params=params, started=time.time())
    def run():
        try:
            JOBS[jid].update(fn(params), status="done")
        except Exception as e:
            JOBS[jid].update(status="error", error=repr(e))
    threading.Thread(target=run, daemon=True).start()
    return jid


def run_practice(p):
    conn = db.connect(DSN); db.init(conn)
    r = rounds.practice(_ask(p["preset"], p["effort"], PRACTICE_MAX_TOKENS), INFO, db.load_notes(conn, p["ai"]),
                        db.load_library(conn, p["ai"]), p["interval"], p.get("seconds", PRACTICE_SECONDS))
    db.save_library(conn, p["ai"], r["library"])
    n = db.save_run(conn, "practice", dict(r["setup"], ai=p["ai"]), r["orders"], r["frames"], None, dict(p, usage=r["usage"]))
    return dict(run=n, usage=r["usage"])


def run_fight(p):
    conn = db.connect(DSN); db.init(conn)
    ais = ("A", "B")
    asks = [_ask(p["presets"][f], p["efforts"][f], FIGHT_MAX_TOKENS) for f in range(2)]
    r = rounds.fight(asks, INFO, [db.load_notes(conn, a) for a in ais], [db.load_library(conn, a) for a in ais], p["interval"], p.get("seconds", FIGHT_SECONDS))
    n = db.save_run(conn, "fight", r["setup"], r["orders"], r["frames"], r["result"], dict(p, usage=r["usage"]))
    for f, a in enumerate(ais):                       # each AI reads its round and writes a memory note
        db.save_library(conn, a, r["libs"][f])
        ans = _ask(p["presets"][f], NOTE_EFFORT, NOTE_MAX_TOKENS)(prompts.note_system(), prompts.note_user(digest.digest(r["events"], r["orders"], r["result"], f)))
        if not ans["error"] and ans["text"].strip(): db.save_note(conn, a, "fight", n, ans["text"].strip()[:NOTE_MAX_CHARS])
    return dict(run=n, result=r["result"], usage=r["usage"])


def _replay(kind, n):
    key = (kind, n)
    with LOCK:
        if key in CACHE: return CACHE[key]
        run = db.load_run(db.connect(DSN), kind, n)
        if not run: return None
        CACHE[key] = dict(status="computing")
    def work():
        out = replay_mod.replay(run["setup"], run["orders"], run["frames"]); out.pop("final_p"); out.pop("events")
        CACHE[key] = dict(status="ready", result=out["result"], init=out["init"], frames=out["frames"])
    threading.Thread(target=work, daemon=True).start()
    return CACHE[key]


def _memory(ai):
    conn = db.connect(DSN); db.init(conn)
    lib = db.load_library(conn, ai)
    return dict(ai=ai, notes=db.load_notes(conn, ai), moves=sorted(lib["moves"]), chains=lib["chains"])


def _ctx():
    def conn_(): c = db.connect(DSN); db.init(c); return c
    return dict(admin_token=os.environ.get("ADMIN_TOKEN", ""), job=JOBS.get,
                start=lambda kind, p: _job(kind, p, run_practice if kind == "practice" else run_fight),
                runs=lambda k: db.list_runs(conn_(), k), memory=_memory, replay=_replay)


class H(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        for k, v in (("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*"),
                     ("Access-Control-Allow-Headers", "Content-Type, X-Token"), ("Content-Length", str(len(data)))): self.send_header(k, v)
        self.end_headers(); self.wfile.write(data)

    def do_OPTIONS(self): self._send(204, {})

    def _go(self, method):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            code, payload = api.handle(method, self.path, body, self.headers.get("X-Token"), _ctx())
        except Exception as e:
            code, payload = 500, dict(error=repr(e))
        self._send(code, payload)

    def do_GET(self): self._go("GET")
    def do_POST(self): self._go("POST")
    def log_message(self, *a): pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"fighter server on :{port}  db={'postgres' if DSN.startswith('postgres') else DSN}  token set={bool(os.environ.get('ADMIN_TOKEN'))}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
