"""ROUNDS: plays a practice round or a fight round.
ask(system, user) -> dict(text, usage, error)
practice(ask, info, notes, library, interval, seconds)          OUT: dict(library, orders, frames, events, usage, setup, result, final_p, interval_descriptions, round_summary)
fight(asks, info, notes, libs, interval, seconds, gap, offset_x) OUT: same, with libs[2]; both AIs are asked at the same time
"""
import concurrent.futures as cf
import math
import re
from config import *
import sim, moves, observe, prompts, practice_eval, translator
try:
    import server_logs
except ImportError:
    server_logs = None


def _plain(steps):
    return [{m: [list(v[0]), v[1]] for m, v in s.items()} for s in steps]


def _decide(ans, lib, info, p=None, spec=None, f=0, fr=None):
    raw_text = ans.get("text") or ""
    thinking_text, word_count, clean_text, think_err = moves.extract_thinking(raw_text)
    # Pass mastered moves for chain validation
    mastered = lib.get("mastered_moves", {})
    parsed = moves.parse(clean_text, info, mastered_moves=mastered)
    lib2 = moves.merge(lib, parsed)
    steps, e2 = moves.compile_do(parsed["do"], lib2)
    
    # Translate position-based steps into motor rotations using IK
    if p is not None and spec is not None and fr is not None:
        steps = [translator.translate_step(s, p, spec, f, fr) for s in steps]
        
    errs = list(parsed["errors"]) + e2
    if think_err:
        errs.append(think_err)
    return lib2, _plain(steps), errs, thinking_text, word_count


def _add(u, a):
    for k in u:
        u[k] += (a or {}).get(k, 0)


