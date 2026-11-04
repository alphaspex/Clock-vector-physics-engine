"""Practice and fight orchestration for the predefined demo-action controller.
Live simulation remains 7 FPS. Replay orders are recorded on the 30-FPS
replay timeline so replay.py can compile at 30 FPS without changing live time.
"""
from __future__ import annotations
import concurrent.futures as cf
import math
import os
from config import (
    FIGHT_SECONDS, LIVE_DT, LIVE_FPS, FPS, PRACTICE_SECONDS,
    DEMO_FIGHT_GAP,
)
import sim, observe, prompts, moves, db


def _conn():
    return db.connect(os.environ.get("DATABASE_URL", "fighter.db"))


def _usage0():
    return {"prompt": 0, "completion": 0, "reasoning": 0}


def _add_usage(total, add):
    if not add:
        return
    for key in total:
        total[key] += int(add.get(key, 0) or 0)


def _emit(callback, **event):
    if callback:
        callback(event)


def _tree(p, spec, state, fighter, events, since, positions_only=False):
    frame = observe.torso_frame(p, spec, fighter)
    return observe.build_fighter_tree(
        p, spec, state.palive, state.lalive, fighter, frame,
        events, since, state.frame, state.frame * LIVE_DT,
        positions_only=positions_only,
    )


def _select_action(ask_fn, system, user):
    usage = _usage0()
    try:
        ans = ask_fn(system, user)
    except Exception as exc:
        return "HOLD", usage, f"AI call failed: {type(exc).__name__}: {exc}"
    _add_usage(usage, ans.get("usage"))
    if ans.get("error"):
        return "HOLD", usage, str(ans["error"])
    action = moves.parse_action(ans.get("text", ""))
    if action is None:
        return "HOLD", usage, "AI returned an unknown action; using HOLD for this interval."
    return action, usage, None


def _replay_records(action_name, start_live_frame, fighter):
    """Flatten timed live macro steps onto the 30-FPS replay timeline."""
    records = []
    offset = 0
    for step in moves.get(action_name):
        motor_commands = {
            name: (list(values), float(power))
            for name, (values, power) in step["motors"].items()
        }
        replay_frame = int(round((start_live_frame + offset) * FPS / LIVE_FPS))
        replay_duration = max(1, int(round(int(step["frames"]) * FPS / LIVE_FPS)))
        # Replay uses timed steps too, scaled to 30-FPS ticks. This is essential:
        # otherwise a replay step would wait for motor convergence instead of
        # ending after the same physical duration as the 7-FPS live action.
        records.append({
            "frame": replay_frame,
            "f": fighter,
            "steps": [{"frames": replay_duration, "motors": motor_commands}],
        })
        offset += int(step["frames"])
    return records


def _execute_action(runners, fighter, action_name):
    steps = moves.get(action_name)
    if steps:
        runners = sim.give_orders(runners, fighter, steps)
    return runners, steps


def _describe_batch(ask_fn, records):
    if not records:
        return [], _usage0()
    try:
        ans = ask_fn(prompts.batch_description_system(), prompts.batch_description_user(records))
    except Exception:
        return ["Physical positions were recorded; a factual interval description could not be generated." for _ in records], _usage0()
    usage = _usage0()
    _add_usage(usage, ans.get("usage"))
    if ans.get("error"):
        return ["Physical positions were recorded; a factual interval description could not be generated." for _ in records], usage
    parsed = {}
    for line in (ans.get("text") or "").splitlines():
        if not line.strip().upper().startswith("INTERVAL") or ":" not in line:
            continue
        try:
            idx = int(line.split(":", 1)[0].split()[-1])
            parsed[idx] = line.split(":", 1)[1].strip()
        except (ValueError, IndexError):
            continue
    descriptions = []
    for i in range(1, len(records) + 1):
        desc = parsed.get(i, "")
        count = len(desc.split())
        if not 15 <= count <= 30:
            desc = "The measured body positions changed during this interval; inspect the before and after trees for the exact physical result."
        descriptions.append(desc)
    return descriptions, usage


def _flush_descriptions(conn, ask_fn, fighter, kind, job_id, usage, on_progress):
    records = db.get_undescribed_intervals(conn, fighter, kind, limit=7, job_id=job_id)
    if not records:
        return []
    descriptions, desc_usage = _describe_batch(ask_fn, records)
    _add_usage(usage, desc_usage)
    for rec, desc in zip(records, descriptions):
        db.update_interval_description(conn, rec["id"], desc, len(desc.split()))
        _emit(on_progress, stage="description_ready", fighter=fighter,
              decision=rec.get("interval_idx"), text=desc,
              word_count=len(desc.split()), pre_tree=rec.get("pre_tree"),
              post_tree=rec.get("post_tree"))
    return descriptions


