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
    conn.commit()


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


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


def list_runs(conn, kind):
    rows = _x(conn, "SELECT n, created, result, frames, info FROM runs WHERE kind=%s ORDER BY n", (kind,)).fetchall()
    return [dict(n=r[0], created=r[1], result=r[2] or None, frames=r[3], info=json.loads(r[4])) for r in rows]
