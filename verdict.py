"""Swapvera verdict action: asks the hosted API for a comparison on the project's production traffic,
waits for it and writes the report. Standard library only; the engine runs on Swapvera, not here."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("SV_API", "https://swapvera.com").rstrip("/")
KEY = os.environ.get("SV_KEY", "").strip()
MARK = "<!-- swapvera-verdict -->"
POLL_SECONDS = float(os.environ.get("SV_POLL_SECONDS", "20"))


def fail(message: str) -> None:
    print(f"::error::{message}")
    sys.exit(2)


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{API}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "User-Agent": "swapvera-verdict-action"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            try:
                detail = json.loads(e.read()).get("detail")
            except ValueError:
                detail = None
            fail(f"Swapvera answered {e.code}: {detail or e.reason}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            fail(f"Could not reach {API}: {e}")
    return {}


def output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{name}={value}\n")


def pick_feature(features: list[dict], wanted: str) -> dict:
    if not features:
        fail("This project has no captured calls yet. Connect the SDK first: " + API + "/docs/#sdk")
    if not wanted:
        if len(features) == 1:
            return features[0]
        fail("This project has several features. Set the 'feature' input to one of: " + "; ".join(f["label"] for f in features))
    w = wanted.strip().lower()
    hits = [f for f in features if f["group_key"] == w or f["label"].strip().lower() == w]
    if len(hits) != 1:
        fail(f"No single feature matches '{wanted}'. Features: " + "; ".join(f"{f['label']} ({f['group_key']})" for f in features))
    return hits[0]


def main() -> None:
    if not KEY:
        fail("Set the 'license' input to your Swapvera project key (sv_...), stored as a secret.")
    project = call("GET", "/v1/project")
    feature = pick_feature(project.get("features") or [], os.environ.get("FEATURE", ""))
    to = os.environ.get("TO", "auto").strip() or "auto"
    if to == "auto":
        if not feature.get("suggestions"):
            fail(f"No suggested replacement for {feature['model']}. Set the 'to' input (provider:model).")
        to = feature["suggestions"][0]["to_model"]
    print(f"Feature: {feature['label']} ({feature['group_key']}), {feature['model']} -> {to}")

    days = int(os.environ.get("REUSE_DAYS", "7") or 0)
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat(timespec="seconds")
    reuse = next((e for e in project.get("experiments") or [] if days > 0 and e["status"] == "done" and e["group_key"] == feature["group_key"]
                  and e["to_model"] == to and e["from_model"] == feature["model"] and e["updated_at"] >= since), None)
    if reuse:
        print(f"Reusing comparison {reuse['id']} from {reuse['updated_at'][:10]} (reuse-days: {days}). No new comparison was spent.")
        exp = call("GET", f"/v1/experiments/{reuse['id']}")
    else:
        exp = call("POST", "/v1/experiments", {"group_key": feature["group_key"], "to_model": to, "n_cases": int(os.environ.get("CASES", "150"))})
        print(f"Started comparison {exp['id']} on up to {os.environ.get('CASES', '150')} production requests.")
        deadline = time.time() + 60 * float(os.environ.get("TIMEOUT_MIN", "60"))
        while True:
            exp = call("GET", f"/v1/experiments/{exp['id']}")
            if exp["status"] in ("done", "failed"):
                break
            if time.time() > deadline:
                fail(f"The comparison {exp['id']} is still {exp['status']}. It keeps running; see it in the dashboard, or raise timeout-minutes.")
            print(f"  {exp['status']}: {exp.get('steps_done', 0)} steps done")
            time.sleep(POLL_SECONDS)
    output("experiment", exp["id"])
    if exp["status"] == "failed":
        fail(f"The comparison failed: {exp.get('error') or 'no detail'}")
    report = exp.get("report_md") or ""
    if MARK not in report:
        report = f"{MARK}\n{report}"
    with open("swapvera-report.md", "w") as f:
        f.write(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(report)
    output("verdict", (exp.get("result") or {}).get("verdict", "inconclusive"))
    output("report", "swapvera-report.md")


if __name__ == "__main__":
    main()
