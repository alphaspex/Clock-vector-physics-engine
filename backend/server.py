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
    c = db.connect(DSN); db.init(c); db.one_time_migration(c); return c


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


COMPILE_JOBS = {}


def _compile_replay(kind, n):
    key = (kind, n)
    with LOCK:
        if key in COMPILE_JOBS:
            return dict(ok=True, status=COMPILE_JOBS[key]["status"], progress=COMPILE_JOBS[key])

    conn = _conn()
    st = db.get_replay_status(conn, kind, n)
    if st and st.get("status") == "ready":
        return dict(ok=True, status="ready", progress=st.get("progress", {}))

    run = db.load_run(conn, kind, n)
    if not run:
        return None

    t0 = time.time()
    prog = dict(
        stage="queued",
        frames_generated=0,
        expected_frames=run["frames"],
        percent=0.0,
        started_at=t0,
        elapsed_ms=0,
        error=None,
    )
    with LOCK:
        COMPILE_JOBS[key] = dict(status="queued", **prog)
    db.save_replay_status(conn, kind, n, "queued", progress=prog)
    server_logs.emit("INFO", "CACHE", f"Queued background replay compilation for {kind} #{n}")

    def work():
        try:
            with LOCK:
                if key in COMPILE_JOBS:
                    COMPILE_JOBS[key].update(status="compiling", stage="compiling")
            db.save_replay_status(_conn(), kind, n, "compiling", progress=dict(stage="compiling", frames_generated=0, expected_frames=run["frames"], percent=0.0, started_at=t0, elapsed_ms=int((time.time()-t0)*1000)))
            server_logs.emit("INFO", "SIMULATION", f"Started 30 FPS replay compilation for {kind} #{n}")

            def on_progress(cur, total):
                el = int((time.time() - t0) * 1000)
                pct = round((cur / max(1, total)) * 100, 1)
                p = dict(stage="compiling", frames_generated=cur, expected_frames=total, percent=pct, started_at=t0, elapsed_ms=el)
                with LOCK:
                    if key in COMPILE_JOBS:
                        COMPILE_JOBS[key].update(p)
                db.save_replay_status(_conn(), kind, n, "compiling", progress=p)

            out = replay_mod.replay(run["setup"], run["orders"], run["frames"], on_progress=on_progress)

            el = int((time.time() - t0) * 1000)
            p_val = dict(stage="validating", frames_generated=len(out.get("frames", [])), expected_frames=run["frames"], percent=100.0, started_at=t0, elapsed_ms=el)
            with LOCK:
                if key in COMPILE_JOBS:
                    COMPILE_JOBS[key].update(status="validating", **p_val)
            db.save_replay_status(_conn(), kind, n, "validating", progress=p_val)

            if not out.get("frames") or len(out["frames"]) == 0:
                raise ValueError("Replay generated 0 frames")
            if "init" not in out or "shapes" not in out["init"]:
                raise ValueError("Replay initialization metadata invalid")

            saved_data = dict(result=out.get("result"), init=out.get("init"), frames=out.get("frames"))
            p_ready = dict(stage="ready", frames_generated=len(out["frames"]), expected_frames=run["frames"], percent=100.0, started_at=t0, elapsed_ms=el)

            with LOCK:
                CACHE[key] = dict(status="ready", result=out["result"], init=out["init"], frames=out["frames"])
                COMPILE_JOBS.pop(key, None)

            db.save_replay_status(_conn(), kind, n, "ready", progress=p_ready, data=saved_data)
            server_logs.emit("INFO", "CACHE", f"Replay compilation completed for {kind} #{n} ({len(out['frames'])} frames, {el}ms)")

        except Exception as e:
            el = int((time.time() - t0) * 1000)
            err_msg = repr(e)
            p_fail = dict(stage="failed", error=err_msg, started_at=t0, elapsed_ms=el)
            with LOCK:
                COMPILE_JOBS.pop(key, None)
            db.save_replay_status(_conn(), kind, n, "failed", progress=p_fail)
            server_logs.emit("ERROR", "SIMULATION", f"Replay compilation failed for {kind} #{n}: {err_msg}")

    threading.Thread(target=work, daemon=True).start()
    return dict(ok=True, status="queued", progress=prog)


def _replay(kind, n):
    key = (kind, n)
    with LOCK:
        if key in CACHE and CACHE[key].get("status") == "ready":
            return CACHE[key]
    return db.get_compiled_replay(_conn(), kind, n)


def _replay_status(kind, n):
    key = (kind, n)
    with LOCK:
        if key in COMPILE_JOBS:
            j = COMPILE_JOBS[key]
            return dict(status=j.get("status", "compiling"), run=n, progress=j, error=j.get("error"))
    conn = _conn()
    st = db.get_replay_status(conn, kind, n)
    if not st:
        return None
    if st["status"] in ("queued", "compiling", "validating"):
        err_p = dict(stage="failed", error="Compilation interrupted by server restart. Please retry.")
        db.save_replay_status(conn, kind, n, "failed", progress=err_p)
        return dict(status="failed", run=n, progress=err_p, error=err_p["error"])
    return dict(status=st["status"], run=n, progress=st.get("progress", {}), error=st.get("progress", {}).get("error"))


