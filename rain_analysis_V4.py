# rain_analysis_V4.py —— 自动识别降水事件 & 生成图表（matplotlib 版本）
# 包含：
#   analyze_rain_events：自动按“雨停”分段
#   plot_rain_events：降水事件强度随时间
#   plot_rain_runway_timeline：降水 & 跑道干湿时间轴

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties

# ================================
# 中文字体（尽量避免乱码）
# ================================
try:
    font = FontProperties(fname="/System/Library/Fonts/STHeiti Medium.ttc")  # macOS
    plt.rcParams["font.family"] = font.get_name()
except Exception:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS"]

plt.rcParams["axes.unicode_minus"] = False  # 负号不乱码

# ================================
# 雨强 → 数值映射
# ================================
RAIN_LEVEL_MAP = {
    "雨停": 0,
    "毛毛雨": 0.5,
    "小雨": 1,
    "中雨": 2,
    "大雨": 3,
    "暴雨": 4,
    "雷阵雨": 3.5,
}


# ---------------------------------------------------------
# 自动分段：把连续降水记录合并成降水事件
# ---------------------------------------------------------
def analyze_rain_events(df: pd.DataFrame):
    """
    df 需包含列：
      - 时间（datetime64）
      - 雨强（小雨/中雨/.../雨停）
    """
    df = df.copy()
    df["强度"] = df["雨强"].map(RAIN_LEVEL_MAP)
    df = df.sort_values("时间")

    events = []
    current = []

    for _, row in df.iterrows():
        if row["雨强"] != "雨停":
            current.append(row)
        else:
            # 雨停作为一个事件的结束
            current.append(row)
            events.append(current)
            current = []

    # 末尾如果没遇到“雨停”，也算一次事件
    if current:
        events.append(current)

    return [format_event(ev) for ev in events]


# ---------------------------------------------------------
# 格式化单个降水事件
# ---------------------------------------------------------
def format_event(records):
    times = [r["时间"] for r in records]
    rains = [r["雨强"] for r in records]
    strengths = [RAIN_LEVEL_MAP[r] for r in rains]

    start = times[0]
    end = times[-1]
    duration = (end - start).total_seconds() / 60
    max_rain = rains[strengths.index(max(strengths))]
    process = " → ".join(rains)

    report = f"""
### 【降水事件】
- 时间：{start.strftime('%Y-%m-%d %H:%M')} — {end.strftime('%H:%M')}（约 {int(duration)} 分钟）
- 过程：{process}
- 最强雨强：{max_rain}
"""

    return {"records": records, "report": report}


# ---------------------------------------------------------
# 降水事件强度随时间图
# ---------------------------------------------------------
def plot_rain_events(events):
    fig, ax = plt.subplots(figsize=(12, 5))

    colors = ["blue", "orange", "green", "red", "purple", "brown", "cyan"]

    for idx, ev in enumerate(events):
        records = ev["records"]
        times = [r["时间"] for r in records]
        vals = [RAIN_LEVEL_MAP[r["雨强"]] for r in records]

        ax.plot(
            times,
            vals,
            marker="o",
            linewidth=2,
            markersize=7,
            color=colors[idx % len(colors)],
            label=f"事件 {idx+1}",
        )

    ax.set_ylabel("降水强度等级", fontsize=12)
    ax.set_title("降水事件强度随时间变化", fontsize=14)

    ax.grid(True, linestyle="--", alpha=0.6)
    plt.xticks(rotation=45, ha="right")
    ax.legend()
    plt.tight_layout()

    return fig


# ---------------------------------------------------------
# 降水 + 跑道状态 时间轴
# ---------------------------------------------------------
def plot_rain_runway_timeline(rain_df: pd.DataFrame, runway_df: pd.DataFrame):
    """
    rain_df: DataFrame，列至少包含 ["时间","雨强"]
    runway_df: DataFrame，列至少包含 ["时间","跑道状态"]
    """
    fig, ax = plt.subplots(figsize=(12, 4))

    # 降水：y = 1
    if rain_df is not None and not rain_df.empty:
        ax.scatter(
            rain_df["时间"],
            [1] * len(rain_df),
            marker="o",
            s=60,
            label="降水",
        )
        for t, label in zip(rain_df["时间"], rain_df["雨强"]):
            ax.text(
                t,
                1.05,
                label,
                rotation=45,
                ha="left",
                va="bottom",
                fontsize=8,
            )

    # 跑道：y = 0
    if runway_df is not None and not runway_df.empty:
        ax.scatter(
            runway_df["时间"],
            [0] * len(runway_df),
            marker="s",
            s=60,
            label="跑道状态",
        )
        for t, label in zip(runway_df["时间"], runway_df["跑道状态"]):
            ax.text(
                t,
                -0.05,
                label,
                rotation=45,
                ha="right",
                va="top",
                fontsize=8,
            )

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["跑道状态", "降水"], fontsize=11)
    ax.set_ylim(-0.6, 1.6)

    ax.set_xlabel("时间", fontsize=12)
    ax.set_title("降水与跑道干湿状态时间轴", fontsize=14)

    ax.grid(True, axis="x", linestyle="--", alpha=0.5)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    return fig
