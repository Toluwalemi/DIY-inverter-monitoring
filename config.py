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

# The inverter reports battery voltage at 2x the real value internally.
# Confirmed: raw Q1 field 6 reads ~54V while actual 24V bank sits at ~27V.
# Every bat_v reading is divided by this before being stored or displayed.
BAT_VOLTAGE_SCALE = 2.0

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

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
