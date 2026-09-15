"""
Shared parsing logic for Label Studio video-annotation exports (packing QA).

Each packaging type has its own export schema, so each has its own parser; all
of them return the same flat cycle-record dicts so the UI doesn't care which
product it's showing:

  SV Packs  (15) — phases "Pick up the bag" -> "Place the bag"; count = signed
                   tablets_count ("Going in" +, "Coming out" -) on
                   "Tablet bag interaction" segments; bad = episode_labelable "No…".
  Tubes     (6)  — same fields as SV Packs, tube phase names
                   ("Pick up tube" -> "Place tube", "Tablet tube interaction").
  Goli Jars (24) — "Pick up box" -> "Push box"; count = sum of jar_delta
                   (1 / 0 / -1, "Unclear" ignored) on "Jar interaction" segments;
                   result/bad come from episode_result (Success / Failure / BAD).
  BBW Jars  (6)  — two independent arms (left_* / right_* fields); a cycle ends on
                   the segment marked <arm>_cycle_end = Yes; count = <arm>_initial
                   + signed <arm>_count; bad = recording_status "Nothing meaningful".

A cycle is a success only if it ends on exactly the product's target count.
"""


def signed_count(direction, count):
    n = int(count)
    return -n if direction == "Coming out" else n


def pick_annotation(task):
    anns = task.get("annotations") or []
    for a in anns:
        if not a.get("was_cancelled"):
            return a
    return anns[0] if anns else None


def _choice(rs, from_name):
    """First choice of `from_name` among results rs, or None (empty choices = None)."""
    for r in rs:
        if r.get("from_name") == from_name:
            choices = (r.get("value") or {}).get("choices") or []
            if choices:
                return choices[0]
    return None


def _all_choices(rs, from_name):
    out = []
    for r in rs:
        if r.get("from_name") == from_name:
            out.extend((r.get("value") or {}).get("choices") or [])
    return out


def _texts(rs, from_name):
    out = []
    for r in rs:
        if r.get("from_name") == from_name:
            out.extend((r.get("value") or {}).get("text") or [])
    return "\n".join(out) or None


def _group_by_id(results):
    by_id = {}
    for r in results:
        by_id.setdefault(r.get("id"), []).append(r)
    return by_id


def _segments(results, phase_field):
    """Timeline segments of `phase_field`, sorted by start, with their sibling results."""
    by_id = _group_by_id(results)
    segs = []
    for r in results:
        if r.get("from_name") == phase_field and r.get("type") == "timelinelabels":
            rng = r["value"]["ranges"][0]
            segs.append({
                "start": rng["start"],
                "end": rng["end"],
                "label": r["value"]["timelinelabels"][0],
                "results": by_id.get(r.get("id"), []),
            })
    segs.sort(key=lambda s: s["start"])
    return segs


def _record(task, project, idx, **kw):
    rec = {
        "task_id": task["id"],
        "project": project,
        "arm": None,
        "cycle_index": idx,
        "bad_episode": False,
        "start": None,
        "end": None,
        "tablet_sum": None,
        "recorded_result": None,
        "placement": None,
        "failures": None,
        "bad_reason": None,
        "episode_notes": None,
    }
    rec.update(kw)
    return rec


# ---------------------------------------------------------------------------
# Phase-sequence products (SV Packs, Tubes, Goli Jars)
# ---------------------------------------------------------------------------

def _tablet_count(rs):
    count = _choice(rs, "tablets_count")
    if count is None:
        return None
    return signed_count(_choice(rs, "tablet_direction"), count)


def _jar_count(rs):
    delta = _choice(rs, "jar_delta")
    try:
        return int(delta)
    except (TypeError, ValueError):  # missing or "Unclear"
        return None


def _labelable_episode(results):
    """SV Packs / Tubes episode-level fields -> (is_bad, bad_reason, notes, result)."""
    labelable = _choice(results, "episode_labelable")
    bad_reason = ", ".join(_all_choices(results, "bad_reason")) or None
    notes = _texts(results, "episode_notes")
    ep = _choice(results, "episode_result")
    result = None
    if ep and not ep.startswith("Not applicable"):
        result = "Success" if ep.startswith("Success") else "Failure"
    return bool(labelable and labelable.startswith("No")), bad_reason, notes, result


def _goli_episode(results):
    ep = _choice(results, "episode_result")
    notes = "\n".join(filter(None, [_texts(results, "feedback"), _texts(results, "segment_notes")])) or None
    if ep == "BAD":
        return True, "BAD", notes, None
    return False, None, notes, ep if ep in ("Success", "Failure") else None


def _failures(results):
    """All *_failures choices in the episode (Goli Jars), e.g. 'Wrong filling pattern'."""
    out = []
    for r in results:
        if (r.get("from_name") or "").endswith("_failures"):
            out.extend((r.get("value") or {}).get("choices") or [])
    return ", ".join(dict.fromkeys(out)) or None


