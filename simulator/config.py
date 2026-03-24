import os
from dotenv import load_dotenv

load_dotenv()

SITE_ID = os.getenv("SITE_ID", "site-1")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
STEP_INTERVAL_S = int(os.getenv("STEP_INTERVAL_S", "60"))
START_TIME = os.getenv("START_TIME", "00:00:00")

SOLAR_MAX_KW = float(os.getenv("SOLAR_MAX_KW", "100.0"))
SOLAR_NOISE_STD = float(os.getenv("SOLAR_NOISE_STD", "5.0"))
