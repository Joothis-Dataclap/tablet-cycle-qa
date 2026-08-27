import json

import pandas as pd
import streamlit as st

from tablet_lib import process_tasks, TARGET_TABLETS

st.set_page_config(page_title="Tablet Cycle QA", layout="wide")

st.title("Tablet-count cycle review")
st.caption(
    "Upload one or more Label Studio export JSON files. Each cycle runs from "
    "'Pick up the bag' to 'Place the bag'; it's a **success** only if exactly "
    f"{TARGET_TABLETS} tablets ended up in the bag (tablets_count summed, "
    "'Going in' = +1/+2, 'Coming out' = -1/-2)."
)

uploaded_files = st.file_uploader(
    "Upload JSON export(s)", type="json", accept_multiple_files=True
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
        all_cycles.extend(process_tasks(data, project))
    except Exception as e:
        errors.append(f"{uf.name}: failed while processing ({e})")

for err in errors:
    st.error(err)

if not all_cycles:
    st.warning("No cycles could be extracted from the uploaded file(s).")
    st.stop()

df = pd.DataFrame(all_cycles)
cycles = df[df["bad_episode"] == False].copy()  # noqa: E712

# A cycle is correct when: sum == 15 -> recorded Success, OR sum != 15 -> recorded Failure.
# Anything else (a 15-count cycle not recorded Success, or a non-15 cycle not recorded
# Failure) breaks that rule and is flagged as an anomaly.
cycles["expected_result"] = cycles["tablet_sum"].apply(lambda s: "Success" if s == TARGET_TABLETS else "Failure")
cycles["is_anomaly"] = cycles["expected_result"] != cycles["recorded_result"]
cycles["flag"] = cycles["is_anomaly"].apply(lambda x: "⚠️" if x else "")

# ---- top-line metrics ----
total_cycles = len(cycles)
exact_15 = (cycles["tablet_sum"] == TARGET_TABLETS).sum()
anomaly_count = int(cycles["is_anomaly"].sum())

m1, m2, m3 = st.columns(3)
m1.metric("Total cycles", total_cycles)
m2.metric(f"= {TARGET_TABLETS} tablets (success)", int(exact_15))
m3.metric("⚠️ Anomalies", anomaly_count)

st.divider()

# ---- filters ----
projects = sorted(cycles["project"].unique())
f1, f2, f3 = st.columns(3)
project_filter = f1.multiselect("Project", projects, default=projects)
view_filter = f2.radio("Show", ["Only anomalies", "All"], index=0)
task_filter = f3.text_input("Filter by task_id (optional)")

view = cycles[cycles["project"].isin(project_filter)]
if task_filter:
    try:
        tid = int(task_filter)
        view = view[view["task_id"] == tid]
    except ValueError:
        st.warning("task_id must be a number")

if view_filter == "Only anomalies":
    view = view[view["is_anomaly"]]


def highlight(row):
    if row.get("is_anomaly"):
        return ["background-color: #7a1f1f"] * len(row)
    return [""] * len(row)


display_cols = [
    "flag", "project", "task_id", "cycle_index", "start", "end",
    "tablet_sum", "recorded_result", "placement",
]
st.dataframe(
    view[display_cols].reset_index(drop=True).style.apply(highlight, axis=1),
    width="stretch",
    height=600,
)

st.caption(
    f"⚠️ rows are cycles where the rule broke: a {TARGET_TABLETS}-tablet cycle not recorded "
    "as Success, or a non-15 cycle not recorded as Failure."
)
