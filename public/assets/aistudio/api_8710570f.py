"""API: the web routes as one pure function. No sockets, no threads, no database in here.
handle(method, path, body, token, ctx) -> (status, payload)
ctx = the outside world as functions: ctx['admin_token'], ctx['start'](kind, params)->job_id, ctx['job'](id), ctx['runs'](kind),
      ctx['memory'](ai), ctx['replay'](kind, n)
Routes:  POST /practice {ai, preset, interval, effort}    POST /fight {presetA, presetB, interval, effortA, effortB}   (need X-Token)
         GET /jobs/<id>   GET /runs/<practice|fight>   GET /replay/<practice|fight>/<n>   GET /memory/<A|B>   GET /health"""
from config import PROVIDERS, EFFORTS, PRACTICE_EFFORT, FIGHT_EFFORT


def _interval(b):
    v = b.get("interval", 3)
    return int(v) if isinstance(v, (int, float)) and 1 <= v <= 10 else None


def handle(method, path, body, token, ctx):
    body, parts = body or {}, [p for p in path.split("?")[0].split("/") if p]
    if method == "GET":
        if parts == ["health"]: return 200, dict(ok=True)
        if len(parts) == 2 and parts[0] == "jobs":
            j = ctx["job"](parts[1]); return (200, j) if j else (404, dict(error="no such job"))
        if len(parts) == 2 and parts[0] == "runs" and parts[1] in ("practice", "fight"): return 200, dict(runs=ctx["runs"](parts[1]))
        if len(parts) == 2 and parts[0] == "memory" and parts[1] in ("A", "B"): return 200, ctx["memory"](parts[1])
        if len(parts) == 3 and parts[0] == "replay" and parts[1] in ("practice", "fight") and parts[2].isdigit():
            r = ctx["replay"](parts[1], int(parts[2])); return (200, r) if r else (404, dict(error="no such round"))
        return 404, dict(error="not found")
    if method == "POST" and parts in (["practice"], ["fight"]):
        if not ctx["admin_token"] or token != ctx["admin_token"]: return 401, dict(error="bad or missing X-Token")
        iv = _interval(body)
        if iv is None: return 400, dict(error="interval must be 1..10 seconds")
        if parts == ["practice"]:
            p, e = body.get("preset", "meta_contrib"), body.get("effort", PRACTICE_EFFORT)
            if body.get("ai") not in ("A", "B"): return 400, dict(error="ai must be A or B")
            if p not in PROVIDERS or e not in EFFORTS: return 400, dict(error=f"preset in {list(PROVIDERS)}, effort in {list(EFFORTS)}")
            return 202, dict(job=ctx["start"]("practice", dict(ai=body["ai"], preset=p, interval=iv, effort=e)))
        ps = [body.get("presetA", "meta_contrib"), body.get("presetB", "meta_contrib")]
        es = [body.get("effortA", FIGHT_EFFORT), body.get("effortB", FIGHT_EFFORT)]
        if any(p not in PROVIDERS for p in ps) or any(e not in EFFORTS for e in es): return 400, dict(error="bad preset or effort")
        return 202, dict(job=ctx["start"]("fight", dict(presets=ps, efforts=es, interval=iv)))
    return 404, dict(error="not found")
