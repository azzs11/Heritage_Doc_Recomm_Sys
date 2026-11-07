"""Smoke tests — no ML dependencies required."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_pyproject_valid():
    """pyproject.toml exists, parses as valid TOML, and pins Python >=3.11."""
    path = ROOT / "pyproject.toml"
    assert path.exists(), "pyproject.toml not found"
    with open(path, "rb") as f:
        config = tomllib.load(f)
    assert config["project"]["requires-python"] == ">=3.11"


def test_dev_deps_declared():
    """ruff and pytest are listed in the dev dependency group."""
    path = ROOT / "pyproject.toml"
    with open(path, "rb") as f:
        config = tomllib.load(f)
    dev = " ".join(config["dependency-groups"]["dev"])
    assert "ruff" in dev
    assert "pytest" in dev


def test_requirements_txt_removed():
    """requirements.txt must not exist; pyproject.toml is the single source."""
    assert not (ROOT / "requirements.txt").exists(), "requirements.txt still exists — delete it and use pyproject.toml"
