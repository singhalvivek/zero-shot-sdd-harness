"""Safety-critical sandbox for executing LLM-generated CadQuery code.

Two responsibilities:
  1. `static_safety_check` — reject forbidden calls/imports BEFORE execution
     (substring/regex match + an AST walk to catch obfuscation).
  2. `run_and_export` — execute the code in a restricted namespace inside a
     child process (multiprocessing `spawn`, Windows-safe timeout) and export
     STL+STEP INSIDE that child (the CadQuery result is not picklable back).

Deliberately keeps top-level imports light so `spawn` re-import is cheap;
CadQuery is imported lazily inside the child.
"""
from __future__ import annotations

import ast
import multiprocessing as mp
import re
import struct
import traceback
from pathlib import Path

# src/sandbox.py -> repo root is two parents up.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_ARTIFACTS_DIR = _REPO_ROOT / "artifacts"
_GENERATED_CODE_DIR = _REPO_ROOT / "generated_code"

# Only these top-level modules may be imported by generated code.
_ALLOWED_IMPORTS = {"cadquery", "math"}

# Regex patterns for forbidden tokens. Word boundaries avoid false positives
# (e.g. `pos.` must NOT trip the `os.` rule).
_FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern]] = [
    (r"open(", re.compile(r"\bopen\s*\(")),
    (r"os.", re.compile(r"\bos\.")),
    (r"sys.", re.compile(r"\bsys\.")),
    (r"subprocess", re.compile(r"\bsubprocess\b")),
    (r"requests", re.compile(r"\brequests\b")),
    (r"socket", re.compile(r"\bsocket\b")),
    (r"shutil", re.compile(r"\bshutil\b")),
    (r"urllib", re.compile(r"\burllib\b")),
    (r"importlib", re.compile(r"\bimportlib\b")),
    (r"pathlib", re.compile(r"\bpathlib\b")),
    (r"__import__", re.compile(r"__import__")),
    (r"eval(", re.compile(r"\beval\s*\(")),
    (r"exec(", re.compile(r"\bexec\s*\(")),
    (r"Path(", re.compile(r"\bPath\s*\(")),
    (r"compile(", re.compile(r"\bcompile\s*\(")),
    (r"globals(", re.compile(r"\bglobals\s*\(")),
    (r"locals(", re.compile(r"\blocals\s*\(")),
    (r"input(", re.compile(r"\binput\s*\(")),
    (r"__builtins__", re.compile(r"__builtins__")),
]

# Dangerous bare names caught by the AST walk (obfuscation like `o = os`).
_FORBIDDEN_NAMES = {
    "os", "sys", "subprocess", "requests", "socket", "shutil", "urllib",
    "importlib", "pathlib", "Path", "eval", "exec", "__import__", "open",
    "compile", "globals", "locals", "input", "builtins", "__builtins__",
}


def static_safety_check(code: str) -> str | None:
    """Return a violation reason string, or None if the code is allowed."""
    if not code or not code.strip():
        return "empty code"

    for label, pat in _FORBIDDEN_PATTERNS:
        if pat.search(code):
            return f"forbidden token: {label!r}"

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in _ALLOWED_IMPORTS:
                    return f"forbidden import: {alias.name!r}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in _ALLOWED_IMPORTS:
                return f"forbidden import from: {node.module!r}"
        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES:
                return f"forbidden name: {node.id!r}"
    return None


# --- Restricted execution builtins (child process) ------------------------

_SAFE_BUILTIN_NAMES = [
    "abs", "all", "any", "bool", "complex", "dict", "divmod", "enumerate",
    "filter", "float", "format", "frozenset", "hasattr", "int", "isinstance",
    "len", "list", "map", "max", "min", "pow", "print", "range", "repr",
    "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple",
    "type", "zip", "True", "False", "None",
]


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root not in _ALLOWED_IMPORTS:
        raise ImportError(f"import of {name!r} is not allowed in the sandbox")
    return __import__(name, globals, locals, fromlist, level)


def _build_restricted_namespace() -> dict:
    import builtins as _bi

    allowed = {}
    for n in _SAFE_BUILTIN_NAMES:
        if hasattr(_bi, n):
            allowed[n] = getattr(_bi, n)
    allowed["__import__"] = _guarded_import
    return {"__builtins__": allowed}


