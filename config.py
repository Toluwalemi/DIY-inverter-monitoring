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
INVERTER_RATED_VA = int(os.getenv("INVERTER_VA", "5000"))

# Battery voltage → SoC % mapping for FLD 12V 200Ah x4 (48V bank)
# These are RESTING / DISCHARGE voltages (open circuit approximations).
# During charging the voltage is artificially elevated by the charger.
BATTERY_VOLTAGE_SOC = [
    (46.4, 0),
    (48.0, 25),
    (49.6, 50),
    (51.2, 75),
    (52.8, 100),
]

# When battery voltage exceeds this, it is in charging mode (Absorption/Float).
# SoC is capped at 100% and the stage is inferred from voltage.
BAT_ABSORPTION_V = 53.5   # V — anything above this is absorption/float charging
BAT_FLOAT_V      = 54.8   # V — float (trickle) charge threshold

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
