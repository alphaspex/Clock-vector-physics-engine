"""Backend tests. Every file is tested alone with fakes: no network, no real model, sqlite instead of Postgres."""
import json, os, threading, time, urllib.request, urllib.error
import numpy as np
import ai_call, api, body, db, digest, frames, moves, prompts, replay, rounds
from config import *

ok = lambda c, m: print(("PASS " if c else "FAIL ") + m)
info = body.build_spec(1).motor_info

# --- prompts
sp, fp = prompts.practice_system(info, ["note one"]), prompts.fight_system(info, [], "A")
ok("L_shoulder" in fp and "note one" in sp and "cannot see anyone's health" in fp and "0..180" in fp, "prompts carry motors, limits, notes; fight says health is hidden")

# --- ai_call with a fake network
seen = []
def fake(statuses):
    it = iter(statuses)
    def post(url, headers, b, timeout):
        seen.append((url, headers, b)); st = next(it)
        return (200, dict(choices=[dict(message=dict(content="do x"))], usage=dict(prompt_tokens=10, completion_tokens=7, completion_tokens_details=dict(reasoning_tokens=5))), {}) if st == 200 else (st, dict(error=dict(message="boom")), {})
    return post

# Test 1: Meta provider primary endpoint /responses API body shape and constraints
seen.clear()
def fake_responses(statuses):
    it = iter(statuses)
    def post(url, headers, b, timeout):
        seen.append((url, headers, b)); st = next(it)
        return (200, dict(
            id="resp_123",
            object="response",
            status="completed",
            model="muse-spark-1.3",
            output=[dict(type="message", role="assistant", content=[dict(type="output_text", text="Parsed output")])],
            usage=dict(input_tokens=15, output_tokens=10)
        ), {}) if st == 200 else (st, dict(error=dict(message="boom")), {})
    return post

r = ai_call.call(PROVIDERS["meta"], "SYSTEM_PROMPT", "USER_PROMPT", "high", 5, "KEY", post=fake_responses([200]), sleep=lambda s: None)
ok(r["text"] == "Parsed output" and r["usage"]["prompt"] == 15 and r["usage"]["completion"] == 10, "Meta official responses text and usage parsed")
req_body = seen[0][2]
ok(seen[0][0] == "https://api.meta.ai/v1/responses", "Meta uses /responses endpoint")
ok(req_body["input"] == "USER_PROMPT" and req_body["instructions"] == "SYSTEM_PROMPT", "input is user, instructions is system")
ok(req_body["max_output_tokens"] == 16, "max_output_tokens is clamped to at least 16")
ok("max_tokens" not in req_body and "messages" not in req_body and "reasoning_effort" not in req_body, "max_tokens, messages, reasoning_effort NEVER sent to /responses")
ok(req_body.get("reasoning") == {"effort": "high"}, "reasoning effort object set correctly")

# Test 2: Effort 'none' omits reasoning object from /responses
seen.clear()
ai_call.call(PROVIDERS["meta"], "S", "U", "none", 500, "KEY", post=fake_responses([200]), sleep=lambda s: None)
ok("reasoning" not in seen[0][2] and "reasoning_effort" not in seen[0][2], "reasoning 'none' omits reasoning field entirely")

# Test 3: Chat completions branch retains reasoning_effort, max_tokens, and messages
seen.clear()
cc_provider = dict(PROVIDERS["meta"], endpoint="/chat/completions")
r = ai_call.call(cc_provider, "S", "U", "medium", 100, "KEY", post=fake([200]), sleep=lambda s: None)
cc_body = seen[0][2]
ok("reasoning_effort" in cc_body and cc_body["reasoning_effort"] == "medium", "Chat completions retains reasoning_effort")
ok("max_tokens" in cc_body and "messages" in cc_body and "reasoning" not in cc_body, "Chat completions retains max_tokens and messages")

# Test 4: Requests when reasoning effort is disabled
seen.clear()
no_effort_provider = dict(PROVIDERS["meta"], effort=False)
ai_call.call(no_effort_provider, "S", "U", "high", 100, "KEY", post=fake([200]), sleep=lambda s: None)
ok("reasoning" not in seen[0][2] and "reasoning_effort" not in seen[0][2], "Disabled reasoning effort sends no reasoning fields")

# Test 5: Existing fallback and retry behavior
seen.clear()
r = ai_call.call(PROVIDERS["meta"], "S", "U", "high", 100, "KEY", post=fake([429, 200]), sleep=lambda s: None)
ok(r["text"] == "do x" and len(seen) == 2, "429 retry still works")

