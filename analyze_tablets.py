"""
CLI helper: parses local Label Studio export JSON files and prints/saves a
tablet-cycle report. The Streamlit app (streamlit_app.py) does this same
processing dynamically for any uploaded file, so this script is only needed
for offline/one-off checks.

Usage: python analyze_tablets.py [--product sv_packs|tubes|goli_jars|bbw_jars] file1.json [file2.json ...]
"""
import argparse
import json
import os

from tablet_lib import PRODUCTS, process_tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", choices=sorted(PRODUCTS), default="sv_packs")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()

    paths = args.paths
    if not paths:
        here = os.path.dirname(__file__)
        paths = [
            os.path.join(here, f)
            for f in os.listdir(here)
            if f.endswith(".json") and f.startswith("project-")
        ]

    target = PRODUCTS[args.product]["target"]
    all_cycles = []
    for path in paths:
        project = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        all_cycles.extend(process_tasks(data, project, args.product))

    out_path = os.path.join(os.path.dirname(__file__), "tablets_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_cycles, f, indent=2)

    real = [c for c in all_cycles if not c["bad_episode"]]
    anomalies = [
        c for c in real
        if (c["tablet_sum"] == target) != (c["recorded_result"] == "Success")
    ]
    print(f"Product: {args.product} (target {target})")
    print(f"Total cycles: {len(real)}")
    print(f"Anomalies (rule broken): {len(anomalies)}")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