def practice(ask, info, notes, library, interval, seconds=PRACTICE_SECONDS, on_progress=None):
    # Determine active goal (default to recovery)
    goal_id = library.get("active_goal", "recovery")
    spec, st, rn = sim.new_match(1)
    
    # Set initial pose for the goal
    st = practice_eval.get_initial_pose(goal_id, spec)
    
    system = prompts.practice_system(info, notes)
    lib, orders, events, errs, last = library, [], [], [], 0.0
    usage = dict(prompt=0, completion=0, reasoning=0)
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0
    interval_history = []
    last_transitions = None
    last_command = None

    while st.frame < max_frame:
        decision_idx += 1
        pct = min(100.0, round((st.frame / max_frame) * 100, 1))

        obs = observe.observe(
            st.p, st.v, spec, st.palive, st.lalive, st.cmd, st, 0,
            st.frame * LIVE_DT, events, since=last, enemy=False,
            total_seconds=seconds, errors=errs, library=lib,
            interval_history=interval_history[-5:],
            transitions=last_transitions,
        )

        fr = observe.torso_frame(st.p, spec, 0)
        ans = ask(system, obs)
        _add(usage, ans.get("usage"))
        errs = []

        if ans.get("error"):
            errs = [f"AI call failed: {ans['error']}"]
            if on_progress:
                on_progress(dict(stage="ai_error", decision=decision_idx, error=ans["error"]))
        else:
            lib, steps, errs, thinking_text, wc = _decide(ans, lib, info, p=st.p, spec=spec, f=0, fr=fr)
            
            # --- MOTOR KNOWLEDGE EXTRACTION ---
            # Extract motor knowledge findings if the AI used the expected format
            # Format: MOTOR KNOWLEDGE: AXIS [axis] DIRECTION [dir] FINDING [finding]
            raw_text = (ans.get("text") or "").strip()
            findings = re.findall(r"MOTOR KNOWLEDGE:\s*AXIS\s+(.*?)\s+DIRECTION\s+(.*?)\s+FINDING\s+(.*)", raw_text, re.I)
            if findings:
                knowledge = lib.get("motor_knowledge", {})
                for axis, direction, finding in findings:
                    axis = axis.strip().lower()
                    direction = direction.strip().lower()
                    finding = finding.strip()
                    knowledge.setdefault(axis, {}).setdefault(direction, []).append(finding)
                    # Deduplicate and limit
                    knowledge[axis][direction] = list(dict.fromkeys(knowledge[axis][direction]))[-5:]
                lib["motor_knowledge"] = knowledge

            display_text = thinking_text if thinking_text else raw_text
            is_fallback = not bool(thinking_text)
            if thinking_text:
                interval_history.append(thinking_text)
            elif raw_text:
                interval_history.append(raw_text)

            if on_progress:
                on_progress(dict(
                    stage="decision", decision=decision_idx, target_decisions=target_decisions,
                    frame=st.frame, max_frame=max_frame, percent=pct,
                    thinking=display_text, raw_text=raw_text, is_fallback=is_fallback,
                    word_count=wc if not is_fallback else len(display_text.split()), fighter="A",
                    time_sec=round(st.frame * LIVE_DT, 2),
                ))

            replay_frame = int(round(st.frame * LIVE_DT * FPS))
            orders.append(dict(frame=replay_frame, f=0, text=ans["text"][:800], steps=steps))
            rn = sim.give_orders(rn, 0, steps)
            last_command = raw_text[:200] + "..." if len(raw_text) > 200 else raw_text
            if server_logs:
                server_logs.emit("DEBUG", "SIMULATION", f"Practice live frame {st.frame}: compiled {len(steps)} motor actuation steps", errors=errs)

        # CAPTURE BEFORE STATE
        fr_before = observe.torso_frame(st.p, spec, 0)
        before_data = dict(
            p=st.p.copy(), v=st.v.copy(), spec=spec, palive=st.palive.copy(), 
            lalive=st.lalive.copy(), f=0, fr=fr_before, events=list(events), 
            since=last, frame=st.frame, sim_time=st.frame * LIVE_DT
        )

        last = st.frame * LIVE_DT
        ticks = min(int(round(interval * LIVE_FPS)), max_frame - st.frame)
        if ticks <= 0:
            break
        for _ in range(ticks):
            st, rn, rec = sim.tick(spec, st, rn, dt=LIVE_DT)
            events += rec
            if server_logs and rec:
                for r in rec:
                    server_logs.emit("INFO", "PHYSICS", f"Practice Live Frame {st.frame} impact: {r.get('event', 'touch')}", **r)

        # CAPTURE AFTER STATE
        fr_after = observe.torso_frame(st.p, spec, 0)
        after_data = dict(
            p=st.p.copy(), v=st.v.copy(), spec=spec, palive=st.palive.copy(), 
            lalive=st.lalive.copy(), f=0, fr=fr_after, events=list(events), 
            since=last, frame=st.frame, sim_time=st.frame * LIVE_DT
        )
        
        if last_command:
            last_transitions = dict(command=last_command, before=before_data, after=after_data)

        pct = min(100.0, round((st.frame / max_frame) * 100, 1))
        if on_progress:
            on_progress(dict(stage="physics", decision=decision_idx, target_decisions=target_decisions,
                             frame=st.frame, max_frame=max_frame, percent=pct))

    total_replay_frames = int(round(st.frame * LIVE_DT * FPS))

    # Evaluate practice result via physical report for AI summary
    phys_report = practice_eval.get_physical_report(goal_id, st, spec, 0)
    
    # Generate end-of-round summary from full round interval descriptions
    # AI will decide success/failure based on telemetry provided in phys_report
    round_summary = ""
    ai_success = False
    
    if interval_history:
        try:
            sum_ans = ask(prompts.round_summary_system(), prompts.round_summary_user(interval_history, phys_report))
            _add(usage, sum_ans.get("usage"))
            round_summary = sum_ans.get("text", "").strip()
            
            # Parse AI judgment: RESULT: SUCCESS or RESULT: FAILED
            if "RESULT: SUCCESS" in round_summary.upper():
                ai_success = True
        except Exception as e:
            round_summary = f"Summary generation failed: {repr(e)}"

    # Update mastery based on AI judgment
    mastered_moves = lib.get("mastered_moves", {})
    target_move_name = goal_id
    move_status = mastered_moves.get(target_move_name, {"streak": 0, "mastered": False})
    
    if ai_success:
        move_status["streak"] = 1
        move_status["mastered"] = True
    else:
        move_status["streak"] = 0
        move_status["mastered"] = False
        
    mastered_moves[target_move_name] = move_status
    lib["mastered_moves"] = mastered_moves

    return dict(
        library=lib, orders=orders, frames=total_replay_frames, events=events, usage=usage, result=None,
        setup=dict(nf=1, gap=3.0, offset_x=0.0), final_p=st.p.copy(),
        interval_descriptions=interval_history, round_summary=round_summary,
        eval_result={"success": ai_success, "diagnostics": phys_report}
    )


