"""Isolated local pandas sandbox.

Generated pandas code is executed in a separate subprocess with the named
dataframes loaded. Raw rows NEVER leave the machine: this runs locally and only
the repr of an aggregate `result` variable, captured stdout, and any error
string are returned to the caller. Cell values are never surfaced unless the
generated code itself assigns them to `result`.

The generated code body is passed to the child process via stdin (never
shell-interpolated), so arbitrary code cannot break the command line.
"""
from __future__ import annotations

import json
import subprocess
import sys

# On Windows, suppress a flashing console window for the child interpreter and
# ensure a clean spawn (Windows always spawns rather than forks, so it does not
# inherit the parent's gRPC/absl background-thread state).
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# The harness runs INSIDE the child process. It reads a JSON payload from stdin
# containing the dataset paths and the user code, loads each CSV into a variable
# named by its df_name key, execs the code, and prints the repr of `result`.
_HARNESS = r'''
import json, sys, io, contextlib, traceback

payload = json.loads(sys.stdin.read())
dataset_paths = payload["dataset_paths"]
user_code = payload["code"]

import pandas as pd

def _load_frame(path):
    lower = path.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return pd.read_excel(path, sheet_name=0)
    return pd.read_csv(path)

namespace = {"pd": pd, "result": None}
for df_name, path in dataset_paths.items():
    namespace[df_name] = _load_frame(path)

out = {"ok": False, "result_repr": "", "stdout": "", "error": None}
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        exec(user_code, namespace)
    out["ok"] = True
    out["result_repr"] = repr(namespace.get("result"))
except Exception:
    out["error"] = traceback.format_exc()
finally:
    out["stdout"] = buf.getvalue()

print("<<<SANDBOX_RESULT>>>" + json.dumps(out))
'''

_SENTINEL = "<<<SANDBOX_RESULT>>>"


def run_pandas(
    code: str,
    dataset_paths: dict[str, str],
    timeout: int = 30,
) -> dict:
    """Execute generated pandas code in an isolated subprocess.

    Args:
        code: pandas snippet that assigns the answer to a `result` variable.
        dataset_paths: {df_name: local_csv_path} loaded into the namespace.
        timeout: hard wall-clock limit in seconds.

    Returns:
        {ok: bool, result_repr: str, stdout: str, error: str | None}
    """
    payload = json.dumps({"dataset_paths": dataset_paths, "code": code})

    try:
        proc = subprocess.run(
            [sys.executable, "-c", _HARNESS],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "result_repr": "",
            "stdout": "",
            "error": f"Execution timed out after {timeout}s",
        }

    stdout = proc.stdout or ""
    if _SENTINEL in stdout:
        marker = stdout.rindex(_SENTINEL) + len(_SENTINEL)
        try:
            return json.loads(stdout[marker:].strip())
        except json.JSONDecodeError:
            pass

    # Harness never reported back — surface child stderr/stdout as the error.
    err = proc.stderr.strip() or stdout.strip() or "Sandbox produced no result"
    return {"ok": False, "result_repr": "", "stdout": stdout, "error": err}
