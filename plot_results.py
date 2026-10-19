"""Plot the results written by experiment.py (reads summary.csv + run_config.json).

    python plot_results.py results
"""

import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"
GRAY = "#a3a29b"
LOW_N = 30  # fewer connected trials than this -> the average is labelled unreliable

XLABEL = "Failed switch-to-switch links (% of edge–agg + agg–core links)"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": TEXT_2, "text.color": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "legend.frameon": False,
})


def load(outdir):
    with open(os.path.join(outdir, "run_config.json")) as f:
        config = json.load(f)
    rows = []
    with open(os.path.join(outdir, "summary.csv")) as f:
        for r in csv.DictReader(f):
            for key in ("percent_failed", "p_connected", "mean_len"):
                r[key] = float(r[key])
            r["connected"] = int(r["connected"])
            rows.append(r)
    return config, rows


def finish(fig, ax, config, title, path):
    ax.set_xlabel(XLABEL)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    ax.set_title(f"k={config['k']} fat-tree, hosts {config['src']} → {config['dst']} "
                 f"(different pods), {config['trials']} trials per point",
                 loc="left", fontsize=9, color=TEXT_2)
    ax.set_xlim(left=-1)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_path_length(config, rows, path):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    conn = [r for r in rows if r["connected"] > 0]
    xs = [r["percent_failed"] for r in conn]
    ys = [r["mean_len"] for r in conn]

    ax.axhline(6, color=GRAY, lw=1, ls="--", zorder=1)
    ax.text(1, 6.08, "intact network: 6 hops", color=TEXT_2, fontsize=8, va="bottom")
    ax.plot(xs, ys, color=GRAY, lw=1.5, zorder=2)
    # Dot colour = connectivity probability, i.e. the share of trials the average is based on.
    dots = ax.scatter(xs, ys, c=[r["p_connected"] for r in conn], cmap="viridis_r",
                      vmin=0, vmax=1, s=60, edgecolors=TEXT_2, linewidths=0.6, zorder=3)
    cbar = fig.colorbar(dots, ax=ax, pad=0.02)
    cbar.set_label("Connectivity probability\n(share of trials in the average)", color=TEXT_2)
    cbar.outline.set_visible(False)
    for r in conn:
        if r["connected"] < LOW_N:  # too few connected trials: the average is unreliable
            ax.annotate(f"n={r['connected']} (unreliable)", (r["percent_failed"], r["mean_len"]),
                        textcoords="offset points", xytext=(-8, -14), ha="right",
                        fontsize=8, color=TEXT_2)
    none = [r for r in rows if r["connected"] == 0]
    if none:
        pts = ", ".join(f"{r['percent_failed']:.1f}%" for r in none)
        ax.text(0.99, 0.03, f"no connected trials at {pts} (not plotted)",
                transform=ax.transAxes, ha="right", fontsize=8, color=TEXT_2)
    ax.set_ylabel("Average shortest path length (hops)\nover connected trials only")
    return finish(fig, ax, config, "Average shortest path length (connected trials only)", path)


def plot_connectivity(config, rows, path):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.plot([r["percent_failed"] for r in rows], [r["p_connected"] for r in rows],
            color=BLUE, lw=2, marker="o", ms=6)
    ax.set_ylim(-0.02, 1.04)
    ax.set_ylabel("Connectivity probability\n(connected trials / all trials)")
    return finish(fig, ax, config, "Probability that the two hosts remain connected", path)


def make_plots(outdir):
    config, rows = load(outdir)
    return [
        plot_path_length(config, rows, os.path.join(outdir, "avg_path_length.png")),
        plot_connectivity(config, rows, os.path.join(outdir, "connectivity_probability.png")),
    ]


if __name__ == "__main__":
    for p in make_plots(sys.argv[1] if len(sys.argv) > 1 else "results"):
        print(f"wrote {p}")
