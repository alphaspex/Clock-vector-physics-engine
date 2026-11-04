"""ROUNDS: plays a practice round or a fight round.
This is the core orchestrator for the AI position-tree control system.
"""
import concurrent.futures as cf
import math
import time
from config import *
import sim, observe, prompts, translator, db

def _conn():
    import os
    from db import connect
    dsn = os.environ.get("DATABASE_URL", "fighter.db")
    return connect(dsn)

def _add_usage(total, add):
    if not add: return
    for k in total:
        total[k] += add.get(k, 0)

def _describe_batch(ask_fn, records):
    """Generates descriptions for a batch of interval records."""
    if not records:
        return []
    system = prompts.batch_description_system()
    user = prompts.batch_description_user(records)
    ans = ask_fn(system, user)
    text = ans.get("text", "")
    
    # Parse descriptions: INTERVAL 1: [Description]
    descriptions = []
    for line in text.split('\n'):
        if line.upper().startswith("INTERVAL"):
            try:
                desc = line.split(":", 1)[1].strip()
                descriptions.append(desc)
            except:
                pass
    
    # Validation: exactly N descriptions, each 15-30 words
    final_descs = []
    for i in range(len(records)):
        d = descriptions[i] if i < len(descriptions) else "Factual physical observation of body movement and posture changes during the interval."
        words = d.split()
        if not (15 <= len(words) <= 30):
            # Normalization/Clipping
            if len(words) < 15:
                d += " The fighter maintains its posture while observing the environment for any potential threats or opportunities."
            words = d.split()[:30]
            d = " ".join(words)
        final_descs.append(d)
    
    return final_descs, ans.get("usage")

def _decide_once(ask_fn, system, current_tree):
    """Makes exactly ONE AI decision call without retries. Continues simulation even if error or invalid."""
    usage = dict(prompt=0, completion=0, reasoning=0)
    ans = ask_fn(system, current_tree)
    _add_usage(usage, ans.get("usage"))
    
    if ans.get("error"):
        return None, usage, 1, ""
        
    raw_text = ans.get("text", "")
    tree_dict = translator.parse_tree(raw_text)
    is_valid, msg = translator.validate_tree(tree_dict)
    
    if is_valid:
        return tree_dict, usage, 1, raw_text
        
    return tree_dict if tree_dict else None, usage, 1, raw_text

