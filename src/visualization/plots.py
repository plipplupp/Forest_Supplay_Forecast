"""Återanvändbara diagramstil + sparning av figurer. Fas 3."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.config import FIGURES_DIR  # noqa: E402

# Diskret, färgblind-vänlig palett
COLORS = {
    "main": "#2C6E8F",      # petroleumsblå
    "accent": "#C46A2B",    # rostorange
    "neutral": "#7B8A93",
    "good": "#3F7D4E",
    "bad": "#A6423A",
    "grid": "#D9DEE2",
}

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "figure.facecolor": "white",
    }
)


def save_fig(fig: plt.Figure, name: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
