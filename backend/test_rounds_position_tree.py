"""Pipeline tests using fake model calls; no network or real provider credentials."""
import os

import db
import rounds
import translator


def _render_tree(values):
    lines = [
        "MY FIGHTER", "CHEST", "  POSITION: ORIGIN", "", "NECK", "",
        "HEAD", f"  POSITION: {values['HEAD']}", "",
        "RIGHT_ARM", "", "NECK_RIGHT_JOINT", "",
        "RIGHT_SHOULDER", f"  POSITION: {values['RIGHT_SHOULDER']}", "",
        "SHOULDER_RIGHT_JOINT", "", "RIGHT_ELBOW", f"  POSITION: {values['RIGHT_ELBOW']}", "",
        "ELBOW_RIGHT_JOINT", "", "RIGHT_FIST", f"  POSITION: {values['RIGHT_FIST']}", "",
        "LEFT_ARM", "", "NECK_LEFT_JOINT", "",
        "LEFT_SHOULDER", f"  POSITION: {values['LEFT_SHOULDER']}", "",
        "SHOULDER_LEFT_JOINT", "", "LEFT_ELBOW", f"  POSITION: {values['LEFT_ELBOW']}", "",
        "ELBOW_LEFT_JOINT", "", "LEFT_FIST", f"  POSITION: {values['LEFT_FIST']}",
    ]
    return "\n".join(lines)


def test_one_action_call_per_interval_and_one_description_call_per_seven(tmp_path, monkeypatch):
    database_path = tmp_path / "rounds.sqlite"
    monkeypatch.setenv("DATABASE_URL", str(database_path))
    connection = db.connect(str(database_path))
    db.init(connection)
    connection.close()

    calls = {"action": 0, "description": 0}
    description = (
        "The chest, head, shoulders, elbows and fists retained nearly the same measured positions, "
        "with no substantial posture change observed during this interval."
    )

    def fake_ask(system, user):
        if "factual physical observer" in system:
            calls["description"] += 1
            count = sum(1 for line in user.splitlines() if line.startswith("INTERVAL ") and line.endswith(":"))
            return {
                "text": "\n".join(f"INTERVAL {i}: {description}" for i in range(1, count + 1)),
                "usage": {"prompt": 1, "completion": 1, "reasoning": 0},
            }
        calls["action"] += 1
        current = translator.parse_tree(user, allow_metadata=True)
        assert translator.validate_tree(current)[0]
        return {
            "text": _render_tree(current),
            "usage": {"prompt": 1, "completion": 1, "reasoning": 0},
        }

    result = rounds.practice(
        fake_ask, info=None, round_summaries=[], library={},
        interval=1 / 7, seconds=1.0, task_text="Stand and keep standing",
        job_id="test-practice-job",
    )

    assert result["frames"] == 30  # seven simulation frames at 7 live frames/second
    assert calls["action"] == 7
    assert calls["description"] == 1

    connection = db.connect(str(database_path))
    records = db.get_interval_descriptions(
        connection, job_id="test-practice-job", kind="practice", fighter="A", limit=20
    )
    connection.close()
    assert len(records) == 7
    assert all(15 <= len(record["text"].split()) <= 30 for record in records)
    assert all(record["pre_tree"] and record["post_tree"] for record in records)


def test_invalid_action_tree_is_rejected_without_partial_result():
    def invalid_ask(system, user):
        return {"text": "MY FIGHTER\nCHEST\n POSITION: ORIGIN\nHEAD\n POSITION: CLOSE FRONT SLIGHT UPPR"}

    tree, usage, error = rounds._decide_once(invalid_ask, "system", "current tree")
    assert tree is None
    assert error
    assert usage == {"prompt": 0, "completion": 0, "reasoning": 0}


