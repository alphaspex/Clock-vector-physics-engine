"""DB: Postgres storage (sqlite for local tests). Every function: connection + plain data in, plain data out.
connect(dsn)                              OUT: connection ('postgres://...' -> Postgres, anything else -> sqlite file)
init(conn)                                create tables
save_note(conn, ai, kind, run_n, text)    / load_notes(conn, ai)             -> [text, ...] oldest first
save_library(conn, ai, lib)               / load_library(conn, ai)           -> {moves, chains}
save_run(conn, kind, setup, orders, frames, result, info) -> n   (n counts per kind: practice 1,2,3.. fight 1,2,3..)
load_run(conn, kind, n) -> dict | None    / list_runs(conn, kind)            -> [dict(n, created, result, frames, info)]
Untested against a real Postgres here (no server available); tested on sqlite with the same SQL."""
import json, time


def connect(dsn):
    if dsn and dsn.startswith(("postgres://", "postgresql://")):
        import psycopg2
        return psycopg2.connect(dsn)
    import sqlite3
    return sqlite3.connect(dsn or "fighter.db", check_same_thread=False)


def _pg(conn):
    return type(conn).__module__.startswith("psycopg2")


def _x(conn, sql, args=()):
    cur = conn.cursor()
    cur.execute(sql if _pg(conn) else sql.replace("%s", "?"), args)
    return cur


def init(conn):
    pk = "BIGSERIAL PRIMARY KEY" if _pg(conn) else "INTEGER PRIMARY KEY AUTOINCREMENT"
    _x(conn, f"CREATE TABLE IF NOT EXISTS notes (id {pk}, ai TEXT, kind TEXT, run_n INTEGER, text TEXT, created TEXT)")
    _x(conn, "CREATE TABLE IF NOT EXISTS library (ai TEXT PRIMARY KEY, data TEXT)")
    _x(conn, f"CREATE TABLE IF NOT EXISTS runs (id {pk}, kind TEXT, n INTEGER, created TEXT, setup TEXT, orders TEXT, frames INTEGER, result TEXT, info TEXT)")
    _x(conn, "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT, status TEXT, stage TEXT, created TEXT, started REAL, elapsed_ms INTEGER, run_n INTEGER, result TEXT, params TEXT, usage TEXT, error TEXT)")
    _x(conn, f"CREATE TABLE IF NOT EXISTS job_events (id {pk}, job_id TEXT, created TEXT, severity TEXT, stage TEXT, message TEXT, metadata TEXT)")
    _x(conn, "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, val TEXT)")
    _x(conn, "CREATE TABLE IF NOT EXISTS replays (kind TEXT, n INTEGER, status TEXT, progress TEXT, data TEXT, PRIMARY KEY (kind, n))")
    _x(conn, f"CREATE TABLE IF NOT EXISTS interval_descriptions (id {pk}, job_id TEXT, kind TEXT, run_n INTEGER, fighter TEXT, interval_idx INTEGER, frame INTEGER, time_sec REAL, text TEXT, word_count INTEGER, created TEXT)")
    _x(conn, f"CREATE TABLE IF NOT EXISTS round_summaries (id {pk}, ai TEXT, kind TEXT, run_n INTEGER, text TEXT, created TEXT)")
    conn.commit()


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def save_interval_description(conn, job_id, kind, run_n, fighter, interval_idx, frame, time_sec, text, word_count):
    _x(conn, "INSERT INTO interval_descriptions (job_id, kind, run_n, fighter, interval_idx, frame, time_sec, text, word_count, created) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
       (job_id or "", kind or "", run_n or 0, fighter or "A", interval_idx or 0, frame or 0, time_sec or 0.0, text, word_count, _now()))
    conn.commit()


