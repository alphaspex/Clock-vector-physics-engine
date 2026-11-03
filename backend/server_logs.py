"""SERVER_LOGS: In-memory circular buffer and real-time event logger for the Fighter Simulation server.
Captures every tiny detail happening on the server: HTTP requests/responses, simulation physics,
AI prompt dispatch & tokens, combat collisions/damage, database queries, and cache computations.
Safe across multiple threads.
"""
import collections, datetime, json, os, threading, time

_LOCK = threading.Lock()
_START_TIME = time.time()
_LOG_COUNTER = 0
_BUFFER_SIZE = 5000
_LOGS = collections.deque(maxlen=_BUFFER_SIZE)

_SERVER_STATE = {
    "activity": "Idle - Awaiting requests",
    "detail": "Server started and ready for commands",
    "job_id": None,
    "last_updated": time.time(),
}


def set_activity(activity, detail=None, job_id=None):
    """Updates the high-level description of what the server is doing right now."""
    with _LOCK:
        _SERVER_STATE["activity"] = activity
        _SERVER_STATE["detail"] = detail or ""
        _SERVER_STATE["job_id"] = job_id
        _SERVER_STATE["last_updated"] = time.time()


def get_activity():
    with _LOCK:
        return dict(_SERVER_STATE)


def emit(level, subsystem, message, **details):
    """Emits a structured log record into the ring buffer and prints to stdout.
    level: DEBUG | INFO | WARN | ERROR
    subsystem: HTTP | SIMULATION | AI_ENGINE | PHYSICS | DATABASE | CACHE | SYSTEM
    """
    global _LOG_COUNTER
    now = time.time()
    iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"
    
    # Clean non-serializable objects from details
    safe_details = {}
    for k, v in details.items():
        try:
            json.dumps(v)
            safe_details[k] = v
        except (TypeError, OverflowError):
            safe_details[k] = str(v)

    with _LOCK:
        _LOG_COUNTER += 1
        entry = {
            "id": _LOG_COUNTER,
            "timestamp": now,
            "iso": iso,
            "level": str(level).upper(),
            "subsystem": str(subsystem).upper(),
            "message": str(message),
            "details": safe_details,
        }
        _LOGS.append(entry)

    # Also log to terminal / stdout so container captures it in Render / Docker
    print(f"[{iso}] [{entry['level']}] [{entry['subsystem']}] {entry['message']}", flush=True)
    return entry


def get_logs(since_id=None, limit=200, level=None, subsystem=None, search=None):
    """Retrieves logs filtered by criteria."""
    limit = max(1, min(int(limit or 200), 1000))
    with _LOCK:
        raw_list = list(_LOGS)

    if since_id is not None:
        try:
            since_id = int(since_id)
            raw_list = [r for r in raw_list if r["id"] > since_id]
        except (ValueError, TypeError):
            pass

    if level:
        lvl = str(level).strip().upper()
        if lvl != "ALL":
            raw_list = [r for r in raw_list if r["level"] == lvl]

    if subsystem:
        sub = str(subsystem).strip().upper()
        if sub != "ALL":
            raw_list = [r for r in raw_list if r["subsystem"] == sub]

    if search:
        s = str(search).strip().lower()
        if s:
            raw_list = [
                r for r in raw_list
                if s in r["message"].lower() or s in r["subsystem"].lower() or s in json.dumps(r["details"]).lower()
            ]

    # Return the most recent entries up to `limit`
    selected = raw_list[-limit:] if len(raw_list) > limit else raw_list
    max_id = _LOG_COUNTER
    return selected, max_id


def clear_logs():
    """Clears the current log buffer."""
    with _LOCK:
        _LOGS.clear()
    emit("INFO", "SYSTEM", "Server log buffer was reset by operator request")
    return True


def get_summary():
    """Returns high-level server stats and what the server is currently doing."""
    with _LOCK:
        total = _LOG_COUNTER
        buf_len = len(_LOGS)
        st = dict(_SERVER_STATE)
    
    uptime = round(time.time() - _START_TIME, 2)
    return {
        "uptime_seconds": uptime,
        "total_logs": total,
        "buffer_size": buf_len,
        "activity": st["activity"],
        "detail": st.get("detail", ""),
        "active_job": st.get("job_id"),
        "status": "online",
    }


# Initial boot log
emit("INFO", "SYSTEM", "Fighter Simulation Server logging engine initialized", buffer_capacity=_BUFFER_SIZE)
