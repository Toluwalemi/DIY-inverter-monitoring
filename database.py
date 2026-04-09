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
                pv_v        REAL,             -- PV input voltage (V)
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
                grid_on_sec INTEGER DEFAULT 0,
                load_kwh    REAL DEFAULT 0   -- energy consumed (estimated from load %)
            );

            CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);
        """)
        # Migration: add pv_v column to existing databases that predate this field
        try:
            conn.execute("ALTER TABLE readings ADD COLUMN pv_v REAL")
        except Exception:
            pass  # column already exists
    logger.info("Database initialised at %s", DB_PATH)


def insert_reading(data: dict):
    ts = int(time.time())
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO readings
                (ts, grid_ok, solar_w, pv_v, bat_v, bat_soc, bat_stage,
                 load_w, load_va, load_pct, raw_line)
            VALUES
                (:ts, :grid_ok, :solar_w, :pv_v, :bat_v, :bat_soc, :bat_stage,
                 :load_w, :load_va, :load_pct, :raw_line)
        """, {**data, "ts": ts})
    return ts


def update_daily_stats(date_str: str, solar_w: float, grid_ok: int, load_w: float, interval_sec: int):
    """Accumulate solar kWh, load kWh, and grid-on seconds for today."""
    solar_kwh_inc = (solar_w / 1000.0) * (interval_sec / 3600.0) if solar_w else 0
    load_kwh_inc  = (load_w  / 1000.0) * (interval_sec / 3600.0) if load_w  else 0
    grid_sec = interval_sec if grid_ok else 0
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO daily_stats (date, solar_kwh, grid_on_sec, load_kwh)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                solar_kwh   = solar_kwh   + excluded.solar_kwh,
                grid_on_sec = grid_on_sec + excluded.grid_on_sec,
                load_kwh    = load_kwh    + excluded.load_kwh
        """, (date_str, solar_kwh_inc, grid_sec, load_kwh_inc))


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
    return dict(row) if row else {"date": date_str, "solar_kwh": 0, "grid_on_sec": 0, "load_kwh": 0}


def get_history(hours: int = 24):
    since = int(time.time()) - hours * 3600
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ts, solar_w, bat_v, bat_soc, load_w, grid_ok "
            "FROM readings WHERE ts > ? ORDER BY ts ASC",
            (since,)
        ).fetchall()
    return [dict(r) for r in rows]
