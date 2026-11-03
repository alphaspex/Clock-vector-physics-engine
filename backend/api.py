"""API: the web routes as one pure function. No sockets, no threads, no database in here.
handle(method, path, body, token, ctx) -> (status, payload)
ctx = the outside world as functions:
  ctx['admin_token']
  ctx['start'](kind, params)->job_id
  ctx['job'](id)
  ctx['runs'](kind)
  ctx['memory'](ai)
  ctx['replay'](kind, n)
  ctx['replay_status'](kind, n)
  ctx['list_jobs'](limit)
  ctx['list_events'](limit, since_id)
  ctx['db_catalog']()
  ctx['db_list'](resource, limit, offset)
  ctx['db_get'](resource, id)
  ctx['db_delete'](resource, id)
  ctx['db_delete_batch'](resource, ids)
  ctx['db_reset_memory'](target)
"""
from config import (
    PROVIDERS, EFFORTS, PRACTICE_EFFORT, FIGHT_EFFORT,
    MIN_DURATION_MINUTES, MAX_DURATION_MINUTES,
    DEFAULT_PRACTICE_MINUTES, DEFAULT_FIGHT_MINUTES,
)


def _interval(b):
    v = b.get("interval", 3)
    return int(v) if isinstance(v, (int, float)) and 1 <= v <= 10 else None


def _duration(b, default_minutes):
    raw = b.get("duration_minutes", b.get("duration"))
    if raw is None:
        return default_minutes, round(default_minutes * 60.0, 2)
    try:
        val = float(raw)
        if MIN_DURATION_MINUTES <= val <= MAX_DURATION_MINUTES:
            return round(val, 2), round(val * 60.0, 2)
    except (ValueError, TypeError):
        pass
    return None, None


def _parse_query(path):
    if "?" not in path:
        return {}
    q = {}
    for part in path.split("?")[1].split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            q[k] = v
    return q


def handle(method, path, body, token, ctx):
    body = body or {}
    query = _parse_query(path)
    clean_path = path.split("?")[0]
    parts = [p for p in clean_path.split("/") if p]

    # --- Public Read Routes ---
    if method == "GET":
        if parts == ["health"]:
            return 200, dict(ok=True)
        if len(parts) == 2 and parts[0] == "jobs":
            j = ctx["job"](parts[1])
            return (200, j) if j else (404, dict(error="no such job"))
        if len(parts) == 2 and parts[0] == "runs" and parts[1] in ("practice", "fight"):
            return 200, dict(runs=ctx["runs"](parts[1]))
        if len(parts) == 2 and parts[0] == "memory" and parts[1] in ("A", "B"):
            return 200, ctx["memory"](parts[1])
        if len(parts) == 3 and parts[0] == "replay" and parts[1] in ("practice", "fight") and parts[2].isdigit():
            r = ctx["replay"](parts[1], int(parts[2]))
            return (200, r) if r else (404, dict(error="no such round"))
        if len(parts) == 4 and parts[0] == "replay" and parts[1] in ("practice", "fight") and parts[2].isdigit() and parts[3] == "status":
            st = ctx["replay_status"](parts[1], int(parts[2]))
            return (200, st) if st else (404, dict(error="no such round"))

    # --- Admin Authentication Barrier for all remaining routes ---
    is_admin_req = parts and parts[0] == "admin"
    is_run_start = method == "POST" and parts in (["practice"], ["fight"])

    if is_admin_req or is_run_start:
        if not ctx.get("admin_token") or token != ctx["admin_token"]:
            return 401, dict(error="bad or missing X-Token")

    # --- Admin Monitoring & Jobs ---
    if method == "GET" and is_admin_req:
        if parts == ["admin", "jobs"]:
            limit = int(query.get("limit", 50))
            return 200, dict(jobs=ctx["list_jobs"](limit))
        if parts == ["admin", "events"]:
            limit = int(query.get("limit", 100))
            since_id = int(query["since_id"]) if "since_id" in query and query["since_id"].isdigit() else None
            return 200, dict(events=ctx["list_events"](limit, since_id))
        if parts == ["admin", "db", "catalog"]:
            return 200, dict(catalog=ctx["db_catalog"]())
        if len(parts) == 3 and parts[:2] == ["admin", "db"]:
            res_key = parts[2]
            limit = int(query.get("limit", 50))
            offset = int(query.get("offset", 0))
            data = ctx["db_list"](res_key, limit, offset)
            return (200, data) if data is not None else (404, dict(error=f"unknown resource {res_key}"))
        if len(parts) == 4 and parts[:2] == ["admin", "db"]:
            res_key, item_id = parts[2], parts[3]
            item = ctx["db_get"](res_key, item_id)
            return (200, dict(item=item)) if item is not None else (404, dict(error=f"item not found in {res_key}"))

    # --- Admin Database Modifications ---
    if method == "DELETE" and is_admin_req:
        if len(parts) == 4 and parts[:2] == ["admin", "db"]:
            res_key, item_id = parts[2], parts[3]
            del_res = ctx["db_delete"](res_key, item_id)
            status = 200 if del_res.get("ok") else 400
            return status, del_res

    if method == "POST" and is_admin_req:
        if len(parts) == 4 and parts[:2] == ["admin", "db"] and parts[3] == "delete-batch":
            res_key = parts[2]
            ids = body.get("ids", [])
            del_res = ctx["db_delete_batch"](res_key, ids)
            status = 200 if del_res.get("ok") else 400
            return status, del_res
        if parts == ["admin", "db", "reset-memory"]:
            target = body.get("target", "all")
            rst_res = ctx["db_reset_memory"](target)
            status = 200 if rst_res.get("ok") else 400
            return status, rst_res

    # --- Simulation Launch Routes ---
    if method == "POST" and parts in (["practice"], ["fight"]):
        iv = _interval(body)
        if iv is None:
            return 400, dict(error="interval must be 1..10 seconds")

        if parts == ["practice"]:
            p, e = body.get("preset", "meta_contrib"), body.get("effort", PRACTICE_EFFORT)
            if body.get("ai") not in ("A", "B"):
                return 400, dict(error="ai must be A or B")
            if p not in PROVIDERS or e not in EFFORTS:
                return 400, dict(error=f"preset in {list(PROVIDERS)}, effort in {list(EFFORTS)}")
            dm, secs = _duration(body, DEFAULT_PRACTICE_MINUTES)
            if dm is None:
                return 400, dict(error=f"duration_minutes must be between {MIN_DURATION_MINUTES} and {MAX_DURATION_MINUTES} minutes")
            jid = ctx["start"]("practice", dict(ai=body["ai"], preset=p, interval=iv, effort=e, duration_minutes=dm, seconds=secs))
            return 202, dict(job=jid)

        ps = [body.get("presetA", "meta_contrib"), body.get("presetB", "meta_contrib")]
        es = [body.get("effortA", FIGHT_EFFORT), body.get("effortB", FIGHT_EFFORT)]
        if any(p not in PROVIDERS for p in ps) or any(e not in EFFORTS for e in es):
            return 400, dict(error="bad preset or effort")
        dm, secs = _duration(body, DEFAULT_FIGHT_MINUTES)
        if dm is None:
            return 400, dict(error=f"duration_minutes must be between {MIN_DURATION_MINUTES} and {MAX_DURATION_MINUTES} minutes")
        jid = ctx["start"]("fight", dict(presets=ps, efforts=es, interval=iv, duration_minutes=dm, seconds=secs))
        return 202, dict(job=jid)

    return 404, dict(error="not found")

