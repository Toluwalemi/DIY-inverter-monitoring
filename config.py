import os

# Serial port settings
SERIAL_PORT = os.getenv("INVERTER_PORT", "/dev/ttyUSB0")
BAUD_RATE = int(os.getenv("INVERTER_BAUD", "2400"))
SERIAL_TIMEOUT = 5  # seconds

# Polling
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))  # seconds

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "inverter.db")

# Web dashboard
DASHBOARD_PORT = 5000
DASHBOARD_HOST = "0.0.0.0"

# Inverter rated capacity (VA) — used to estimate load watts from load %
INVERTER_RATED_VA = int(os.getenv("INVERTER_VA", "3000"))

# The inverter reports battery voltage at a scaled value internally.
# Calibrated by comparing raw Q1 field 6 against a multimeter reading:
#   raw=53.0V, actual measured=24.2V -> scale = 53.0 / 24.2 = 2.19
# To recalibrate: measure battery voltage with a multimeter, read raw Q1
# field 6 from reader.py --probe, then set scale = raw / measured.
BAT_VOLTAGE_SCALE = 2.19

# Battery voltage -> SoC % mapping for FLD 12V x2 in series (24V bank)
# These are RESTING / DISCHARGE voltages (open circuit approximations).
# During charging the voltage is artificially elevated by the charger.
BATTERY_VOLTAGE_SOC = [
    (21.0, 0),
    (23.0, 25),
    (24.0, 50),
    (26.0, 75),
    (27.6, 100),
]

# When battery voltage exceeds this, it is in charging mode (Absorption/Float).
# SoC is capped at 100% and the stage is inferred from voltage.
BAT_ABSORPTION_V = 29.0   # V — constant-voltage/absorption region for 24V FLD bank
BAT_FLOAT_V      = 27.0   # V — float (trickle) charge threshold

# Minimum PV input voltage (V) to consider solar active.
# Below this threshold it is night/overcast and solar_w is set to None.
PV_MIN_VOLTAGE = float(os.getenv("PV_MIN_VOLTAGE", "10.0"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
