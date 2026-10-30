"""
scripts/plot_video.py -- Person 3.

The result charts (README and video), read from the `final250-*` retrieval-only
reports (100 answerable questions per mailbox; no network, no credits):

1. hit@5 per mailbox: flat, PARA with the owner's folder (oracle), PARA routed
   by Nemotron Super and by Nemotron Ultra.
2. The oracle's gain over flat (hit@5 and MRR) with its 95% bootstrap interval.
3. Where Super and Ultra send each question, by the folder that holds the answer.

matplotlib is not a project dependency:

    uv run --with matplotlib python -m scripts.plot_video
"""

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPORTS = Path(".cache/reports")
MAILBOXES = {"kaminski": "Kaminski (research)", "shapiro": "Shapiro (gov. affairs)"}
FOLDERS = ("projects", "areas", "resources")

# Reference palette, light mode (dataviz skill): the first three categorical
# slots validate all-pairs; flat is the gray baseline, not a series hue.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
FLAT = "#a9a8a2"
ORACLE = "#2a78d6"
SUPER = "#eb6834"
ULTRA = "#1baf7a"
NO_FOLDER = "#d6d5d0"
WRONG_OTHER = "#7d7c77"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 20,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "text.color": INK,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
    }
)

ROW = re.compile(
    r"^\| (?P<group>\S+) \| (?P<n>\d+) \| \d+ \| (?P<flat>[\d.]+) \| (?P<para>[\d.]+) "
    r"\| [^|]+ \| \**(?P<diff>[-+]?[\d.]+)\** \| \[(?P<lo>[-+]?[\d.]+), (?P<hi>[-+]?[\d.]+)\] \|$"
)
ROUTE = re.compile(
    r"^\| (projects|areas|resources) \| (\d+) \| (\d+) \(\d+%\) \| \d+ \| (.*) \|$"
)


def section(text: str, title: str) -> list[str]:
    lines = text.split("\n## " + title + "\n", 1)[1].split("\n## ", 1)[0]
    return lines.splitlines()


def overall(run: str, metric: str) -> dict:
    text = (REPORTS / f"final250-{run}.md").read_text()
    for line in section(text, f"{metric} overall"):
        if m := ROW.match(line):
            return {k: float(v) for k, v in m.groupdict().items() if k != "group"}
    raise SystemExit(f"no overall {metric} row in {run}")


def routing(run: str) -> dict[str, dict[str, int]]:
    """True folder -> {chosen folder: count}."""
    text = (REPORTS / f"final250-{run}.md").read_text()
    out = {}
    for line in section(text, "PARA routing (query classifier)"):
        if m := ROUTE.match(line):
            out[m[1]] = {
                name: int(count)
                for name, count in (part.rsplit(" ", 1) for part in m[4].split(", "))
            }
    return out


def clean(ax) -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def title(fig, text: str, sub: str) -> None:
    fig.text(0.05, 0.93, text, fontsize=31, fontweight="bold", color=INK)
    fig.text(0.05, 0.875, sub, fontsize=21, color=INK_2)


def chart_hit(out: Path) -> None:
    arms = [
        ("Flat index", FLAT, lambda b: overall(f"{b}-oracle", "hit@5")["flat"]),
        (
            "PARA · owner's folder",
            ORACLE,
            lambda b: overall(f"{b}-oracle", "hit@5")["para"],
        ),
        (
            "PARA · routed by Super",
            SUPER,
            lambda b: overall(f"{b}-super", "hit@5")["para"],
        ),
        (
            "PARA · routed by Ultra",
            ULTRA,
            lambda b: overall(f"{b}-ultra", "hit@5")["para"],
        ),
    ]
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.8, bottom=0.17)
    width, gap = 0.19, 0.012
    for i, (label, color, value) in enumerate(arms):
        for j, box in enumerate(MAILBOXES):
            x = j + (i - 1.5) * (width + gap)
            v = value(box)
            ax.bar(x, v, width, color=color, label=label if j == 0 else None, zorder=2)
            ax.text(
                x,
                v + 0.015,
                f"{v:.2f}",
                ha="center",
                va="bottom",
                fontsize=22,
                color=INK,
            )
    ax.set_xticks(
        range(len(MAILBOXES)), list(MAILBOXES.values()), fontsize=24, color=INK
    )
    ax.set_ylim(0, 1.08)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_ylabel("hit@5 — right email in the top 5")
    clean(ax)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.09),
        ncol=4,
        frameon=False,
        fontsize=20,
        handlelength=1.2,
    )
    title(
        fig,
        "PARA helps with the owner's folder; automatic routing is still hard",
        "Enron, two real mailboxes · 100 human-verified questions each · same index, same questions",
    )
    fig.savefig(out / "1_hit_at_5.png")
    plt.close(fig)


