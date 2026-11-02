"""REPLAY: rebuilds a round from its stored orders. Physics is deterministic, so the same orders give the same round.
replay(setup, orders, frames)   IN: setup dict(nf,gap,offset_x), orders[], number of frames   OUT: dict(init, frames[], result, events)"""
import sim, frames as fr


def replay(setup, orders, frames):
    spec, st, rn = sim.new_match(setup["nf"], setup["gap"], setup["offset_x"])
    out, events, i = [fr.snapshot(spec, st)], [], 0
    orders = sorted(orders, key=lambda o: o["frame"])
    while st.frame < frames:
        while i < len(orders) and orders[i]["frame"] <= st.frame:
            rn = sim.give_orders(rn, orders[i]["f"], orders[i]["steps"]); i += 1
        st, rn, rec = sim.tick(spec, st, rn); events += rec
        out.append(fr.snapshot(spec, st))
    return dict(init=fr.describe(spec), frames=out, result=st.result, events=events, final_p=st.p.copy())
