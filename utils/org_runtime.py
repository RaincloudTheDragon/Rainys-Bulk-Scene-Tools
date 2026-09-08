"""
Local org runtime helpers: GGUF + llama-cli binary under addon cache.

No pip / no Blender-Python llama_cpp. Artist flow is one-click install.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import tarfile
import zipfile
from typing import Any

import bpy

# Pin a known-good llama.cpp release.
# Prefer Vulkan on Win/Linux (GPU without CUDA toolkit). macOS builds use Metal.
LLAMA_CPP_TAG = "b9973"
RUNTIME_FLAVOR = f"vulkan-{LLAMA_CPP_TAG}"

MODEL_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/"
    f"resolve/main/{MODEL_FILENAME}"
)

# Platform → release asset filename under ggml-org/llama.cpp releases.
_LLAMA_ASSETS: dict[tuple[str, str], str] = {
    ("Windows", "AMD64"): f"llama-{LLAMA_CPP_TAG}-bin-win-vulkan-x64.zip",
    ("Windows", "x86_64"): f"llama-{LLAMA_CPP_TAG}-bin-win-vulkan-x64.zip",
    ("Windows", "ARM64"): f"llama-{LLAMA_CPP_TAG}-bin-win-cpu-arm64.zip",
    ("Linux", "x86_64"): f"llama-{LLAMA_CPP_TAG}-bin-ubuntu-vulkan-x64.tar.gz",
    ("Linux", "AMD64"): f"llama-{LLAMA_CPP_TAG}-bin-ubuntu-vulkan-x64.tar.gz",
    ("Linux", "aarch64"): f"llama-{LLAMA_CPP_TAG}-bin-ubuntu-arm64.tar.gz",
    ("Darwin", "arm64"): f"llama-{LLAMA_CPP_TAG}-bin-macos-arm64.tar.gz",
    ("Darwin", "x86_64"): f"llama-{LLAMA_CPP_TAG}-bin-macos-x64.tar.gz",
}


def org_cache_root(addon_package: str) -> str:
    """Addon user cache root (models + bin live under this)."""
    try:
        base = bpy.utils.extension_path_user(addon_package, path="cache", create=True)
    except Exception:
        base = bpy.utils.user_resource("SCRIPTS", path="addons_user", create=True)
        base = os.path.join(base, "rbst_cache")
        os.makedirs(base, exist_ok=True)
    return base


def org_model_cache_dir(addon_package: str) -> str:
    models = os.path.join(org_cache_root(addon_package), "org_models")
    os.makedirs(models, exist_ok=True)
    return models


def org_bin_cache_dir(addon_package: str) -> str:
    bins = os.path.join(org_cache_root(addon_package), "bin")
    os.makedirs(bins, exist_ok=True)
    return bins


def runtime_flavor_path(addon_package: str) -> str:
    return os.path.join(org_bin_cache_dir(addon_package), "runtime_flavor.txt")


def runtime_flavor_ok(addon_package: str) -> bool:
    path = runtime_flavor_path(addon_package)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip() == RUNTIME_FLAVOR
    except OSError:
        return False


def write_runtime_flavor(addon_package: str) -> None:
    path = runtime_flavor_path(addon_package)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(RUNTIME_FLAVOR + "\n")


def blender_python_executable() -> str:
    """Blender's bundled python — not sys.executable under VS Code debugpy."""
    ver = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
    root = os.path.dirname(bpy.app.binary_path)
    candidates = [
        os.path.join(root, ver, "python", "bin", "python.exe"),
        os.path.join(root, ver, "python", "bin", "python3"),
        os.path.join(root, ver, "python", "bin", "python"),
        os.path.join(root, "python", "bin", "python.exe"),
        os.path.join(root, "python", "bin", "python3"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return sys.executable


def platform_key() -> tuple[str, str]:
    return platform.system(), platform.machine()


def llama_asset_for_platform() -> tuple[str, str] | None:
    """Return (asset_filename, download_url) or None if unsupported."""
    key = platform_key()
    # Normalize Windows machine names
    sys_name, machine = key
    if sys_name == "Windows":
        machine = machine.upper() if machine.upper() in {"AMD64", "ARM64", "X86_64"} else machine
        if machine.lower() == "amd64":
            machine = "AMD64"
    asset = _LLAMA_ASSETS.get((sys_name, machine))
    if not asset:
        # Try loose match
        for (s, m), name in _LLAMA_ASSETS.items():
            if s == sys_name and m.lower() == machine.lower():
                asset = name
                break
    if not asset:
        return None
    url = (
        f"https://github.com/ggml-org/llama.cpp/releases/download/"
        f"{LLAMA_CPP_TAG}/{asset}"
    )
    return asset, url


def resolve_gguf_path(addon_package: str, prefs=None) -> str | None:
    """Return existing GGUF path from prefs or cache, else None."""
    if prefs is not None:
        custom = getattr(prefs, "org_gguf_path", "") or ""
        if custom and os.path.isfile(custom):
            return custom
        preferred = getattr(prefs, "org_gguf_filename", "") or ""
        if preferred:
            path = os.path.join(org_model_cache_dir(addon_package), preferred)
            if os.path.isfile(path):
                return path
    cache = org_model_cache_dir(addon_package)
    preferred_default = os.path.join(cache, MODEL_FILENAME)
    if os.path.isfile(preferred_default):
        return preferred_default
    try:
        for name in sorted(os.listdir(cache)):
            if name.lower().endswith(".gguf"):
                return os.path.join(cache, name)
    except OSError:
        pass
    return None


def resolve_llama_cli(addon_package: str, prefs=None) -> str | None:
    """Return path to llama-cli(.exe) in cache or prefs override."""
    if prefs is not None:
        custom = getattr(prefs, "org_llama_cli_path", "") or ""
        if custom and os.path.isfile(custom):
            return custom
    bin_dir = org_bin_cache_dir(addon_package)
    names = ("llama-cli.exe", "llama-cli")
    # Prefer top-level, then recursive search one level deep.
    for name in names:
        path = os.path.join(bin_dir, name)
        if os.path.isfile(path):
            return path
    try:
        for root, _dirs, files in os.walk(bin_dir):
            for name in names:
                if name in files:
                    return os.path.join(root, name)
    except OSError:
        pass
    return None


def org_runtime_ready(addon_package: str, prefs=None) -> bool:
    """True when GGUF + llama-cli present and runtime flavor is current."""
    return (
        resolve_gguf_path(addon_package, prefs) is not None
        and resolve_llama_cli(addon_package, prefs) is not None
        and runtime_flavor_ok(addon_package)
    )


def org_runtime_status(addon_package: str, prefs=None) -> dict[str, Any]:
    """Human-readable install status for prefs UI."""
    gguf = resolve_gguf_path(addon_package, prefs)
    cli = resolve_llama_cli(addon_package, prefs)
    asset = llama_asset_for_platform()
    flavor_ok = runtime_flavor_ok(addon_package)
    return {
        "gguf": gguf,
        "llama_cli": cli,
        "flavor_ok": flavor_ok,
        "ready": bool(gguf and cli and flavor_ok),
        "needs_upgrade": bool(cli and not flavor_ok),
        "platform_supported": asset is not None,
        "asset": asset[0] if asset else None,
    }


def extract_llama_archive(archive_path: str, dest_dir: str) -> str | None:
    """
    Extract llama.cpp release archive into dest_dir.
    Returns path to llama-cli if found.
    """
    os.makedirs(dest_dir, exist_ok=True)
    lower = archive_path.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
    elif lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(dest_dir)
    else:
        raise ValueError(f"Unsupported archive: {archive_path}")

    # Flatten: if a single top folder, keep contents accessible.
    cli = None
    for root, _dirs, files in os.walk(dest_dir):
        for name in ("llama-cli.exe", "llama-cli"):
            if name in files:
                found = os.path.join(root, name)
                # Copy/symlink to dest_dir root for easy resolve
                target = os.path.join(dest_dir, name)
                if os.path.abspath(found) != os.path.abspath(target):
                    try:
                        shutil.copy2(found, target)
                        # Also copy sibling DLLs/dylibs next to cli at root
                        for sib in os.listdir(root):
                            if sib.endswith((".dll", ".so", ".dylib")):
                                shutil.copy2(
                                    os.path.join(root, sib),
                                    os.path.join(dest_dir, sib),
                                )
                    except OSError:
                        pass
                    cli = target if os.path.isfile(target) else found
                else:
                    cli = found
                break
        if cli:
            break

    if cli and os.name != "nt":
        try:
            os.chmod(cli, os.stat(cli).st_mode | 0o111)
        except OSError:
            pass
    return cli if cli and os.path.isfile(cli) else None
