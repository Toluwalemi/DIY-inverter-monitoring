# DIY Inverter Monitoring

Lightweight Raspberry Pi monitor for a Simba/Talegent inverter.  
It reads inverter data over RS232, stores time-series data in SQLite, and serves a live Flask dashboard.

## Current Hardware Setup

- **Inverter:** Simba/Talegent, RS232 @ 2400 baud, firmware `R1.4.018`
- **Battery bank:** 24V flooded lead-acid (2 × 220Ah in series)
- **Solar:** 4 × 650W panels installed (note inverter PV input limit is 1200W)
- **Controller host:** Raspberry Pi 3B+ (`/dev/ttyUSB0` via CH340 USB-RS232 cable)

## Project Layout

- `reader.py` — polls inverter (`Q1\r`) and writes readings to SQLite
- `database.py` — DB schema and query helpers (`readings`, `daily_stats`)
- `dashboard.py` — Flask UI and JSON APIs
- `config.py` — serial, polling, battery curve, and dashboard settings
- `run.sh` — starts reader (background) + dashboard (foreground)
- `inverter-reader.service` / `inverter-dashboard.service` — systemd units

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Dashboard: `http://<your-pi-ip>:5000`

## Configuration

You can override key settings with environment variables:

- `INVERTER_PORT` (default `/dev/ttyUSB0`)
- `INVERTER_BAUD` (default `2400`)
- `POLL_INTERVAL` (default `10` seconds)
- `INVERTER_VA` (used for load estimation)
- `LOG_LEVEL` (default `INFO`)

Edit `config.py` for battery voltage-to-SoC tuning and charge-stage thresholds.

## API Endpoints

- `GET /` — live dashboard
- `GET /api/live` — latest reading + today summary
- `GET /api/history` — last 24h points