def practice(ask_fn, info, round_summaries, library, interval, seconds=PRACTICE_SECONDS, on_progress=None, task_text="Stand and keep standing", job_id=None):
    spec, st, rn = sim.new_match(1)
    # Clear old runner if needed, but sim.new_match does it.
    
    system = prompts.practice_system(task_text, "", []) # Placeholder, will update in loop
    usage = dict(prompt=0, completion=0, reasoning=0)
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0
    
    last_since = 0.0
    events = []
    
    # Task memory: latest 7
    conn = _conn()
    task_memory = db.get_latest_intervals(conn, "A", "practice", limit=7)

    while st.frame < max_frame:
        decision_idx += 1
        pct = min(100.0, round((st.frame / max_frame) * 100, 1))
        
        fr = observe.torso_frame(st.p, spec, 0)
        current_tree = observe.build_fighter_tree(st.p, spec, st.palive, st.lalive, 0, fr, events, last_since, st.frame, st.frame * LIVE_DT)
        
        # Build prompt with memory
        system = prompts.practice_system(task_text, current_tree, task_memory)
        
        # PRE-TREE for memory (positions only)
        pre_tree = observe.build_fighter_tree(st.p, spec, st.palive, st.lalive, 0, fr, events, last_since, st.frame, st.frame * LIVE_DT, positions_only=True)

        # AI DECISION
        tree_dict, u_dec, attempts, raw_text = _decide_once(ask_fn, system, current_tree)
        _add_usage(usage, u_dec)
        
        orders_dict = {}
        if tree_dict:
            orders_dict = translator.translate_trees({"A": pre_tree}, tree_dict, spec, 0, st.p)
            # Apply orders
            rn = sim.give_orders(rn, 0, [orders_dict])
        
        if on_progress:
            on_progress(dict(
                stage="decision", decision=decision_idx, target_decisions=target_decisions,
                frame=st.frame, max_frame=max_frame, percent=pct,
                thinking="Awaiting interval description...", # Will be updated later or shown as pending
                fighter="A", attempts=attempts,
                pre_tree=pre_tree
            ))

        # ADVANCE PHYSICS
        last_since = st.frame * LIVE_DT
        ticks = min(int(round(interval * LIVE_FPS)), max_frame - st.frame)
        if ticks <= 0: break
        
        for _ in range(ticks):
            st, rn, rec = sim.tick(spec, st, rn, dt=LIVE_DT)
            events += rec

        # POST-TREE for memory
        fr_post = observe.torso_frame(st.p, spec, 0)
        post_tree = observe.build_fighter_tree(st.p, spec, st.palive, st.lalive, 0, fr_post, events, last_since, st.frame, st.frame * LIVE_DT, positions_only=True)

        # SAVE INTERVAL RECORD (undescribed)
        db.save_interval_description(conn, job_id, "practice", 0, "A", decision_idx, st.frame, st.frame * LIVE_DT, "", 0, pre_tree, post_tree)
        
        # Send update with post_tree
        if on_progress:
             on_progress(dict(
                stage="interval_complete", decision=decision_idx, fighter="A",
                post_tree=post_tree
            ))
        
        # IMMEDIATE DESCRIPTION CHECK
        undescribed = db.get_undescribed_intervals(conn, "A", "practice", limit=1)
        if undescribed:
            descs, u_desc = _describe_batch(ask_fn, undescribed)
            _add_usage(usage, u_desc)
            for i, d in enumerate(descs):
                db.update_interval_description(conn, undescribed[i]["id"], d, len(d.split()))
            # Update local task memory for next prompt
            task_memory = db.get_latest_intervals(conn, "A", "practice", limit=7)

    # FINAL BATCH DESCRIPTION
    undescribed = db.get_undescribed_intervals(conn, "A", "practice", limit=7)
    if undescribed:
        descs, u_desc = _describe_batch(ask_fn, undescribed)
        _add_usage(usage, u_desc)
        for i, d in enumerate(descs):
            db.update_interval_description(conn, undescribed[i]["id"], d, len(d.split()))

    return dict(
        library=library, orders=[], frames=int(st.frame * LIVE_DT * FPS), events=events, usage=usage,
        setup=dict(nf=1, gap=3.0, offset_x=0.0), final_p=st.p.copy(), result=st.result
    )