def _child_exec(code: str, stl_path: str, step_path: str, formats, queue) -> None:
    """Runs INSIDE the spawned child. Execs code + exports STL/STEP."""
    try:
        namespace = _build_restricted_namespace()
        exec(compile(code, "<generated_part>", "exec"), namespace, namespace)
        result = namespace.get("result")
        if result is None:
            queue.put({
                "ok": False,
                "error": "code did not assign the final solid to a variable named `result`",
                "stl_path": None,
                "step_path": None,
            })
            return

        import cadquery as cq  # real import inside the child

        if "stl" in formats:
            cq.exporters.export(result, stl_path)
        if "step" in formats:
            cq.exporters.export(result, step_path)

        queue.put({
            "ok": True,
            "error": None,
            "stl_path": stl_path if "stl" in formats else None,
            "step_path": step_path if "step" in formats else None,
        })
    except Exception:
        queue.put({
            "ok": False,
            "error": traceback.format_exc(limit=8),
            "stl_path": None,
            "step_path": None,
        })


_cadquery_warmed = False


def warm_cadquery() -> None:
    """Import CadQuery in the PARENT once so child `spawn`s hit a warm OS cache.

    The very first CadQuery/OCP import on a Windows machine can take ~60-90s
    (large OCP DLLs, Defender scan); warm imports are ~3-4s. Warming the parent
    keeps every spawned child's import comfortably inside the exec timeout.
    Idempotent — safe to call at startup and before each run.
    """
    global _cadquery_warmed
    if _cadquery_warmed:
        return
    import cadquery  # noqa: F401 — warms the OS DLL cache for child spawns
    _cadquery_warmed = True


def exports_dir(part_id: str) -> Path:
    return _ARTIFACTS_DIR / "exports" / f"part_{part_id}"


def code_artifacts_dir(part_id: str) -> Path:
    return _ARTIFACTS_DIR / "code" / f"part_{part_id}"


def generated_code_dir(part_id: str) -> Path:
    return _GENERATED_CODE_DIR / f"part_{part_id}"


def run_and_export(
    code: str,
    part_id: str,
    version: int,
    formats=("stl", "step"),
    timeout: int = 20,
) -> dict:
    """Execute `code` in a sandboxed child process; export STL+STEP there.

    Returns a picklable dict: {ok, error, stl_path, step_path}. On timeout the
    child is terminated (Windows-safe — never signal.alarm).
    """
    warm_cadquery()  # ensure the OS DLL cache is hot before spawning the child

    exp_dir = exports_dir(part_id)
    exp_dir.mkdir(parents=True, exist_ok=True)
    generated_code_dir(part_id).mkdir(parents=True, exist_ok=True)

    stl_path = str(exp_dir / f"part_v{version}.stl")
    step_path = str(exp_dir / f"part_v{version}.step")

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(
        target=_child_exec,
        args=(code, stl_path, step_path, list(formats), queue),
    )
    proc.start()
    proc.join(timeout)

    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        return {
            "ok": False,
            "error": f"execution timed out after {timeout}s",
            "stl_path": None,
            "step_path": None,
        }

    try:
        result = queue.get(timeout=5)
    except Exception:
        result = {
            "ok": False,
            "error": f"sandbox process exited without a result (exit code {proc.exitcode})",
            "stl_path": None,
            "step_path": None,
        }
    return result


def write_code_artifacts(part_id: str, version: int, code: str) -> str:
    """Persist the CadQuery source to generated_code/ and artifacts/code/.

    Returns the artifacts-relative URL path (leading '/') for code_url.
    """
    gen_dir = generated_code_dir(part_id)
    art_dir = code_artifacts_dir(part_id)
    gen_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)

    (gen_dir / f"v{version}.py").write_text(code, encoding="utf-8")
    (art_dir / f"v{version}.py").write_text(code, encoding="utf-8")

    return f"/artifacts/code/part_{part_id}/v{version}.py"


def count_stl_triangles(path: str) -> int:
    """Count triangles in an STL file (binary header count or ASCII facets)."""
    data = Path(path).read_bytes()
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if len(data) == 84 + n * 50:
            return n
    return data.count(b"facet normal")
