"""ROUNDS: runs practice and fight intervals for the position-tree controller."""
from __future__ import annotations

import concurrent.futures as cf
import math

import db
import observe
import prompts
import sim
import translator
from config import FIGHT_SECONDS, FPS, LIVE_DT, LIVE_FPS, PRACTICE_SECONDS, NOTE_EFFORT, NOTE_MAX_TOKENS


def _conn():
    import os
    from db import connect
    return connect(os.environ.get("DATABASE_URL", "fighter.db"))


def _empty_usage():
    return {"prompt": 0, "completion": 0, "reasoning": 0}


def _add_usage(total, add):
    if not add:
        return
    for key in total:
        total[key] += int(add.get(key, 0) or 0)


def _emit(on_progress, **event):
    if on_progress:
        on_progress(event)


def _decide_once(ask_fn, system, user_tree):
    """Make one action call. Invalid output is rejected completely; no retries."""
    usage = _empty_usage()
    try:
        answer = ask_fn(system, user_tree)
    except Exception as exc:
        return None, usage, f"AI request raised {type(exc).__name__}: {exc}"

    _add_usage(usage, answer.get("usage"))
    if answer.get("error"):
        return None, usage, str(answer.get("error"))

    raw_text = answer.get("text", "")
    tree = translator.parse_tree(raw_text)
    valid, message = translator.validate_tree(tree)
    if not valid:
        return None, usage, message
    return tree, usage, None


def _describe_batch(ask_fn, records):
    """Return validated descriptions, usage and an error; never fabricate text."""
    if not records:
        return [], _empty_usage(), None

    try:
        answer = ask_fn(prompts.batch_description_system(), prompts.batch_description_user(records))
    except Exception as exc:
        return None, _empty_usage(), f"Description request raised {type(exc).__name__}: {exc}"

    usage = _empty_usage()
    _add_usage(usage, answer.get("usage"))
    if answer.get("error"):
        return None, usage, str(answer.get("error"))

    text = answer.get("text", "") or ""
    parsed = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if not line.upper().startswith("INTERVAL") or ":" not in line:
            return None, usage, "Description response contained unexpected text or format"
        left, description = line.split(":", 1)
        try:
            number = int(left.strip().split()[-1])
        except (ValueError, IndexError):
            return None, usage, "Description response contained an invalid interval number"
        if number in parsed or not description.strip():
            return None, usage, "Description response contained a duplicate or empty interval description"
        parsed[number] = description.strip()

    expected = set(range(1, len(records) + 1))
    if set(parsed) != expected:
        return None, usage, f"Expected descriptions for intervals 1-{len(records)}, received {sorted(parsed)}"

    descriptions = [parsed[i] for i in range(1, len(records) + 1)]
    for index, description in enumerate(descriptions, 1):
        word_count = len(description.split())
        if not 15 <= word_count <= 30:
            return None, usage, f"Interval {index} description has {word_count} words; expected 15-30"
    return descriptions, usage, None


def _describe_pending(conn, ask_fn, fighter, kind, job_id, usage, on_progress=None):
    """Describe one pending batch of up to seven intervals for this job."""
    pending = db.get_undescribed_intervals(
        conn, fighter, kind, limit=7, job_id=job_id
    )
    if not pending:
        return True

    _emit(
        on_progress,
        stage="description_started",
        fighter=fighter,
        count=len(pending),
        message=f"Generating physical summaries for {len(pending)} completed intervals.",
    )
    descriptions, batch_usage, error = _describe_batch(ask_fn, pending)
    _add_usage(usage, batch_usage)
    if error:
        _emit(
            on_progress,
            stage="description_error",
            fighter=fighter,
            message=f"Interval summaries could not be generated: {error}",
        )
        return False

    for record, description in zip(pending, descriptions):
        word_count = len(description.split())
        db.update_interval_description(conn, record["id"], description, word_count)
        _emit(
            on_progress,
            stage="description_ready",
            fighter=fighter,
            decision=record.get("interval_idx"),
            frame=record.get("frame"),
            time_sec=record.get("time_sec"),
            text=description,
            word_count=word_count,
            pre_tree=record.get("pre_tree"),
            post_tree=record.get("post_tree"),
        )
    return True



def _translation_status_text(translation):
    """Explain why a valid target did or did not produce new motor targets."""
    arms = (translation or {}).get("arms", {})
    statuses = [f"{side}: {data.get('status', 'unknown')}" for side, data in arms.items()]
    errors = (translation or {}).get("errors", [])
    if errors:
        statuses.extend(errors)
    if not statuses:
        return "The translator returned no arm diagnostics."
    if all(data.get("status") == "unchanged" for data in arms.values()) and arms:
        return "The requested elbow and fist positions match the current pose, so no new motor rotation was needed."
    if all(data.get("status") == "within_same_motor_bin" for data in arms.values()) and arms:
        return "The requested pose rounds to the currently active legal motor angles, so no new motor rotation was sent."
    return "Translator result: " + "; ".join(statuses) + "."