seen.clear()
r = ai_call.call(PROVIDERS["baseten"], "S", "U", "high", 100, "K", post=fake([200]), sleep=lambda s: None)
ok("reasoning_effort" not in seen[0][2] and seen[0][2]["messages"][0]["role"] == "developer" and "baseten.co" in seen[0][0], "Baseten request shape")

# --- db (sqlite stand-in)
c = db.connect(":memory:"); db.init(c)
db.save_note(c, "A", "fight", 1, "n1"); db.save_note(c, "A", "fight", 2, "n2"); db.save_note(c, "B", "fight", 2, "other")
ok(db.load_notes(c, "A") == ["n1", "n2"], "notes load oldest first, per AI")
db.save_library(c, "A", dict(moves={"m": [{"L_elbow": [[10.0], 1.0]}]}, chains={"c": ["m"]})); db.save_library(c, "A", dict(moves={}, chains={"c2": []}))
ok(db.load_library(c, "A") == dict(moves={}, chains={"c2": []}) and db.load_library(c, "Z") == dict(moves={}, chains={}), "library saved/updated/empty default")
n1 = db.save_run(c, "fight", dict(nf=2), [1], 90, "A", {}); n2 = db.save_run(c, "fight", dict(nf=2), [2], 30, None, {}); p1 = db.save_run(c, "practice", {}, [], 5, None, {})
ok((n1, n2, p1) == (1, 2, 1) and db.load_run(c, "fight", 2)["orders"] == [2] and db.load_run(c, "fight", 9) is None and [r["n"] for r in db.list_runs(c, "fight")] == [1, 2], "runs numbered per kind")

# --- frames
spec = body.build_spec(2); st = body.initial_state(spec)
d, s = frames.describe(spec), frames.snapshot(spec, st)
ok(d["points"] == 44 and len(d["shapes"]) == 44 + 58 and len(s["p"]) == 132 and s["x"] == [], f"frame messages: {len(d['shapes'])} shapes, {len(json.dumps(s))} bytes/frame")

# --- rounds with a scripted fake AI
script = iter(["Raise arm.\nmove wave = L_shoulder 90,0 1 ; L_elbow 90 1\ndo wave", "again\ndo wave", "oops\ndo nothing_here", "x\nmove bad = L_pinky 5"])
def ask1(system, user):
    return dict(text=next(script, "do wave"), usage=dict(prompt=100, completion=20, reasoning=5), error=None)
t0 = time.time(); pr = rounds.practice(ask1, info, [], dict(moves={}, chains={}), interval=2, seconds=8)
ok(len(pr["orders"]) == 4 and "wave" in pr["library"]["moves"] and pr["frames"] == 240 and pr["usage"]["prompt"] == 400, f"practice: 4 calls, move saved, 240 frames ({time.time()-t0:.1f}s)")
ok(pr["orders"][2]["steps"] == [] and "wave" in pr["library"]["moves"], "unknown 'do' name is ignored, library kept")
a1 = lambda s, u: dict(text="x\nmove punch = R_shoulder 100,0 1 ; R_elbow 0 1\ndo punch", usage=dict(prompt=1, completion=1, reasoning=0), error=None)
a2 = lambda s, u: dict(text="", usage=dict(prompt=0, completion=0, reasoning=0), error="HTTP 429: slow down")
fr_ = rounds.fight([a1, a2], info, [[], []], [dict(moves={}, chains={})] * 2, interval=2, seconds=4, gap=1.0, offset_x=0.0)
ok(len(fr_["orders"]) == 2 and all(o["f"] == 0 for o in fr_["orders"]) and fr_["frames"] == 120, "fight: AI B failed every call, A still acted, game continued")

# --- replay = same round
for name, run in (("practice", pr), ("fight", fr_)):
    rp = replay.replay(run["setup"], json.loads(json.dumps(run["orders"])), run["frames"])   # orders pass through JSON like in the database
    ok(np.array_equal(rp["final_p"], run["final_p"]) and rp["result"] == run["result"] and len(rp["frames"]) == run["frames"] + 1, f"replay of {name} reproduces the exact final positions")

# --- digest
dg = digest.digest(fr_["events"], fr_["orders"], fr_["result"], 0)
ok("Result:" in dg and "R_shoulder" not in dg and "t=0s punch" in dg, "digest has result and commands")