def _run_practice(jid, p):
    conn = _conn()
    server_logs.set_activity(f"Practicing: Fighter {p['ai']}", f"Job {jid} running {p.get('seconds', PRACTICE_SECONDS)}s practice", job_id=jid)
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} started practice simulation for Fighter {p['ai']}", params=p)
    with LOCK:
        JOBS[jid].update(stage="simulation", thinking_history=[])
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
                
                if ev.get("stage") == "decision":
                    t_item = dict(
                        fighter=ev.get("fighter", "A"), 
                        text=ev.get("text", "Selecting a predefined action..."),
                        action=ev.get("action"),
                        valid=ev.get("valid"),
                        error=ev.get("error"),
                        pre_tree=ev.get("pre_tree"),
                        frame=ev.get("frame", 0),
                        decision=ev.get("decision", 0),
                        attempts=ev.get("attempts", 1)
                    )
                    JOBS[jid]["latest_thinking"] = t_item
                    JOBS[jid].setdefault("thinking_history", []).append(t_item)
                elif ev.get("stage") == "interval_complete":
                    # Update the last thinking item with post_tree
                    if JOBS[jid].get("thinking_history"):
                        JOBS[jid]["thinking_history"][-1]["post_tree"] = ev.get("post_tree")

        stg = ev.get("stage")
        if stg == "decision":
            server_logs.set_activity(f"Practicing: Fighter {p['ai']}", f"Decision #{ev.get('decision')}/{ev.get('target_decisions')} (Frame {ev.get('frame')}/{ev.get('max_frame')})", job_id=jid)
            server_logs.emit("DEBUG", "SIMULATION", f"Job {jid} decision #{ev.get('decision')} at frame {ev.get('frame')} ({ev.get('percent')}%)", **ev)
        elif stg == "ai_error":
            server_logs.emit("WARN", "AI_ENGINE", f"Job {jid} AI error: {ev.get('error')}", **ev)
            db.save_event(_conn(), jid, "warn", "ai_error", ev.get("error", "AI error"), ev)

    r = rounds.practice(_ask(p["preset"], p["effort"], PRACTICE_MAX_TOKENS, jid=jid), INFO,
                        db.load_round_summaries(conn, p["ai"], "practice", limit=3), {},
                        p["interval"], p.get("seconds", PRACTICE_SECONDS), on_progress=on_progress, 
                        task_text=p.get("task_text", "Stand and keep standing"), job_id=jid)

    # Persistence stage
    server_logs.set_activity("Saving practice run", f"Writing practice data to database ({r['frames']} frames)", job_id=jid)
    server_logs.emit("INFO", "DATABASE", f"Job {jid} saving {r['frames']} practice frames to database", usage=r["usage"])
    with LOCK:
        JOBS[jid].update(stage="saving", elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "saving", f"Saving practice results to database", dict(frames=r["frames"]))

    n = db.save_run(conn, "practice", dict(r["setup"], ai=p["ai"]), r["orders"], r["frames"], None, dict(p, usage=r["usage"]))
    db.save_replay_status(conn, "practice", n, "not_compiled", progress=dict(stage="not_compiled", expected_frames=r["frames"]))

    with LOCK:
        elapsed = int((time.time() - JOBS[jid]["started"]) * 1000)
        JOBS[jid].update(
            status="done", stage="completed", run=n, usage=r["usage"], elapsed_ms=elapsed, replay_status="not_compiled",
        )
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "completed", f"Practice #{n} simulation completed (replay not compiled)", dict(run=n, frames=r["frames"]))

    server_logs.set_activity("Idle - Awaiting requests", f"Practice #{n} completed ({r['frames']} frames, replay not compiled)")
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} completed Practice #{n} simulation in {elapsed}ms", run=n, frames=r["frames"])


