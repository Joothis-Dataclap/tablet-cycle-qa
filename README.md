# dataclap — Tablet Cycle QA

Streamlit app to review Label Studio video-annotation exports for a
tablet-in-bag packing task.

Each cycle runs from "Pick up the bag" to "Place the bag". A cycle is a
success only if exactly the expected number of tablets ended up in the bag
(`tablets_count` summed per segment, signed by `tablet_direction`:
"Going in" = +count, "Coming out" = -count). The app flags any cycle where the
recorded result doesn't match that rule as an anomaly.

The expected count depends on the packaging type, so the app has one page per
type (same UI on each, different target):

| Page | Product | Tablets per cycle |
| --- | --- | --- |
| SV Packs (landing page) | `sv_pack` | 15 |
| Tubes | `tubes` | 6 |
| Goli Jars | `goli_jars` | 24 |
| BBW Jars | `BBW_jars` | 6 |

## Run

```
pip install streamlit pandas
streamlit run streamlit_app.py
```

Upload one or more Label Studio JSON exports in the browser UI, then switch
packaging type with the sidebar pages. Each page keeps its own upload.

## Files

- `tablet_lib.py` — shared parsing/cycle-extraction logic
- `page_view.py` — `render_review_page(title, target)`: the whole dashboard UI
  (upload, metrics, anomaly table), parameterized by product name + tablet count
- `streamlit_app.py` — entry point: sets the app title (`dataclap`) and routes
  to the four pages with `st.navigation`
- `views/sv_packs.py`, `views/tubes.py`, `views/goli_jars.py`,
  `views/bbw_jars.py` — the four pages, one `render_review_page(...)` call each
- `analyze_tablets.py` — CLI helper for offline checks: `python analyze_tablets.py file1.json [file2.json ...]`