def fight(ask_fns, info, round_summaries, libs, interval, seconds=FIGHT_SECONDS, gap=3.0, offset_x=0.0, on_progress=None, job_id=None):
    spec, st, rn = sim.new_match(2, gap, offset_x)
    usage = dict(prompt=0, completion=0, reasoning=0)
    max_frame = max(1, int(round(seconds * LIVE_FPS)))
    target_decisions = max(1, int(math.ceil(seconds / interval)))
    decision_idx = 0
    
    last_since = 0.0
    events = []
    conn = _conn()
    
    # Fight memory: latest 7
    fight_memories = [db.get_latest_intervals(conn, "AB"[f], "fight", limit=7) for f in range(2)]
    # Fight summaries
    fight_summaries = [db.load_round_summaries(conn, "AB"[f], "fight", limit=100) for f in range(2)]

    with cf.ThreadPoolExecutor(2) as ex:
        while st.result is None and st.frame < max_frame:
            decision_idx += 1
            pct = min(100.0, round((st.frame / max_frame) * 100, 1))
            
            # CAPTURE SHARED STATE
            frames = [observe.torso_frame(st.p, spec, f) for f in range(2)]
            my_trees = [observe.build_fighter_tree(st.p, spec, st.palive, st.lalive, f, frames[f], events, last_since, st.frame, st.frame * LIVE_DT) for f in range(2)]
            enemy_trees = [observe.build_enemy_tree(st.p, spec, f, frames[f], palive=st.palive) for f in range(2)]
            pre_trees = [observe.build_fighter_tree(st.p, spec, st.palive, st.lalive, f, frames[f], events, last_since, st.frame, st.frame * LIVE_DT, positions_only=True) for f in range(2)]

            # Build prompts
            prompts_list = [prompts.fight_system("AB"[f], my_trees[f], enemy_trees[f], fight_memories[f], fight_summaries[f]) for f in range(2)]

            # CONCURRENT AI CALLS
            futs = [ex.submit(_decide_once, ask_fns[f], prompts_list[f], my_trees[f]) for f in range(2)]
            results = [f.result() for f in futs]
            
            for f in range(2):
                tree_dict, u_dec, attempts, raw_text = results[f]
                _add_usage(usage, u_dec)
                if tree_dict:
                    orders_dict = translator.translate_trees({"A": pre_trees[f]}, tree_dict, spec, f, st.p)
                    rn = sim.give_orders(rn, f, [orders_dict])
                
                if on_progress:
                    on_progress(dict(
                        stage="decision", decision=decision_idx, target_decisions=target_decisions,
                        frame=st.frame, max_frame=max_frame, percent=pct,
                        fighter="AB"[f], attempts=attempts,
                        pre_tree=pre_trees[f]
                    ))

            # ADVANCE PHYSICS
            last_since = st.frame * LIVE_DT
            ticks = min(int(round(interval * LIVE_FPS)), max_frame - st.frame)
            if ticks <= 0: break
            
            for _ in range(ticks):
                if st.result: break
                st, rn, rec = sim.tick(spec, st, rn, dt=LIVE_DT)
                events += rec

            # CAPTURE POST STATE & SAVE RECORDS
            for f in range(2):
                fr_post = observe.torso_frame(st.p, spec, f)
                post_tree = observe.build_fighter_tree(st.p, spec, st.palive, st.lalive, f, fr_post, events, last_since, st.frame, st.frame * LIVE_DT, positions_only=True)
                db.save_interval_description(conn, job_id, "fight", 0, "AB"[f], decision_idx, st.frame, st.frame * LIVE_DT, "", 0, pre_trees[f], post_tree)
                
                # Send update with post_tree
                if on_progress:
                     on_progress(dict(
                        stage="interval_complete", decision=decision_idx, fighter="AB"[f],
                        post_tree=post_tree
                    ))

            # IMMEDIATE DESCRIPTION CHECK
            for f in range(2):
                undescribed = db.get_undescribed_intervals(conn, "AB"[f], "fight", limit=1)
                if undescribed:
                    descs, u_desc = _describe_batch(ask_fns[f], undescribed)
                    _add_usage(usage, u_desc)
                    for i, d in enumerate(descs):
                        db.update_interval_description(conn, undescribed[i]["id"], d, len(d.split()))
                    fight_memories[f] = db.get_latest_intervals(conn, "AB"[f], "fight", limit=7)

    # FINAL BATCH DESCRIPTIONS
    for f in range(2):
        undescribed = db.get_undescribed_intervals(conn, "AB"[f], "fight", limit=7)
        if undescribed:
            descs, u_desc = _describe_batch(ask_fns[f], undescribed)
            _add_usage(usage, u_desc)
            for i, d in enumerate(descs):
                db.update_interval_description(conn, undescribed[i]["id"], d, len(d.split()))

    # ROUND SUMMARIES
    round_summaries = ["", ""]
    for f in range(2):
        # Load all intervals for this round
        # Actually, for simplicity, let's just use the latest descriptions from the DB for this run/job
        # But we don't have job_id here easily. Let's use latest intervals.
        latest_recs = db.get_latest_intervals(conn, "AB"[f], "fight", limit=decision_idx)
        res_text = st.result if st.result else "DRAW"
        sys_p = prompts.round_summary_system("AB"[f])
        usr_p = prompts.round_summary_user(latest_recs, res_text)
        ans = ask_fns[f](sys_p, usr_p)
        round_summaries[f] = ans.get("text", "").strip()
        _add_usage(usage, ans.get("usage"))

    return dict(
        libs=libs, orders=[], frames=int(st.frame * LIVE_DT * FPS), events=events, usage=usage,
        setup=dict(nf=2, gap=gap, offset_x=offset_x), final_p=st.p.copy(), result=st.result,
        round_summaries=round_summaries
    )