def get_interval_descriptions(conn, job_id=None, kind=None, run_n=None, fighter=None, limit=100):
    query = "SELECT job_id, kind, run_n, fighter, interval_idx, frame, time_sec, text, word_count, created FROM interval_descriptions WHERE 1=1"
    args = []
    if job_id:
        query += " AND job_id=%s"
        args.append(job_id)
    if kind:
        query += " AND kind=%s"
        args.append(kind)
    if run_n:
        query += " AND run_n=%s"
        args.append(run_n)
    if fighter:
        query += " AND fighter=%s"
        args.append(fighter)
    query += " ORDER BY id ASC LIMIT %s"
    args.append(limit)
    rows = _x(conn, query, tuple(args)).fetchall()
    return [dict(job_id=r[0], kind=r[1], run_n=r[2], fighter=r[3], interval_idx=r[4], frame=r[5], time_sec=r[6], text=r[7], word_count=r[8], created=r[9]) for r in rows]


def save_round_summary(conn, ai, kind, run_n, text):
    """Saves end-of-round summary. Practice and fight summaries are strictly separated."""
    _x(conn, "INSERT INTO round_summaries (ai, kind, run_n, text, created) VALUES (%s,%s,%s,%s,%s)", (ai, kind, run_n, text, _now()))
    conn.commit()


def load_round_summaries(conn, ai, kind, limit=3):
    """Loads latest three completed round summaries for this fighter and mode, oldest first."""
    rows = _x(conn, "SELECT text FROM round_summaries WHERE ai=%s AND kind=%s ORDER BY id DESC LIMIT %s", (ai, kind, limit)).fetchall()
    return [r[0] for r in reversed(rows)]


def save_note(conn, ai, kind, run_n, text):
    _x(conn, "INSERT INTO notes (ai, kind, run_n, text, created) VALUES (%s,%s,%s,%s,%s)", (ai, kind, run_n, text, _now()))
    conn.commit()


def load_notes(conn, ai, limit=30):
    rows = _x(conn, "SELECT text FROM notes WHERE ai=%s ORDER BY id DESC LIMIT %s", (ai, limit)).fetchall()
    return [r[0] for r in reversed(rows)]


def save_library(conn, ai, lib):
    data = json.dumps(lib)
    if _x(conn, "SELECT 1 FROM library WHERE ai=%s", (ai,)).fetchone():
        _x(conn, "UPDATE library SET data=%s WHERE ai=%s", (data, ai))
    else:
        _x(conn, "INSERT INTO library (ai, data) VALUES (%s,%s)", (ai, data))
    conn.commit()


def load_library(conn, ai):
    r = _x(conn, "SELECT data FROM library WHERE ai=%s", (ai,)).fetchone()
    return json.loads(r[0]) if r else dict(moves={}, chains={})


def save_run(conn, kind, setup, orders, frames, result, info):
    n = _x(conn, "SELECT COALESCE(MAX(n),0)+1 FROM runs WHERE kind=%s", (kind,)).fetchone()[0]
    _x(conn, "INSERT INTO runs (kind, n, created, setup, orders, frames, result, info) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
       (kind, n, _now(), json.dumps(setup), json.dumps(orders), frames, result or "", json.dumps(info)))
    conn.commit()
    return n


def load_run(conn, kind, n):
    r = _x(conn, "SELECT n, created, setup, orders, frames, result, info FROM runs WHERE kind=%s AND n=%s", (kind, n)).fetchone()
    if not r: return None
    return dict(kind=kind, n=r[0], created=r[1], setup=json.loads(r[2]), orders=json.loads(r[3]), frames=r[4], result=r[5] or None, info=json.loads(r[6]))


def save_replay_status(conn, kind, n, status, progress=None, data=None):
    prog_str = json.dumps(progress) if progress is not None else None
    data_str = json.dumps(data) if data is not None else None

    existing = _x(conn, "SELECT 1 FROM replays WHERE kind=%s AND n=%s", (kind, int(n))).fetchone()
    if existing:
        if data_str is not None:
            _x(conn, "UPDATE replays SET status=%s, progress=COALESCE(%s, progress), data=%s WHERE kind=%s AND n=%s",
               (status, prog_str, data_str, kind, int(n)))
        else:
            _x(conn, "UPDATE replays SET status=%s, progress=COALESCE(%s, progress) WHERE kind=%s AND n=%s",
               (status, prog_str, kind, int(n)))
    else:
        _x(conn, "INSERT INTO replays (kind, n, status, progress, data) VALUES (%s,%s,%s,%s,%s)",
           (kind, int(n), status, prog_str or "{}", data_str))
    conn.commit()