def test_practice_pipeline_reaches_translator_and_physics(tmp_path, monkeypatch):
    import numpy as np
    import body

    database_path = tmp_path / "movement.sqlite"
    monkeypatch.setenv("DATABASE_URL", str(database_path))
    connection = db.connect(str(database_path))
    db.init(connection)
    connection.close()

    def fake_ask(system, user):
        if "factual physical observer" in system:
            return {
                "text": (
                    "INTERVAL 1: The right elbow moved forward while the fist changed direction, "
                    "and the chest shifted as the arm motors acted during the interval."
                ),
                "usage": {},
            }
        target = translator.parse_tree(user, allow_metadata=True)
        assert translator.validate_tree(target)[0]
        target["RIGHT_ELBOW"] = "CLOSE FRONT DIAGONAL RIGHT LOWER"
        target["RIGHT_FIST"] = "MID FRONT RIGHT LOWER"
        return {"text": _render_tree(target), "usage": {}}

    result = rounds.practice(
        fake_ask, info=None, round_summaries=[], library={},
        interval=1.0, seconds=1.0, task_text="Move the right arm forward",
        job_id="test-movement-job",
    )

    spec = body.build_spec(1)
    initial = body.initial_state(spec)
    before_elbow = initial.p[spec.idx["elR"]]
    after_elbow = result["final_p"][spec.idx["elR"]]
    assert np.linalg.norm(after_elbow - before_elbow) > 0.005
    assert result["orders"], "Accepted motor rotations must be recorded for replay."
    assert result["orders"][0]["frame"] == 0
    assert result["orders"][0]["f"] == 0
    assert "R_shoulder" in result["orders"][0]["steps"][0]

    import replay as replay_module
    replayed = replay_module.replay(
        result["setup"], result["orders"], result["frames"]
    )
    initial = body.initial_state(spec)
    assert np.linalg.norm(replayed["final_p"][spec.idx["elR"]] - initial.p[spec.idx["elR"]]) > 0.005


def test_server_progress_replaces_pending_text_with_batch_description():
    import time
    import server

    job_id = "test-live-progress"
    server.JOBS[job_id] = {
        "id": job_id, "kind": "practice", "status": "running", "stage": "simulation",
        "started": time.time(), "thinking_history": [],
    }
    try:
        server._apply_interval_progress(job_id, {
            "stage": "decision_started", "fighter": "A", "decision": 1,
            "frame": 0, "pre_tree": "PRE", "text": "AI is choosing the next target pose.",
        })
        assert "choosing" in server.JOBS[job_id]["latest_thinking"]["text"]
        assert server.JOBS[job_id]["latest_thinking"]["status"] == "thinking"

        server._apply_interval_progress(job_id, {
            "stage": "decision", "fighter": "A", "decision": 1,
            "frame": 0, "pre_tree": "PRE", "text": "Target accepted.", "valid": True,
            "target_tree": "MY FIGHTER\nCHEST\n  POSITION: ORIGIN",
        })
        assert server.JOBS[job_id]["thinking_history"][0]["status"] == "target_ready"
        assert server.JOBS[job_id]["thinking_history"][0]["target_tree"].startswith("MY FIGHTER")

        server._apply_interval_progress(job_id, {
            "stage": "interval_complete", "fighter": "A", "decision": 1,
            "frame": 7, "post_tree": "POST",
            "text": "Physical interval complete; summary pending the seven-interval batch.",
        })
        server._apply_interval_progress(job_id, {
            "stage": "description_ready", "fighter": "A", "decision": 1,
            "frame": 7, "pre_tree": "PRE", "post_tree": "POST",
            "text": "The chest remained stable while both fists shifted slightly forward and downward during the measured interval.",
            "word_count": 17,
        })
        item = server.JOBS[job_id]["thinking_history"][0]
        assert item["text"].startswith("The chest remained stable")
        assert item["word_count"] == 17
        assert item["status"] == "described"
        assert item["pre_tree"] == "PRE" and item["post_tree"] == "POST"
        assert server.JOBS[job_id]["stage"] == "simulation"
    finally:
        server.JOBS.pop(job_id, None)


