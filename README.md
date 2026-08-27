# Tablet Cycle QA

Streamlit app to review Label Studio video-annotation exports for a
tablet-in-bag packing task.

Each cycle runs from "Pick up the bag" to "Place the bag". A cycle is a
success only if exactly 15 tablets ended up in the bag (`tablets_count`
summed per segment, signed by `tablet_direction`: "Going in" = +count,
"Coming out" = -count). The app flags any cycle where the recorded result
doesn't match that rule as an anomaly.

## Run

```
pip install streamlit pandas
streamlit run streamlit_app.py
```

Upload one or more Label Studio JSON exports in the browser UI.

## Files

- `tablet_lib.py` — shared parsing/cycle-extraction logic
- `streamlit_app.py` — the dashboard (upload, metrics, anomaly table)
- `analyze_tablets.py` — CLI helper for offline checks: `python analyze_tablets.py file1.json [file2.json ...]`
