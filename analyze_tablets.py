"""
CLI helper: parses local Label Studio export JSON files and prints/saves a
tablet-cycle report. The Streamlit app (streamlit_app.py) does this same
processing dynamically for any uploaded file, so this script is only needed
for offline/one-off checks.

Usage: python analyze_tablets.py file1.json [file2.json ...]
"""
import json
import os
import sys

from tablet_lib import process_tasks, TARGET_TABLETS


def main():
    paths = sys.argv[1:]
    if not paths:
        here = os.path.dirname(__file__)
        paths = [
            os.path.join(here, f)
            for f in os.listdir(here)
            if f.endswith(".json") and f.startswith("project-")
        ]

    all_cycles = []
    for path in paths:
        project = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        all_cycles.extend(process_tasks(data, project))

    out_path = os.path.join(os.path.dirname(__file__), "tablets_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_cycles, f, indent=2)

    real = [c for c in all_cycles if not c["bad_episode"]]
    anomalies = [
        c for c in real
        if (c["tablet_sum"] == TARGET_TABLETS) != (c["recorded_result"] == "Success")
    ]
    print(f"Total cycles: {len(real)}")
    print(f"Anomalies (rule broken): {len(anomalies)}")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
