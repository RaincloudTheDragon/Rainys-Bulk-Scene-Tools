"""
Local org worker CLI (#18).

Reads inventory JSON from stdin, writes plan JSON to stdout.
Prefers a downloaded llama-cli binary (--llama-cli + --model). Falls back to
heuristic when runtime is missing (dev/test only).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from typing import Any

PLAN_KEYS = (
    "rename_collections",
    "move_collections",
    "move_objects",
    "view_layer_exclude",
    "notes",
)

DEFAULT_GRAMMAR = r"""
root ::= object
object ::= "{" ws rename-kv "," ws move-c-kv "," ws move-o-kv "," ws exclude-kv "," ws notes-kv ws "}"
rename-kv ::= "\"rename_collections\"" ws ":" ws array-rename
move-c-kv ::= "\"move_collections\"" ws ":" ws array-move-c
move-o-kv ::= "\"move_objects\"" ws ":" ws array-move-o
exclude-kv ::= "\"view_layer_exclude\"" ws ":" ws array-paths
notes-kv ::= "\"notes\"" ws ":" ws array-str
array-rename ::= "[" ws (rename-item ("," ws rename-item)*)? ws "]"
array-move-c ::= "[" ws (move-c-item ("," ws move-c-item)*)? ws "]"
array-move-o ::= "[" ws (move-o-item ("," ws move-o-item)*)? ws "]"
array-paths ::= "[" ws (path ("," ws path)*)? ws "]"
array-str ::= "[" ws (string ("," ws string)*)? ws "]"
rename-item ::= "{" ws "\"from\"" ws ":" ws string "," ws "\"to\"" ws ":" ws string ws "}"
move-c-item ::= "{" ws "\"name\"" ws ":" ws string "," ws "\"to\"" ws ":" ws path ws "}"
move-o-item ::= "{" ws "\"name\"" ws ":" ws string "," ws "\"to\"" ws ":" ws path ("," ws "\"why\"" ws ":" ws string)? ws "}"
path ::= "[" ws (string ("," ws string)*)? ws "]"
string ::= "\"" ([^"\\] | "\\" ["\\/bfnrt])* "\""
ws ::= [ \t\n]*
"""


def empty_plan(notes: list[str] | None = None) -> dict[str, Any]:
    return {
        "rename_collections": [],
        "move_collections": [],
        "move_objects": [],
        "view_layer_exclude": [],
        "notes": notes or [],
    }


def sanitize(raw: Any) -> dict[str, Any]:
    plan = empty_plan()
    if not isinstance(raw, dict):
        plan["notes"].append("invalid model output")
        return plan
    for key in PLAN_KEYS:
        if key not in raw:
            continue
        val = raw[key]
        if key == "notes" and isinstance(val, list):
            plan["notes"] = [str(n) for n in val]
        elif isinstance(val, list):
            plan[key] = val
    for bad in ("make_local", "unlink_override", "python", "actions"):
        if bad in raw:
            plan["notes"].append(f"stripped forbidden key: {bad}")
    return plan


def _char_like(name: str) -> bool:
    lower = name.lower()
    return any(h in lower for h in ("char", "rig", "hero", "actor", "npc", "creature"))


def heuristic_plan(inventory: dict) -> dict[str, Any]:
    """Fallback when llama-cli / GGUF is unavailable."""
    plan = empty_plan(["heuristic worker (no llama)"])
    aliases = {
        "env": "Env",
        "camera": "Cam",
        "cameras": "Cam",
        "lights": "Lgt",
        "light": "Lgt",
        "lgt": "Lgt",
        "animation": "Animation",
        "char": "Char",
        "character": "Char",
        "props": "Props",
        "dressing": "Dressing",
        "roots": "ROOTS",
    }
    for node in inventory.get("collections") or []:
        name = node.get("name") or ""
        target = aliases.get(name.lower())
        if (
            target
            and target != name
            and not node.get("library")
            and not node.get("override")
        ):
            plan["rename_collections"].append({"from": name, "to": target})
        if (node.get("library") or node.get("override")) and not node.get("parent"):
            dest = ["Animation", "Char"] if _char_like(name) else ["Env"]
            plan["move_collections"].append({"name": name, "to": dest})
    for obj in inventory.get("loose_objects") or []:
        if obj.get("type") == "CAMERA":
            plan["move_objects"].append(
                {"name": obj["name"], "to": ["Animation", "Cam"]}
            )
        elif obj.get("type") == "LIGHT":
            plan["move_objects"].append({"name": obj["name"], "to": ["Lgt"]})
    plan["view_layer_exclude"].append(["Env", "ROOTS"])
    return plan


def extract_json_object(text: str) -> Any:
    """Pull plan JSON from model text (ignore echoed inventory / banners)."""
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


def _build_prompt(inventory: dict) -> str:
    return (
        "You organize a Blender outliner. Reply with ONE JSON object only, keys: "
        "rename_collections, move_collections, move_objects, view_layer_exclude, notes. "
        "Never include make_local. Nest override collections as wholes only when they "
        "are orphans on the scene root. "
        "Inventory:\n"
        f"{json.dumps(inventory, indent=2)}\n"
    )


def run_llama_cli(
    cli_path: str,
    model_path: str,
    grammar_path: str | None,
    inventory: dict,
) -> dict[str, Any]:
    """Run downloaded llama-cli binary; never imports llama_cpp into this process."""
    prompt = _build_prompt(inventory)
    prompt_file = None
    grammar_file = grammar_path
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".txt", delete=False
        ) as handle:
            handle.write(prompt)
            prompt_file = handle.name

        if not grammar_file or not os.path.isfile(grammar_file):
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", suffix=".gbnf", delete=False
            ) as handle:
                handle.write(DEFAULT_GRAMMAR)
                grammar_file = handle.name

        # -st/--single-turn is required: without it llama-cli returns to an
        # interactive ">" prompt and never exits (hangs the worker).
        cmd = [
            cli_path,
            "-m",
            model_path,
            "-no-cnv",
            "-st",
            "-n",
            "512",
            "--temp",
            "0.1",
            "-ngl",
            "99",
            "--no-display-prompt",
            "--grammar-file",
            grammar_file,
            "-f",
            prompt_file,
        ]
        # Keep cwd next to cli so sibling DLLs resolve on Windows.
        cwd = os.path.dirname(cli_path) or None
        try:
            completed = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired:
            plan = empty_plan(
                ["llama-cli timed out after 90s — try Vulkan reinstall or smaller scene"]
            )
            return plan
        text = (completed.stdout or "") + "\n" + (completed.stderr or "")
        parsed = extract_json_object(completed.stdout or "")
        if parsed is None:
            parsed = extract_json_object(text)
        if parsed is None:
            plan = heuristic_plan(inventory)
            plan["notes"].append("llama-cli output unparseable; used heuristic")
            if completed.returncode:
                plan["notes"].append(f"llama-cli exit {completed.returncode}")
            return plan
        plan = sanitize(parsed)
        plan["notes"].append("llama-cli")
        return plan
    except Exception as exc:
        plan = heuristic_plan(inventory)
        plan["notes"].append(f"llama-cli failed: {exc}")
        return plan
    finally:
        for path in (prompt_file,):
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        # Keep shipped grammar; only delete temp grammar we created.
        if (
            grammar_file
            and grammar_file != grammar_path
            and os.path.isfile(grammar_file)
        ):
            try:
                os.remove(grammar_file)
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RBST outliner org worker")
    parser.add_argument("--model", default="", help="Path to GGUF model")
    parser.add_argument("--grammar", default="", help="Path to GBNF grammar file")
    parser.add_argument(
        "--llama-cli",
        default="",
        help="Path to llama-cli binary (preferred over llama_cpp)",
    )
    args = parser.parse_args(argv)

    raw_in = sys.stdin.read()
    try:
        inventory = json.loads(raw_in) if raw_in.strip() else {}
    except json.JSONDecodeError:
        sys.stdout.write(json.dumps(empty_plan(["invalid inventory JSON"])))
        return 1

    if args.model and args.llama_cli and os.path.isfile(args.llama_cli):
        plan = run_llama_cli(
            args.llama_cli, args.model, args.grammar or None, inventory
        )
    elif args.model:
        plan = heuristic_plan(inventory)
        plan["notes"].append("llama-cli missing; used heuristic")
    else:
        plan = heuristic_plan(inventory)

    sys.stdout.write(json.dumps(sanitize(plan)))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
