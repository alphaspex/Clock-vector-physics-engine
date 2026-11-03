"""SERVER: the only file with sockets, threads and secrets. Wires api + db + ai_call + rounds + replay.
Environment: DATABASE_URL (Postgres), MODEL_API_KEY (Meta), BASETEN_API_KEY, ADMIN_TOKEN, PORT.
Run: python server.py     Needs: numpy, psycopg2-binary (Postgres only)"""
import json, os, threading, uuid, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from config import *
import ai_call, api, db, digest, prompts, replay as replay_mod, rounds, body as body_mod
import server_logs

DSN = os.environ.get("DATABASE_URL", "fighter.db")
JOBS, CACHE, LOCK = {}, {}, threading.Lock()
INFO = body_mod.build_spec(1).motor_info


def _conn():
    c = db.connect(DSN); db.init(c); return c


def _get_provider_config(preset, conn=None):
    p = dict(PROVIDERS[preset])
    override = db.get_setting(conn or _conn(), f"model_override_{preset}")
    if override:
        p["model"] = override
        p["overridden"] = True
    return p


def _ask(preset, effort, max_tokens, jid=None):
    p = _get_provider_config(preset); key = os.environ.get(p["key_env"], "")
    def on_event(ev_kind, ev_data):
        c = _conn()
        sev = "error" if "error" in ev_kind else "warn" if "retry" in ev_kind else "info"
        msg = f"AI {preset} ({p['model']}): {ev_kind}"
        # Inject more details into custom log if it's an error or completion
        if ev_kind == "ai_done":
            msg += f" | {ev_data.get('elapsed_ms')}ms | {ev_data.get('usage', {})}"
            server_logs.emit("INFO", "AI_ENGINE", f"Job {jid or 'direct'} - AI completed in {ev_data.get('elapsed_ms')}ms ({p['model']})", **ev_data)
        elif ev_kind == "ai_error":
            msg += f" | ERROR: {ev_data.get('error')}"
            server_logs.emit("ERROR", "AI_ENGINE", f"Job {jid or 'direct'} - AI error ({p['model']}): {ev_data.get('error')}", **ev_data)
        elif ev_kind == "ai_retry":
            server_logs.emit("WARN", "AI_ENGINE", f"Job {jid or 'direct'} - AI retry #{ev_data.get('attempt')}: {ev_data.get('error')}", **ev_data)
        elif ev_kind == "ai_start":
            server_logs.emit("DEBUG", "AI_ENGINE", f"Job {jid or 'direct'} - Dispatched prompt to {p['model']} (max_tokens={ev_data.get('max_tokens')})", **ev_data)
        db.save_event(c, jid or "", sev, ev_kind, msg, ev_data)
    return lambda system, user: ai_call.call(p, system, user, effort, max_tokens, key, on_event=on_event)


def _get_effective_config():
    c = _conn()
    return {k: _get_provider_config(k, c) for k in PROVIDERS}


def _set_model_override(preset, model):
    db.set_setting(_conn(), f"model_override_{preset}", model)


