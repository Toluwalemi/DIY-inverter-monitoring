import sqlite3
import time
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          INTEGER NOT NULL,
                grid_ok     INTEGER,          -- 1=ON, 0=OFF
                solar_w     REAL,             -- PV watts
                bat_v       REAL,             -- battery voltage
                bat_soc     REAL,             -- SoC %
                bat_stage   TEXT,             -- Bulk/Absorption/Float/Discharge
                load_w      REAL,             -- AC output watts
                load_va     REAL,             -- AC output VA
                load_pct    REAL,             -- load %
                raw_line    TEXT              -- raw serial line for debug
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date        TEXT PRIMARY KEY, -- YYYY-MM-DD
                solar_kwh   REAL DEFAULT 0,
                grid_on_sec INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);
        """)
    logger.info("Database initialised at %s", DB_PATH)


def insert_reading(data: dict):
    ts = int(time.time())
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO readings
                (ts, grid_ok, solar_w, bat_v, bat_soc, bat_stage,
                 load_w, load_va, load_pct, raw_line)
            VALUES
                (:ts, :grid_ok, :solar_w, :bat_v, :bat_soc, :bat_stage,
                 :load_w, :load_va, :load_pct, :raw_line)
        """, {**data, "ts": ts})
    return ts


def update_daily_stats(date_str: str, solar_w: float, grid_ok: int, interval_sec: int):
    """Accumulate solar kWh and grid-on seconds for today."""
    kwh_increment = (solar_w / 1000.0) * (interval_sec / 3600.0) if solar_w else 0
    grid_sec = interval_sec if grid_ok else 0
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO daily_stats (date, solar_kwh, grid_on_sec)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                solar_kwh   = solar_kwh   + excluded.solar_kwh,
                grid_on_sec = grid_on_sec + excluded.grid_on_sec
        """, (date_str, kwh_increment, grid_sec))


def get_latest():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM readings ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else {}


def get_daily(date_str: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_stats WHERE date = ?", (date_str,)
        ).fetchone()
    return dict(row) if row else {"date": date_str, "solar_kwh": 0, "grid_on_sec": 0}


def get_history(hours: int = 24):
    since = int(time.time()) - hours * 3600
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ts, solar_w, bat_v, bat_soc, load_w, grid_ok "
            "FROM readings WHERE ts > ? ORDER BY ts ASC",
            (since,)
        ).fetchall()
    return [dict(r) for r in rows]
