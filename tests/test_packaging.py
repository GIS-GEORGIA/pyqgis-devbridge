"""Packaging: `pip install -e .` (used everywhere else in this repo's own test
suite) can't catch a missing package-data entry, because an editable install
just points back at the source tree - the i18n JSON files are found next to
i18n_util.py regardless. A real (non-editable) wheel build is the only thing
that actually exercises this (see the CI 'wheel' job), and was confirmed once
by hand to drop the files silently without the pyproject.toml section this
test locks in. A plain text search avoids depending on a TOML parser that
isn't otherwise needed (tomllib only ships from Python 3.11)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_package_data_declares_the_i18n_files():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"\[tool\.setuptools\.package-data\]\n(.*?)(\n\[|\Z)", text, re.S)
    assert section, "no [tool.setuptools.package-data] section in pyproject.toml"
    assert "i18n" in section.group(1) and ".json" in section.group(1), section.group(1)
