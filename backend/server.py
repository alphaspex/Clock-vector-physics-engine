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


def _conn():
    c = db.connect(DSN); db.init(c); return c


def _ask(preset, effort, max_tokens, jid=None):
    p = PROVIDERS[preset]; key = os.environ.get(p["key_env"], "")
    def on_event(ev_kind, ev_data):
        if jid:
            c = _conn()
            sev = "error" if "error" in ev_kind else "warn" if "retry" in ev_kind else "info"
            db.save_event(c, jid, sev, ev_kind, f"AI {preset} ({p['model']}): {ev_kind}", ev_data)
    return lambda system, user: ai_call.call(p, system, user, effort, max_tokens, key, on_event=on_event)


def _compute_replay(kind, n, setup, orders, frames):
    key = (kind, n)
    with LOCK:
        if key in CACHE and CACHE[key].get("status") == "ready":
            return CACHE[key]
        CACHE[key] = dict(status="computing")
    try:
        out = replay_mod.replay(setup, orders, frames)
        out.pop("final_p", None); out.pop("events", None)
        with LOCK:
            CACHE[key] = dict(status="ready", result=out["result"], init=out["init"], frames=out["frames"])
        return CACHE[key]
    except Exception as e:
        with LOCK:
            CACHE[key] = dict(status="error", error=repr(e))
        return CACHE[key]


def _replay(kind, n):
    key = (kind, n)
    with LOCK:
        if key in CACHE:
            return CACHE[key]
    run = db.load_run(_conn(), kind, n)
    if not run:
        return None
    with LOCK:
        CACHE[key] = dict(status="computing")
    def work():
        _compute_replay(kind, n, run["setup"], run["orders"], run["frames"])
    threading.Thread(target=work, daemon=True).start()
    return CACHE[key]


def _replay_status(kind, n):
    key = (kind, n)
    with LOCK:
        if key in CACHE:
            return dict(status=CACHE[key].get("status", "computing"), run=n, error=CACHE[key].get("error"))
    run = db.load_run(_conn(), kind, n)
    if not run:
        return None
    # Trigger computation in background if not already cached
    _replay(kind, n)
    return dict(status="computing", run=n)


def _run_practice(jid, p):
    conn = _conn()
    with LOCK:
        JOBS[jid].update(stage="simulation")
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "simulation", f"Beginning practice simulation for Fighter {p['ai']}", dict(p=p))

    def on_progress(ev):
        with LOCK:
            if jid in JOBS:
                JOBS[jid]["stage"] = ev.get("stage", JOBS[jid].get("stage"))
                JOBS[jid]["elapsed_ms"] = int((time.time() - JOBS[jid]["started"]) * 1000)
                if "percent" in ev: JOBS[jid]["percent"] = ev["percent"]
                if "decision" in ev: JOBS[jid]["decision"] = ev["decision"]
                if "target_decisions" in ev: JOBS[jid]["target_decisions"] = ev["target_decisions"]
                if "frame" in ev: JOBS[jid]["frame"] = ev["frame"]
                if "max_frame" in ev: JOBS[jid]["max_frame"] = ev["max_frame"]
        if ev.get("stage") == "ai_error":
            db.save_event(_conn(), jid, "warn", "ai_error", ev.get("error", "AI error"), ev)

    r = rounds.practice(_ask(p["preset"], p["effort"], PRACTICE_MAX_TOKENS, jid=jid), INFO,
                        db.load_notes(conn, p["ai"]), db.load_library(conn, p["ai"]),
                        p["interval"], p.get("seconds", PRACTICE_SECONDS), on_progress=on_progress)

    # Persistence stage
    with LOCK:
        JOBS[jid].update(stage="saving", elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "saving", f"Saving practice results to database", dict(frames=r["frames"]))

    db.save_library(conn, p["ai"], r["library"])
    n = db.save_run(conn, "practice", dict(r["setup"], ai=p["ai"]), r["orders"], r["frames"], None, dict(p, usage=r["usage"]))

    # Replay generation stage
    with LOCK:
        JOBS[jid].update(stage="preparing_replay", run=n, elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "preparing_replay", f"Preparing replay for practice #{n}", dict(run=n))

    _compute_replay("practice", n, dict(r["setup"], ai=p["ai"]), r["orders"], r["frames"])

    with LOCK:
        elapsed = int((time.time() - JOBS[jid]["started"]) * 1000)
        JOBS[jid].update(status="done", stage="ready", run=n, usage=r["usage"], elapsed_ms=elapsed)
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "ready", f"Practice #{n} is ready for replay playback", dict(run=n, frames=r["frames"]))


