#!/usr/bin/env python3
"""
Inverter serial reader — Simba/Talegent 3kVA 24V.

PROTOCOL DISCOVERY NOTES (confirmed via brute-force probing):
  - Baud rate: 2400, 8N1  (only rate that responds)
  - Protocol: custom single-letter + Q1 variant (NOT standard PIP/Voltronic)
  - Query command: Q1\r  (no CRC required, \r terminator only)
  - Response format: (f0 f1 f2 f3 f4 f5 f6 f7\r
    where fields are space-separated and:
      f0: grid input voltage (V) — 0 when grid is off
      f1: grid input frequency (Hz) — 0 when grid is off
      f2: AC output voltage (V)
      f3: AC output load percentage (%)
      f4: unknown / PV input voltage — always 0 on this unit, not usable
      f5: battery charge current (A) — proxy for solar power
      f6: battery voltage (V) — reported at 2x actual; divided by BAT_VOLTAGE_SCALE before use
      f7: 8-bit status flags (ASCII '0'/'1', MSB first)
             bit7=AC output active, remaining bits TBD

  Other confirmed commands:
      F\r  → #ac_v load_pct bat_charge_a freq
      I\r  → #<serial><firmware_version>
      Q\r  → ACK  (ready/alive check)

Run with --probe to dump raw discovery output.
"""

import os
import sys
import time
import logging
import argparse
from datetime import date

import serial

import database
from config import (
    SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT,
    POLL_INTERVAL, BATTERY_VOLTAGE_SOC,
    BAT_ABSORPTION_V, BAT_FLOAT_V,
    BAT_VOLTAGE_SCALE, INVERTER_RATED_VA, LOG_LEVEL,
)

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reader.log")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger("reader")


# Battery utilities

def voltage_to_soc(volts: float) -> float:
    """
    Interpolate SoC % from battery voltage using the resting discharge curve.
    This is most accurate when the battery is not actively being charged.
    When voltage is above the top of the curve the battery is full (100%).
    When below the bottom it is empty (0%).
    """
    points = BATTERY_VOLTAGE_SOC
    if volts <= points[0][0]:
        return 0.0
    if volts >= points[-1][0]:
        return 100.0
    for i in range(len(points) - 1):
        v0, s0 = points[i]
        v1, s1 = points[i + 1]
        if v0 <= volts <= v1:
            ratio = (volts - v0) / (v1 - v0)
            return round(s0 + ratio * (s1 - s0), 1)
    return 0.0


def infer_charge_stage(bat_v: float) -> str:
    """
    Determine battery stage from voltage alone.
    Field 5 in the Q1 response is not solar current — it stays non-zero
    at night and does not correlate with solar production, so it cannot
    be used to detect charging. Voltage thresholds are the only reliable signal.
    """
    if bat_v >= BAT_ABSORPTION_V:
        return "Absorption"
    if bat_v >= BAT_FLOAT_V:
        return "Float"
    return "Discharge"


# Q1 response parser

def parse_q1(raw: bytes) -> dict | None:
    """
    Parse the Q1\r response from the inverter.

    Expected format (starts with '(', space-separated):
      (grid_v grid_f ac_v load_pct pv_v charge_a bat_v flags\r
    """
    try:
        text = raw.decode("ascii", errors="replace").strip()
    except Exception:
        return None

    if not text.startswith("("):
        logger.debug("Q1 response doesn't start with '(': %r", text[:40])
        return None

    parts = text[1:].split()  # strip leading '('
    if len(parts) < 7:
        logger.warning("Q1 too short (%d fields): %r", len(parts), text[:60])
        return None

    try:
        grid_v   = float(parts[0])
        # parts[1] = grid frequency
        # parts[2] = AC output voltage
        load_pct = float(parts[3])
        pv_v     = float(parts[4])   # PV input voltage (V); 0 at night
        charge_a = float(parts[5])   # battery charge current (A); stays non-zero at night
        bat_v    = float(parts[6]) / BAT_VOLTAGE_SCALE
        flags    = parts[7] if len(parts) > 7 else "00000000"
    except (ValueError, IndexError) as e:
        logger.warning("Q1 parse error: %s — %r", e, text[:60])
        return None

    grid_ok   = 1 if grid_v > 100.0 else 0
    bat_stage = infer_charge_stage(bat_v)
    bat_soc   = voltage_to_soc(bat_v)

    # Field 4 (pv_v) is always 0 on this inverter — it does not report PV voltage.
    # Estimate solar charging power from charge current × battery voltage.
    # This may overcount slightly at night (inverter draws a small standby current)
    # but is the only available proxy for solar power on this protocol.
    solar_w = round(charge_a * bat_v, 0) if charge_a > 0 else None

    # Load watts estimated from load percentage and rated inverter capacity.
    # Assumes 0.8 power factor for mixed loads.
    load_va = round(load_pct / 100.0 * INVERTER_RATED_VA, 0)
    load_w  = round(load_va * 0.8, 0)

    return {
        "grid_ok":   grid_ok,
        "solar_w":   solar_w,
        "pv_v":      pv_v,
        "bat_v":     bat_v,
        "bat_soc":   bat_soc,
        "bat_stage": bat_stage,
        "load_w":    load_w,
        "load_va":   load_va,
        "load_pct":  load_pct,
        "raw_line":  text[:500],
    }