def test_practice_initial_pose_settles_on_fists_instead_of_chest(tmp_path, monkeypatch):
    """The default pose is supported by the fists; the chest does not fall to the floor."""
    import sim
    from config import LIVE_DT
    from observe import GROUND_CONTACT_TOLERANCE

    spec, state, runners = sim.new_match(1)
    chest = spec.idx["chest"]
    fist_r = spec.idx["fistR"]
    fist_l = spec.idx["fistL"]
    initial_chest_bottom = state.p[chest, 1] - spec.r[chest]
    initial_fist_bottom = state.p[fist_r, 1] - spec.r[fist_r]

    for _ in range(14):
        state, runners, _ = sim.tick(spec, state, runners, dt=LIVE_DT)

    final_chest_bottom = state.p[chest, 1] - spec.r[chest]
    final_fist_r_bottom = state.p[fist_r, 1] - spec.r[fist_r]
    final_fist_l_bottom = state.p[fist_l, 1] - spec.r[fist_l]

    assert initial_chest_bottom > 0.20
    assert 0.0 < initial_fist_bottom < 0.025
    assert final_chest_bottom < initial_chest_bottom - 0.05
    assert final_chest_bottom > 0.10
    assert final_fist_r_bottom <= GROUND_CONTACT_TOLERANCE + 1e-4
    assert final_fist_l_bottom <= GROUND_CONTACT_TOLERANCE + 1e-4


def test_fight_uses_one_shared_snapshot_and_waits_for_both_fighters(tmp_path, monkeypatch):
    import re
    import threading

    database_path = tmp_path / "fight-sync.sqlite"
    monkeypatch.setenv("DATABASE_URL", str(database_path))
    connection = db.connect(str(database_path))
    db.init(connection)
    connection.close()

    barrier = threading.Barrier(2, timeout=5)
    seen_frames = {"A": [], "B": []}
    calls = {"description_A": 0, "description_B": 0, "summary_A": 0, "summary_B": 0}
    description = (
        "Both fists reached floor contact while the chest settled lower, and the head remained raised above the chest."
    )

    def make_ask(fighter):
        def fake_ask(system, user):
            if "factual physical observer" in system:
                calls[f"description_{fighter}"] += 1
                count = sum(
                    1 for line in user.splitlines()
                    if line.startswith("INTERVAL ") and line.endswith(":")
                )
                return {"text": "\n".join(
                    f"INTERVAL {i}: {description}" for i in range(1, count + 1)
                )}
            if "strategic memory processor" in system:
                calls[f"summary_{fighter}"] += 1
                return {"text": f"Fighter {fighter} maintained a stable supported posture during the test round."}

            barrier.wait()
            prefix = "MY CURRENT PHYSICAL BODY TREE (POSE 1):\n"
            assert prefix in user
            own_tree = user.split(prefix, 1)[1].split(
                "\n\nENEMY CURRENT BODY TREE (READ-ONLY):", 1
            )[0]
            frame_match = re.search(r"^FRAME: (\d+)$", own_tree, re.MULTILINE)
            assert frame_match
            seen_frames[fighter].append(int(frame_match.group(1)))
            current = translator.parse_tree(own_tree, allow_metadata=True)
            assert translator.validate_tree(current)[0]
            current["RIGHT_ELBOW"] = "CLOSE FRONT DIAGONAL RIGHT LOWER"
            current["RIGHT_FIST"] = "MID FRONT RIGHT LOWER"
            return {"text": _render_tree(current)}
        return fake_ask

    result = rounds.fight(
        [make_ask("A"), make_ask("B")], info=None,
        round_summaries=[[], []], libs=[{}, {}], interval=0.5,
        seconds=0.5, job_id="fight-sync-test",
    )

    assert seen_frames == {"A": [0], "B": [0]}
    assert calls == {
        "description_A": 1, "description_B": 1,
        "summary_A": 1, "summary_B": 1,
    }
    assert len(result["round_summaries"]) == 2
    assert {record["f"] for record in result["orders"]} == {0, 1}
    assert all(record["frame"] == 0 for record in result["orders"])
    connection = db.connect(str(database_path))
    records_a = db.get_interval_descriptions(
        connection, job_id="fight-sync-test", kind="fight", fighter="A", limit=10
    )
    records_b = db.get_interval_descriptions(
        connection, job_id="fight-sync-test", kind="fight", fighter="B", limit=10
    )
    connection.close()
    assert len(records_a) == len(records_b) == 1
    assert records_a[0]["pre_tree"] == records_b[0]["pre_tree"]
    assert records_a[0]["post_tree"] == records_b[0]["post_tree"]
