#!/usr/bin/env python3
"""Flask dashboard — serves live inverter metrics on port 5000."""

import time
from datetime import date

from flask import Flask, jsonify, render_template_string

import database
from config import DASHBOARD_HOST, DASHBOARD_PORT

app = Flask(__name__)

# HTML template, kept inline so there are no external template files to manage

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Inverter Monitor</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f1117;
      color: #e0e0e0;
      padding: 16px;
    }
    h1 { font-size: 1.3rem; color: #aaa; margin-bottom: 16px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .card {
      background: #1c1f2e;
      border-radius: 10px;
      padding: 16px;
      border: 1px solid #2a2d3e;
    }
    .card .label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { font-size: 2rem; font-weight: 700; margin: 4px 0 2px; }
    .card .sub   { font-size: 0.8rem; color: #aaa; }
    .green  { color: #4caf50; }
    .yellow { color: #ffca28; }
    .red    { color: #ef5350; }
    .blue   { color: #42a5f5; }
    .orange { color: #ffa726; }

    .soc-bar-wrap { background: #2a2d3e; border-radius: 6px; height: 8px; margin-top: 8px; overflow: hidden; }
    .soc-bar      { height: 100%; border-radius: 6px; transition: width 1s ease; }

    .section-title { color: #aaa; font-size: 0.8rem; text-transform: uppercase;
                     letter-spacing: 0.06em; margin: 20px 0 10px; }
    .row-stat {
      display: flex; justify-content: space-between; align-items: center;
      background: #1c1f2e; border-radius: 8px; padding: 10px 14px;
      margin-bottom: 8px; border: 1px solid #2a2d3e;
    }
    .row-stat .k { font-size: 0.85rem; color: #aaa; }
    .row-stat .v { font-weight: 600; font-size: 0.95rem; }
    .footer { font-size: 0.72rem; color: #555; margin-top: 20px; text-align: center; }
  </style>
</head>
<body>
  <h1>Inverter Monitor</h1>

  <div class="grid">
    <div class="card">
      <div class="label">Grid</div>
      <div class="value" id="grid-status">--</div>
      <div class="sub" id="grid-hours">--</div>
    </div>
    <div class="card">
      <div class="label">Solar PV</div>
      <div class="value blue" id="solar-w">--</div>
      <div class="sub" id="solar-kwh">-- kWh today</div>
    </div>
    <div class="card">
      <div class="label">Battery</div>
      <div class="value" id="bat-v">--</div>
      <div class="sub" id="bat-stage">--</div>
      <div class="soc-bar-wrap"><div class="soc-bar" id="soc-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <div class="label">Load</div>
      <div class="value orange" id="load-w">--</div>
      <div class="sub" id="load-pct">--</div>
    </div>
  </div>

  <div class="section-title">Details</div>
  <div class="row-stat">
    <span class="k">Battery SoC</span>
    <span class="v" id="bat-soc">--</span>
  </div>
  <div class="row-stat">
    <span class="k">Battery Voltage</span>
    <span class="v" id="bat-v2">--</span>
  </div>
  <div class="row-stat">
    <span class="k">Charge Stage</span>
    <span class="v" id="bat-stage2">--</span>
  </div>
  <div class="row-stat">
    <span class="k">AC Load (VA)</span>
    <span class="v" id="load-va">--</span>
  </div>
  <div class="row-stat">
    <span class="k">Solar Energy Today</span>
    <span class="v" id="solar-kwh2">--</span>
  </div>
  <div class="row-stat">
    <span class="k">Grid Availability Today</span>
    <span class="v" id="grid-avail">--</span>
  </div>
  <div class="row-stat">
    <span class="k">Last Reading</span>
    <span class="v" id="last-ts">--</span>
  </div>

  <div class="footer">Auto-refreshing every 10s &bull; Simba/Talegent 5KVA 48V</div>

<script>
function fmt(v, unit, decimals=0) {
  if (v === null || v === undefined) return '--';
  return Number(v).toFixed(decimals) + unit;
}
function socColor(pct) {
  if (pct >= 60) return '#4caf50';
  if (pct >= 30) return '#ffca28';
  return '#ef5350';
}
function fetchData() {
  fetch('/api/live')
    .then(r => r.json())
    .then(d => {
      const r = d.reading;
      const s = d.daily;
      const ts = r.ts ? new Date(r.ts * 1000).toLocaleTimeString() : '--';

      // Grid
      const gridOk = r.grid_ok;
      const gEl = document.getElementById('grid-status');
      gEl.textContent = gridOk === 1 ? 'ON' : gridOk === 0 ? 'OFF' : '--';
      gEl.className = 'value ' + (gridOk === 1 ? 'green' : gridOk === 0 ? 'red' : '');
      const gh = s.grid_on_sec ? (s.grid_on_sec / 3600).toFixed(1) + 'h today' : '--';
      document.getElementById('grid-hours').textContent = gh;

      // Solar
      document.getElementById('solar-w').textContent = fmt(r.solar_w, 'W');
      const kwh = s.solar_kwh ? s.solar_kwh.toFixed(2) + ' kWh today' : '-- kWh today';
      document.getElementById('solar-kwh').textContent = kwh;
      document.getElementById('solar-kwh2').textContent = s.solar_kwh ? s.solar_kwh.toFixed(2) + ' kWh' : '--';

      // Battery
      const soc = r.bat_soc;
      const batVText = fmt(r.bat_v, 'V', 1);
      const socText = soc !== null ? soc.toFixed(0) + '%' : '--';
      const batEl = document.getElementById('bat-v');
      batEl.textContent = batVText;
      batEl.className = 'value ' + (soc >= 60 ? 'green' : soc >= 30 ? 'yellow' : 'red');
      document.getElementById('bat-stage').textContent = r.bat_stage || '--';
      document.getElementById('bat-soc').textContent = socText;
      document.getElementById('bat-v2').textContent = batVText;
      document.getElementById('bat-stage2').textContent = r.bat_stage || '--';
      const bar = document.getElementById('soc-bar');
      bar.style.width = (soc || 0) + '%';
      bar.style.background = socColor(soc || 0);

      // Load
      document.getElementById('load-w').textContent = fmt(r.load_w, 'W');
      document.getElementById('load-pct').textContent = r.load_pct !== null ? r.load_pct.toFixed(0) + '% capacity' : '--';
      document.getElementById('load-va').textContent = fmt(r.load_va, ' VA');

      // Grid avail
      document.getElementById('grid-avail').textContent = s.grid_on_sec
        ? (s.grid_on_sec / 3600).toFixed(1) + ' h' : '--';

      document.getElementById('last-ts').textContent = ts;
    })
    .catch(e => console.error('Fetch error:', e));
}

fetchData();
setInterval(fetchData, 10000);
</script>
</body>
</html>
"""


# Routes

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/live")
def api_live():
    reading = database.get_latest()
    today = date.today().isoformat()
    daily = database.get_daily(today)
    return jsonify({"reading": reading, "daily": daily, "server_time": int(time.time())})


@app.route("/api/history")
def api_history():
    rows = database.get_history(hours=24)
    return jsonify(rows)


if __name__ == "__main__":
    database.init_db()
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)
