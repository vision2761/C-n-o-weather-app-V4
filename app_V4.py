# app_V4.py —— ✈ 昆岛机场气象&跑道记录系统 V4

import streamlit as st
import pandas as pd
import re

from db_V4 import (
    init_db,
    insert_forecast,
    get_forecasts,
    insert_metar,
    get_recent_metars,
    insert_rain_event,
    get_rain_events,
    get_rain_stats_by_day,
    insert_runway_state,
    get_runway_states,
)
from metar_parser_V4 import parse_metar
from rain_analysis_V4 import (
    analyze_rain_events,
    plot_rain_events,
    plot_rain_runway_timeline,
    split_wet_runway_episodes,   # ✅ 新增
)

st.set_page_config(page_title="昆岛机场气象&跑道记录系统 V4", layout="wide")

# 初始化数据库
init_db()


# ============================================================
# 通用：数字时间解析（如 1130 / 1201 / 1624）
# ============================================================
def parse_time_numeric(s: str):
    s = (s or "").strip()
    if not s.isdigit():
        return None
    if len(s) == 4:  # HHMM
        hh, mm = s[:2], s[2:]
    elif len(s) == 3:  # HMM
        hh, mm = "0" + s[0], s[1:]
    elif len(s) == 2:  # MM
        hh, mm = "00", s
    elif len(s) == 1:  # M
        hh, mm = "00", "0" + s
    else:
        return None
    try:
        hh_i = int(hh)
        mm_i = int(mm)
        if not (0 <= hh_i <= 23 and 0 <= mm_i <= 59):
            return None
    except Exception:
        return None
    return f"{hh}:{mm}"


# ============================================================
# 1）天气预报
# ============================================================
def page_forecast():
    st.header("📋 昆岛天气预报录入与查询")

    c1, c2 = st.columns(2)
    with c1:
        date_val = st.date_input("预报日期")
    with c2:
        wind = st.text_input("风向/风速（如 030/05）")

    c3, c4 = st.columns(2)
    with c3:
        temp_min = st.number_input("最低气温 (℃)", value=25.0, format="%.1f")
    with c4:
        temp_max = st.number_input("最高气温 (℃)", value=28.0, format="%.1f")

    weather = st.text_input("天气现象（可自由填写）")

    if st.button("保存预报记录"):
        insert_forecast(str(date_val), wind, temp_min, temp_max, weather)
        st.success("✅ 预报记录已保存")

    st.markdown("---")
    st.subheader("📑 历史预报查询")

    s1, s2 = st.columns(2)
    with s1:
        start = st.date_input("开始日期", key="fc_s")
    with s2:
        end = st.date_input("结束日期", key="fc_e")

    if st.button("查询预报记录"):
        rows = get_forecasts(str(start), str(end))
        if not rows:
            st.info("此时间段无记录")
            return
        df = pd.DataFrame(rows, columns=["日期", "风向风速", "最低温", "最高温", "天气现象"])
        st.dataframe(df, use_container_width=True)


