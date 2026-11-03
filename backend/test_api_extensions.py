"""Comprehensive tests for API routes, database catalog, CRUD operations, duration handling,
Baseten fixed model validation, and admin authentication."""
import json, time, os, sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

import config
import api
import db
import ai_call

passed = 0
failed = 0

def ok(cond, msg):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS: {msg}")
    else:
        failed += 1
        print(f"FAIL: {msg}")

# ==========================================
# 1. Config & Provider Verification
# ==========================================
ok("meta" in config.PROVIDERS and config.PROVIDERS["meta"]["model"] == "muse-spark-1.3", "Meta Muse Spark model is muse-spark-1.3")
ok("meta_contrib" in config.PROVIDERS and config.PROVIDERS["meta_contrib"]["model"] == "muse-spark-1.3-contributor", "Meta Contributor model is muse-spark-1.3-contributor")
ok("baseten" in config.PROVIDERS and config.PROVIDERS["baseten"]["model"] == "meta-models/muse-spark-open-1026", "Baseten model is exactly meta-models/muse-spark-open-1026")
ok(len(config.PROVIDERS) == 3, "Only Meta (2 presets) and Baseten (1 preset) exist in PROVIDERS")
ok(config.DEFAULT_PRACTICE_MINUTES == 3.0 and config.DEFAULT_FIGHT_MINUTES == 1.0, "Default practice is 3m and fight is 1m")

# ==========================================
# 2. Database Schema, Jobs, Events, Catalog & Deletions
# ==========================================
conn = db.connect(":memory:")
db.init(conn)

# Runs & notes
p1 = db.save_run(conn, "practice", dict(ai="A"), [{"step": 1}], 90, None, dict(duration_minutes=3.0))
f1 = db.save_run(conn, "fight", dict(nf=2), [{"step": 1}], 180, "A", dict(duration_minutes=1.0))
f2 = db.save_run(conn, "fight", dict(nf=2), [{"step": 2}], 120, "B", dict(duration_minutes=1.5))
ok(p1 == 1 and f1 == 1 and f2 == 2, "Runs saved and numbered per kind")

db.save_note(conn, "A", "fight", 1, "A fight note 1")
db.save_note(conn, "A", "fight", 2, "A fight note 2")
db.save_note(conn, "B", "fight", 2, "B fight note 1")
ok(db.load_notes(conn, "A") == ["A fight note 1", "A fight note 2"], "Notes loaded for AI A")

db.save_library(conn, "A", dict(moves={"jab": 1}, chains={"c1": ["jab"]}))
ok(len(db.load_library(conn, "A")["moves"]) == 1, "Library saved and loaded")

# Jobs
db.save_or_update_job(conn, dict(id="j1", kind="fight", status="running", stage="simulation", started=time.time(), params=dict(interval=3)))
db.save_or_update_job(conn, dict(id="j1", status="done", stage="ready", run=1, result="A"))
j = db.get_job(conn, "j1")
ok(j and j["status"] == "done" and j["stage"] == "ready" and j["result"] == "A", "Job updated and retrieved from DB")

# Events
db.save_event(conn, "j1", "info", "simulation", "Sim started", dict(p=1))
db.save_event(conn, "j1", "warn", "ai_retry", "Retry 1", dict(attempt=1))
events = db.list_events(conn, limit=10)
ok(len(events) == 2 and events[0]["message"] == "Sim started" and events[1]["severity"] == "warn", "Events logged and retrieved chronologically")

# Catalog
cat = db.get_catalog(conn)
cat_keys = [c["key"] for c in cat]
ok("runs_fight" in cat_keys and "runs_practice" in cat_keys and "notes" in cat_keys and "library" in cat_keys and "jobs" in cat_keys and "events" in cat_keys, "Catalog exposes all 6 DB resources")

# Resource listing
fights = db.list_resource(conn, "runs_fight")
ok(fights["total"] == 2 and len(fights["items"]) == 2, "list_resource returns fight runs with pagination metadata")
notes = db.list_resource(conn, "notes")
ok(notes["total"] == 3 and len(notes["items"]) == 3, "list_resource returns notes")