def _check_api(preset):
    p = _get_provider_config(preset); key = os.environ.get(p["key_env"], "")
    # Simple check call
    res = ai_call.call(p, "You are a diagnostic tool.", "Respond with 'OK' and nothing else.", "minimal", 10, key)
    if res.get("error"):
        return dict(ok=False, error=res["error"], model=p["model"])
    return dict(ok=True, text=res["text"], model=p["model"], elapsed_ms=res.get("elapsed_ms"))


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
    server_logs.set_activity(f"Practicing: Fighter {p['ai']}", f"Job {jid} running {p.get('seconds', PRACTICE_SECONDS)}s practice", job_id=jid)
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} started practice simulation for Fighter {p['ai']}", params=p)
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
        stg = ev.get("stage")
        if stg == "decision":
            server_logs.set_activity(f"Practicing: Fighter {p['ai']}", f"Decision #{ev.get('decision')}/{ev.get('target_decisions')} (Frame {ev.get('frame')}/{ev.get('max_frame')})", job_id=jid)
            server_logs.emit("DEBUG", "SIMULATION", f"Job {jid} decision #{ev.get('decision')} at frame {ev.get('frame')} ({ev.get('percent')}%)", **ev)
        elif stg == "physics":
            server_logs.emit("DEBUG", "PHYSICS", f"Job {jid} physics advanced to frame {ev.get('frame')}/{ev.get('max_frame')}", **ev)
        elif stg == "ai_error":
            server_logs.emit("WARN", "AI_ENGINE", f"Job {jid} AI error: {ev.get('error')}", **ev)
            db.save_event(_conn(), jid, "warn", "ai_error", ev.get("error", "AI error"), ev)

    r = rounds.practice(_ask(p["preset"], p["effort"], PRACTICE_MAX_TOKENS, jid=jid), INFO,
                        db.load_notes(conn, p["ai"]), db.load_library(conn, p["ai"]),
                        p["interval"], p.get("seconds", PRACTICE_SECONDS), on_progress=on_progress)

    # Persistence stage
    server_logs.set_activity("Saving practice run", f"Writing practice data to database ({r['frames']} frames)", job_id=jid)
    server_logs.emit("INFO", "DATABASE", f"Job {jid} saving {r['frames']} practice frames to database", usage=r["usage"])
    with LOCK:
        JOBS[jid].update(stage="saving", elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "saving", f"Saving practice results to database", dict(frames=r["frames"]))

    db.save_library(conn, p["ai"], r["library"])
    n = db.save_run(conn, "practice", dict(r["setup"], ai=p["ai"]), r["orders"], r["frames"], None, dict(p, usage=r["usage"]))

    # Replay generation stage
    server_logs.set_activity(f"Preparing Replay: Practice #{n}", f"Computing 3D skeletal frames for #{n}", job_id=jid)
    server_logs.emit("INFO", "CACHE", f"Job {jid} computing 3D skeletal replay for practice #{n}")
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

    server_logs.set_activity("Idle - Awaiting requests", f"Practice #{n} ready ({r['frames']} frames, {elapsed}ms)")
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} completed Practice #{n} successfully in {elapsed}ms", run=n, frames=r["frames"])