# ============================================================
# 2）METAR 多条解析
# ============================================================
def page_metar():
    st.header("🛬 METAR 报文解析（支持一次粘贴多条）")

    raw_block = st.text_area(
        "输入报文：",
        height=200,
        placeholder=(
            "示例：\n"
            "Rx 210326Z METAR VVCS 210330Z 07008KT 340V130 9999 SCT015 BKN040 28/24 Q1011 TEMPO 10016G28KT=\n"
            "Rx 210332Z METAR VVCT 210330Z 01006KT 9999 SCT015 BKN040 27/23 Q1012 NOSIG=\n"
            "...\n"
            "仍然按 '=' 作为每条报文结束。"
        ),
    )

    if st.button("解析并保存所有报文"):
        text = raw_block.strip()
        if not text:
            st.warning("请先输入报文")
            return

        parts = text.split("=")
        count = 0
        for p in parts:
            t = p.strip()
            if not t:
                continue
            one_line = " ".join(t.split())
            rec = parse_metar(one_line)
            insert_metar(rec)
            count += 1

        st.success(f"✅ 共解析并保存 {count} 条报文")

    st.markdown("---")
    st.subheader("📑 最近 METAR 解析记录")

    rows = get_recent_metars(limit=200)
    if not rows:
        st.info("暂无记录")
        return

    df = pd.DataFrame(
        rows,
        columns=[
            "UTC时间",
            "站号",
            "原始报文",
            "风向(°)",
            "风速(kt)",
            "阵风(kt)",
            "能见度(m)",
            "温度(℃)",
            "露点(℃)",
            "天气(中文)",
            "是否雨",
            "雨型",
            "云1量",
            "云1高(m)",
            "云2量",
            "云2高(m)",
            "云3量",
            "云3高(m)",
        ],
    )

    # 越南时间 UTC+7
    def to_vn(t):
        if not isinstance(t, str):
            return ""
        m = re.match(r"(\d{2})(\d{2})(\d{2})Z", t)
        if not m:
            return ""
        dd, hh, mm = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh2 = hh + 7
        add = 0
        if hh2 >= 24:
            hh2 -= 24
            add = 1
        return f"{dd+add:02d}日 {hh2:02d}:{mm:02d}"

    df.insert(1, "越南时间(UTC+7)", df["UTC时间"].apply(to_vn))

    st.dataframe(df, use_container_width=True)


# ============================================================
# 3）降水记录 & 跑道记录（V4 核心）
# ============================================================
def page_rain_runway():
    st.header("🌧 降水过程记录 & 跑道干湿状态记录（V4）")

    # ---------- A. 降水节点记录 ----------
    st.subheader("A. 记录降水变化节点")

    c1, c2 = st.columns(2)
    with c1:
        rain_date = st.date_input("降水日期", key="rain_date")
    with c2:
        rain_time_raw = st.text_input("时间（如1130,1201,1624）", key="rain_time")

    rain_time_hhmm = parse_time_numeric(rain_time_raw)
    rain_time_str = f"{rain_date} {rain_time_hhmm}" if rain_time_hhmm else None

    rain_level = st.selectbox(
        "雨强",
        ["毛毛雨", "小雨", "中雨", "大雨", "暴雨", "雷阵雨", "雨停"],
        key="rain_level",
    )
    rain_code = st.text_input(
        "对应报文代码（如 -RA、RA、+RA、TSRA 等，可选）", key="rain_code"
    )
    rain_note = st.text_input("备注（可选）", key="rain_note")

    if st.button("保存降水记录"):
        if not rain_time_str:
            st.error("时间格式错误，请输入类似 1130/1201/1624 的数字")
        else:
            insert_rain_event(rain_time_str, rain_level, rain_code, rain_note)
            st.success(f"✅ 已记录降水：{rain_time_str} — {rain_level}")

    st.markdown("---")

    # ---------- B. 跑道干湿状态记录 ----------
    st.subheader("B. 记录跑道干湿状态（与降水过程对应）")

    r1, r2 = st.columns(2)
    with r1:
        rw_date = st.date_input("跑道状态日期", key="rw_date")
    with r2:
        rw_time_raw = st.text_input("时间（如1130,1201,1624）", key="rw_time")

    rw_time_hhmm = parse_time_numeric(rw_time_raw)
    rw_time_str = f"{rw_date} {rw_time_hhmm}" if rw_time_hhmm else None

    rw_state = st.selectbox(
        "跑道状态",
        [
            "跑道干",
            "跑道大部湿（仍视为干跑道）",
            "跑道湿",
            "跑道恢复干",
        ],
        key="rw_state",
    )
    rw_note = st.text输入 = st.text_input("跑道备注（可选，如 T/O 滑跑明显）", key="rw_note")

    if st.button("保存跑道状态记录"):
        if not rw_time_str:
            st.error("时间格式错误，请输入类似 1130/1201/1624 的数字")
        else:
            insert_runway_state(rw_time_str, rw_state, rw_note)
            st.success(f"✅ 已记录跑道状态：{rw_time_str} — {rw_state}")

    st.markdown("---")

    # ---------- C. 历史降水 & 跑道查询 + 时间轴 ----------
    st.subheader("C. 历史降水 & 跑道状态查询（含时间轴）")

    q1, q2 = st.columns(2)
    with q1:
        start = st.date_input("开始日期", key="his_start")
    with q2:
        end = st.date_input("结束日期", key="his_end")

    if st.button("查询降水 & 跑道历史"):
        # 降水
        rain_rows = get_rain_events(str(start), str(end))
        if rain_rows:
            df_rain = pd.DataFrame(rain_rows, columns=["时间", "雨强", "报文代码", "备注"])
            df_rain["时间"] = pd.to_datetime(df_rain["时间"])
            df_rain = df_rain.sort_values("时间")
            st.subheader("📑 降水记录")
            st.dataframe(df_rain, use_container_width=True)
        else:
            df_rain = pd.DataFrame(columns=["时间", "雨强"])
            st.info("该时间段无降水记录")

        # 跑道
        rw_rows = get_runway_states(str(start), str(end))
        if rw_rows:
            df_rw = pd.DataFrame(rw_rows, columns=["时间", "跑道状态", "备注"])
            df_rw["时间"] = pd.to_datetime(df_rw["时间"])
            df_rw = df_rw.sort_values("时间")
            st.subheader("📑 跑道干湿状态记录")
            st.dataframe(df_rw, use_container_width=True)
        else:
            df_rw = pd.DataFrame(columns=["时间", "跑道状态"])
            st.info("该时间段无跑道状态记录")

        # ① 整体时间轴
        if not df_rain.empty or not df_rw.empty:
            st.subheader("🕒 降水 & 跑道干湿状态时间轴（整体）")
            fig_all = plot_rain_runway_timeline(df_rain, df_rw)
            st.pyplot(fig_all)

            # ② 按“湿跑道过程”拆分，多张图展示
            episodes = split_wet_runway_episodes(df_rain, df_rw)
            if episodes:
                st.subheader("🌧 各次湿跑道过程（分图显示）")
                for idx, ep in enumerate(episodes, start=1):
                    start_t = ep["start"].strftime("%Y-%m-%d %H:%M") if ep["start"] else "?"
                    end_t = ep["end"].strftime("%H:%M") if ep["end"] else "?"
                    st.markdown(f"**湿跑道过程 {idx}：{start_t} ~ {end_t}**")
                    fig_ep = plot_rain_runway_timeline(ep["rain_df"], ep["runway_df"])
                    st.pyplot(fig_ep)
            else:
                st.info("尚未形成完整的湿跑道过程（可能缺少“跑道恢复干”的记录）。")
        else:
            st.info("无可绘制的时间轴数据")