def _run_fight(jid, p):
    conn = _conn()
    server_logs.set_activity("Fighting: Fighter A vs Fighter B", f"Job {jid} running {p.get('seconds', FIGHT_SECONDS)}s match", job_id=jid)
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} started fight match Fighter A vs Fighter B", params=p)
    with LOCK:
        JOBS[jid].update(stage="simulation", thinking_history=[])
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
                
                if ev.get("stage") == "decision":
                    f_letter = ev.get("fighter", "A")
                    t_item = dict(
                        fighter=f_letter,
                        text=ev.get("text", "Selecting a predefined action..."),
                        action=ev.get("action"),
                        valid=ev.get("valid"),
                        error=ev.get("error"),
                        pre_tree=ev.get("pre_tree"),
                        frame=ev.get("frame", 0),
                        decision=ev.get("decision", 0),
                        attempts=ev.get("attempts", 1)
                    )
                    if f_letter == "A":
                        JOBS[jid]["latest_thinking_A"] = t_item
                    else:
                        JOBS[jid]["latest_thinking_B"] = t_item
                    JOBS[jid].setdefault("thinking_history", []).append(t_item)
                elif ev.get("stage") == "interval_complete":
                    # Update the last thinking item for this fighter with post_tree
                    f_letter = ev.get("fighter", "A")
                    for item in reversed(JOBS[jid].get("thinking_history", [])):
                        if item.get("fighter") == f_letter and item.get("decision") == ev.get("decision"):
                            item["post_tree"] = ev.get("post_tree")
                            break

        stg = ev.get("stage")
        if stg == "ai_error":
            server_logs.emit("WARN", "AI_ENGINE", f"Job {jid} fighter {ev.get('fighter')} error: {ev.get('error')}", **ev)
            db.save_event(_conn(), jid, "warn", "ai_error", ev.get("error", "AI error"), ev)

    ais = ("A", "B")
    asks = [_ask(p["presets"][f], p["efforts"][f], FIGHT_MAX_TOKENS, jid=jid) for f in range(2)]
    summaries_per_fighter = [db.load_round_summaries(conn, a, "fight", limit=100) for a in ais]
    r = rounds.fight(asks, INFO, summaries_per_fighter, [{}, {}],
                     p["interval"], p.get("seconds", FIGHT_SECONDS), on_progress=on_progress, job_id=jid)

    # Persistence stage
    server_logs.set_activity("Saving fight result", f"Result: {r['result'] or 'draw'}, {r['frames']} frames", job_id=jid)
    server_logs.emit("INFO", "DATABASE", f"Job {jid} saving fight result: {r['result'] or 'draw'}", frames=r["frames"])
    with LOCK:
        JOBS[jid].update(stage="saving", elapsed_ms=int((time.time() - JOBS[jid]["started"]) * 1000))
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "saving", f"Saving fight result ({r['result'] or 'draw'}) to database", dict(frames=r["frames"]))

    n = db.save_run(conn, "fight", r["setup"], r["orders"], r["frames"], r["result"], dict(p, usage=r["usage"]))
    db.save_replay_status(conn, "fight", n, "not_compiled", progress=dict(stage="not_compiled", expected_frames=r["frames"]))

    # Save fight round summaries (one per fighter)
    round_sums = r.get("round_summaries", ["", ""])
    for f, a in enumerate(ais):
        if f < len(round_sums) and round_sums[f]:
            db.save_round_summary(conn, a, "fight", n, round_sums[f])
            db.save_event(conn, jid, "info", "round_summary", f"Fighter {a} stored fight round summary for #{n}")
            server_logs.emit("INFO", "AI_ENGINE", f"Job {jid} - Fighter {a} saved fight round summary", summary_preview=round_sums[f][:100])

    with LOCK:
        elapsed = int((time.time() - JOBS[jid]["started"]) * 1000)
        JOBS[jid].update(
            status="done", stage="completed", run=n, result=r["result"], usage=r["usage"], elapsed_ms=elapsed, replay_status="not_compiled",
            round_summaries=round_sums,
        )
        db.save_or_update_job(conn, JOBS[jid])
        db.save_event(conn, jid, "info", "completed", f"Fight #{n} simulation completed (replay not compiled)", dict(run=n, result=r["result"], frames=r["frames"]))

    server_logs.set_activity("Idle - Awaiting requests", f"Fight #{n} completed (Winner: {r['result'] or 'draw'}, {elapsed}ms)")
    server_logs.emit("INFO", "SIMULATION", f"Job {jid} completed Fight #{n} simulation. Winner: {r['result'] or 'draw'} ({elapsed}ms)", run=n, result=r["result"])


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


def _db_purge_all():
    with LOCK:
        active = [jid for jid, j in JOBS.items() if j.get("status") == "running"]
        CACHE.clear()
    return db.purge_all_database_data(_conn(), active_jobs=active)


def _memory(ai):
    conn = _conn()
    return dict(
        ai=ai,
        practice_summaries=db.load_round_summaries(conn, ai, "practice", limit=10),
        fight_summaries=db.load_round_summaries(conn, ai, "fight", limit=10),
        task_memory=db.get_latest_intervals(conn, ai, "practice", limit=20),
        fight_memory=db.get_latest_intervals(conn, ai, "fight", limit=20),
    )


def _ctx():
    return dict(
        admin_token=os.environ.get("ADMIN_TOKEN", ""),
        start=_start_job,
        job=_get_job,
        runs=lambda k: db.list_runs(_conn(), k),
        memory=_memory,
        replay=_replay,
        replay_status=_replay_status,
        compile_replay=_compile_replay,
        list_jobs=_list_jobs,
        list_events=_list_events,
        db_catalog=lambda: db.get_catalog(_conn()),
        db_list=lambda r, lim, off: db.list_resource(_conn(), r, lim, off),
        db_get=lambda r, iid: db.get_resource_item(_conn(), r, iid),
        db_delete=_db_delete,
        db_delete_batch=_db_delete_batch,
        db_purge_all=_db_purge_all,
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