def fight(asks, info, notes, libs, interval, seconds=FIGHT_SECONDS, gap=3.0, offset_x=0.0, on_progress=None):
    spec, st, rn = sim.new_match(2, gap, offset_x)
    systems = [prompts.fight_system(info, notes[f], "AB"[f]) for f in range(2)]
    libs, orders, events = list(libs), [], []
    errs = [[], []]
    last = 0.0
    usage = dict(prompt=0, completion=0, reasoning=0)
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0
    interval_histories = [[], []]

    with cf.ThreadPoolExecutor(2) as ex:
        while st.result is None and st.frame < max_frame:
            decision_idx += 1
            pct = min(100.0, round((st.frame / max_frame) * 100, 1))

            obs = [
                observe.observe(
                    st.p, st.v, spec, st.palive, st.lalive, st.cmd, st, f,
                    st.frame * LIVE_DT, events, since=last, enemy=True,
                    total_seconds=seconds, errors=errs[f], library=libs[f],
                    interval_history=interval_histories[f][-5:],
                )
                for f in range(2)
            ]

            futs = [ex.submit(ask, systems[f], obs[f]) for f, ask in enumerate(asks)]
            answers = [x.result() for x in futs]

            for f, ans in enumerate(answers):
                _add(usage, ans.get("usage"))
                errs[f] = []
                if ans.get("error"):
                    errs[f] = [f"AI call failed: {ans['error']}"]
                    if on_progress:
                        on_progress(dict(stage="ai_error", decision=decision_idx, fighter="AB"[f], error=ans["error"]))
                    continue

                fr_f = observe.torso_frame(st.p, spec, f)
                libs[f], steps, errs[f], thinking_text, wc = _decide(ans, libs[f], info, p=st.p, spec=spec, f=f, fr=fr_f)
                raw_text = (ans.get("text") or "").strip()
                display_text = thinking_text if thinking_text else raw_text
                is_fallback = not bool(thinking_text)
                if thinking_text:
                    interval_histories[f].append(thinking_text)
                elif raw_text:
                    interval_histories[f].append(raw_text)

                if on_progress:
                    on_progress(dict(
                        stage="decision", decision=decision_idx, target_decisions=target_decisions,
                        frame=st.frame, max_frame=max_frame, percent=pct,
                        thinking=display_text, raw_text=raw_text, is_fallback=is_fallback,
                        word_count=wc if not is_fallback else len(display_text.split()), fighter="AB"[f],
                        time_sec=round(st.frame * LIVE_DT, 2),
                    ))

                replay_frame = int(round(st.frame * LIVE_DT * FPS))
                orders.append(dict(frame=replay_frame, f=f, text=ans["text"][:800], steps=steps))
                rn = sim.give_orders(rn, f, steps)
                if server_logs:
                    server_logs.emit("DEBUG", "SIMULATION", f"Fight Live Frame {st.frame}: Fighter {'AB'[f]} ordered {len(steps)} steps", errors=errs[f])

            last = st.frame * LIVE_DT
            ticks = min(int(round(interval * LIVE_FPS)), max_frame - st.frame)
            if ticks <= 0:
                break
            for _ in range(ticks):
                if st.result is not None:
                    break
                st, rn, rec = sim.tick(spec, st, rn, dt=LIVE_DT)
                events += rec
                if server_logs and rec:
                    for r in rec:
                        server_logs.emit("INFO", "PHYSICS", f"Fight Live Frame {st.frame} combat impact: {r.get('event', 'touch')}", **r)

            if server_logs and st.result:
                server_logs.emit("WARN", "RULES", f"Fight match determined at frame {st.frame}! Winner/Result: {st.result}")

            pct = min(100.0, round((st.frame / max_frame) * 100, 1))
            if on_progress:
                on_progress(dict(stage="physics", decision=decision_idx, target_decisions=target_decisions,
                                 frame=st.frame, max_frame=max_frame, result=st.result, percent=pct))

    total_replay_frames = int(round(st.frame * LIVE_DT * FPS))

    # Generate separate round summaries for Fighter A and Fighter B concurrently
    round_summaries = ["", ""]
    def _gen_summary(f):
        if not interval_histories[f]:
            return f, "", {}
        try:
            sum_ans = asks[f](prompts.round_summary_system(), prompts.round_summary_user(interval_histories[f]))
            return f, sum_ans.get("text", "").strip(), sum_ans.get("usage", {})
        except Exception as e:
            return f, f"Summary generation failed: {repr(e)}", {}

    with cf.ThreadPoolExecutor(2) as ex:
        sum_futs = [ex.submit(_gen_summary, f) for f in range(2)]
        for fut in sum_futs:
            f, text, u = fut.result()
            round_summaries[f] = text
            _add(usage, u)

    return dict(
        libs=libs, orders=orders, frames=total_replay_frames, events=events, usage=usage, result=st.result,
        setup=dict(nf=2, gap=gap, offset_x=offset_x), final_p=st.p.copy(),
        interval_descriptions=interval_histories, round_summaries=round_summaries,
    )
