"""Images for the channel post and the article (PNG, 16:9, light surface)."""
import os
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backtest import stats
from pm import ROOT, load

OUT = os.path.join(ROOT, "..", "channel", "img")
os.makedirs(OUT, exist_ok=True)

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
POS, NEG = "#2a78d6", "#e34948"
plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans"], "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})


def frame(title, subtitle):
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    fig.text(0.06, 0.92, title, fontsize=34, fontweight="bold", color=INK)
    fig.text(0.06, 0.865, subtitle, fontsize=19, color=INK2)
    fig.text(0.06, 0.03, "Polymarket, июнь 2025 – октябрь 2026 · t.me/architectkulees", fontsize=15, color=INK2)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, labelsize=18)
    return fig, ax


def hbars(ax, labels, vals, ci=None, fmt="{:+.0f}%"):
    y = list(range(len(labels)))[::-1]
    colors = [POS if v >= 0 else NEG for v in vals]
    ax.barh(y, vals, height=0.56, color=colors, edgecolor=SURFACE, linewidth=2, zorder=3)
    if ci:
        for yi, (lo, hi) in zip(y, ci):
            ax.plot([lo, hi], [yi, yi], color=INK2, linewidth=2, zorder=4, solid_capstyle="round")
            ax.plot([lo, lo], [yi - 0.12, yi + 0.12], color=INK2, linewidth=2, zorder=4)
            ax.plot([hi, hi], [yi - 0.12, yi + 0.12], color=INK2, linewidth=2, zorder=4)
    ax.axvline(0, color=INK2, linewidth=1.5, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=20, color=INK)
    ax.xaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0%"))
    for yi, v in zip(y, vals):
        ax.text(v + (2 if v >= 0 else -2), yi + (0.36 if ci else 0), fmt.format(v), va="center",
                ha="left" if v >= 0 else "right", fontsize=22, fontweight="bold", color=INK, zorder=5)


def pct(s):
    return s["roi"] * 100, (s["roi_lo"] * 100, s["roi_hi"] * 100)


def main():
    A = load("alerts.json")

    groups = [("Самые «инсайдерские»\n(балл ≥ 10)", [r for r in A if r["score"] >= 10]),
              ("Балл 8–9", [r for r in A if 8 <= r["score"] <= 9]),
              ("Балл 5–7", [r for r in A if 5 <= r["score"] <= 7]),
              ("Обычные крупные\nпокупки (≤ 4)", [r for r in A if r["score"] <= 4])]
    ss = [pct(stats(rows)) for _, rows in groups]
    fig, ax = frame("Сигнал «инсайдера» не предсказывает прибыль",
                    "Доход на $1 по баллу подозрительности · серые линии — 95% интервал: все пересекают ноль")
    hbars(ax, [g for g, _ in groups], [v for v, _ in ss], [c for _, c in ss])
    ax.set_xlim(-110, 110)
    fig.subplots_adjust(left=0.22, right=0.95, top=0.80, bottom=0.12)
    fig.savefig(os.path.join(OUT, "1_score.png"), facecolor=SURFACE)

    low = [r for r in A if 0.05 < r["price"] <= 0.30]
    prof = Counter()
    for r in low:
        prof[r["event"]] += r["roi"]
    top5 = {e for e, _ in prof.most_common(5)}
    vals = [stats(low)["roi"] * 100, stats([r for r in low if r["event"] not in top5])["roi"] * 100]
    fig, ax = frame("Вся «прибыль» — из пяти событий",
                    f"Крупные покупки исходов по 5–30 центов, {len(low):,} ставок · доход на $1".replace("5,5", "5 5"))
    hbars(ax, ["Все события", "Без 5 самых удачных\n(ЧМ-2026, Иран)"], vals)
    ax.set_xlim(-40, 75)
    fig.subplots_adjust(left=0.22, right=0.95, top=0.80, bottom=0.12)
    fig.savefig(os.path.join(OUT, "2_top5.png"), facecolor=SURFACE)

    names = {"sports": "Спорт", "geopolitics": "Геополитика", "culture": "Культура",
             "esports": "Киберспорт", "business": "Бизнес", "politics": "Политика"}
    rows = sorted(((names[c], stats([r for r in A if r["category"] == c])) for c in names),
                  key=lambda x: -x[1]["roi"])
    fig, ax = frame("Политика — кладбище крупных ставок",
                    "Доход на $1 по категориям, все крупные покупки · серые линии — 95% интервал")
    hbars(ax, [n for n, _ in rows], [s["roi"] * 100 for _, s in rows], [pct(s)[1] for _, s in rows])
    ax.set_xlim(-60, 100)
    fig.subplots_adjust(left=0.18, right=0.95, top=0.80, bottom=0.12)
    fig.savefig(os.path.join(OUT, "3_categories.png"), facecolor=SURFACE)
    print("saved to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