def _build_position_tree(p, spec, state, fighter, events, since):
    frame = observe.torso_frame(p, spec, fighter)
    full_tree = observe.build_fighter_tree(
        p, spec, state.palive, state.lalive, fighter, frame,
        events, since, state.frame, state.frame * LIVE_DT,
    )
    positions_tree = observe.build_fighter_tree(
        p, spec, state.palive, state.lalive, fighter, frame,
        events, since, state.frame, state.frame * LIVE_DT,
        positions_only=True,
    )
    parsed = translator.parse_tree(positions_tree)
    valid, reason = translator.validate_tree(parsed)
    if not valid:
        raise RuntimeError(f"Server-generated current position tree is invalid: {reason}")
    return full_tree, positions_tree, parsed


def practice(
    ask_fn, info, round_summaries, library, interval,
    seconds=PRACTICE_SECONDS, on_progress=None,
    task_text="Stand and keep standing", job_id=None, description_ask_fn=None,
):
    spec, state, runners = sim.new_match(1)
    usage = _empty_usage()
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0
    last_event_time = 0.0
    events = []
    orders = []
    conn = _conn()
    task_memory = db.get_latest_intervals(conn, "A", "practice", limit=7)
    description_ask_fn = description_ask_fn or ask_fn
    intervals_in_batch = 0

    try:
        while state.frame < max_frame:
            decision_idx += 1
            percent = min(100.0, round((state.frame / max_frame) * 100, 1))
            current_tree, pre_tree, pose1 = _build_position_tree(
                state.p, spec, state, 0, events, last_event_time
            )

            system = prompts.practice_system(task_text, memory_records=task_memory)
            _emit(
                on_progress,
                stage="decision_started",
                decision=decision_idx,
                target_decisions=target_decisions,
                frame=state.frame,
                max_frame=max_frame,
                percent=percent,
                fighter="A",
                pre_tree=pre_tree,
                text="AI is choosing the next target pose from the current physical tree.",
            )

            target_tree, decision_usage, decision_error = _decide_once(ask_fn, system, current_tree)
            _add_usage(usage, decision_usage)
            motor_orders = {}
            translation = {"arms": {}, "errors": []}

            if target_tree is not None:
                try:
                    motor_orders, translation = translator.translate_trees(
                        pose1, target_tree, spec, 0, state.p,
                        motor_targets=state.cmd,
                        return_diagnostics=True,
                    )
                    if motor_orders:
                        runners = sim.give_orders(runners, 0, [motor_orders])
                        replay_steps = {
                            name: (list(values), float(power))
                            for name, (values, power) in motor_orders.items()
                        }
                        orders.append({
                            "frame": int(round(state.frame * LIVE_DT * FPS)),
                            "f": 0,
                            "steps": [replay_steps],
                        })
                        decision_text = "Target tree accepted. Python calculated new shoulder/elbow rotations; physics will test the requested pose."
                    else:
                        decision_text = "Target tree accepted, but no new motor rotation was sent. " + _translation_status_text(translation)
                    valid_target = True
                except Exception as exc:
                    translation = {"arms": {}, "errors": [f"{type(exc).__name__}: {exc}"]}
                    decision_text = f"Target tree was valid, but the rotation translator failed: {type(exc).__name__}: {exc}. Existing motor targets remain unchanged."
                    valid_target = False
            else:
                decision_text = f"Target tree rejected: {decision_error}. Existing motor targets remain unchanged."
                valid_target = False

            _emit(
                on_progress,
                stage="decision",
                decision=decision_idx,
                target_decisions=target_decisions,
                frame=state.frame,
                max_frame=max_frame,
                percent=percent,
                fighter="A",
                pre_tree=pre_tree,
                text=decision_text,
                valid=valid_target,
                translation=translation,
                target_tree=(translator.format_position_tree(target_tree) if target_tree is not None else None),
            )

            last_event_time = state.frame * LIVE_DT
            ticks = min(max(1, int(round(interval * LIVE_FPS))), max_frame - state.frame)
            if ticks <= 0:
                break
            for _ in range(ticks):
                state, runners, records = sim.tick(spec, state, runners, dt=LIVE_DT)
                events.extend(records)

            _, post_tree, _ = _build_position_tree(
                state.p, spec, state, 0, events, last_event_time
            )
            db.save_interval_description(
                conn, job_id, "practice", 0, "A", decision_idx,
                state.frame, state.frame * LIVE_DT, "", 0, pre_tree, post_tree,
            )
            _emit(
                on_progress,
                stage="interval_complete",
                decision=decision_idx,
                fighter="A",
                frame=state.frame,
                post_tree=post_tree,
                text=(
                    "Physical interval complete. Its factual 15-30-word summary will appear after this seven-interval batch is processed."
                    if valid_target else
                    "Physical interval complete. No new motor target was accepted; the next decision will use this measured pose."
                ),
            )

            intervals_in_batch += 1
            if intervals_in_batch >= 7:
                _describe_pending(conn, description_ask_fn, "A", "practice", job_id, usage, on_progress)
                task_memory = db.get_latest_intervals(conn, "A", "practice", limit=7)
                intervals_in_batch = 0

        # Flush the final partial batch so no completed interval is left pending.
        while True:
            pending = db.get_undescribed_intervals(conn, "A", "practice", limit=7, job_id=job_id)
            if not pending:
                break
            if not _describe_pending(conn, description_ask_fn, "A", "practice", job_id, usage, on_progress):
                break
            task_memory = db.get_latest_intervals(conn, "A", "practice", limit=7)

        return dict(
            library=library, orders=orders, frames=int(state.frame * LIVE_DT * FPS),
            events=events, usage=usage,
            setup=dict(nf=1, gap=3.0, offset_x=0.0),
            final_p=state.p.copy(), result=state.result,
        )
    finally:
        conn.close()


