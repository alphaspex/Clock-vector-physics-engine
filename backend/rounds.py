"""ROUNDS: plays a practice round or a fight round. Does not know any API or database: the AI is a function `ask`.
ask(system, user) -> dict(text, usage, error)
practice(ask, info, notes, library, interval, seconds)          OUT: dict(library, orders, frames, events, usage, setup, result, final_p)
fight(asks, info, notes, libs, interval, seconds, gap, offset_x) OUT: same, with libs[2]; both AIs are asked at the same time, the game waits
An order = dict(frame, f, text, steps): exactly what a replay needs."""
import concurrent.futures as cf, math
from config import *
import sim, moves, observe, prompts


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
    max_frame = max(1, int(round(seconds * FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0

    while st.frame < max_frame:
        decision_idx += 1
        pct = min(100.0, round((st.frame / max_frame) * 100, 1))
        if on_progress:
            on_progress(dict(stage="decision", decision=decision_idx, target_decisions=target_decisions,
                             frame=st.frame, max_frame=max_frame, percent=pct))

        obs = observe.observe(st.p, spec, st.palive, st.cmd, 0, st.frame * DT, events, last, enemy=False)
        ans = ask(system, prompts.turn_message(obs, errs, lib)); _add(usage, ans.get("usage"))
        errs = []
        if ans.get("error"):
            errs = [f"AI call failed: {ans['error']}"]
            if on_progress:
                on_progress(dict(stage="ai_error", decision=decision_idx, error=ans["error"]))
        else:
            lib, steps, errs = _decide(ans, lib, info)
            orders.append(dict(frame=st.frame, f=0, text=ans["text"][:800], steps=steps))
            rn = sim.give_orders(rn, 0, steps)

        last = st.frame * DT
        # Step physics until next decision point or max_frame
        ticks = min(int(interval * FPS), max_frame - st.frame)
        if ticks <= 0:
            break
        for _ in range(ticks):
            st, rn, rec = sim.tick(spec, st, rn); events += rec

        pct = min(100.0, round((st.frame / max_frame) * 100, 1))
        if on_progress:
            on_progress(dict(stage="physics", decision=decision_idx, target_decisions=target_decisions,
                             frame=st.frame, max_frame=max_frame, percent=pct))

    return dict(library=lib, orders=orders, frames=st.frame, events=events, usage=usage, result=None,
                setup=dict(nf=1, gap=3.0, offset_x=0.0), final_p=st.p.copy())


def fight(asks, info, notes, libs, interval, seconds=FIGHT_SECONDS, gap=3.0, offset_x=0.0, on_progress=None):
    spec, st, rn = sim.new_match(2, gap, offset_x)
    systems = [prompts.fight_system(info, notes[f], "AB"[f]) for f in range(2)]
    libs, orders, events, errs, last, usage = list(libs), [], [], [[], []], 0.0, dict(prompt=0, completion=0, reasoning=0)
    max_frame = max(1, int(round(seconds * FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0

    with cf.ThreadPoolExecutor(2) as ex:
        while st.result is None and st.frame < max_frame:
            decision_idx += 1
            pct = min(100.0, round((st.frame / max_frame) * 100, 1))
            if on_progress:
                on_progress(dict(stage="decision", decision=decision_idx, target_decisions=target_decisions,
                                 frame=st.frame, max_frame=max_frame, percent=pct))

            obs = [observe.observe(st.p, spec, st.palive, st.cmd, f, st.frame * DT, events, last, enemy=True) for f in range(2)]
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
                orders.append(dict(frame=st.frame, f=f, text=ans["text"][:800], steps=steps))
                rn = sim.give_orders(rn, f, steps)

            last = st.frame * DT
            ticks = min(int(interval * FPS), max_frame - st.frame)
            if ticks <= 0:
                break
            for _ in range(ticks):
                if st.result is not None: break
                st, rn, rec = sim.tick(spec, st, rn); events += rec

            pct = min(100.0, round((st.frame / max_frame) * 100, 1))
            if on_progress:
                on_progress(dict(stage="physics", decision=decision_idx, target_decisions=target_decisions,
                                 frame=st.frame, max_frame=max_frame, result=st.result, percent=pct))

    return dict(libs=libs, orders=orders, frames=st.frame, events=events, usage=usage, result=st.result,
                setup=dict(nf=2, gap=gap, offset_x=offset_x), final_p=st.p.copy())

