"""Static dashboard contract tests."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402


def test_index_has_no_inline_style_attributes_under_csp():
    html = (HERE / "index.html").read_text(encoding="utf-8")
    js = (HERE / "app.js").read_text(encoding="utf-8")

    assert ' style="' not in html
    assert 'style="' not in js


def test_index_declares_served_favicon():
    html = (HERE / "index.html").read_text(encoding="utf-8")

    assert '<link rel="icon" href="/favicon.svg" type="image/svg+xml">' in html
    fname, ctype = server.STATIC["/favicon.svg"]
    assert ctype == "image/svg+xml; charset=utf-8"
    assert (HERE / fname).is_file()


def test_boot_renders_cached_snapshot_before_forcing_reminders():
    js = (HERE / "app.js").read_text(encoding="utf-8")

    cached = "poll(false);              // first paint"
    forced = "poll(true);               // refresh reminders"
    assert cached in js
    assert forced in js
    assert js.index(cached) < js.index(forced)
