# db_V4.py —— 昆岛机场气象&跑道记录系统 V4 数据库模块

import sqlite3
from contextlib import contextmanager

DB_NAME = "kunda.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()

        # 预报表
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                wind TEXT,
                temp_min REAL,
                temp_max REAL,
                weather TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # METAR 解析结果表
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS metars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obs_time TEXT,
                station TEXT,
                raw TEXT,
                wind_dir TEXT,
                wind_speed REAL,
                wind_gust REAL,
                visibility INTEGER,
                temp REAL,
                dewpoint REAL,
                weather TEXT,
                rain_flag INTEGER,
                rain_level_cn TEXT,
                cloud_1_amount TEXT,
                cloud_1_height_m REAL,
                cloud_2_amount TEXT,
                cloud_2_height_m REAL,
                cloud_3_amount TEXT,
                cloud_3_height_m REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 降水记录表
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS rain_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT,        -- YYYY-MM-DD HH:MM
                rain_level_cn TEXT,     -- 小雨/中雨/大雨/暴雨/雷阵雨/毛毛雨/雨停
                rain_code TEXT,         -- -RA / RA / +RA / TSRA 等
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 跑道干湿状态表（V4 新增）
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS runway_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time TEXT,        -- YYYY-MM-DD HH:MM
                state TEXT,             -- 跑道干、跑道湿等
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        conn.commit()


# ---------------- 预报 ----------------
def insert_forecast(date_str, wind, temp_min, temp_max, weather):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO forecasts (date, wind, temp_min, temp_max, weather) "
            "VALUES (?, ?, ?, ?, ?)",
            (date_str, wind, temp_min, temp_max, weather),
        )
        conn.commit()


def get_forecasts(start_date, end_date):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT date, wind, temp_min, temp_max, weather
            FROM forecasts
            WHERE date BETWEEN ? AND ?
            ORDER BY date
            """,
            (start_date, end_date),
        )
        return c.fetchall()


# ---------------- METAR ----------------
def insert_metar(rec):
    station = rec["station"]
    obs = rec["obs_time"]
    raw = rec["raw"]

    wind_dir = str(rec.get("wind_direction")) if rec.get("wind_direction") else None
    wind_speed = rec.get("wind_speed")
    wind_gust = rec.get("wind_gust")
    vis = rec.get("visibility")
    temp = rec.get("temperature")
    dew = rec.get("dewpoint")

    weather_text = ", ".join(rec["weather"]) if rec["weather"] else None
    rain_flag = 1 if rec["is_raining"] else 0
    rain_level = rec.get("rain_type")

    clouds = rec.get("clouds", [])

    def cl(i):
        if i < len(clouds):
            return clouds[i]["amount"], clouds[i]["height_m"]
        return None, None

    c1, h1 = cl(0)
    c2, h2 = cl(1)
    c3, h3 = cl(2)

    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO metars (
                obs_time, station, raw,
                wind_dir, wind_speed, wind_gust,
                visibility, temp, dewpoint,
                weather, rain_flag, rain_level_cn,
                cloud_1_amount, cloud_1_height_m,
                cloud_2_amount, cloud_2_height_m,
                cloud_3_amount, cloud_3_height_m
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obs,
                station,
                raw,
                wind_dir,
                wind_speed,
                wind_gust,
                vis,
                temp,
                dew,
                weather_text,
                rain_flag,
                rain_level,
                c1,
                h1,
                c2,
                h2,
                c3,
                h3,
            ),
        )
        conn.commit()


def get_recent_metars(limit=100):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT
                obs_time, station, raw,
                wind_dir, wind_speed, wind_gust,
                visibility, temp, dewpoint,
                weather, rain_flag, rain_level_cn,
                cloud_1_amount, cloud_1_height_m,
                cloud_2_amount, cloud_2_height_m,
                cloud_3_amount, cloud_3_height_m
            FROM metars
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return c.fetchall()


# ---------------- 降水记录 ----------------
def insert_rain_event(time_str, rain_level, rain_code, note):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO rain_events (start_time, rain_level_cn, rain_code, note) "
            "VALUES (?, ?, ?, ?)",
            (time_str, rain_level, rain_code, note),
        )
        conn.commit()


def get_rain_events(start_date, end_date):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT start_time, rain_level_cn, rain_code, note
            FROM rain_events
            WHERE date(start_time) BETWEEN ? AND ?
            ORDER BY start_time
            """,
            (start_date, end_date),
        )
        return c.fetchall()


def get_rain_stats_by_day(start_date, end_date):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT date(start_time), COUNT(*)
            FROM rain_events
            WHERE date(start_time) BETWEEN ? AND ?
            GROUP BY date(start_time)
            ORDER BY date(start_time)
            """,
            (start_date, end_date),
        )
        return c.fetchall()


# ---------------- 跑道状态（V4 新增） ----------------
def insert_runway_state(time_str, state, note):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO runway_states (event_time, state, note) "
            "VALUES (?, ?, ?)",
            (time_str, state, note),
        )
        conn.commit()


def get_runway_states(start_date, end_date):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT event_time, state, note
            FROM runway_states
            WHERE date(event_time) BETWEEN ? AND ?
            ORDER BY event_time
            """,
            (start_date, end_date),
        )
        return c.fetchall()