# Delete single item
del_res = db.delete_resource_item(conn, "runs_fight", 2)
ok(del_res["ok"] and del_res["deleted"] == 1, "Individual fight run deleted")
ok(db.list_resource(conn, "runs_fight")["total"] == 1, "Fight run count reduced to 1")

# Bulk delete
bdel = db.delete_resource_batch(conn, "notes", [notes["items"][0]["id"], notes["items"][1]["id"]])
ok(bdel["ok"] and bdel["deleted"] == 2, "Batch deletion of notes succeeded")
ok(db.list_resource(conn, "notes")["total"] == 1, "Remaining notes count is 1")

# Reset memory safety: verifies notes and libraries are reset, but runs are preserved!
rst = db.reset_memory(conn, target="all")
ok(rst["ok"] and rst["deleted_notes"] == 1 and rst["reset_libraries"] == 2, "Reset memory cleared remaining notes and reset 2 libraries")
ok(db.list_resource(conn, "runs_fight")["total"] == 1 and db.list_resource(conn, "runs_practice")["total"] == 1, "Runs history completely preserved after Reset Memory")

# Active job protection
db.save_or_update_job(conn, dict(id="active_j", kind="practice", status="running", stage="simulation", started=time.time()))
del_act = db.delete_resource_item(conn, "jobs", "active_j", active_jobs=["active_j"])
ok(not del_act["ok"] and "cannot be deleted" in del_act["error"], "Active running job cannot be deleted")

# ==========================================
# 3. API Handler: Duration, Auth, Endpoints
# ==========================================
mock_jobs = {"j_test": dict(id="j_test", status="running", stage="simulation")}
mock_ctx = dict(
    admin_token="SECRET",
    start=lambda kind, p: f"started_{kind}_{p.get('duration_minutes')}",
    job=lambda jid: mock_jobs.get(jid),
    runs=lambda k: [{"n": 1}],
    memory=lambda a: dict(ai=a, notes=[]),
    replay=lambda k, n: dict(status="ready"),
    replay_status=lambda k, n: dict(status="ready", run=n),
    list_jobs=lambda lim: [dict(id="j_test")],
    list_events=lambda lim, since: [dict(id=1, message="ev")],
    db_catalog=lambda: [{"key": "notes"}],
    db_list=lambda r, lim, off: dict(items=[], total=0),
    db_get=lambda r, iid: dict(id=iid),
    db_delete=lambda r, iid: dict(ok=True, deleted=1),
    db_delete_batch=lambda r, ids: dict(ok=True, deleted=len(ids)),
    db_reset_memory=lambda target: dict(ok=True, deleted_notes=0, reset_libraries=2),
    get_logs=lambda since_id=None, limit=200, level=None, subsystem=None, search=None: ([dict(id=1, message="test log", level="INFO", subsystem="SYSTEM")], 1),
    clear_logs=lambda: True,
    server_status=lambda: dict(status="online", uptime_seconds=10.0, total_logs=1, activity="Idle"),
    emit_log=lambda lvl, sub, msg, **det: dict(id=2, level=lvl, subsystem=sub, message=msg, details=det),
)

h = lambda m, p, b=None, t=None: api.handle(m, p, b, t, mock_ctx)

# Public routes
ok(h("GET", "/health")[0] == 200, "GET /health is 200 public")
ok(h("GET", "/runs/fight")[0] == 200, "GET /runs/fight is 200 public")
ok(h("GET", "/replay/fight/1")[0] == 200, "GET /replay/fight/1 is 200 public")
ok(h("GET", "/replay/fight/1/status")[0] == 200, "GET /replay/fight/1/status is 200 public")
ok(h("GET", "/logs")[0] == 200 and len(h("GET", "/logs")[1]["logs"]) == 1, "GET /logs returns 200 with logs and server status")
ok(h("POST", "/logs/test", dict(message="ping"))[0] == 200, "POST /logs/test emits diagnostic ping")

# Admin token enforcement
ok(h("POST", "/practice", dict(ai="A", interval=3), None)[0] == 401, "POST /practice without token -> 401")
ok(h("POST", "/practice", dict(ai="A", interval=3), "WRONG")[0] == 401, "POST /practice with wrong token -> 401")
ok(h("GET", "/admin/jobs", None, None)[0] == 401, "GET /admin/jobs without token -> 401")
ok(h("GET", "/admin/logs", None, "SECRET")[0] == 200, "GET /admin/logs with valid token returns 200")
ok(h("POST", "/admin/logs/clear", None, "SECRET")[0] == 200, "POST /admin/logs/clear resets buffer")