# Serial helpers

def open_serial() -> serial.Serial:
    logger.info("Opening %s at %d baud", SERIAL_PORT, BAUD_RATE)
    return serial.Serial(
        SERIAL_PORT,
        baudrate=BAUD_RATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=SERIAL_TIMEOUT,
    )


def send_command(ser: serial.Serial, cmd: bytes) -> bytes:
    """Send cmd and read until \\r or timeout."""
    ser.reset_input_buffer()
    time.sleep(0.2)
    ser.write(cmd)
    buf = bytearray()
    deadline = time.time() + SERIAL_TIMEOUT
    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            buf.extend(ser.read(n))
            if b'\r' in buf:
                break
        time.sleep(0.05)
    return bytes(buf)


# Probe mode

def probe_mode():
    """Print raw discovery output — useful for protocol debugging."""
    print("=== Inverter Protocol Probe ===\n")
    ser = open_serial()

    def qry(cmd, wait=3.0):
        ser.reset_input_buffer()
        time.sleep(0.3)
        ser.write(cmd)
        buf = bytearray()
        deadline = time.time() + wait
        while time.time() < deadline:
            n = ser.in_waiting
            if n:
                buf.extend(ser.read(n))
            time.sleep(0.05)
        return bytes(buf)

    print("Known working commands:")
    for cmd, label in [(b'Q1\r', 'Q1 (main status)'), (b'F\r', 'F (fast status)'),
                       (b'I\r', 'I (firmware/serial)'), (b'Q\r', 'Q (ping)')]:
        r = qry(cmd)
        txt = r.decode("ascii", errors="replace").strip()
        print(f"  {label:25s}: {txt!r}")
        time.sleep(0.5)

    print("\nQ1 field decode:")
    r = qry(b'Q1\r')
    txt = r.decode("ascii", errors="replace").strip()
    if txt.startswith("("):
        parts = txt[1:].split()
        labels = [
            "grid_voltage(V)", "grid_freq(Hz)", "ac_output_v(V)",
            "load_pct(%)", "pv_voltage(V?)", "charge_current(A)",
            "bat_voltage(V)", "status_flags"
        ]
        for i, p in enumerate(parts):
            lbl = labels[i] if i < len(labels) else f"field{i}"
            print(f"  [{i}] {lbl:25s}: {p}")

    ser.close()


# Main polling loop

def run_loop():
    database.init_db()
    ser = None
    consecutive_errors = 0

    while True:
        try:
            if ser is None or not ser.is_open:
                ser = open_serial()
                consecutive_errors = 0

            raw = send_command(ser, b'Q1\r')

            if not raw:
                logger.debug("No data from inverter")
                time.sleep(POLL_INTERVAL)
                continue

            txt = raw.decode("ascii", errors="replace").strip()
            if txt in ("NAK", "ACK") or not txt.startswith("("):
                logger.warning("Unexpected response: %r", txt[:40])
                time.sleep(POLL_INTERVAL)
                continue

            data = parse_q1(raw)
            if data is None:
                logger.warning("Parse failed: %r", raw[:60])
                time.sleep(POLL_INTERVAL)
                continue

            database.insert_reading(data)

            today = date.today().isoformat()
            database.update_daily_stats(
                today,
                data.get("solar_w") or 0,
                data.get("grid_ok") or 0,
                data.get("load_w") or 0,
                POLL_INTERVAL,
            )

            logger.info(
                "BAT %.1fV SoC %.0f%% [%s] | Solar ~%.0fW | Load %.0fW (%.0f%%) | Grid %s",
                data.get("bat_v") or 0,
                data.get("bat_soc") or 0,
                data.get("bat_stage", "?"),
                data.get("solar_w") or 0,
                data.get("load_w") or 0,
                data.get("load_pct") or 0,
                "ON" if data.get("grid_ok") else "OFF",
            )
            consecutive_errors = 0

        except serial.SerialException as e:
            consecutive_errors += 1
            logger.error("Serial error (%d): %s", consecutive_errors, e)
            if ser:
                try:
                    ser.close()
                except Exception:
                    pass
            ser = None
            time.sleep(min(10 * consecutive_errors, 60))
            continue

        except Exception as e:
            logger.exception("Unexpected error: %s", e)

        time.sleep(POLL_INTERVAL)


# Entry point

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true",
                        help="Probe mode: show raw commands and field decode")
    args = parser.parse_args()

    if args.probe:
        probe_mode()
    else:
        run_loop()
