"""
Shared Streamlit page for tablet-count cycle review.

Every product type (SV Packs, Tubes, Goli Jars, BBW Jars) uses the exact same
UI; the page title, export parser and expected count per cycle differ, so each
page script is a one-line call into render_review_page().
"""
import json

import pandas as pd
import streamlit as st

from tablet_lib import PRODUCTS, process_tasks


def render_review_page(title, product):
    """Render the full review page for one product type.

    title: product name shown in the page heading / sidebar nav.
    product: key into tablet_lib.PRODUCTS (picks the parser and target count).

    set_page_config / sidebar branding live in streamlit_app.py, which routes to
    these pages with st.navigation.
    """
    target = PRODUCTS[product]["target"]
    st.title(f"{title} — tablet-count cycle review")
    st.caption(
        f"Upload one or more {title} Label Studio export JSON files. A cycle is a "
        f"**success** only if it ends with exactly {target} tablets packed "
        "(items going in counted +, coming out counted -); anything else is a failure."
    )

    uploaded_files = st.file_uploader(
        "Upload JSON export(s)",
        type="json",
        accept_multiple_files=True,
        key=f"upload_{title}",
    )

    if not uploaded_files:
        st.info("Upload one or more Label Studio JSON exports to begin.")
        st.stop()

    all_cycles = []
    errors = []
    for uf in uploaded_files:
        project = uf.name.rsplit(".", 1)[0]
        try:
            data = json.loads(uf.getvalue().decode("utf-8"))
        except Exception as e:
            errors.append(f"{uf.name}: could not parse JSON ({e})")
            continue
        if not isinstance(data, list):
            errors.append(f"{uf.name}: expected a list of tasks, got {type(data).__name__}")
            continue
        try:
            all_cycles.extend(process_tasks(data, project, product))
        except Exception as e:
            errors.append(f"{uf.name}: failed while processing ({e})")

    for err in errors:
        st.error(err)

    if not all_cycles:
        st.warning("No cycles could be extracted from the uploaded file(s).")
        st.stop()

    df = pd.DataFrame(all_cycles)
    total_episodes = df["task_id"].nunique()
    bad_episodes = df[df["bad_episode"]].copy()
    bad_episode_count = bad_episodes["task_id"].nunique()
    cycles = df[df["bad_episode"] == False].copy()  # noqa: E712

    # A cycle is correct when: sum == target -> recorded Success, OR sum != target ->
    # recorded Failure. Anything else (a target-count cycle not recorded Success, or an
    # off-target cycle not recorded Failure) breaks that rule and is flagged as an anomaly.
    cycles["expected_result"] = cycles["tablet_sum"].apply(lambda s: "Success" if s == target else "Failure")
    cycles["is_anomaly"] = cycles["expected_result"] != cycles["recorded_result"]
    cycles["flag"] = cycles["is_anomaly"].apply(lambda x: "⚠️" if x else "")

    # ---- top-line metrics ----
    total_cycles = len(cycles)
    success_count = int((cycles["recorded_result"] == "Success").sum())
    failure_count = int((cycles["recorded_result"] == "Failure").sum())
    anomaly_count = int(cycles["is_anomaly"].sum())

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Episodes", total_episodes, delta=f"-{bad_episode_count} bad" if bad_episode_count else None, delta_color="inverse")
    m2.metric("Total cycles", total_cycles)
    m3.metric("Successes", success_count)
    m4.metric("Failures", failure_count)
    m5.metric("⚠️ Anomalies", anomaly_count)

    st.divider()

    # ---- full detail: every episode / cycle row, nothing hidden ----
    st.subheader(f"Episode & cycle detail ({total_episodes} episodes, {total_cycles} cycles)")

    detail = pd.concat([cycles, bad_episodes], ignore_index=True, sort=False)
    detail = detail.sort_values(["project", "task_id", "arm", "cycle_index"], na_position="first").reset_index(drop=True)
    # isna first: is_anomaly is NaN on bad-episode rows, and NaN is truthy.
    detail["flag"] = detail["is_anomaly"].apply(lambda x: "🚫" if pd.isna(x) else ("⚠️" if x else ""))

    projects = sorted(df["project"].unique())
    f1, f2, f3 = st.columns(3)
    project_filter = f1.multiselect("Project", projects, default=projects)
    view_filter = f2.radio("Show", ["All", "Only anomalies", "Only bad episodes"], index=0)
    task_filter = f3.text_input("Filter by task_id (optional)")

    view = detail[detail["project"].isin(project_filter)]
    if task_filter:
        try:
            tid = int(task_filter)
            view = view[view["task_id"] == tid]
        except ValueError:
            st.warning("task_id must be a number")

    if view_filter == "Only anomalies":
        view = view[view["is_anomaly"] == True]  # noqa: E712
    elif view_filter == "Only bad episodes":
        view = view[view["bad_episode"] == True]  # noqa: E712

    display_cols = [
        "flag", "project", "task_id", "arm", "cycle_index", "bad_episode", "start", "end",
        "tablet_sum", "expected_result", "recorded_result", "placement", "failures",
        "bad_reason", "episode_notes",
    ]
    # arm only exists for BBW (two arms); failures only for Goli Jars
    display_cols = [c for c in display_cols if c not in ("arm", "failures") or view[c].notna().any()]
    # reindex (not view[display_cols]): an export missing an optional field entirely
    # would otherwise raise KeyError instead of showing a blank column.
    table = view.reindex(columns=display_cols).reset_index(drop=True)
    # is_anomaly isn't a displayed column, so the row styler reads the flags from here,
    # aligned to table by position.
    flags = view.reset_index(drop=True).reindex(columns=["bad_episode", "is_anomaly", "recorded_result"])

    def highlight(row):
        if flags.at[row.name, "bad_episode"] == True:  # noqa: E712
            return ["background-color: #ff4b4b; color: #ffffff"] * len(row)
        if flags.at[row.name, "is_anomaly"] == True:  # noqa: E712  (NaN for bad episodes)
            return ["background-color: #ffb400; color: #000000"] * len(row)
        if flags.at[row.name, "recorded_result"] == "Failure":
            return ["background-color: #fff176; color: #000000"] * len(row)
        return [""] * len(row)

    st.dataframe(
        table.style.apply(highlight, axis=1),
        width="stretch",
        height=700,
    )

    st.caption(
        "Every episode is listed, bad ones included (red = bad episode, yellow = failure cycle). "
        f"⚠️/orange rows are cycles where the rule broke: a {target}-tablet cycle not recorded "
        f"as Success, or a cycle that isn't {target} tablets not recorded as Failure."
    )