# ============================================================
# 4）自动降水事件分析
# ============================================================
def page_rain_analysis():
    st.header("📘 自动降水事件分析")

    a1, a2 = st.columns(2)
    with a1:
        start = st.date_input("开始日期", key="ana_start")
    with a2:
        end = st.date_input("结束日期", key="ana_end")

    if st.button("生成降水事件分析"):
        rows = get_rain_events(str(start), str(end))
        if not rows:
            st.info("该时间段无降水记录")
            return

        df = pd.DataFrame(rows, columns=["时间", "雨强", "代码", "备注"])
        df["时间"] = pd.to_datetime(df["时间"])
        events = analyze_rain_events(df)

        st.subheader("📝 降水事件文本报告")
        for ev in events:
            st.markdown(ev["report"])

        st.subheader("📈 降水事件强度随时间变化")
        fig = plot_rain_events(events)
        st.pyplot(fig)


# ============================================================
# 主程序入口
# ============================================================
def main():
    st.title("✈ 昆岛机场气象&跑道记录系统 V4")

    page = st.sidebar.radio(
        "功能选择",
        [
            "天气预报",
            "METAR 多条解析",
            "降水 & 跑道记录",
            "自动降水事件分析",
        ],
    )

    if page == "天气预报":
        page_forecast()
    elif page == "METAR 多条解析":
        page_metar()
    elif page == "降水 & 跑道记录":
        page_rain_runway()
    elif page == "自动降水事件分析":
        page_rain_analysis()


if __name__ == "__main__":
    main()
