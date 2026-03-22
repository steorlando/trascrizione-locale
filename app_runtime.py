#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "Trascrizione Locale"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_project_dir() -> Path:
    return Path(__file__).resolve().parent


def get_resource_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return get_project_dir()


def _platform_data_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))


def _platform_cache_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))


def get_app_support_dir() -> Path:
    path = _platform_data_root() / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_app_cache_dir() -> Path:
    path = _platform_cache_root() / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_runtime_dir() -> Path:
    if is_frozen():
        return get_app_support_dir()
    return get_project_dir()


def get_env_file_path() -> Path:
    return get_runtime_dir() / ".env.local"


def get_example_env_path() -> Path:
    return get_runtime_dir() / ".env.local.example"


def read_env_values(path: Path | None = None) -> dict[str, str]:
    env_path = path or get_env_file_path()
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def write_env_values(values: dict[str, str], path: Path | None = None) -> Path:
    env_path = path or get_env_file_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Configurazione locale dell'app", ""]
    for key in ("OPENAI_API_KEY", "HF_TOKEN"):
        lines.append(f"{key}={values.get(key, '').strip()}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def ensure_runtime_layout() -> None:
    runtime_dir = get_runtime_dir()
    cache_dir = get_app_cache_dir() if is_frozen() else get_project_dir() / ".cache"

    runtime_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "matplotlib").mkdir(parents=True, exist_ok=True)
    (cache_dir / "huggingface").mkdir(parents=True, exist_ok=True)
    (cache_dir / "torch").mkdir(parents=True, exist_ok=True)

    source_example = get_resource_dir() / ".env.local.example"
    target_example = get_example_env_path()
    if source_example.exists() and not target_example.exists():
        target_example.write_text(source_example.read_text(encoding="utf-8"), encoding="utf-8")


def configure_runtime_environment() -> None:
    ensure_runtime_layout()

    cache_dir = get_app_cache_dir() if is_frozen() else get_project_dir() / ".cache"
    matplotlib_dir = cache_dir / "matplotlib"
    hf_dir = cache_dir / "huggingface"
    torch_dir = cache_dir / "torch"

    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    os.environ.setdefault("HF_HOME", str(hf_dir))
    os.environ.setdefault("TORCH_HOME", str(torch_dir))