ok(h("GET", "/admin/events", None, None)[0] == 401, "GET /admin/events without token -> 401")
ok(h("GET", "/admin/db/catalog", None, None)[0] == 401, "GET /admin/db/catalog without token -> 401")

# Admin routes with valid token
ok(h("GET", "/admin/jobs", None, "SECRET")[0] == 200, "GET /admin/jobs with token -> 200")
ok(h("GET", "/admin/events", None, "SECRET")[0] == 200, "GET /admin/events with token -> 200")
ok(h("GET", "/admin/db/catalog", None, "SECRET")[0] == 200, "GET /admin/db/catalog with token -> 200")
ok(h("GET", "/admin/db/notes", None, "SECRET")[0] == 200, "GET /admin/db/notes with token -> 200")
ok(h("DELETE", "/admin/db/notes/1", None, "SECRET")[0] == 200, "DELETE /admin/db/notes/1 -> 200")
ok(h("POST", "/admin/db/notes/delete-batch", dict(ids=[1, 2]), "SECRET")[0] == 200, "POST /admin/db/notes/delete-batch -> 200")
ok(h("POST", "/admin/db/reset-memory", dict(target="all"), "SECRET")[0] == 200, "POST /admin/db/reset-memory -> 200")

# Duration validation: Practice
status, res = h("POST", "/practice", dict(ai="A", interval=3, preset="meta", duration_minutes=5.0), "SECRET")
ok(status == 202 and "5.0" in res["job"], "Practice starts with custom duration (5.0 min)")

status, res = h("POST", "/practice", dict(ai="A", interval=3, preset="meta"), "SECRET")
ok(status == 202 and "3.0" in res["job"], "Practice defaults to 3.0 min duration")

status, res = h("POST", "/practice", dict(ai="A", interval=3, duration_minutes=0.01), "SECRET")
ok(status == 400 and "duration_minutes" in res["error"], "Practice rejects duration below minimum")

status, res = h("POST", "/practice", dict(ai="A", interval=3, duration_minutes=999.0), "SECRET")
ok(status == 400 and "duration_minutes" in res["error"], "Practice rejects duration above maximum")

# Duration validation: Fight
status, res = h("POST", "/fight", dict(presetA="meta", presetB="baseten", interval=3, duration_minutes=2.5), "SECRET")
ok(status == 202 and "2.5" in res["job"], "Fight starts with custom duration (2.5 min)")

status, res = h("POST", "/fight", dict(presetA="meta", presetB="baseten", interval=3), "SECRET")
ok(status == 202 and "1.0" in res["job"], "Fight defaults to 1.0 min duration")

# Provider validation
status, res = h("POST", "/fight", dict(presetA="unknown_provider", presetB="baseten", interval=3), "SECRET")
ok(status == 400 and "bad preset" in res["error"], "Fight rejects unknown provider")

# ==========================================
# 4. AI Call Error Reporting & Model Identification
# ==========================================
seen_calls = []
def mock_post(url, headers, body, timeout):
    seen_calls.append((url, headers, body))
    # Return 404 with error message
    return 404, dict(error=dict(message="Model not found")), {}

call_res = ai_call.call(config.PROVIDERS["baseten"], "system", "user", "minimal", 100, "KEY", post=mock_post, sleep=lambda s: None)
ok("meta-models/muse-spark-open-1026" in call_res["error"], "Baseten error clearly identifies exact model meta-models/muse-spark-open-1026")
ok("HTTP 404" in call_res["error"], "Error contains HTTP 404 code")
ok(seen_calls[0][2]["model"] == "meta-models/muse-spark-open-1026", "Baseten request payload used exact model identifier")
ok("elapsed_ms" in call_res, "ai_call returns elapsed_ms latency")

print("=" * 50)
print(f"TESTS FINISHED: {passed} PASSED, {failed} FAILED")
if failed > 0:
    sys.exit(1)