def _run_fight(jid, p):
    conn = _conn()
    with LOCK:
        JOBS[jid].update(stage="simulation")
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "simulation", f"Beginning fight simulation: Fighter A vs Fighter B", dict(p=p))

    def on_progress(ev):
        with LOCK:
            if jid in JOBS:
                JOBS[jid]["stage"] = ev.get("stage", JOBS[jid].get("stage"))
                JOBS[jid]["elapsed_ms"] = int((time.time() - JOBS[jid]["started"]) * 1000)
                if "percent" in ev: JOBS[jid]["percent"] = ev["percent"]
                if "decision" in ev: JOBS[jid]["decision"] = ev["decision"]
                if "target_decisions" in ev: JOBS[jid]["target_decisions"] = ev["target_decisions"]
                if "frame" in ev: JOBS[jid]["frame"] = ev["frame"]
                if "max_frame" in ev: JOBS[jid]["max_frame"] = ev["max_frame"]
        if ev.get("stage") == "ai_error":
            db.save_event(_conn(), jid, "warn", "ai_error", ev.get("error", "AI error"), ev)

    ais = ("A", "B")
    asks = [_ask(p["presets"][f], p["efforts"][f], FIGHT_MAX_TOKENS, jid=jid) for f in range(2)]
    r = rounds.fight(asks, INFO, [db.load_notes(conn, a) for a in ais], [db.load_library(conn, a) for a in ais],
                     p["interval"], p.get("seconds", FIGHT_SECONDS), on_progress=on_progress)

    # Persistence stage
    with LOCK:
        JOBS[jid].update(stage="saving", elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "saving", f"Saving fight result ({r['result'] or 'draw'}) to database", dict(frames=r["frames"]))

    n = db.save_run(conn, "fight", r["setup"], r["orders"], r["frames"], r["result"], dict(p, usage=r["usage"]))

    # Memory reflections
    for f, a in enumerate(ais):
        db.save_library(conn, a, r["libs"][f])
        ans = _ask(p["presets"][f], NOTE_EFFORT, NOTE_MAX_TOKENS, jid=jid)(
            prompts.note_system(), prompts.note_user(digest.digest(r["events"], r["orders"], r["result"], f)))
        if not ans.get("error") and ans.get("text", "").strip():
            db.save_note(conn, a, "fight", n, ans["text"].strip()[:NOTE_MAX_CHARS])
            db.save_event(conn, jid, "info", "memory", f"Fighter {a} stored post-fight memory note for round #{n}")

    # Replay preparation stage
    with LOCK:
        JOBS[jid].update(stage="preparing_replay", run=n, result=r["result"], elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "preparing_replay", f"Preparing replay for fight #{n}", dict(run=n))

    _compute_replay("fight", n, r["setup"], r["orders"], r["frames"])

    with LOCK:
        elapsed = int((time.time() - JOBS[jid]["started"]) * 1000)
        JOBS[jid].update(status="done", stage="ready", run=n, result=r["result"], usage=r["usage"], elapsed_ms=elapsed)
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "ready", f"Fight #{n} is ready for replay playback", dict(run=n, result=r["result"], frames=r["frames"]))


def run_practice(p):
    jid = "direct_" + uuid.uuid4().hex[:6]
    with LOCK:
        JOBS[jid] = dict(id=jid, kind="practice", status="running", stage="starting", params=p, started=time.time(), elapsed_ms=0)
    _run_practice(jid, p)
    return dict(run=JOBS[jid].get("run", 1), usage=JOBS[jid].get("usage", {}))


def run_fight(p):
    jid = "direct_" + uuid.uuid4().hex[:6]
    with LOCK:
        JOBS[jid] = dict(id=jid, kind="fight", status="running", stage="starting", params=p, started=time.time(), elapsed_ms=0)
    _run_fight(jid, p)
    return dict(run=JOBS[jid].get("run", 1), result=JOBS[jid].get("result"), usage=JOBS[jid].get("usage", {}))



