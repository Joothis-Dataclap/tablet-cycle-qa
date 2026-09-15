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

Each product's export uses a different Label Studio schema, so each page has
its own parser (`tablet_lib.PRODUCTS`):

| Product | Cycle | Count | Bad episode |
| --- | --- | --- | --- |
| SV Packs | `Pick up the bag` → `Place the bag` | signed `tablets_count` | `episode_labelable` = No |
| Tubes | `Pick up tube` → `Place tube` | signed `tablets_count` | `episode_labelable` = No |
| Goli Jars | `Pick up box` → `Push box` | sum of `jar_delta` (Unclear ignored) | `episode_result` = BAD |
| BBW Jars | per arm (left / right), ends at `<arm>_cycle_end` = Yes | `<arm>_initial` + signed `<arm>_count` | `recording_status` ≠ Labelable |

A cycle cut off by the end of the video takes the episode-level result.

## Run

```
pip install streamlit pandas
streamlit run streamlit_app.py
```

Upload one or more Label Studio JSON exports in the browser UI, then switch
packaging type with the sidebar pages. Each page keeps its own upload.

## Files

- `tablet_lib.py` — shared parsing/cycle-extraction logic
- `page_view.py` — `render_review_page(title, product)`: the whole dashboard UI
  (upload, metrics, anomaly table), parameterized by page title + product key
- `streamlit_app.py` — entry point: sets the app title (`dataclap`) and routes
  to the four pages with `st.navigation`
- `views/sv_packs.py`, `views/tubes.py`, `views/goli_jars.py`,
  `views/bbw_jars.py` — the four pages, one `render_review_page(...)` call each
- `analyze_tablets.py` — CLI helper for offline checks: `python analyze_tablets.py --product goli_jars file1.json [file2.json ...]`
