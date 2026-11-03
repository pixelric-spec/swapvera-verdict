"""La Action contra un servidor falso: elige la funcion, reutiliza comparaciones recientes, espera y escribe el informe."""
import datetime as dt
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOW = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
FEATURES = [{"group_key": "aaaaaaaaaa", "label": "text correction", "model": "anthropic:claude-sonnet-4-5",
             "suggestions": [{"to_model": "anthropic:claude-sonnet-5-5"}]},
            {"group_key": "bbbbbbbbbb", "label": "summaries", "model": "anthropic:claude-haiku-4-5", "suggestions": []}]


def serve(state: dict):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get("Authorization") != "Bearer sv_test":
                return self.reply(401, {"detail": "Unknown license key."})
            if self.path == "/v1/project":
                return self.reply(200, {"features": FEATURES, "experiments": state["experiments"]})
            state["polls"] += 1
            done = state["polls"] >= 2
            self.reply(200, {"id": self.path.rsplit("/", 1)[1], "status": "done" if done else "running", "steps_done": state["polls"],
                             "result": {"verdict": "review"} if done else None, "report_md": "## Swapvera verdict: REVIEW" if done else None})

        def do_POST(self):
            state["posted"].append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.reply(200, {"id": "x_new", "status": "queued"})

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run(tmp_path, state, **env):
    srv = serve(state)
    out = tmp_path / "out.txt"
    base = {"SV_API": f"http://127.0.0.1:{srv.server_port}", "SV_KEY": "sv_test", "SV_POLL_SECONDS": "0", "GITHUB_OUTPUT": str(out), "PATH": os.environ["PATH"]}
    p = subprocess.run([sys.executable, str(HERE / "verdict.py")], cwd=tmp_path, env={**base, **env}, capture_output=True, text=True)
    srv.shutdown()
    outputs = dict(line.split("=", 1) for line in out.read_text().splitlines()) if out.exists() else {}
    return p, outputs


def test_runs_a_comparison_for_the_named_feature_and_waits(tmp_path):
    state = {"experiments": [], "posted": [], "polls": 0}
    p, outputs = run(tmp_path, state, FEATURE="Text Correction", TO="auto", CASES="120")
    assert p.returncode == 0, p.stdout + p.stderr
    assert state["posted"] == [{"group_key": "aaaaaaaaaa", "to_model": "anthropic:claude-sonnet-5-5", "n_cases": 120}]
    assert outputs == {"experiment": "x_new", "verdict": "review", "report": "swapvera-report.md"}
    assert (tmp_path / "swapvera-report.md").read_text().startswith("<!-- swapvera-verdict -->")


def test_reuses_a_recent_comparison_instead_of_spending_one(tmp_path):
    old = {"id": "x_old", "status": "done", "group_key": "aaaaaaaaaa", "from_model": "anthropic:claude-sonnet-4-5",
           "to_model": "anthropic:claude-sonnet-5-5", "updated_at": NOW}
    state = {"experiments": [old], "posted": [], "polls": 5}
    p, outputs = run(tmp_path, state, FEATURE="aaaaaaaaaa")
    assert p.returncode == 0 and state["posted"] == [] and outputs["experiment"] == "x_old"


def test_says_which_features_exist_when_the_name_is_missing_or_wrong(tmp_path):
    state = {"experiments": [], "posted": [], "polls": 0}
    p, _ = run(tmp_path, state)
    assert p.returncode == 2 and "text correction" in p.stdout and "summaries" in p.stdout
    p, _ = run(tmp_path, state, FEATURE="summaries")
    assert p.returncode == 2 and "Set the 'to' input" in p.stdout
    p, _ = run(tmp_path, state, SV_KEY="sv_wrong", FEATURE="summaries")
    assert p.returncode == 2 and "401" in p.stdout and state["posted"] == []