def _run_fight(jid, p):
    conn = _conn()
    server_logs.set_activity("Fighting: Fighter A vs Fighter B", f"Job {jid} running {p.get('seconds', FIGHT_SECONDS)}s match", job_id=jid)
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} started fight match Fighter A vs Fighter B", params=p)
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
        stg = ev.get("stage")
        if stg == "decision":
            server_logs.set_activity("Fighting: Fighter A vs Fighter B", f"Decision #{ev.get('decision')}/{ev.get('target_decisions')} (Frame {ev.get('frame')}/{ev.get('max_frame')})", job_id=jid)
            server_logs.emit("DEBUG", "SIMULATION", f"Job {jid} fight decision #{ev.get('decision')} at frame {ev.get('frame')} ({ev.get('percent')}%)", **ev)
        elif stg == "physics":
            res_str = f" [Result: {ev.get('result')}]" if ev.get("result") else ""
            server_logs.emit("DEBUG", "PHYSICS", f"Job {jid} physics frame {ev.get('frame')}/{ev.get('max_frame')}{res_str}", **ev)
        elif stg == "ai_error":
            server_logs.emit("WARN", "AI_ENGINE", f"Job {jid} fighter {ev.get('fighter')} error: {ev.get('error')}", **ev)
            db.save_event(_conn(), jid, "warn", "ai_error", ev.get("error", "AI error"), ev)

    ais = ("A", "B")
    asks = [_ask(p["presets"][f], p["efforts"][f], FIGHT_MAX_TOKENS, jid=jid) for f in range(2)]
    r = rounds.fight(asks, INFO, [db.load_notes(conn, a) for a in ais], [db.load_library(conn, a) for a in ais],
                     p["interval"], p.get("seconds", FIGHT_SECONDS), on_progress=on_progress)

    # Persistence stage
    server_logs.set_activity("Saving fight result", f"Result: {r['result'] or 'draw'}, {r['frames']} frames", job_id=jid)
    server_logs.emit("INFO", "DATABASE", f"Job {jid} saving fight result: {r['result'] or 'draw'}", frames=r["frames"])
    with LOCK:
        JOBS[jid].update(stage="saving", elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "saving", f"Saving fight result ({r['result'] or 'draw'}) to database", dict(frames=r["frames"]))

    n = db.save_run(conn, "fight", r["setup"], r["orders"], r["frames"], r["result"], dict(p, usage=r["usage"]))

    # Memory reflections
    server_logs.set_activity(f"Formulating AI Memories for Fight #{n}", f"Generating tactical lessons", job_id=jid)
    for f, a in enumerate(ais):
        db.save_library(conn, a, r["libs"][f])
        ans = _ask(p["presets"][f], NOTE_EFFORT, NOTE_MAX_TOKENS, jid=jid)(
            prompts.note_system(), prompts.note_user(digest.digest(r["events"], r["orders"], r["result"], f)))
        if not ans.get("error") and ans.get("text", "").strip():
            db.save_note(conn, a, "fight", n, ans["text"].strip()[:NOTE_MAX_CHARS])
            db.save_event(conn, jid, "info", "memory", f"Fighter {a} stored post-fight memory note for round #{n}")
            server_logs.emit("INFO", "AI_ENGINE", f"Job {jid} - Fighter {a} saved post-fight memory note", note_preview=ans["text"][:100])

    # Replay preparation stage
    server_logs.set_activity(f"Preparing Replay: Fight #{n}", f"Computing 3D skeletal frames for #{n}", job_id=jid)
    server_logs.emit("INFO", "CACHE", f"Job {jid} computing 3D skeletal replay for fight #{n}")
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

    server_logs.set_activity("Idle - Awaiting requests", f"Fight #{n} ready (Winner: {r['result'] or 'draw'}, {elapsed}ms)")
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} completed Fight #{n} successfully. Winner: {r['result'] or 'draw'} ({elapsed}ms)", run=n, result=r["result"])


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
        get_effective_config=_get_effective_config,
        set_model_override=_set_model_override,
        check_api=_check_api,
        get_logs=server_logs.get_logs,
        clear_logs=server_logs.clear_logs,
        server_status=server_logs.get_summary,
        emit_log=server_logs.emit,
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
        t0 = time.time()
        client_ip = self.client_address[0] if self.client_address else "unknown"
        # Avoid noisy self-logging when the client is continuously polling /logs
        is_log_polling = "/logs" in self.path
        if not is_log_polling:
            server_logs.emit("DEBUG", "HTTP", f"{method} {self.path} incoming from {client_ip}")

        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            code, payload = api.handle(method, self.path, body, self.headers.get("X-Token"), _ctx())
        except Exception as e:
            code, payload = 500, dict(error=repr(e))
            server_logs.emit("ERROR", "HTTP", f"Exception processing {method} {self.path}: {repr(e)}", error=str(e), client=client_ip)

        elapsed_ms = int((time.time() - t0) * 1000)
        if not is_log_polling:
            lvl = "INFO" if code < 400 else ("WARN" if code < 500 else "ERROR")
            server_logs.emit(lvl, "HTTP", f"{method} {self.path} -> {code} ({elapsed_ms}ms)", code=code, duration_ms=elapsed_ms, client=client_ip)

        self._send(code, payload)

    def do_GET(self): self._go("GET")
    def do_POST(self): self._go("POST")
    def do_DELETE(self): self._go("DELETE")
    def log_message(self, *a): pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server_logs.emit("INFO", "SYSTEM", f"Fighter server listening on port {port}", dsn=DSN, db_type="postgres" if DSN.startswith("postgres") else "sqlite", token_configured=bool(os.environ.get("ADMIN_TOKEN")))
    print(f"fighter server on :{port}  db={'postgres' if DSN.startswith('postgres') else DSN}  token set={bool(os.environ.get('ADMIN_TOKEN'))}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


