"""Drawing the paper's figures with matplotlib: SVGs set in the paper's font, Old Standard TT, with their text
left as text, so Typst sets it like the body. The same figure always gives the same file, so a build can tell
when one changed."""

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib
from matplotlib import font_manager

from paper import FONTS

matplotlib.use("svg")
import matplotlib.pyplot as plt  # noqa: E402  (after choosing the backend)

for font in sorted(FONTS.glob("*.ttf")):
    font_manager.fontManager.addfont(str(font))
plt.rcParams["font.family"] = "Old Standard TT"  # so labels are measured as Typst will set them
plt.rcParams["svg.fonttype"] = "none"  # text stays text
plt.rcParams["svg.hashsalt"] = "paper"  # element ids don't change from one run to the next


def render[T](path: Path, draw: Callable[[Any, T], None], data: T, size: tuple[float, float]) -> str:
    """Draws `data` with draw(ax, data) on a figure of `size` inches, to the SVG at `path`. Returns the
    file's hash."""
    fig, ax = plt.subplots(figsize=size)
    try:
        draw(ax, data)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, bbox_inches="tight", metadata={"Date": None})
    finally:
        plt.close(fig)
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