def _start_job(kind, params):
    jid = uuid.uuid4().hex[:8]
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    with LOCK:
        JOBS[jid] = dict(id=jid, kind=kind, status="running", stage="queued", params=params,
                         started=time.time(), elapsed_ms=0, created=now_str)
        c = _conn()
        db.save_or_update_job(c, JOBS[jid])
        db.save_event(c, jid, "info", "queue", f"Queued {kind} simulation job {jid}", dict(params=params))

    def run():
        try:
            if kind == "practice":
                _run_practice(jid, params)
            else:
                _run_fight(jid, params)
        except Exception as e:
            with LOCK:
                elapsed = int((time.time() - JOBS[jid]["started"]) * 1000)
                JOBS[jid].update(status="error", stage="failed", elapsed_ms=elapsed, error=repr(e))
                c = _conn()
                db.save_or_update_job(c, JOBS[jid])
                db.save_event(c, jid, "error", "failed", f"Simulation job {jid} failed: {repr(e)}")

    threading.Thread(target=run, daemon=True).start()
    return jid


def _get_job(jid):
    with LOCK:
        if jid in JOBS:
            j = dict(JOBS[jid])
            if j.get("status") == "running" and j.get("started"):
                j["elapsed_ms"] = int((time.time() - j["started"]) * 1000)
            return j
    return db.get_job(_conn(), jid)


def _list_jobs(limit=50):
    db_jobs = db.list_jobs(_conn(), limit=limit)
    with LOCK:
        active = {jid: dict(j) for jid, j in JOBS.items()}
    # Merge active in-memory with DB records
    merged = {}
    for j in db_jobs:
        merged[j["id"]] = j
    for jid, j in active.items():
        if j.get("status") == "running" and j.get("started"):
            j["elapsed_ms"] = int((time.time() - j["started"]) * 1000)
        merged[jid] = j
    items = sorted(merged.values(), key=lambda x: x.get("started", 0.0), reverse=True)
    return items[:limit]


def _list_events(limit=100, since_id=None):
    return db.list_events(_conn(), limit=limit, since_id=since_id)


def _db_delete(resource, item_id):
    with LOCK:
        active = [jid for jid, j in JOBS.items() if j.get("status") == "running"]
    res = db.delete_resource_item(_conn(), resource, item_id, active_jobs=active)
    if res.get("ok"):
        if resource == "runs_fight":
            with LOCK: CACHE.pop(("fight", int(item_id)), None)
        elif resource == "runs_practice":
            with LOCK: CACHE.pop(("practice", int(item_id)), None)
    return res


def _db_delete_batch(resource, item_ids):
    with LOCK:
        active = [jid for jid, j in JOBS.items() if j.get("status") == "running"]
    res = db.delete_resource_batch(_conn(), resource, item_ids, active_jobs=active)
    if res.get("ok"):
        for iid in item_ids:
            if resource == "runs_fight":
                with LOCK: CACHE.pop(("fight", int(iid)), None)
            elif resource == "runs_practice":
                with LOCK: CACHE.pop(("practice", int(iid)), None)
    return res


def _memory(ai):
    conn = _conn()
    lib = db.load_library(conn, ai)
    return dict(ai=ai, notes=db.load_notes(conn, ai), moves=sorted(lib.get("moves", {}).keys()), chains=lib.get("chains", {}))


def _ctx():
    return dict(
        admin_token=os.environ.get("ADMIN_TOKEN", ""),
        start=_start_job,
        job=_get_job,
        runs=lambda k: db.list_runs(_conn(), k),
        memory=_memory,
        replay=_replay,
        replay_status=_replay_status,
        list_jobs=_list_jobs,
        list_events=_list_events,
        db_catalog=lambda: db.get_catalog(_conn()),
        db_list=lambda r, lim, off: db.list_resource(_conn(), r, lim, off),
        db_get=lambda r, iid: db.get_resource_item(_conn(), r, iid),
        db_delete=_db_delete,
        db_delete_batch=_db_delete_batch,
        db_reset_memory=lambda target: db.reset_memory(_conn(), target),
    )


class H(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        for k, v in (
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, X-Token"),
            ("Content-Length", str(len(data))),
        ):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in (
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, X-Token"),
            ("Access-Control-Max-Age", "600"),
        ):
            self.send_header(k, v)
        self.end_headers()

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
    def do_DELETE(self): self._go("DELETE")
    def log_message(self, *a): pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"fighter server on :{port}  db={'postgres' if DSN.startswith('postgres') else DSN}  token set={bool(os.environ.get('ADMIN_TOKEN'))}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()