def _record_interval(conn, job_id, kind, fighter, decision, state, pre_tree, post_tree):
    db.save_interval_description(
        conn, job_id, kind, 0, fighter, decision, state.frame,
        state.frame * LIVE_DT, "", 0, pre_tree, post_tree,
    )


def practice(ask_fn, info, round_summaries, library, interval,
             seconds=PRACTICE_SECONDS, on_progress=None,
             task_text="Stand and keep standing", job_id=None):
    spec, state, runners = sim.new_match(1)
    usage = _usage0()
    max_live_ticks = max(1, int(round(seconds * LIVE_FPS)))
    ticks_per_interval = max(1, int(round(interval * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(max_live_ticks / ticks_per_interval)))
    decision = 0
    since = 0.0
    events, replay_orders = [], []
    conn = _conn()
    memory = db.get_latest_intervals(conn, "A", "practice", limit=7)
    pending_count = 0
    try:
        while state.frame < max_live_ticks:
            decision += 1
            pre_full = _tree(state.p, spec, state, 0, events, since, False)
            pre_pos = _tree(state.p, spec, state, 0, events, since, True)
            _emit(on_progress, stage="decision_started", decision=decision,
                  target_decisions=target_decisions, frame=state.frame,
                  max_frame=max_live_ticks, percent=round(state.frame / max_live_ticks * 100, 1),
                  fighter="A", text="AI is selecting a predefined physical action.")
            system = prompts.practice_system(task_text, pre_full, memory)
            action, call_usage, error = _select_action(ask_fn, system, pre_full)
            _add_usage(usage, call_usage)
            start_frame = state.frame
            runners, steps = _execute_action(runners, 0, action)
            replay_orders.extend(_replay_records(action, start_frame, 0))
            action_info = moves.info(action)
            _emit(on_progress, stage="decision", decision=decision,
                  target_decisions=target_decisions, frame=state.frame,
                  max_frame=max_live_ticks, percent=round(state.frame / max_live_ticks * 100, 1),
                  fighter="A", action=action, text=f"Selected {action}: {action_info['description']}",
                  valid=error is None, error=error, pre_tree=pre_pos)

            since = state.frame * LIVE_DT
            ticks = min(ticks_per_interval, max_live_ticks - state.frame)
            for _ in range(ticks):
                state, runners, rec = sim.tick(spec, state, runners, dt=LIVE_DT)
                events.extend(rec)
            post_pos = _tree(state.p, spec, state, 0, events, since, True)
            _record_interval(conn, job_id, "practice", "A", decision, state, pre_pos, post_pos)
            pending_count += 1
            _emit(on_progress, stage="interval_complete", decision=decision,
                  fighter="A", frame=state.frame, post_tree=post_pos,
                  text=f"Executed {action}; physical result measured. Summary is generated in batches of seven.")
            if pending_count >= 7:
                _flush_descriptions(conn, ask_fn, "A", "practice", job_id, usage, on_progress)
                memory = db.get_latest_intervals(conn, "A", "practice", limit=7)
                pending_count = 0

        if pending_count:
            _flush_descriptions(conn, ask_fn, "A", "practice", job_id, usage, on_progress)
            memory = db.get_latest_intervals(conn, "A", "practice", limit=7)
        return dict(
            library=library, orders=replay_orders,
            frames=int(round(state.frame * FPS / LIVE_FPS)),
            events=events, usage=usage,
            setup=dict(nf=1, gap=3.0, offset_x=0.0),
            final_p=state.p.copy(), result=state.result,
        )
    finally:
        conn.close()


def fight(ask_fns, info, round_summaries, libs, interval,
          seconds=FIGHT_SECONDS, gap=DEMO_FIGHT_GAP, offset_x=0.0,
          on_progress=None, job_id=None):
    spec, state, runners = sim.new_match(2, gap, offset_x)
    usage = _usage0()
    max_live_ticks = max(1, int(round(seconds * LIVE_FPS)))
    ticks_per_interval = max(1, int(round(interval * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(max_live_ticks / ticks_per_interval)))
    decision, since = 0, 0.0
    events, replay_orders = [], []
    conn = _conn()
    fighters = ("A", "B")
    memories = [db.get_latest_intervals(conn, f, "fight", limit=7) for f in fighters]
    summaries = [db.load_round_summaries(conn, f, "fight", limit=100) for f in fighters]
    pending = [0, 0]
    try:
        with cf.ThreadPoolExecutor(max_workers=2) as executor:
            while state.result is None and state.frame < max_live_ticks:
                decision += 1
                # Both prompts use the same pre-physics snapshot.
                trees = [_tree(state.p, spec, state, f, events, since, False) for f in range(2)]
                pre_trees = [_tree(state.p, spec, state, f, events, since, True) for f in range(2)]
                enemy_trees = [observe.build_enemy_tree(
                    state.p, spec, f, observe.torso_frame(state.p, spec, f), palive=state.palive
                ) for f in range(2)]
                for f in range(2):
                    _emit(on_progress, stage="decision_started", decision=decision,
                          target_decisions=target_decisions, frame=state.frame,
                          max_frame=max_live_ticks,
                          percent=round(state.frame / max_live_ticks * 100, 1),
                          fighter=fighters[f], text=f"Fighter {fighters[f]} is selecting an action.")
                systems = [prompts.fight_system(fighters[f], trees[f], enemy_trees[f], memories[f], summaries[f]) for f in range(2)]
                futures = [executor.submit(_select_action, ask_fns[f], systems[f],
                                           "MY CURRENT TREE:\n" + trees[f] +
                                           "\n\nENEMY TREE (READ ONLY):\n" + enemy_trees[f]) for f in range(2)]
                selected = [future.result() for future in futures]
                # Apply both actions from the same snapshot before stepping physics.
                for f in range(2):
                    action, call_usage, error = selected[f]
                    _add_usage(usage, call_usage)
                    start_frame = state.frame
                    runners, _ = _execute_action(runners, f, action)
                    replay_orders.extend(_replay_records(action, start_frame, f))
                    item = moves.info(action)
                    _emit(on_progress, stage="decision", decision=decision,
                          target_decisions=target_decisions, frame=state.frame,
                          max_frame=max_live_ticks,
                          percent=round(state.frame / max_live_ticks * 100, 1),
                          fighter=fighters[f], action=action,
                          text=f"Selected {action}: {item['description']}",
                          valid=error is None, error=error, pre_tree=pre_trees[f])

                since = state.frame * LIVE_DT
                ticks = min(ticks_per_interval, max_live_ticks - state.frame)
                for _ in range(ticks):
                    if state.result:
                        break
                    state, runners, rec = sim.tick(spec, state, runners, dt=LIVE_DT)
                    events.extend(rec)

                for f in range(2):
                    post_pos = _tree(state.p, spec, state, f, events, since, True)
                    _record_interval(conn, job_id, "fight", fighters[f], decision, state, pre_trees[f], post_pos)
                    pending[f] += 1
                    _emit(on_progress, stage="interval_complete", decision=decision,
                          fighter=fighters[f], frame=state.frame, post_tree=post_pos,
                          text=f"Executed the selected action; physical result measured.")
                for f in range(2):
                    if pending[f] >= 7:
                        _flush_descriptions(conn, ask_fns[f], fighters[f], "fight", job_id, usage, on_progress)
                        memories[f] = db.get_latest_intervals(conn, fighters[f], "fight", limit=7)
                        pending[f] = 0

        for f in range(2):
            if pending[f]:
                _flush_descriptions(conn, ask_fns[f], fighters[f], "fight", job_id, usage, on_progress)
                memories[f] = db.get_latest_intervals(conn, fighters[f], "fight", limit=7)

        result_text = state.result or "DRAW"
        round_sums = ["", ""]
        for f in range(2):
            records = db.get_interval_descriptions(conn, job_id=job_id, kind="fight", fighter=fighters[f], limit=max(1, decision))
            ans = ask_fns[f](prompts.round_summary_system(fighters[f]), prompts.round_summary_user(records, result_text))
            round_sums[f] = (ans.get("text") or "").strip()
            _add_usage(usage, ans.get("usage"))
        return dict(
            libs=libs, orders=replay_orders,
            frames=int(round(state.frame * FPS / LIVE_FPS)),
            events=events, usage=usage,
            setup=dict(nf=2, gap=gap, offset_x=offset_x),
            final_p=state.p.copy(), result=state.result,
            round_summaries=round_sums,
        )
    finally:
        conn.close()
