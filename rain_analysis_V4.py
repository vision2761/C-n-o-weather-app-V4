# rain_analysis_V4.py —— 自动识别降水事件 & 生成图表（matplotlib 版本）
# 包含：
#   analyze_rain_events：自动按“雨停”分段
#   plot_rain_events：降水事件强度随时间
#   plot_rain_runway_timeline：降水 & 跑道干湿时间轴
#   split_wet_runway_episodes：按“湿跑道过程”拆成多段（给多张图用）

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties

# ================================
# 中文字体（尽量避免乱码）
# ================================
try:
    # 本地开发（Mac）优先用系统黑体
    CH_FONT = FontProperties(fname="/System/Library/Fonts/STHeiti Medium.ttc")
    plt.rcParams["font.family"] = CH_FONT.get_name()
except Exception:
    CH_FONT = None
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]

plt.rcParams["axes.unicode_minus"] = False  # 负号不乱码

# 用于 ax.text(...) 的字体参数
TEXT_KW = {"fontproperties": CH_FONT} if CH_FONT is not None else {}

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

# ---------------- 工具函数：跑道状态是否“干” ----------------
def is_runway_dry_state(state: str) -> bool:
    return state in ["跑道干", "跑道恢复干"]

def is_runway_wet_state(state: str) -> bool:
    return state in ["跑道湿", "跑道大部湿（仍视为干跑道）"]


# ---------------------------------------------------------
# 自动按“雨停”把降水记录分成多个降水事件（只看降水）
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
# 降水 + 跑道状态 时间轴（整体用）
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
                **TEXT_KW,
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
                **TEXT_KW,
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


# ---------------------------------------------------------
# 按“湿跑道过程”拆分成多段
# 规则：
#   - 第一次出现“有雨”（雨强 ≠ 雨停）且当前不在过程内 → 开始一个新的湿跑道过程
#   - 期间可能多次“雨停”、“再次下雨”，只要跑道没恢复干，都视作同一过程
#   - 当跑道状态记录为“跑道干 / 跑道恢复干” → 该湿跑道过程结束
#   - 下次再有雨时，再开一个新的过程
# ---------------------------------------------------------
def split_wet_runway_episodes(rain_df: pd.DataFrame, runway_df: pd.DataFrame):
    if (rain_df is None or rain_df.empty) and (runway_df is None or runway_df.empty):
        return []

    # 拷贝 & 排序
    r_df = rain_df.copy()
    rw_df = runway_df.copy()
    r_df = r_df.sort_values("时间")
    rw_df = rw_df.sort_values("时间")

    events = []

    # 合并时间线：kind = rain / runway
    for _, r in r_df.iterrows():
        events.append({"时间": r["时间"], "kind": "rain", "雨强": r["雨强"]})
    for _, r in rw_df.iterrows():
        events.append(
            {"时间": r["时间"], "kind": "runway", "跑道状态": r["跑道状态"]}
        )

    timeline = pd.DataFrame(events).sort_values("时间")

    episodes = []
    in_episode = False
    rain_records = []
    runway_records = []
    start_time = None
    end_time = None

    for _, ev in timeline.iterrows():
        kind = ev["kind"]

        # ===== 降水事件 =====
        if kind == "rain":
            level = ev["雨强"]
            t = ev["时间"]

            if level != "雨停":
                # 有雨
                if not in_episode:
                    # 新开一个湿跑道过程
                    in_episode = True
                    rain_records = []
                    runway_records = []
                    start_time = t
                rain_records.append({"时间": t, "雨强": level})
                end_time = t
            else:
                # 雨停
                if in_episode:
                    rain_records.append({"时间": t, "雨强": level})
                    end_time = t

        # ===== 跑道事件 =====
        else:
            state = ev["跑道状态"]
            t = ev["时间"]

            if in_episode:
                runway_records.append({"时间": t, "跑道状态": state})
                end_time = t

                if is_runway_dry_state(state):
                    # 跑道恢复干 → 本次湿跑道过程结束
                    ep_rain_df = pd.DataFrame(rain_records) if rain_records else pd.DataFrame(columns=["时间","雨强"])
                    ep_rw_df = pd.DataFrame(runway_records) if runway_records else pd.DataFrame(columns=["时间","跑道状态"])
                    episodes.append(
                        {
                            "start": start_time,
                            "end": end_time,
                            "rain_df": ep_rain_df,
                            "runway_df": ep_rw_df,
                        }
                    )
                    in_episode = False
                    rain_records = []
                    runway_records = []
                    start_time = None
                    end_time = None
            else:
                # 不在湿跑道过程中，跑道状态只作为背景，不计入任何过程
                pass

    # 如果最后还在过程里（还没恢复干），也输出一段
    if in_episode and (rain_records or runway_records):
        ep_rain_df = pd.DataFrame(rain_records) if rain_records else pd.DataFrame(columns=["时间","雨强"])
        ep_rw_df = pd.DataFrame(runway_records) if runway_records else pd.DataFrame(columns=["时间","跑道状态"])
        episodes.append(
            {
                "start": start_time,
                "end": end_time,
                "rain_df": ep_rain_df,
                "runway_df": ep_rw_df,
            }
        )

    return episodes
