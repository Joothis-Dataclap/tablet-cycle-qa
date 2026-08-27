"""
Shared parsing logic for Label Studio video-annotation exports (tablet-in-bag task).

Works with any project export following this schema, not just project-391/392:
each task has annotations[].result[] entries keyed by from_name
(phase, tablets_count, tablet_direction, placement, cycle_result,
episode_labelable, cycle_mode, episode_result, ...).

A cycle runs from "Pick up the bag" to "Place the bag" and is expected to end
with exactly TARGET_TABLETS tablets in the bag (tablets_count summed, signed
by tablet_direction: "Going in" = +count, "Coming out" = -count).
"""

TARGET_TABLETS = 15


def signed_count(direction, count):
    n = int(count)
    return -n if direction == "Coming out" else n


def pick_annotation(task):
    anns = task.get("annotations") or []
    for a in anns:
        if not a.get("was_cancelled"):
            return a
    return anns[0] if anns else None


def extract_cycles(task, project):
    ann = pick_annotation(task)
    if ann is None:
        return []

    results = ann.get("result") or []

    by_id = {}
    for r in results:
        rid = r.get("id")
        by_id.setdefault(rid, []).append(r)

    episode_labelable = None
    episode_result = None
    for r in results:
        if r.get("from_name") == "episode_labelable":
            episode_labelable = r["value"]["choices"][0]
        elif r.get("from_name") == "episode_result":
            episode_result = r["value"]["choices"][0]

    phase_segs = []
    for r in results:
        if r.get("from_name") == "phase" and r.get("type") == "timelinelabels":
            rng = r["value"]["ranges"][0]
            phase_segs.append({
                "start": rng["start"],
                "end": rng["end"],
                "label": r["value"]["timelinelabels"][0],
                "id": r.get("id"),
            })
    phase_segs.sort(key=lambda s: s["start"])

    tablet_by_id = {}
    for r in results:
        if r.get("from_name") == "tablets_count":
            rid = r.get("id")
            count = r["value"]["choices"][0]
            direction = None
            for r2 in by_id.get(rid, []):
                if r2.get("from_name") == "tablet_direction":
                    direction = r2["value"]["choices"][0]
            tablet_by_id[rid] = signed_count(direction, count)

    placement_by_id = {}
    cycle_result_by_id = {}
    for r in results:
        if r.get("from_name") == "placement":
            placement_by_id[r.get("id")] = r["value"]["choices"][0]
        elif r.get("from_name") == "cycle_result":
            cycle_result_by_id[r.get("id")] = r["value"]["choices"][0]

    if episode_labelable and episode_labelable.startswith("No"):
        return [{
            "task_id": task["id"],
            "project": project,
            "cycle_index": 0,
            "bad_episode": True,
            "start": None, "end": None,
            "tablet_sum": None,
            "recorded_result": None,
            "placement": None,
        }]

    cycles = []
    current_tablets = []
    current_start = None
    cycle_idx = 0

    for seg in phase_segs:
        if seg["label"] == "Pick up the bag" and current_start is None:
            current_start = seg["start"]
        if seg["label"] == "Tablet bag interaction":
            if seg["id"] in tablet_by_id:
                current_tablets.append(tablet_by_id[seg["id"]])
        if seg["label"] == "Place the bag":
            tablet_sum = sum(current_tablets)
            recorded = cycle_result_by_id.get(seg["id"])
            if recorded is None and episode_result and not episode_result.startswith("Not applicable"):
                recorded = "Success" if episode_result.startswith("Success") else "Failure"
            cycles.append({
                "task_id": task["id"],
                "project": project,
                "cycle_index": cycle_idx,
                "bad_episode": False,
                "start": current_start,
                "end": seg["end"],
                "tablet_sum": tablet_sum,
                "recorded_result": recorded,
                "placement": placement_by_id.get(seg["id"]),
            })
            cycle_idx += 1
            current_tablets = []
            current_start = None

    # trailing cycle with no "Place the bag" segment yet (video ends mid-cycle)
    if current_tablets:
        cycles.append({
            "task_id": task["id"],
            "project": project,
            "cycle_index": cycle_idx,
            "bad_episode": False,
            "start": current_start,
            "end": None,
            "tablet_sum": sum(current_tablets),
            "recorded_result": None,
            "placement": None,
        })

    if not cycles:
        cycles.append({
            "task_id": task["id"],
            "project": project,
            "cycle_index": 0,
            "bad_episode": False,
            "start": None, "end": None,
            "tablet_sum": 0,
            "recorded_result": episode_result,
            "placement": None,
        })

    return cycles


def process_tasks(data, project):
    """data: list of Label Studio task dicts. Returns a flat list of cycle records."""
    all_cycles = []
    for task in data:
        all_cycles.extend(extract_cycles(task, project))
    return all_cycles
