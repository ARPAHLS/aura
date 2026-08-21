"""Configuration paths and merge order."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


DEFAULTS: dict[str, Any] = {
    "storage": "global",  # global | project
    "default_session_mode": "script",
    "export_on_close": True,
}


def user_home() -> Path:
    return Path(os.environ.get("AURA_HOME", Path.home() / ".aura"))


@dataclass
class AuraConfig:
    """Merged configuration: defaults → global → project → overrides."""

    home: Path = field(default_factory=user_home)
    project_dir: Path | None = None
    values: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.values:
            self.values = self.load()

    @property
    def project_aura_dir(self) -> Path | None:
        if self.project_dir is None:
            return None
        return self.project_dir / ".aura"

    def load(self, project_dir: Path | None = None) -> dict[str, Any]:
        merged = dict(DEFAULTS)
        global_file = self.home / "config.yaml"
        if global_file.is_file() and yaml is not None:
            merged.update(_read_yaml(global_file))
        proj = project_dir or self.project_dir
        if proj is not None:
            project_file = proj / "aura.project.yaml"
            if project_file.is_file() and yaml is not None:
                merged.update(_read_yaml(project_file))
        return merged

    def registry_dir(self) -> Path:
        if self.values.get("storage") == "project" and self.project_aura_dir:
            path = self.project_aura_dir / "agents"
        else:
            path = self.home / "agents"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def sessions_dir(self) -> Path:
        if self.values.get("storage") == "project" and self.project_aura_dir:
            path = self.project_aura_dir / "sessions"
        else:
            path = self.home / "sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def state_file(self) -> Path:
        base = (
            self.project_aura_dir
            if self.values.get("storage") == "project" and self.project_aura_dir
            else self.home
        )
        base.mkdir(parents=True, exist_ok=True)
        return base / "registry_state.json"


_config: AuraConfig | None = None


def configure(project_dir: str | Path | None = None, **overrides: Any) -> AuraConfig:
    """Set global config. Call once at app startup if needed."""
    global _config
    proj = Path(project_dir).resolve() if project_dir else None
    cfg = AuraConfig(project_dir=proj)
    cfg = _apply_persisted_project(cfg)
    cfg.values.update(overrides)
    _config = cfg
    return cfg


def get_config() -> AuraConfig:
    global _config
    if _config is None:
        _config = AuraConfig()
        _config = _apply_persisted_project(_config)
    return _config


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return dict(data) if isinstance(data, dict) else {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    if yaml is None:  # pragma: no cover
        raise RuntimeError("pyyaml is required to write config files")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def global_config_path(home: Path | None = None) -> Path:
    return (home or user_home()) / "config.yaml"


def project_config_path(project_dir: Path) -> Path:
    return project_dir / "aura.project.yaml"


def save_global_config(updates: dict[str, Any], home: Path | None = None) -> Path:
    path = global_config_path(home)
    merged = _read_yaml(path) if path.is_file() else {}
    merged.update(updates)
    _write_yaml(path, merged)
    return path


def save_project_config(updates: dict[str, Any], project_dir: Path) -> Path:
    path = project_config_path(project_dir)
    merged = _read_yaml(path) if path.is_file() else {}
    merged.update(updates)
    _write_yaml(path, merged)
    return path


def config_sources(cfg: AuraConfig | None = None) -> list[tuple[str, Path, bool]]:
    """Return (label, path, loaded) for each config layer."""
    cfg = cfg or get_config()
    layers: list[tuple[str, Path, bool]] = []
    global_path = global_config_path(cfg.home)
    layers.append(("global", global_path, global_path.is_file()))
    if cfg.project_dir is not None:
        proj_path = project_config_path(cfg.project_dir)
        layers.append(("project", proj_path, proj_path.is_file()))
    return layers


def _apply_persisted_project(cfg: AuraConfig) -> AuraConfig:
    if cfg.project_dir is not None:
        return cfg
    persisted = cfg.values.get("project_dir")
    if not persisted:
        return cfg
    cfg.project_dir = Path(str(persisted)).expanduser().resolve()
    cfg.values = cfg.load(project_dir=cfg.project_dir)
    return cfg


def reload_config(project_dir: str | Path | None = None, **overrides: Any) -> AuraConfig:
    """Reset and rebuild global config (after YAML writes)."""
    global _config
    _config = None
    return configure(project_dir=project_dir, **overrides)