def chart_gain(out: Path) -> None:
    rows = []
    for box, name in MAILBOXES.items():
        for metric, label in (("hit@5", "hit@5"), ("mrr", "MRR")):
            r = overall(f"{box}-oracle", metric)
            rows.append((f"{name}\n{label}", r["diff"], r["lo"], r["hi"]))
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
    fig.subplots_adjust(left=0.27, right=0.95, top=0.76, bottom=0.14)
    ys = list(range(len(rows)))[::-1]
    for y, (_, diff, lo, hi) in zip(ys, rows, strict=True):
        ax.plot(
            [lo, hi],
            [y, y],
            color=ORACLE,
            linewidth=3,
            solid_capstyle="round",
            zorder=2,
        )
        ax.plot(
            diff,
            y,
            "o",
            color=ORACLE,
            markersize=16,
            markeredgecolor=SURFACE,
            markeredgewidth=2,
            zorder=3,
        )
        ax.text(
            hi + 0.004,
            y,
            f"{diff:+.2f}  [{lo:+.2f}, {hi:+.2f}]",
            va="center",
            fontsize=21,
            color=INK,
        )
    ax.axvline(0, color=INK_2, linewidth=1.5, zorder=1)
    ax.set_yticks(ys, [r[0] for r in rows], fontsize=21, color=INK)
    ax.set_xlim(-0.03, 0.14)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.xaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_xlabel(
        "PARA with the owner's folder − flat (dot: mean · line: 95% bootstrap interval)"
    )
    clean(ax)
    title(
        fig,
        "With the owner's folder, PARA ranks the answer higher",
        "Gain over the flat index, both mailboxes · MRR gain significant in both · hit@5 near its ceiling (flat 0.91–0.95)",
    )
    fig.savefig(out / "2_oracle_gain.png")
    plt.close(fig)


def chart_routing(out: Path) -> None:
    segments = [
        ("Right folder", ORACLE),
        ("Sent to resources instead", SUPER),
        ("Sent to another folder", WRONG_OTHER),
        ("Archive (empty: falls back to flat)", NO_FOLDER),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(19.2, 10.8), dpi=100, sharey=True)
    fig.subplots_adjust(left=0.14, right=0.97, top=0.74, bottom=0.2, wspace=0.14)
    for ax, (model, label) in zip(
        axes, (("super", "Nemotron Super"), ("ultra", "Nemotron Ultra")), strict=True
    ):
        pooled = {f: {} for f in FOLDERS}
        for box in MAILBOXES:
            for true, picks in routing(f"{box}-{model}").items():
                for chosen, count in picks.items():
                    pooled[true][chosen] = pooled[true].get(chosen, 0) + count
        for y, true in enumerate(reversed(FOLDERS)):
            picks = pooled[true]
            n = sum(picks.values())
            right = picks.get(true, 0)
            to_res = 0 if true == "resources" else picks.get("resources", 0)
            none = picks.get("archive", 0)
            other = n - right - to_res - none
            left = 0.0
            for (name, color), count in zip(
                segments, (right, to_res, other, none), strict=True
            ):
                share = count / n
                if share:
                    ax.barh(
                        y, share - 0.004, left=left, height=0.62, color=color, zorder=2
                    )
                    if share >= 0.05:
                        ink = SURFACE if color in (ORACLE, SUPER, WRONG_OTHER) else INK
                        ax.text(
                            left + share / 2,
                            y,
                            f"{share:.0%}",
                            ha="center",
                            va="center",
                            fontsize=21 if share >= 0.08 else 16,
                            color=ink,
                            fontweight="bold",
                        )
                left += share
        ax.set_title(label, fontsize=26, color=INK, pad=14, fontweight="bold")
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.5, 1], ["0%", "50%", "100%"])
        clean(ax)
    axes[0].set_yticks(
        range(3), [f"answer in\n{f}" for f in reversed(FOLDERS)], fontsize=22, color=INK
    )
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in segments]
    fig.legend(
        handles,
        [s for s, _ in segments],
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=20,
        bbox_to_anchor=(0.55, 0.05),
        handlelength=1.2,
    )
    title(
        fig,
        "Routing is the hard part: both models lean toward Resources",
        "Where the query router sends each question · both mailboxes pooled (66–68 questions per row)",
    )
    fig.savefig(out / "3_routing.png")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", type=Path, default=Path("assets"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    chart_hit(args.out)
    chart_gain(args.out)
    chart_routing(args.out)
    print(f"3 charts -> {args.out}")


if __name__ == "__main__":
    main()