def get_replay_status(conn, kind, n):
    r = _x(conn, "SELECT status, progress FROM replays WHERE kind=%s AND n=%s", (kind, int(n))).fetchone()
    if not r:
        run_exists = _x(conn, "SELECT 1 FROM runs WHERE kind=%s AND n=%s", (kind, int(n))).fetchone()
        if run_exists:
            return dict(status="not_compiled", progress={})
        return None
    status, prog_raw = r[0], r[1]
    progress = json.loads(prog_raw) if prog_raw else {}
    return dict(status=status, progress=progress)


def get_compiled_replay(conn, kind, n):
    r = _x(conn, "SELECT status, progress, data FROM replays WHERE kind=%s AND n=%s", (kind, int(n))).fetchone()
    if not r:
        run_exists = _x(conn, "SELECT 1 FROM runs WHERE kind=%s AND n=%s", (kind, int(n))).fetchone()
        if run_exists:
            return dict(status="not_compiled", error="Replay has not been compiled yet")
        return None
    status, prog_raw, data_raw = r[0], r[1], r[2]
    progress = json.loads(prog_raw) if prog_raw else {}
    if status == "ready" and data_raw:
        data = json.loads(data_raw)
        return dict(status="ready", result=data.get("result"), init=data.get("init"), frames=data.get("frames"))
    return dict(status=status, progress=progress, error=progress.get("error") if status == "failed" else None)


def list_runs(conn, kind):
    rows = _x(conn, "SELECT n, created, result, frames, info FROM runs WHERE kind=%s ORDER BY n", (kind,)).fetchall()
    res = []
    for r in rows:
        st = get_replay_status(conn, kind, r[0])
        replay_status = st["status"] if st else "not_compiled"
        replay_progress = st.get("progress") if st else {}
        res.append(dict(n=r[0], created=r[1], result=r[2] or None, frames=r[3], info=json.loads(r[4]),
                        replay_status=replay_status, replay_progress=replay_progress))
    return res


# ---- Jobs & Events audit persistence ----
def save_or_update_job(conn, job):
    jid = job.get("id")
    if not jid: return
    kind = job.get("kind", "")
    status = job.get("status", "running")
    stage = job.get("stage", "")
    created = job.get("created", _now())
    started = float(job.get("started") or 0.0)
    elapsed_ms = int(job.get("elapsed_ms") or 0)
    run_n = job.get("run")
    result = job.get("result") or ""
    params = json.dumps(job.get("params") or {})
    usage = json.dumps(job.get("usage") or {})
    error = str(job.get("error") or "")

    existing = _x(conn, "SELECT 1 FROM jobs WHERE id=%s", (jid,)).fetchone()
    if existing:
        _x(conn, "UPDATE jobs SET status=%s, stage=%s, elapsed_ms=%s, run_n=%s, result=%s, params=%s, usage=%s, error=%s WHERE id=%s",
           (status, stage, elapsed_ms, run_n, result, params, usage, error, jid))
    else:
        _x(conn, "INSERT INTO jobs (id, kind, status, stage, created, started, elapsed_ms, run_n, result, params, usage, error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
           (jid, kind, status, stage, created, started, elapsed_ms, run_n, result, params, usage, error))
    conn.commit()


def get_job(conn, jid):
    r = _x(conn, "SELECT id, kind, status, stage, created, started, elapsed_ms, run_n, result, params, usage, error FROM jobs WHERE id=%s", (jid,)).fetchone()
    if not r: return None
    return dict(id=r[0], kind=r[1], status=r[2], stage=r[3], created=r[4], started=r[5],
                elapsed_ms=r[6], run=r[7], result=r[8] or None,
                params=json.loads(r[9]) if r[9] else {},
                usage=json.loads(r[10]) if r[10] else {},
                error=r[11] or None)