def _phase_extractor(start_label, interaction_label, end_label, count_fn, episode_fn):
    def extract(task, project):
        ann = pick_annotation(task)
        if ann is None:
            return []
        results = ann.get("result") or []
        is_bad, bad_reason, notes, episode_result = episode_fn(results)
        common = {"bad_reason": bad_reason, "episode_notes": notes}

        if is_bad:
            return [_record(task, project, 0, bad_episode=True, **common)]

        cycles = []
        current = []
        current_start = None
        failures = []

        for seg in _segments(results, "phase"):
            if seg["label"] == start_label and current_start is None:
                current_start = seg["start"]
            if seg["label"] == interaction_label:
                n = count_fn(seg["results"])
                if n is not None:
                    current.append(n)
                failures.extend(_all_choices(seg["results"], "jar_failures"))
            if seg["label"] == end_label:
                recorded = _choice(seg["results"], "cycle_result") or episode_result
                cycles.append(_record(
                    task, project, len(cycles),
                    start=current_start, end=seg["end"],
                    tablet_sum=sum(current), recorded_result=recorded,
                    placement=_choice(seg["results"], "placement"),
                    **common,
                ))
                current = []
                current_start = None

        # trailing cycle: video ends before the end phase
        if current or current_start is not None:
            cycles.append(_record(
                task, project, len(cycles),
                start=current_start, tablet_sum=sum(current),
                recorded_result=episode_result, **common,
            ))

        if not cycles:
            cycles.append(_record(task, project, 0, tablet_sum=0, recorded_result=episode_result, **common))

        ep_failures = _failures(results)
        if ep_failures:
            for c in cycles:
                c["failures"] = ep_failures
        return cycles

    return extract


extract_sv_cycles = _phase_extractor(
    "Pick up the bag", "Tablet bag interaction", "Place the bag", _tablet_count, _labelable_episode)
extract_tube_cycles = _phase_extractor(
    "Pick up tube", "Tablet tube interaction", "Place tube", _tablet_count, _labelable_episode)
extract_goli_cycles = _phase_extractor(
    "Pick up box", "Jar interaction", "Push box", _jar_count, _goli_episode)

# backwards-compatible name (SV Packs was the original schema)
extract_cycles = extract_sv_cycles


# ---------------------------------------------------------------------------
# BBW Jars: two independent arms, cycle ends on <arm>_cycle_end = Yes
# ---------------------------------------------------------------------------

def extract_bbw_cycles(task, project):
    ann = pick_annotation(task)
    if ann is None:
        return []
    results = ann.get("result") or []
    status = _choice(results, "recording_status")
    notes = _texts(results, "episode_notes")

    if status and status != "Labelable":
        return [_record(task, project, 0, bad_episode=True, bad_reason=status, episode_notes=notes)]

    by_id = _group_by_id(results)
    cycles = []
    for arm in ("left", "right"):
        segs = []
        for rid, rs in by_id.items():
            phase = next((r for r in rs if r.get("from_name") == f"{arm}_phase"), None)
            if phase is None:
                continue
            rng = phase["value"]["ranges"][0]
            segs.append((rng["start"], rng["end"], rs))
        segs.sort(key=lambda s: s[0])

        total = 0
        started = False
        cycle_start = None
        arm_notes = "\n".join(filter(None, [notes, _texts(results, f"{arm}_notes")])) or None
        idx = 0
        for start, end, rs in segs:
            if cycle_start is None:
                cycle_start = start
            initial = _choice(rs, f"{arm}_initial")
            if initial is not None:
                total += int(initial)
                started = True
            count = _choice(rs, f"{arm}_count")
            if count is not None:
                total += signed_count(_choice(rs, f"{arm}_direction"), count)
                started = True
            if _choice(rs, f"{arm}_cycle_end") == "Yes":
                cycles.append(_record(
                    task, project, idx, arm=arm.capitalize(),
                    start=cycle_start, end=end, tablet_sum=total,
                    recorded_result=_choice(rs, f"{arm}_cycle_result"),
                    placement=_choice(rs, f"{arm}_placement"),
                    episode_notes=arm_notes,
                ))
                idx += 1
                total = 0
                started = False
                cycle_start = None
        if started and total:
            cycles.append(_record(
                task, project, idx, arm=arm.capitalize(),
                start=cycle_start, tablet_sum=total, episode_notes=arm_notes,
            ))

    if not cycles:
        cycles.append(_record(task, project, 0, tablet_sum=0, episode_notes=notes))
    return cycles


# ---------------------------------------------------------------------------

PRODUCTS = {
    "sv_packs": {"target": 15, "extract": extract_sv_cycles},
    "tubes": {"target": 6, "extract": extract_tube_cycles},
    "goli_jars": {"target": 24, "extract": extract_goli_cycles},
    "bbw_jars": {"target": 6, "extract": extract_bbw_cycles},
}

# default used by the analyze_tablets.py CLI helper
TARGET_TABLETS = PRODUCTS["sv_packs"]["target"]


def process_tasks(data, project, product="sv_packs"):
    """data: list of Label Studio task dicts. Returns a flat list of cycle records."""
    extract = PRODUCTS[product]["extract"]
    all_cycles = []
    for task in data:
        all_cycles.extend(extract(task, project))
    return all_cycles
