"""Plot the results written by experiment.py (reads summary.csv + run_config.json).

    python plot_results.py results/main
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
# Sequential blue ramp (light -> dark) for path lengths 6, 8, 10, 12, >=14.
LENGTH_COLORS = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
LOW_N = 30  # connected trials below this -> estimate flagged as unreliable

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": TEXT_2, "text.color": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12,
    "legend.frameon": False,
})


def load(outdir):
    with open(os.path.join(outdir, "run_config.json")) as f:
        config = json.load(f)
    rows = []
    with open(os.path.join(outdir, "summary.csv")) as f:
        for r in csv.DictReader(f):
            for key in ("percent_failed", "p_connected", "p_connected_lo95",
                        "p_connected_hi95", "p_connected_edge_bound", "mean_len",
                        "mean_len_ci95"):
                r[key] = float(r[key])
            r["trials"] = int(r["trials"])
            r["connected"] = int(r["connected"])
            r["length_counts"] = {int(d): c for d, c in json.loads(r["length_counts"]).items()}
            rows.append(r)
    return config, rows


def subtitle(config):
    return (f"k={config['k']} fat-tree, hosts {config['src']} → {config['dst']} "
            f"(different pods), {config['trials']} trials per point, "
            f"{config['eligible_links']} eligible links")


XLABEL = "Failed switch-to-switch links (% of edge–agg + agg–core links)"


def finish(fig, ax, config, title, path, xlabel=XLABEL):
    ax.set_xlabel(xlabel)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    ax.set_title(subtitle(config), loc="left", fontsize=9, color=TEXT_2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_path_length(config, rows, path):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ok = [r for r in rows if r["connected"] >= LOW_N]
    low = [r for r in rows if 0 < r["connected"] < LOW_N]
    none = [r for r in rows if r["connected"] == 0]

    ax.axhline(6, color=GRAY, lw=1, ls="--", zorder=1)
    ax.text(1, 6.08, "intact network: 6 hops", color=TEXT_2, fontsize=8, va="bottom")
    xs = [r["percent_failed"] for r in rows if r["connected"] > 0]
    ys = [r["mean_len"] for r in rows if r["connected"] > 0]
    ax.plot(xs, ys, color=BLUE, lw=2, zorder=2)
    for group, face, label in ((ok, BLUE, f"mean, ≥{LOW_N} connected trials"),
                               (low, SURFACE, f"mean, <{LOW_N} connected trials (unreliable)")):
        if not group:
            continue
        ax.errorbar([r["percent_failed"] for r in group], [r["mean_len"] for r in group],
                    yerr=[0 if r["connected"] < 2 else r["mean_len_ci95"] for r in group],
                    fmt="o", ms=7, mfc=face, mec=BLUE, mew=2, ecolor=BLUE, elinewidth=1.2,
                    capsize=3, label=label, zorder=3)
    for r in low:
        ax.annotate(f"n={r['connected']}", (r["percent_failed"], r["mean_len"]),
                    textcoords="offset points", xytext=(8, -12), fontsize=8, color=TEXT_2)
    if none:
        pts = ", ".join(f"{r['percent_failed']:.1f}%" for r in none)
        ax.text(0.99, 0.03, f"no connected trials at {pts} (not plotted)",
                transform=ax.transAxes, ha="right", fontsize=8, color=TEXT_2)
    ax.set_ylabel("Mean shortest path length (hops)\nover connected trials only")
    ax.set_xlim(left=-1)
    ax.legend(loc="upper left", fontsize=8.5, title="error bars: 95% CI of the mean",
              title_fontsize=8)
    return finish(fig, ax, config, "Average shortest path length, conditional on connectivity", path)


def plot_connectivity(config, rows, path):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = [r["percent_failed"] for r in rows]
    ax.fill_between(x, [r["p_connected_lo95"] for r in rows],
                    [r["p_connected_hi95"] for r in rows], color=BLUE, alpha=0.18, lw=0,
                    label="95% Wilson interval")
    ax.plot(x, [r["p_connected_edge_bound"] for r in rows], color=GRAY, lw=1.5, ls="--",
            label="upper bound: 1 − P(src or dst edge switch loses all uplinks), exact")
    ax.plot(x, [r["p_connected"] for r in rows], color=BLUE, lw=2, marker="o", ms=6,
            label="fraction of trials with a src–dst path")
    ax.set_ylim(-0.02, 1.04)
    ax.set_xlim(left=-1)
    ax.set_ylabel("Connectivity probability")
    ax.legend(loc="lower left", fontsize=8.5)
    return finish(fig, ax, config, "Probability that the two hosts remain connected", path)


def plot_distribution(config, rows, path):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    labels = ["6", "8", "10", "12", "≥14"]
    pos = range(len(rows))
    bottom = [0.0] * len(rows)

    def fractions(select):
        return [sum(c for d, c in r["length_counts"].items() if select(d)) / r["trials"]
                for r in rows]

    series = [fractions(lambda d, L=L: d == L) for L in (6, 8, 10, 12)]
    series.append(fractions(lambda d: d >= 14))
    series.append([1 - r["p_connected"] for r in rows])
    for vals, color, label in zip(series, LENGTH_COLORS + [GRAY],
                                  [f"{l} hops" for l in labels] + ["disconnected"]):
        ax.bar(pos, vals, bottom=bottom, color=color, edgecolor=SURFACE, linewidth=1,
               width=0.75, label=label, zorder=2)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(pos))
    ax.set_xticklabels([f"{r['percent_failed']:.1f}" for r in rows], rotation=45)
    ax.set_ylim(0, 1)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Fraction of trials")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8.5,
              title="shortest path", title_fontsize=8.5)
    return finish(fig, ax, config, "Distribution of the shortest path length (all trials)", path,
                  xlabel=XLABEL + "\n(one bar per tested rate; not to scale)")


def make_plots(outdir):
    config, rows = load(outdir)
    return [
        plot_path_length(config, rows, os.path.join(outdir, "avg_path_length.png")),
        plot_connectivity(config, rows, os.path.join(outdir, "connectivity_probability.png")),
        plot_distribution(config, rows, os.path.join(outdir, "path_length_distribution.png")),
    ]


if __name__ == "__main__":
    for p in make_plots(sys.argv[1] if len(sys.argv) > 1 else "results/main"):
        print(f"wrote {p}")