def fight(
    ask_fns, info, round_summaries, libs, interval,
    seconds=FIGHT_SECONDS, gap=3.0, offset_x=0.0,
    on_progress=None, job_id=None, description_ask_fns=None,
):
    spec, state, runners = sim.new_match(2, gap, offset_x)
    usage = _empty_usage()
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0
    last_event_time = 0.0
    events = []
    orders = []
    conn = _conn()
    fighters = ("A", "B")
    fight_memories = [
        db.get_latest_intervals(conn, fighter, "fight", limit=7)
        for fighter in fighters
    ]
    fight_summaries = [
        db.load_round_summaries(conn, fighter, "fight", limit=100)
        for fighter in fighters
    ]
    description_ask_fns = description_ask_fns or ask_fns
    intervals_in_batch = [0, 0]

    try:
        while state.result is None and state.frame < max_frame:
            decision_idx += 1
            percent = min(100.0, round((state.frame / max_frame) * 100, 1))

            # Both fighters receive trees from this exact shared physical snapshot.
            snapshots = [
                _build_position_tree(state.p, spec, state, fighter, events, last_event_time)
                for fighter in range(2)
            ]
            current_trees = [item[0] for item in snapshots]
            pre_trees = [item[1] for item in snapshots]
            pose1_trees = [item[2] for item in snapshots]
            torso_frames = [observe.torso_frame(state.p, spec, fighter) for fighter in range(2)]
            enemy_trees = [
                observe.build_enemy_tree(state.p, spec, fighter, torso_frames[fighter], palive=state.palive)
                for fighter in range(2)
            ]

            # Publish both pending decisions before waiting for either provider.
            for fighter in range(2):
                _emit(
                    on_progress,
                    stage="decision_started",
                    decision=decision_idx,
                    target_decisions=target_decisions,
                    frame=state.frame,
                    max_frame=max_frame,
                    percent=percent,
                    fighter=fighters[fighter],
                    pre_tree=pre_trees[fighter],
                    text=f"Fighter {fighters[fighter]} is choosing a target pose from the shared fight snapshot.",
                )

            systems = [
                prompts.fight_system(
                    fighters[f], memory_records=fight_memories[f],
                    round_summaries=fight_summaries[f],
                )
                for f in range(2)
            ]
            users = [
                prompts.fight_user(current_trees[f], enemy_trees[f])
                for f in range(2)
            ]

            results = [None, None]
            with cf.ThreadPoolExecutor(max_workers=2) as executor:
                future_to_fighter = {
                    executor.submit(_decide_once, ask_fns[f], systems[f], users[f]): f
                    for f in range(2)
                }
                for future in cf.as_completed(future_to_fighter):
                    fighter = future_to_fighter[future]
                    try:
                        results[fighter] = future.result()
                    except Exception as exc:
                        results[fighter] = (None, _empty_usage(), f"AI future failed: {exc}")

            # Wait for BOTH calls, then apply both accepted target trees before physics advances.
            for fighter in range(2):
                target_tree, decision_usage, decision_error = results[fighter]
                _add_usage(usage, decision_usage)
                motor_orders = {}
                translation = {"arms": {}, "errors": []}
                valid_target = target_tree is not None
                if valid_target:
                    try:
                        motor_orders, translation = translator.translate_trees(
                            pose1_trees[fighter], target_tree, spec, fighter, state.p,
                            motor_targets=state.cmd,
                            return_diagnostics=True,
                        )
                        if motor_orders:
                            runners = sim.give_orders(runners, fighter, [motor_orders])
                            replay_steps = {
                                name: (list(values), float(power))
                                for name, (values, power) in motor_orders.items()
                            }
                            orders.append({
                                "frame": int(round(state.frame * LIVE_DT * FPS)),
                                "f": fighter,
                                "steps": [replay_steps],
                            })
                            decision_text = f"Target tree accepted. Fighter {fighters[fighter]} has new shoulder/elbow targets for the shared physics interval."
                        else:
                            decision_text = f"Target tree accepted, but Fighter {fighters[fighter]} received no new motor rotation. " + _translation_status_text(translation)
                    except Exception as exc:
                        translation = {"arms": {}, "errors": [f"{type(exc).__name__}: {exc}"]}
                        decision_text = f"Fighter {fighters[fighter]}'s target tree was valid, but its rotation translator failed: {type(exc).__name__}: {exc}. Existing targets remain unchanged."
                        valid_target = False
                else:
                    decision_text = f"Target tree rejected for Fighter {fighters[fighter]}: {decision_error}. Existing motor targets remain unchanged."

                _emit(
                    on_progress,
                    stage="decision",
                    decision=decision_idx,
                    target_decisions=target_decisions,
                    frame=state.frame,
                    max_frame=max_frame,
                    percent=percent,
                    fighter=fighters[fighter],
                    pre_tree=pre_trees[fighter],
                    text=decision_text,
                    valid=valid_target,
                    translation=translation,
                    target_tree=(translator.format_position_tree(target_tree) if target_tree is not None else None),
                )

            # Only now, after both fighters have returned, advance the shared physics.
            last_event_time = state.frame * LIVE_DT
            ticks = min(max(1, int(round(interval * LIVE_FPS))), max_frame - state.frame)
            if ticks <= 0:
                break
            for _ in range(ticks):
                if state.result:
                    break
                state, runners, records = sim.tick(spec, state, runners, dt=LIVE_DT)
                events.extend(records)

            # Save both fighters' actual post-physics trees from the same resulting state.
            for fighter in range(2):
                _, post_tree, _ = _build_position_tree(
                    state.p, spec, state, fighter, events, last_event_time
                )
                db.save_interval_description(
                    conn, job_id, "fight", 0, fighters[fighter], decision_idx,
                    state.frame, state.frame * LIVE_DT, "", 0,
                    pre_trees[fighter], post_tree,
                )
                _emit(
                    on_progress,
                    stage="interval_complete",
                    decision=decision_idx,
                    fighter=fighters[fighter],
                    frame=state.frame,
                    post_tree=post_tree,
                    text="Physical interval complete. Its factual summary will appear after the seven-interval batch is processed.",
                )
                intervals_in_batch[fighter] += 1

            # Generate one independent batch for each fighter after seven intervals.
            due = [f for f in range(2) if intervals_in_batch[f] >= 7]
            for fighter in due:
                _describe_pending(
                    conn, description_ask_fns[fighter], fighters[fighter],
                    "fight", job_id, usage, on_progress,
                )
                fight_memories[fighter] = db.get_latest_intervals(
                    conn, fighters[fighter], "fight", limit=7
                )
                intervals_in_batch[fighter] = 0

        # Flush each fighter's remaining partial batch for this job.
        for fighter in range(2):
            while True:
                pending = db.get_undescribed_intervals(
                    conn, fighters[fighter], "fight", limit=7, job_id=job_id
                )
                if not pending:
                    break
                if not _describe_pending(
                    conn, description_ask_fns[fighter], fighters[fighter], "fight",
                    job_id, usage, on_progress,
                ):
                    break
                fight_memories[fighter] = db.get_latest_intervals(
                    conn, fighters[fighter], "fight", limit=7
                )

        # Each fighter gets a strategic summary based only on this fight job's records.
        summaries = ["", ""]
        result_text = state.result or "DRAW"
        for fighter in range(2):
            records = db.get_interval_descriptions(
                conn, job_id=job_id, kind="fight", fighter=fighters[fighter],
                limit=max(1, decision_idx),
            )
            try:
                answer = description_ask_fns[fighter](
                    prompts.round_summary_system(fighters[fighter]),
                    prompts.round_summary_user(records, result_text),
                )
                _add_usage(usage, answer.get("usage"))
                if not answer.get("error"):
                    summaries[fighter] = (answer.get("text") or "").strip()
            except Exception:
                summaries[fighter] = ""

        return dict(
            libs=libs, orders=orders, frames=int(state.frame * LIVE_DT * FPS),
            events=events, usage=usage,
            setup=dict(nf=2, gap=gap, offset_x=offset_x),
            final_p=state.p.copy(), result=state.result,
            round_summaries=summaries,
        )
    finally:
        conn.close()