def list_jobs(conn, limit=50):
    rows = _x(conn, "SELECT id, kind, status, stage, created, started, elapsed_ms, run_n, result, params, usage, error FROM jobs ORDER BY started DESC LIMIT %s", (limit,)).fetchall()
    return [dict(id=r[0], kind=r[1], status=r[2], stage=r[3], created=r[4], started=r[5],
                 elapsed_ms=r[6], run=r[7], result=r[8] or None,
                 params=json.loads(r[9]) if r[9] else {},
                 usage=json.loads(r[10]) if r[10] else {},
                 error=r[11] or None) for r in rows]


def save_event(conn, job_id, severity, stage, message, metadata=None):
    meta_str = json.dumps(metadata or {})
    _x(conn, "INSERT INTO job_events (job_id, created, severity, stage, message, metadata) VALUES (%s,%s,%s,%s,%s,%s)",
       (job_id or "", _now(), severity, stage, message, meta_str))
    conn.commit()


def list_events(conn, limit=100, since_id=None):
    if since_id is not None and since_id > 0:
        rows = _x(conn, "SELECT id, job_id, created, severity, stage, message, metadata FROM job_events WHERE id > %s ORDER BY id DESC LIMIT %s", (since_id, limit)).fetchall()
    else:
        rows = _x(conn, "SELECT id, job_id, created, severity, stage, message, metadata FROM job_events ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
    res = [dict(id=r[0], job_id=r[1], created=r[2], severity=r[3], stage=r[4], message=r[5],
                metadata=json.loads(r[6]) if r[6] else {}) for r in rows]
    return list(reversed(res))


# ---- Dynamic Catalog & Database Management ----
def get_catalog(conn):
    """Dynamic resource descriptors for UI database management."""
    counts = {
        "runs_fight": _x(conn, "SELECT COUNT(*) FROM runs WHERE kind='fight'").fetchone()[0],
        "runs_practice": _x(conn, "SELECT COUNT(*) FROM runs WHERE kind='practice'").fetchone()[0],
        "round_summaries": _x(conn, "SELECT COUNT(*) FROM round_summaries").fetchone()[0],
        "interval_descriptions": _x(conn, "SELECT COUNT(*) FROM interval_descriptions").fetchone()[0],
        "notes": _x(conn, "SELECT COUNT(*) FROM notes").fetchone()[0],
        "library": _x(conn, "SELECT COUNT(*) FROM library").fetchone()[0],
        "jobs": _x(conn, "SELECT COUNT(*) FROM jobs").fetchone()[0],
        "events": _x(conn, "SELECT COUNT(*) FROM job_events").fetchone()[0],
    }

    return [
        dict(
            key="runs_fight",
            label="Fight History",
            description="Saved AI vs AI matches with deterministic physics frames and decisions.",
            count=counts["runs_fight"],
            primary_key="n",
            operations=["list", "inspect", "delete", "bulk_delete"],
            reversible=False,
            fields=[
                dict(key="n", label="Run #", type="number", primary=True),
                dict(key="created", label="Created (UTC)", type="string"),
                dict(key="result", label="Result / Winner", type="string"),
                dict(key="frames", label="Frames", type="number"),
                dict(key="duration", label="Duration (s)", type="number"),
            ]
        ),
        dict(
            key="runs_practice",
            label="Practice History",
            description="Saved solo motor-learning practice sessions.",
            count=counts["runs_practice"],
            primary_key="n",
            operations=["list", "inspect", "delete", "bulk_delete"],
            reversible=False,
            fields=[
                dict(key="n", label="Run #", type="number", primary=True),
                dict(key="created", label="Created (UTC)", type="string"),
                dict(key="ai", label="Fighter Slot", type="string"),
                dict(key="frames", label="Frames", type="number"),
                dict(key="duration", label="Duration (s)", type="number"),
            ]
        ),
        dict(
            key="round_summaries",
            label="Round Summaries",
            description="AI-generated post-round summary narratives combining interval thoughts.",
            count=counts["round_summaries"],
            primary_key="id",
            operations=["list", "inspect", "delete", "bulk_delete", "reset"],
            reversible=False,
            fields=[
                dict(key="id", label="ID", type="number", primary=True),
                dict(key="ai", label="Fighter", type="string"),
                dict(key="kind", label="Round Kind", type="string"),
                dict(key="run_n", label="Run #", type="number"),
                dict(key="created", label="Timestamp", type="string"),
                dict(key="text", label="Summary Narrative", type="string"),
            ]
        ),
        dict(
            key="interval_descriptions",
            label="Interval Descriptions",
            description="Fine-grained interval thoughts recorded every decision cycle (e.g. 5s).",
            count=counts["interval_descriptions"],
            primary_key="id",
            operations=["list", "inspect", "delete", "bulk_delete", "reset"],
            reversible=False,
            fields=[
                dict(key="id", label="ID", type="number", primary=True),
                dict(key="fighter", label="Fighter", type="string"),
                dict(key="kind", label="Kind", type="string"),
                dict(key="interval_idx", label="Interval #", type="number"),
                dict(key="time_sec", label="Time (s)", type="number"),
                dict(key="word_count", label="Words", type="number"),
                dict(key="created", label="Timestamp", type="string"),
                dict(key="text", label="Thinking Text", type="string"),
            ]
        ),
        dict(
            key="notes",
            label="AI Memories / Notes",
            description="Reflective memories and combat notes generated post-fight.",
            count=counts["notes"],
            primary_key="id",
            operations=["list", "inspect", "delete", "bulk_delete", "reset"],
            reversible=False,
            fields=[
                dict(key="id", label="ID", type="number", primary=True),
                dict(key="ai", label="Fighter", type="string"),
                dict(key="kind", label="Round Kind", type="string"),
                dict(key="run_n", label="Source Run #", type="number"),
                dict(key="created", label="Timestamp", type="string"),
                dict(key="text", label="Note Content", type="string"),
            ]
        ),
        dict(
            key="library",
            label="Move Libraries & Chains",
            description="Learned motor moves and combo chains registered per fighter.",
            count=counts["library"],
            primary_key="ai",
            operations=["list", "inspect", "delete", "reset"],
            reversible=False,
            fields=[
                dict(key="ai", label="Fighter Slot", type="string", primary=True),
                dict(key="move_count", label="Moves Count", type="number"),
                dict(key="chain_count", label="Chains Count", type="number"),
            ]
        ),
        dict(
            key="jobs",
            label="Simulation Jobs History",
            description="Audited execution records for practice and fight jobs.",
            count=counts["jobs"],
            primary_key="id",
            operations=["list", "inspect", "delete", "bulk_delete"],
            reversible=False,
            fields=[
                dict(key="id", label="Job ID", type="string", primary=True),
                dict(key="kind", label="Kind", type="string"),
                dict(key="status", label="Status", type="string"),
                dict(key="stage", label="Stage", type="string"),
                dict(key="run_n", label="Run #", type="number"),
                dict(key="created", label="Created", type="string"),
                dict(key="error", label="Error", type="string"),
            ]
        ),
        dict(
            key="events",
            label="Activity Event Feed",
            description="Fine-grained chronological event stream from physics, AI calls, and lifecycle stages.",
            count=counts["events"],
            primary_key="id",
            operations=["list", "inspect", "delete", "bulk_delete"],
            reversible=False,
            fields=[
                dict(key="id", label="Event ID", type="number", primary=True),
                dict(key="job_id", label="Job ID", type="string"),
                dict(key="severity", label="Severity", type="string"),
                dict(key="stage", label="Stage", type="string"),
                dict(key="message", label="Message", type="string"),
                dict(key="created", label="Timestamp", type="string"),
            ]
        ),
    ]


def list_resource(conn, resource, limit=50, offset=0):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    if resource == "runs_fight":
        total = _x(conn, "SELECT COUNT(*) FROM runs WHERE kind='fight'").fetchone()[0]
        rows = _x(conn, "SELECT n, created, result, frames, info, setup FROM runs WHERE kind='fight' ORDER BY n DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = []
        for r in rows:
            info = json.loads(r[4]) if r[4] else {}
            items.append(dict(n=r[0], created=r[1], result=r[2] or None, frames=r[3], duration=round(r[3] / 30.0, 1), info=info))
        return dict(items=items, total=total, limit=limit, offset=offset)

    if resource == "runs_practice":
        total = _x(conn, "SELECT COUNT(*) FROM runs WHERE kind='practice'").fetchone()[0]
        rows = _x(conn, "SELECT n, created, frames, info, setup FROM runs WHERE kind='practice' ORDER BY n DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = []
        for r in rows:
            info = json.loads(r[3]) if r[3] else {}
            setup = json.loads(r[4]) if r[4] else {}
            items.append(dict(n=r[0], created=r[1], frames=r[2], duration=round(r[2] / 30.0, 1), ai=setup.get("ai", "A"), info=info))
        return dict(items=items, total=total, limit=limit, offset=offset)

    if resource == "round_summaries":
        total = _x(conn, "SELECT COUNT(*) FROM round_summaries").fetchone()[0]
        rows = _x(conn, "SELECT id, ai, kind, run_n, text, created FROM round_summaries ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = [dict(id=r[0], ai=r[1], kind=r[2], run_n=r[3], text=r[4], created=r[5]) for r in rows]
        return dict(items=items, total=total, limit=limit, offset=offset)

    if resource == "interval_descriptions":
        total = _x(conn, "SELECT COUNT(*) FROM interval_descriptions").fetchone()[0]
        rows = _x(conn, "SELECT id, job_id, kind, run_n, fighter, interval_idx, frame, time_sec, text, word_count, created FROM interval_descriptions ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = [dict(id=r[0], job_id=r[1], kind=r[2], run_n=r[3], fighter=r[4], interval_idx=r[5], frame=r[6], time_sec=r[7], text=r[8], word_count=r[9], created=r[10]) for r in rows]
        return dict(items=items, total=total, limit=limit, offset=offset)

    if resource == "notes":
        total = _x(conn, "SELECT COUNT(*) FROM notes").fetchone()[0]
        rows = _x(conn, "SELECT id, ai, kind, run_n, text, created FROM notes ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = [dict(id=r[0], ai=r[1], kind=r[2], run_n=r[3], text=r[4], created=r[5]) for r in rows]
        return dict(items=items, total=total, limit=limit, offset=offset)

    if resource == "library":
        total = _x(conn, "SELECT COUNT(*) FROM library").fetchone()[0]
        rows = _x(conn, "SELECT ai, data FROM library ORDER BY ai LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = []
        for r in rows:
            data = json.loads(r[1]) if r[1] else {}
            moves = data.get("moves", {})
            chains = data.get("chains", {})
            items.append(dict(ai=r[0], move_count=len(moves), chain_count=len(chains), data=data))
        return dict(items=items, total=total, limit=limit, offset=offset)

    if resource == "jobs":
        total = _x(conn, "SELECT COUNT(*) FROM jobs").fetchone()[0]
        rows = _x(conn, "SELECT id, kind, status, stage, created, started, elapsed_ms, run_n, result, params, usage, error FROM jobs ORDER BY started DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = [dict(id=r[0], kind=r[1], status=r[2], stage=r[3], created=r[4], started=r[5],
                      elapsed_ms=r[6], run_n=r[7], result=r[8] or None,
                      params=json.loads(r[9]) if r[9] else {},
                      usage=json.loads(r[10]) if r[10] else {},
                      error=r[11] or None) for r in rows]
        return dict(items=items, total=total, limit=limit, offset=offset)

    if resource == "events":
        total = _x(conn, "SELECT COUNT(*) FROM job_events").fetchone()[0]
        rows = _x(conn, "SELECT id, job_id, created, severity, stage, message, metadata FROM job_events ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset)).fetchall()
        items = [dict(id=r[0], job_id=r[1], created=r[2], severity=r[3], stage=r[4], message=r[5],
                      metadata=json.loads(r[6]) if r[6] else {}) for r in rows]
        return dict(items=items, total=total, limit=limit, offset=offset)

    return None


def get_resource_item(conn, resource, item_id):
    if resource == "runs_fight":
        r = _x(conn, "SELECT n, created, setup, orders, frames, result, info FROM runs WHERE kind='fight' AND n=%s", (int(item_id),)).fetchone()
        if not r: return None
        return dict(kind="fight", n=r[0], created=r[1], setup=json.loads(r[2]), orders=json.loads(r[3]), frames=r[4], result=r[5] or None, info=json.loads(r[6]))

    if resource == "runs_practice":
        r = _x(conn, "SELECT n, created, setup, orders, frames, result, info FROM runs WHERE kind='practice' AND n=%s", (int(item_id),)).fetchone()
        if not r: return None
        return dict(kind="practice", n=r[0], created=r[1], setup=json.loads(r[2]), orders=json.loads(r[3]), frames=r[4], result=r[5] or None, info=json.loads(r[6]))

    if resource == "round_summaries":
        r = _x(conn, "SELECT id, ai, kind, run_n, text, created FROM round_summaries WHERE id=%s", (int(item_id),)).fetchone()
        if not r: return None
        return dict(id=r[0], ai=r[1], kind=r[2], run_n=r[3], text=r[4], created=r[5])

    if resource == "interval_descriptions":
        r = _x(conn, "SELECT id, job_id, kind, run_n, fighter, interval_idx, frame, time_sec, text, word_count, created FROM interval_descriptions WHERE id=%s", (int(item_id),)).fetchone()
        if not r: return None
        return dict(id=r[0], job_id=r[1], kind=r[2], run_n=r[3], fighter=r[4], interval_idx=r[5], frame=r[6], time_sec=r[7], text=r[8], word_count=r[9], created=r[10])

    if resource == "notes":
        r = _x(conn, "SELECT id, ai, kind, run_n, text, created FROM notes WHERE id=%s", (int(item_id),)).fetchone()
        if not r: return None
        return dict(id=r[0], ai=r[1], kind=r[2], run_n=r[3], text=r[4], created=r[5])

    if resource == "library":
        r = _x(conn, "SELECT ai, data FROM library WHERE ai=%s", (str(item_id),)).fetchone()
        if not r: return None
        return dict(ai=r[0], data=json.loads(r[1]) if r[1] else {})

    if resource == "jobs":
        return get_job(conn, str(item_id))

    if resource == "events":
        r = _x(conn, "SELECT id, job_id, created, severity, stage, message, metadata FROM job_events WHERE id=%s", (int(item_id),)).fetchone()
        if not r: return None
        return dict(id=r[0], job_id=r[1], created=r[2], severity=r[3], stage=r[4], message=r[5], metadata=json.loads(r[6]) if r[6] else {})

    return None


def delete_resource_item(conn, resource, item_id, active_jobs=()):
    """Safely delete one item. Prevent deleting active simulation state."""
    # Check if deleting an active job
    if resource == "jobs":
        if str(item_id) in active_jobs:
            return dict(ok=False, error=f"Job {item_id} is currently running and cannot be deleted", deleted=0)
        cur = _x(conn, "DELETE FROM jobs WHERE id=%s", (str(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    if resource == "events":
        cur = _x(conn, "DELETE FROM job_events WHERE id=%s", (int(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    if resource == "runs_fight":
        _x(conn, "DELETE FROM replays WHERE kind='fight' AND n=%s", (int(item_id),))
        cur = _x(conn, "DELETE FROM runs WHERE kind='fight' AND n=%s", (int(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    if resource == "runs_practice":
        _x(conn, "DELETE FROM replays WHERE kind='practice' AND n=%s", (int(item_id),))
        cur = _x(conn, "DELETE FROM runs WHERE kind='practice' AND n=%s", (int(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    if resource == "round_summaries":
        cur = _x(conn, "DELETE FROM round_summaries WHERE id=%s", (int(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    if resource == "interval_descriptions":
        cur = _x(conn, "DELETE FROM interval_descriptions WHERE id=%s", (int(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    if resource == "notes":
        cur = _x(conn, "DELETE FROM notes WHERE id=%s", (int(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    if resource == "library":
        cur = _x(conn, "DELETE FROM library WHERE ai=%s", (str(item_id),))
        conn.commit()
        return dict(ok=True, deleted=cur.rowcount)

    return dict(ok=False, error=f"Unknown resource {resource}", deleted=0)


def delete_resource_batch(conn, resource, item_ids, active_jobs=()):
    """Bulk delete records by list of IDs."""
    if not item_ids:
        return dict(ok=True, deleted=0)

    total_deleted = 0
    for iid in item_ids:
        res = delete_resource_item(conn, resource, iid, active_jobs)
        if res.get("ok"):
            total_deleted += res.get("deleted", 0)
        else:
            return dict(ok=False, error=res.get("error", "Error deleting item"), deleted=total_deleted)

    return dict(ok=True, deleted=total_deleted)


def reset_memory(conn, target="all"):
    """
    Clears round summaries, notes, and resets learned libraries to empty for specified target ('A', 'B', or 'all').
    Leaves runs (practice and fight history) intact!
    """
    deleted_notes = 0
    reset_libs = 0

    if target in ("A", "B"):
        cur = _x(conn, "DELETE FROM notes WHERE ai=%s", (target,))
        deleted_notes = cur.rowcount
        _x(conn, "DELETE FROM round_summaries WHERE ai=%s", (target,))
        _x(conn, "DELETE FROM interval_descriptions WHERE fighter=%s", (target,))
        save_library(conn, target, dict(moves={}, chains={}, move_descriptions={}, chain_descriptions={}))
        reset_libs = 1
    elif target == "all":
        cur = _x(conn, "DELETE FROM notes")
        deleted_notes = cur.rowcount
        _x(conn, "DELETE FROM round_summaries")
        _x(conn, "DELETE FROM interval_descriptions")
        for a in ("A", "B"):
            save_library(conn, a, dict(moves={}, chains={}, move_descriptions={}, chain_descriptions={}))
        reset_libs = 2
    else:
        return dict(ok=False, error="Target must be 'A', 'B', or 'all'")

    conn.commit()
    return dict(ok=True, deleted_notes=deleted_notes, reset_libraries=reset_libs, target=target)


def set_setting(conn, key, val):
    if _x(conn, "SELECT 1 FROM settings WHERE key=%s", (key,)).fetchone():
        _x(conn, "UPDATE settings SET val=%s WHERE key=%s", (val, key))
    else:
        _x(conn, "INSERT INTO settings (key, val) VALUES (%s,%s)", (key, val))
    conn.commit()


def get_setting(conn, key):
    r = _x(conn, "SELECT val FROM settings WHERE key=%s", (key,)).fetchone()
    return r[0] if r else None


def purge_all_database_data(conn, active_jobs=()):
    """Completely purges all data across all tables in the database."""
    _x(conn, "DELETE FROM notes")
    _x(conn, "DELETE FROM round_summaries")
    _x(conn, "DELETE FROM interval_descriptions")
    _x(conn, "DELETE FROM replays")
    _x(conn, "DELETE FROM runs")
    _x(conn, "DELETE FROM library")
    _x(conn, "DELETE FROM job_events")
    _x(conn, "DELETE FROM settings")

    # Keep active jobs if running, delete inactive jobs
    active_set = set(active_jobs)
    if active_set:
        ph = ",".join(["%s"] * len(active_set))
        _x(conn, f"DELETE FROM jobs WHERE id NOT IN ({ph})", tuple(active_set))
    else:
        _x(conn, "DELETE FROM jobs")

    conn.commit()
    return dict(ok=True, message="All database records have been purged successfully.")


