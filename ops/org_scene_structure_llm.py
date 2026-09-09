"""Modal organize-with-local-model + one-click runtime install (#18)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

import bpy
from bpy.props import BoolProperty

from ..utils.org_runtime import (
    MODEL_FILENAME,
    MODEL_URL,
    extract_llama_archive,
    llama_asset_for_platform,
    org_bin_cache_dir,
    org_model_cache_dir,
    org_runtime_ready,
    org_runtime_status,
    resolve_gguf_path,
    resolve_llama_cli,
    runtime_flavor_ok,
    write_runtime_flavor,
)
from ..utils.outliner_org import (
    apply_plan,
    build_inventory,
    clear_accidental_structure_excludes,
    fill_missed_decide_object_moves,
    filter_plan_against_inventory,
    heuristic_decide_object_moves,
    load_template,
    merge_org_reports,
    plan_action_count,
    run_org,
    sanitize_plan,
)
from .org_scene_structure import _get_org_template_path, show_org_summary

# Module-level llama-cli handle for prefs / cancel.
_worker_proc: subprocess.Popen | None = None
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Background install state (thread → modal).
_install_state: dict = {
    "progress": 0.0,
    "label": "",
    "error": None,
    "done": False,
    "cancel": False,
    "thread": None,
    "gguf_path": "",
    "cli_path": "",
}


def worker_script_dir() -> str:
    """Directory containing rbst_org_worker package."""
    addon_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(addon_root, "worker")


def grammar_path() -> str:
    return os.path.join(worker_script_dir(), "rbst_org_worker", "plan.gbnf")


def _compact_inventory(inventory: dict) -> dict:
    """Shrink inventory for small local models — decide_objects is the payload."""
    decide = list(inventory.get("decide_objects") or [])[:16]
    # Tiny structure index so the model knows legal destinations exist.
    structure = []
    for node in inventory.get("collections") or []:
        name = node.get("name")
        if name in (
            "Env",
            "Dressing",
            "ROOTS",
            "Animation",
            "Cam",
            "Char",
            "Props",
            "Lgt",
        ):
            structure.append(
                {
                    "name": name,
                    "parent": node.get("parent"),
                    "library": bool(node.get("library")),
                    "override": bool(node.get("override")),
                }
            )
    return {
        "scene": inventory.get("scene"),
        "structure": structure,
        "decide_objects": decide,
        # Allow filter lookups for decide names.
        "collections": structure,
        "loose_objects": [],
    }


def _extract_json_object(text: str):
    """Pull plan JSON from llama-cli stdout (may echo prompt + banner)."""
    text = text or ""
    decoder = json.JSONDecoder()
    best = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if any(
            k in obj
            for k in (
                "rename_collections",
                "move_collections",
                "move_objects",
                "view_layer_exclude",
            )
        ):
            best = obj
    return best


def _build_org_prompt(inventory: dict) -> str:
    """Short few-shot prompt — decide_objects Props vs Dressing only."""
    example = (
        '{"rename_collections":[],"move_collections":[],'
        '"move_objects":['
        '{"name":"HelperEmpty","to":["Animation","Char","Props"],'
        '"why":"empty with constraint"},'
        '{"name":"HatMesh","to":["Animation","Char","Props"],'
        '"why":"constrained to character rig"},'
        '{"name":"AnimatedProp","to":["Animation","Char","Props"],'
        '"why":"has action"},'
        '{"name":"LooseMesh","to":["Env","Dressing"],'
        '"why":"loose leftover mesh"}'
        '],"view_layer_exclude":[["Env","ROOTS"]],"notes":[]}'
    )
    decide = inventory.get("decide_objects") or []
    return (
        "Move decide_objects into Props or Dressing. ONE JSON object only.\n"
        "Rules:\n"
        "- Only names from decide_objects.\n"
        "- Destinations must be exact paths only: "
        '["Animation","Char","Props"] or ["Env","Dressing"] or ["Lgt"].\n'
        "- Never use Char alone, Animation alone, MESH, or invented folders.\n"
        "- empty_on_parent / anim_helper_empty / animated / constrained → "
        '["Animation","Char","Props"] (full Props path).\n'
        '- light_group → ["Lgt"]\n'
        '- armature_child (static) / loose mesh → ["Env","Dressing"]\n'
        "- Collection-instance set packs are not in decide_objects; never "
        "treat an EMPTY that instances a whole scene as Dressing.\n"
        "- Never unpack objects that already live in a non-structure / "
        "instance / ROOTS collection — those are preserved homes.\n"
        "- Include short why on each move_objects item when possible.\n"
        "- Leave WGTS/WGT widget trees untouched. Never make_local.\n"
        f"Example:\n{example}\n"
        f"decide_objects:\n{json.dumps(decide, separators=(',', ':'))}\n"
    )


def _print_model_decisions(inventory: dict, parsed: dict | None, filtered: dict | None):
    """Console dump of model why / skips so they can be pasted without screenshots."""
    decide = list((inventory or {}).get("decide_objects") or [])
    print("\n=== RBST Model Decisions ===")
    if decide:
        print(f"decide_objects ({len(decide)}):")
        for c in decide:
            print(
                f"  ? {c.get('name')} type={c.get('type')} "
                f"parent={c.get('parent')} home={c.get('home')} "
                f"hint={c.get('hint')} cons={c.get('constraints')}"
            )
    else:
        print("decide_objects: (none)")

    raw_moves = list((parsed or {}).get("move_objects") or []) if parsed else []
    print(f"model proposed move_objects ({len(raw_moves)}):")
    proposed_names: set[str] = set()
    for item in raw_moves:
        if not isinstance(item, dict):
            print(f"  ! bad item: {item!r}")
            continue
        name = item.get("name")
        dest = item.get("to")
        why = item.get("why") or "(no why)"
        proposed_names.add(str(name))
        print(f"  → {name} → {dest} | why: {why}")

    kept = list((filtered or {}).get("move_objects") or []) if filtered else []
    print(f"kept after filter ({len(kept)}):")
    for item in kept:
        why = item.get("why") or "(no why)"
        print(f"  ✓ {item.get('name')} → {item.get('to')} | why: {why}")

    for c in decide:
        name = c.get("name")
        if name and name not in proposed_names:
            print(
                f"  ∅ model did not decide: {name} "
                f"(hint={c.get('hint')} parent={c.get('parent')} "
                f"home={c.get('home')})"
            )

    for n in (filtered or {}).get("notes") or []:
        s = str(n)
        if s.startswith("filter drops") or s.startswith("  ·") or "filtered" in s:
            print(s)
    print("=== End Model Decisions ===\n")


def kill_worker():
    """Terminate the llama-cli subprocess if running."""
    global _worker_proc
    proc = _worker_proc
    _worker_proc = None
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
    except Exception:
        pass


def _addon_package() -> str:
    return __package__.rsplit(".", 1)[0] if __package__ else ""


def _prefs():
    addon = bpy.context.preferences.addons.get(_addon_package())
    return addon.preferences if addon else None


def _stream_download(url: str, dest: str, state: dict, progress_lo: float, progress_hi: float):
    """Download url → dest with cancel checks; map progress into [lo, hi]."""
    import urllib.request

    partial = dest + ".partial"
    req = urllib.request.Request(url, headers={"User-Agent": "RBST-org-runtime/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        chunk_size = 256 * 1024
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(partial, "wb") as handle:
            while True:
                if state.get("cancel"):
                    raise InterruptedError("cancelled")
                data = resp.read(chunk_size)
                if not data:
                    break
                handle.write(data)
                downloaded += len(data)
                if total > 0:
                    frac = downloaded / float(total)
                    state["progress"] = progress_lo + (progress_hi - progress_lo) * frac
                else:
                    state["progress"] = min(
                        progress_hi - 0.01,
                        state.get("progress", progress_lo) + 0.01,
                    )
    if state.get("cancel"):
        raise InterruptedError("cancelled")
    os.replace(partial, dest)


class InstallOrgRuntime(bpy.types.Operator):
    """Download llama-cli + default GGUF into the addon cache (non-blocking)"""

    bl_idname = "bst.install_org_runtime"
    bl_label = "Install Local Org Runtime"
    bl_options = {"REGISTER"}

    # Legacy id used by older prefs buttons
    # (also registered as DownloadOrgModel alias below)

    _timer = None

    @classmethod
    def poll(cls, context):
        prefs = _prefs()
        if prefs is None:
            return False
        return not bool(getattr(prefs, "is_downloading_org_model", False))

    def invoke(self, context, event):
        prefs = _prefs()
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences unavailable")
            return {"CANCELLED"}

        pkg = _addon_package()
        status = org_runtime_status(pkg, prefs)
        if status["ready"]:
            self.report({"INFO"}, "Local org runtime already installed")
            return {"FINISHED"}
        if not status["platform_supported"]:
            self.report(
                {"ERROR"},
                f"No llama.cpp CPU build for this platform: {status.get('asset')}",
            )
            return {"CANCELLED"}

        import threading

        _install_state.update(
            {
                "progress": 0.0,
                "label": "Starting…",
                "error": None,
                "done": False,
                "cancel": False,
                "gguf_path": "",
                "cli_path": "",
            }
        )
        prefs.is_downloading_org_model = True
        prefs.org_download_progress = 0.0
        prefs.org_download_label = "Starting…"

        thread = threading.Thread(
            target=self._install_thread,
            args=(pkg, _install_state),
            daemon=True,
        )
        _install_state["thread"] = thread
        thread.start()

        wm = context.window_manager
        wm.progress_begin(0, 100)
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        self.report({"INFO"}, "Installing local org runtime… (Esc to cancel)")
        return {"RUNNING_MODAL"}

    @staticmethod
    def _install_thread(addon_package: str, state: dict):
        import shutil

        archive_path = None
        try:
            bin_dir = org_bin_cache_dir(addon_package)
            models_dir = org_model_cache_dir(addon_package)
            gguf_dest = os.path.join(models_dir, MODEL_FILENAME)

            # --- llama-cli ---
            cli = resolve_llama_cli(addon_package, None)
            if cli and not runtime_flavor_ok(addon_package):
                state["label"] = "Upgrading llama-cli (Vulkan)…"
                for name in os.listdir(bin_dir):
                    path = os.path.join(bin_dir, name)
                    try:
                        if os.path.isfile(path):
                            os.remove(path)
                        elif os.path.isdir(path):
                            shutil.rmtree(path)
                    except OSError:
                        pass
                cli = None

            if cli and runtime_flavor_ok(addon_package):
                state["cli_path"] = cli
                state["label"] = "llama-cli ready"
                state["progress"] = 0.45
            else:
                asset = llama_asset_for_platform()
                if not asset:
                    raise RuntimeError("Unsupported platform for llama-cli download")
                asset_name, url = asset
                state["label"] = f"Downloading {asset_name}…"
                archive_path = os.path.join(bin_dir, asset_name)
                _stream_download(url, archive_path, state, 0.0, 0.4)
                state["label"] = "Extracting llama-cli…"
                state["progress"] = 0.42
                cli = extract_llama_archive(archive_path, bin_dir)
                if not cli:
                    raise RuntimeError("llama-cli not found in archive")
                write_runtime_flavor(addon_package)
                state["cli_path"] = cli
                state["progress"] = 0.48
                try:
                    os.remove(archive_path)
                except OSError:
                    pass

            if state.get("cancel"):
                raise InterruptedError("cancelled")

            # --- GGUF ---
            gguf = resolve_gguf_path(addon_package, None)
            if gguf:
                state["gguf_path"] = gguf
                state["label"] = "GGUF ready"
                state["progress"] = 1.0
            else:
                state["label"] = f"Downloading {MODEL_FILENAME}…"
                _stream_download(MODEL_URL, gguf_dest, state, 0.5, 0.98)
                state["gguf_path"] = gguf_dest
                state["progress"] = 1.0
                state["label"] = "Installed"

            if not runtime_flavor_ok(addon_package):
                write_runtime_flavor(addon_package)

            state["done"] = True
        except Exception as exc:
            state["error"] = str(exc)
            state["done"] = True
            if archive_path and os.path.isfile(archive_path):
                try:
                    os.remove(archive_path)
                except OSError:
                    pass
            for path in (
                (archive_path or "") + ".partial",
                os.path.join(org_model_cache_dir(addon_package), MODEL_FILENAME)
                + ".partial",
            ):
                if path.endswith(".partial") and os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def modal(self, context, event):
        prefs = _prefs()
        wm = context.window_manager

        if event.type == "ESC" and event.value == "PRESS":
            _install_state["cancel"] = True
            self.report({"WARNING"}, "Install cancel requested…")
            return {"RUNNING_MODAL"}

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        progress = float(_install_state.get("progress") or 0.0)
        label = _install_state.get("label") or ""
        if prefs is not None:
            prefs.org_download_progress = progress
            if hasattr(prefs, "org_download_label"):
                prefs.org_download_label = label
        wm.progress_update(int(progress * 100))

        for window in wm.windows:
            for area in window.screen.areas:
                if area.type in {"PREFERENCES", "VIEW_3D"}:
                    area.tag_redraw()

        if not _install_state.get("done"):
            return {"PASS_THROUGH"}

        return self._finish(context)

    def _finish(self, context):
        prefs = _prefs()
        wm = context.window_manager
        if self._timer is not None:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        try:
            wm.progress_end()
        except Exception:
            pass

        err = _install_state.get("error")
        cancelled = _install_state.get("cancel") and err and "cancel" in str(err).lower()
        gguf = _install_state.get("gguf_path") or ""
        cli = _install_state.get("cli_path") or ""

        if prefs is not None:
            prefs.is_downloading_org_model = False
            if not err:
                prefs.org_download_progress = 1.0
                if hasattr(prefs, "org_download_label"):
                    prefs.org_download_label = "Ready"
                if gguf:
                    prefs.org_gguf_filename = os.path.basename(gguf)
                    prefs.org_gguf_path = gguf
                if cli and hasattr(prefs, "org_llama_cli_path"):
                    prefs.org_llama_cli_path = cli
            else:
                prefs.org_download_progress = 0.0
                if hasattr(prefs, "org_download_label"):
                    prefs.org_download_label = ""

        _install_state["thread"] = None

        if err:
            if cancelled or "cancel" in str(err).lower():
                self.report({"WARNING"}, "Install cancelled")
            else:
                self.report({"ERROR"}, f"Install failed: {err}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Org runtime ready (cli + GGUF)")
        return {"FINISHED"}

    def execute(self, context):
        return self.invoke(context, None)

    def cancel(self, context):
        _install_state["cancel"] = True
        self._finish(context)


# Back-compat operator id for older UI references
class DownloadOrgModel(InstallOrgRuntime):
    bl_idname = "bst.download_org_gguf"
    bl_label = "Download Org Model"


# Printed once per LLM org so the terminal proves which code path ran.
_ORG_LLM_PATH_TAG = "RBST org_llm — baseline + filtered object moves"


class OrgSceneStructureLLM(bpy.types.Operator):
    """Organize via deterministic rules; local model is advisory-only (not applied)."""

    bl_idname = "bst.org_scene_structure_llm"
    bl_label = "Organize with Local Model"
    bl_options = {"REGISTER", "UNDO"}

    dry_run: BoolProperty(
        name="Dry Run",
        description="Preview changes without modifying the scene",
        default=False,
    )

    _timer = None
    _proc: subprocess.Popen | None = None
    _started: float
    _timeout: float
    _baseline_done: bool
    _prompt_file: str = ""
    _stdout_file: str = ""
    _stderr_file: str = ""
    _stdout_handle: object = None
    _stderr_handle: object = None
    _last_heartbeat: float = 0.0
    _baseline_report: dict | None = None
    _inventory: dict | None = None

    @classmethod
    def poll(cls, context):
        prefs = _prefs()
        if prefs is None:
            return False
        if getattr(prefs, "is_inferring_org", False):
            return False
        if getattr(prefs, "org_llm_allow_heuristic", False):
            return True
        return org_runtime_ready(_addon_package(), prefs)

    def invoke(self, context, event):
        prefs = _prefs()
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences unavailable")
            return {"CANCELLED"}

        print(f"[RBST] {_ORG_LLM_PATH_TAG}")

        pkg = _addon_package()
        model = resolve_gguf_path(pkg, prefs)
        cli = resolve_llama_cli(pkg, prefs)
        allow_heuristic = getattr(prefs, "org_llm_allow_heuristic", False)
        if (model is None or cli is None) and not allow_heuristic:
            self.report(
                {"ERROR"},
                "Install local org runtime in addon preferences (llama-cli + GGUF)",
            )
            return {"CANCELLED"}

        kill_worker()
        prefs.is_inferring_org = True
        self._baseline_report = None
        self._inventory = None
        self._stdout_file = ""
        self._stderr_file = ""
        self._stdout_handle = None
        self._stderr_handle = None
        self._last_heartbeat = 0.0

        # Always run deterministic org first — this is the only mutate path.
        self._baseline_done = False
        template = load_template(_get_org_template_path())
        print("[RBST] org_llm: running baseline deterministic org…")
        self._baseline_report = run_org(
            context, template=template, dry_run=bool(self.dry_run)
        )
        self._baseline_done = True
        print("[RBST] org_llm: baseline done; building inventory…")

        inventory = _compact_inventory(build_inventory(context))
        self._inventory = inventory
        n_decide = len(inventory.get("decide_objects") or [])
        print(f"[RBST] org_llm: inventory ready (decide_objects={n_decide})")

        # No runtime: finish with baseline only.
        if not (model and cli):
            plan = sanitize_plan(
                {
                    "notes": [
                        "baseline org only (no llama-cli)",
                        _ORG_LLM_PATH_TAG,
                    ],
                }
            )
            self._finish_baseline_only(context, plan)
            return {"FINISHED"}

        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", suffix=".txt", delete=False
            ) as handle:
                prompt = _build_org_prompt(inventory)
                handle.write(prompt)
                self._prompt_file = handle.name
            prompt_bytes = os.path.getsize(self._prompt_file)
        except Exception as e:
            prefs.is_inferring_org = False
            self.report({"ERROR"}, f"Failed to write prompt: {e}")
            return {"CANCELLED"}

        # Avoid PIPE deadlock: llama-cli banners fill stderr while we only poll.
        try:
            out_fd, self._stdout_file = tempfile.mkstemp(suffix=".out.txt")
            err_fd, self._stderr_file = tempfile.mkstemp(suffix=".err.txt")
            self._stdout_handle = os.fdopen(out_fd, "wb", buffering=0)
            self._stderr_handle = os.fdopen(err_fd, "wb", buffering=0)
        except Exception as e:
            prefs.is_inferring_org = False
            self._unlink_prompt()
            self.report({"ERROR"}, f"Failed to open llama log files: {e}")
            return {"CANCELLED"}

        gram = grammar_path()
        cmd = [
            cli,
            "-m",
            model,
            "-no-cnv",
            "-st",
            "-n",
            "384",
            "--temp",
            "0.1",
            "-ngl",
            "99",
            "--no-display-prompt",
            "--log-disable",
            "--grammar-file",
            gram,
            "-f",
            self._prompt_file,
        ]
        popen_kw: dict = {
            "cwd": os.path.dirname(cli) or None,
            "stdout": self._stdout_handle,
            "stderr": self._stderr_handle,
            "stdin": subprocess.DEVNULL,
        }
        if _CREATE_NO_WINDOW:
            popen_kw["creationflags"] = _CREATE_NO_WINDOW

        try:
            print(
                f"[RBST] org_llm: starting llama-cli "
                f"(prompt={prompt_bytes} bytes, timeout="
                f"{float(getattr(prefs, 'org_llm_timeout', 120.0) or 120.0):.0f}s)"
            )
            self._proc = subprocess.Popen(cmd, **popen_kw)
        except Exception as e:
            prefs.is_inferring_org = False
            self._close_log_handles()
            self._unlink_prompt()
            self._unlink_logs()
            self.report({"ERROR"}, f"Failed to start llama-cli: {e}")
            return {"CANCELLED"}

        global _worker_proc
        _worker_proc = self._proc

        self._started = time.monotonic()
        self._last_heartbeat = self._started
        self._timeout = float(getattr(prefs, "org_llm_timeout", 120.0) or 120.0)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.25, window=context.window)
        wm.modal_handler_add(self)
        self.report(
            {"INFO"},
            "Baseline done; waiting on local model… (Esc to cancel)",
        )
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC" and event.value == "PRESS":
            # Baseline already applied; cancel only stops waiting on llama.
            plan = sanitize_plan(
                {
                    "notes": [
                        "model wait cancelled; baseline org kept",
                        _ORG_LLM_PATH_TAG,
                    ],
                }
            )
            self._finish_baseline_only(context, plan)
            self.report({"WARNING"}, "Model cancelled; baseline org kept")
            return {"FINISHED"}

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        proc = self._proc
        if proc is None:
            self._cleanup()
            return {"CANCELLED"}

        now = time.monotonic()
        if proc.poll() is None:
            if now - self._last_heartbeat >= 5.0:
                elapsed = now - self._started
                out_sz = 0
                err_sz = 0
                try:
                    if self._stdout_file and os.path.isfile(self._stdout_file):
                        out_sz = os.path.getsize(self._stdout_file)
                    if self._stderr_file and os.path.isfile(self._stderr_file):
                        err_sz = os.path.getsize(self._stderr_file)
                except OSError:
                    pass
                print(
                    f"[RBST] org_llm: llama-cli still running… "
                    f"{elapsed:.0f}s (out={out_sz}B err={err_sz}B)"
                )
                self._last_heartbeat = now
            if now - self._started > self._timeout:
                plan = sanitize_plan(
                    {
                        "notes": [
                            "llama-cli timed out; baseline org kept",
                            _ORG_LLM_PATH_TAG,
                        ],
                    }
                )
                self._finish_baseline_only(context, plan)
                self.report({"WARNING"}, "llama-cli timed out; baseline org kept")
                return {"FINISHED"}
            return {"PASS_THROUGH"}

        # Process exited — close handles then read log files.
        exit_code = proc.returncode
        self._close_log_handles()
        raw = ""
        err_text = ""
        try:
            if self._stdout_file and os.path.isfile(self._stdout_file):
                with open(self._stdout_file, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            if self._stderr_file and os.path.isfile(self._stderr_file):
                with open(self._stderr_file, "r", encoding="utf-8", errors="replace") as f:
                    err_text = f.read().strip()
            print(
                f"[RBST llama-cli] exit={exit_code} "
                f"stdout={len(raw)}B stderr={len(err_text)}B"
            )
            if err_text:
                print(f"[RBST llama-cli stderr] {err_text[:2000]}")
            if raw:
                print(f"[RBST llama-cli stdout head] {raw[:400]!r}")
                if len(raw) > 400:
                    print(f"[RBST llama-cli stdout tail] {raw[-400:]!r}")
            else:
                print("[RBST llama-cli] stdout empty")
        except Exception as e:
            print(f"[RBST llama-cli] read logs failed: {e}")

        parsed = _extract_json_object(raw)
        notes = [_ORG_LLM_PATH_TAG]
        llm_moves: list = []
        filtered = None
        if parsed is None:
            notes.append("llama-cli output unparseable; using decide heuristic")
            fallback = heuristic_decide_object_moves(
                self._inventory or {}, context=context
            )
            filtered = filter_plan_against_inventory(
                sanitize_plan({"move_objects": fallback, "notes": []}),
                self._inventory or {},
            )
            llm_moves = list(filtered.get("move_objects") or [])
            notes.append(f"heuristic object moves applied: {len(llm_moves)}")
            for n in filtered.get("notes") or []:
                if n not in notes:
                    notes.append(str(n))
            _print_model_decisions(self._inventory or {}, None, filtered)
        else:
            filtered = filter_plan_against_inventory(
                sanitize_plan(parsed), self._inventory or {}
            )
            llm_moves = list(filtered.get("move_objects") or [])
            if not llm_moves:
                notes.append("model proposed 0 kept moves; using decide heuristic")
                fallback = heuristic_decide_object_moves(
                    self._inventory or {}, context=context
                )
                filtered = filter_plan_against_inventory(
                    sanitize_plan({"move_objects": fallback, "notes": []}),
                    self._inventory or {},
                )
                llm_moves = list(filtered.get("move_objects") or [])
                notes.append(f"heuristic object moves applied: {len(llm_moves)}")
            else:
                notes.append(
                    f"model object moves applied: {len(llm_moves)} "
                    f"(collection moves still ignored)"
                )
                # Fill constrained/animated props the model skipped or mis-routed.
                extras = fill_missed_decide_object_moves(
                    self._inventory or {}, llm_moves, context=context
                )
                if extras:
                    llm_moves = list(llm_moves) + list(extras)
                    notes.append(
                        f"heuristic filled {len(extras)} missed decide move(s)"
                    )
                    # Re-wrap filtered for console dump with filled moves.
                    filtered = sanitize_plan(
                        {
                            "move_objects": llm_moves,
                            "notes": list(filtered.get("notes") or []),
                        }
                    )
            for n in filtered.get("notes") or []:
                if n not in notes:
                    notes.append(str(n))
            _print_model_decisions(self._inventory or {}, parsed, filtered)

        plan = sanitize_plan({"move_objects": llm_moves, "notes": notes})
        self._finish_with_optional_object_moves(context, plan)
        return {"FINISHED"}

    def _finish_with_optional_object_moves(self, context, plan: dict):
        """Baseline already applied; optionally apply filtered model object moves."""
        plan_report = {
            "renamed": [],
            "moved": [],
            "nested": [],
            "merged": [],
            "excluded": [],
            "skipped": [],
            "notes": list(plan.get("notes") or []),
        }
        if plan_action_count(plan) > 0:
            plan_report = apply_plan(
                context, plan, dry_run=bool(self.dry_run)
            )
            plan_report["notes"] = list(plan.get("notes") or []) + list(
                plan_report.get("notes") or []
            )

        report = merge_org_reports(self._baseline_report or {}, plan_report)
        report["dry_run"] = bool(self.dry_run)
        if not self.dry_run:
            cleared = clear_accidental_structure_excludes(context, dry_run=False)
            for label in cleared.get("cleared") or []:
                report.setdefault("notes", []).append(f"cleared exclude: {label}")
        show_org_summary(report)
        self._cleanup()
        self.report({"INFO"}, "Organize with local model finished")

    def _finish_baseline_only(self, context, plan: dict):
        """Show baseline org summary when model wait is cancelled/timed out."""
        self._finish_with_optional_object_moves(
            context, sanitize_plan({"notes": list(plan.get("notes") or [])})
        )

    def _unlink_prompt(self):
        path = getattr(self, "_prompt_file", "") or ""
        self._prompt_file = ""
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _close_log_handles(self):
        for attr in ("_stdout_handle", "_stderr_handle"):
            handle = getattr(self, attr, None)
            setattr(self, attr, None)
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass

    def _unlink_logs(self):
        for attr in ("_stdout_file", "_stderr_file"):
            path = getattr(self, attr, "") or ""
            setattr(self, attr, "")
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _cleanup(self):
        wm = bpy.context.window_manager
        if self._timer is not None:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        kill_worker()
        self._proc = None
        self._close_log_handles()
        self._unlink_prompt()
        self._unlink_logs()
        prefs = _prefs()
        if prefs is not None:
            prefs.is_inferring_org = False

    def execute(self, context):
        return self.invoke(context, None)