# --- api routing (fake outside world)
ctx = dict(
    admin_token="T",
    start=lambda k, p: "j1",
    job=lambda i: dict(id=i) if i == "j1" else None,
    runs=lambda k: [],
    memory=lambda a: dict(ai=a),
    replay=lambda k, n: dict(status="ready") if n == 1 else dict(status="not_compiled"),
    replay_status=lambda k, n: dict(status="not_compiled", run=n),
    compile_replay=lambda k, n: dict(ok=True, status="queued") if n == 1 else None,
)
h = lambda m, p, b=None, t=None: api.handle(m, p, b, t, ctx)[0]
ok(h("POST", "/practice", dict(ai="A"), None) == 401 and h("POST", "/practice", dict(ai="A"), "bad") == 401, "start needs the token")
ok(h("POST", "/practice", dict(ai="A", interval=3), "T") == 202 and h("POST", "/practice", dict(ai="Q"), "T") == 400 and h("POST", "/practice", dict(ai="A", interval=99), "T") == 400, "practice validation")
ok(h("POST", "/practice", dict(ai="A", effort="none"), "T") == 400 and h("POST", "/fight", dict(presetA="nope"), "T") == 400 and h("POST", "/fight", dict(interval=2), "T") == 202, "effort 'none' and unknown presets rejected; fight starts")
ok(h("GET", "/health") == 200 and h("GET", "/jobs/j1") == 200 and h("GET", "/jobs/zz") == 404 and h("GET", "/replay/fight/1") == 200 and h("GET", "/replay/fight/2") == 400 and h("GET", "/runs/practice") == 200 and h("GET", "/memory/A") == 200 and h("GET", "/nope") == 404, "read routes & non-ready replay returning 400")
ok(h("POST", "/replay/practice/1/compile", None, "T") == 202 and h("POST", "/replay/practice/99/compile", None, "T") == 404, "compile replay route")

# --- server end to end (fake AI, sqlite file, real HTTP on localhost)
import server
server.DSN = "/tmp/t_fighter.db"
if os.path.exists(server.DSN): os.remove(server.DSN)
server._ask = lambda preset, effort, mt: (lambda s, u: dict(text="x\nmove up = L_shoulder 120,0 1\ndo up", usage=dict(prompt=1, completion=1, reasoning=0), error=None))
os.environ["ADMIN_TOKEN"] = "T"
out = server.run_practice(dict(ai="A", preset="meta", interval=2, effort="high", seconds=4)); ok(out["run"] == 1, "server.run_practice saved run 1")
out = server.run_fight(dict(presets=["meta", "baseten"], efforts=["minimal", "minimal"], interval=2, seconds=4)); ok(out["run"] == 1, f"server.run_fight saved run 1, result {out['result']}")
ok(len(server._memory("A")["notes"]) == 1 and "up" in server._memory("A")["moves"], "after the fight AI A has a memory note and its moves")

httpd = server.ThreadingHTTPServer(("127.0.0.1", 8123), server.H); threading.Thread(target=httpd.serve_forever, daemon=True).start()
get = lambda p: json.loads(urllib.request.urlopen("http://127.0.0.1:8123" + p).read())
req_post = lambda p, body=None: json.loads(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8123" + p, data=json.dumps(body or {}).encode() if body else b"", headers={"X-Token": "T", "Content-Type": "application/json"}, method="POST")).read())

ok(get("/health") == dict(ok=True) and [r["n"] for r in get("/runs/fight")["runs"]] == [1], "real HTTP: /health and /runs/fight")

# Verify initial replay status is not_compiled and GET /replay returns 400 uncompiled status
try:
    urllib.request.urlopen("http://127.0.0.1:8123/replay/practice/1")
except urllib.error.HTTPError as e:
    resp = json.loads(e.read())
    ok(e.code == 400 and resp.get("status") == "not_compiled", "GET /replay/practice/1 returns HTTP 400 for uncompiled round")

# Trigger compilation explicitly
comp_res = req_post("/replay/practice/1/compile")
ok(comp_res.get("ok") and comp_res.get("status") == "queued", "Explicit compile request initiated")

# Poll for ready replay
rp = None
for _ in range(60):
    st_res = get("/replay/practice/1/status")
    if st_res.get("status") == "ready":
        rp = get("/replay/practice/1")
        break
    time.sleep(0.5)

ok(rp is not None and rp["status"] == "ready" and len(rp["frames"]) == 121, f"replay compilation job finishes on demand ({len(json.dumps(rp))//1000} KB for 4 s)")

