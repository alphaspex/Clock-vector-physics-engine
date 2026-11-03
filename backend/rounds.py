"""ROUNDS: plays a practice round or a fight round. Does not know any API or database: the AI is a function `ask`.
ask(system, user) -> dict(text, usage, error)
practice(ask, info, notes, library, interval, seconds)          OUT: dict(library, orders, frames, events, usage, setup, result, final_p)
fight(asks, info, notes, libs, interval, seconds, gap, offset_x) OUT: same, with libs[2]; both AIs are asked at the same time, the game waits
An order = dict(frame, f, text, steps): exactly what a replay needs."""
import concurrent.futures as cf, math
from config import *
import sim, moves, observe, prompts
try:
    import server_logs
except ImportError:
    server_logs = None


def _plain(steps):
    return [{m: [list(v[0]), v[1]] for m, v in s.items()} for s in steps]


def _decide(ans, lib, info):
    parsed = moves.parse(ans.get("text") or "", info)
    lib2 = moves.merge(lib, parsed)
    steps, e2 = moves.compile_do(parsed["do"], lib2)
    return lib2, _plain(steps), parsed["errors"] + e2


def _add(u, a):
    for k in u: u[k] += (a or {}).get(k, 0)


def practice(ask, info, notes, library, interval, seconds=PRACTICE_SECONDS, on_progress=None):
    spec, st, rn = sim.new_match(1)
    system, lib, orders, events, errs, last, usage = prompts.practice_system(info, notes), library, [], [], [], 0.0, dict(prompt=0, completion=0, reasoning=0)
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0

    while st.frame < max_frame:
        decision_idx += 1
        pct = min(100.0, round((st.frame / max_frame) * 100, 1))
        if on_progress:
            on_progress(dict(stage="decision", decision=decision_idx, target_decisions=target_decisions,
                             frame=st.frame, max_frame=max_frame, percent=pct))

        obs = observe.observe(st.p, spec, st.palive, st.cmd, 0, st.frame * LIVE_DT, events, last, enemy=False)
        ans = ask(system, prompts.turn_message(obs, errs, lib)); _add(usage, ans.get("usage"))
        errs = []
        if ans.get("error"):
            errs = [f"AI call failed: {ans['error']}"]
            if on_progress:
                on_progress(dict(stage="ai_error", decision=decision_idx, error=ans["error"]))
        else:
            lib, steps, errs = _decide(ans, lib, info)
            replay_frame = int(round(st.frame * LIVE_DT * FPS))
            orders.append(dict(frame=replay_frame, f=0, text=ans["text"][:800], steps=steps))
            rn = sim.give_orders(rn, 0, steps)
            if server_logs:
                server_logs.emit("DEBUG", "SIMULATION", f"Practice live frame {st.frame}: compiled {len(steps)} motor actuation steps", errors=errs)

        last = st.frame * LIVE_DT
        # Step live physics at 7 FPS until next decision point or max_frame
        ticks = min(int(round(interval * LIVE_FPS)), max_frame - st.frame)
        if ticks <= 0:
            break
        for _ in range(ticks):
            st, rn, rec = sim.tick(spec, st, rn, dt=LIVE_DT); events += rec
            if server_logs and rec:
                for r in rec:
                    server_logs.emit("INFO", "PHYSICS", f"Practice Live Frame {st.frame} impact: {r.get('event', 'touch')}", **r)

        pct = min(100.0, round((st.frame / max_frame) * 100, 1))
        if on_progress:
            on_progress(dict(stage="physics", decision=decision_idx, target_decisions=target_decisions,
                             frame=st.frame, max_frame=max_frame, percent=pct))

    total_replay_frames = int(round(st.frame * LIVE_DT * FPS))
    return dict(library=lib, orders=orders, frames=total_replay_frames, events=events, usage=usage, result=None,
                setup=dict(nf=1, gap=3.0, offset_x=0.0), final_p=st.p.copy())


def fight(asks, info, notes, libs, interval, seconds=FIGHT_SECONDS, gap=3.0, offset_x=0.0, on_progress=None):
    spec, st, rn = sim.new_match(2, gap, offset_x)
    systems = [prompts.fight_system(info, notes[f], "AB"[f]) for f in range(2)]
    libs, orders, events, errs, last, usage = list(libs), [], [], [[], []], 0.0, dict(prompt=0, completion=0, reasoning=0)
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0

    with cf.ThreadPoolExecutor(2) as ex:
        while st.result is None and st.frame < max_frame:
            decision_idx += 1
            pct = min(100.0, round((st.frame / max_frame) * 100, 1))
            if on_progress:
                on_progress(dict(stage="decision", decision=decision_idx, target_decisions=target_decisions,
                                 frame=st.frame, max_frame=max_frame, percent=pct))

            obs = [observe.observe(st.p, spec, st.palive, st.cmd, f, st.frame * LIVE_DT, events, last, enemy=True) for f in range(2)]
            futs = [ex.submit(ask, systems[f], prompts.turn_message(obs[f], errs[f], libs[f])) for f, ask in enumerate(asks)]
            answers = [x.result() for x in futs]               # the game waits for both AIs
            for f, ans in enumerate(answers):
                _add(usage, ans.get("usage")); errs[f] = []
                if ans.get("error"):
                    errs[f] = [f"AI call failed: {ans['error']}"]
                    if on_progress:
                        on_progress(dict(stage="ai_error", decision=decision_idx, fighter="AB"[f], error=ans["error"]))
                    continue
                libs[f], steps, errs[f] = _decide(ans, libs[f], info)
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
                if st.result is not None: break
                st, rn, rec = sim.tick(spec, st, rn, dt=LIVE_DT); events += rec
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
    return dict(libs=libs, orders=orders, frames=total_replay_frames, events=events, usage=usage, result=st.result,
                setup=dict(nf=2, gap=gap, offset_x=offset_x), final_p=st.p.copy())

