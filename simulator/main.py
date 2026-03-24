import config
from clock import SimClock
from models.solar import SolarModel
from mqtt_client import MqttClient

if __name__ == "__main__":
    print(f"EnergyOrchestrator simulator starting")
    print(f"  Site ID:         {config.SITE_ID}")
    print(f"  MQTT host:       {config.MQTT_HOST}:{config.MQTT_PORT}")
    print(f"  Step interval:   {config.STEP_INTERVAL_S}s")
    print(f"  Start time:      {config.START_TIME}")

    clock = SimClock(
        start_time=config.START_TIME,
        step_interval_s=config.STEP_INTERVAL_S,
    )
    print(f"  Clock ready:     simulated time={clock.simulated_time}, fraction={clock.time_of_day_fraction:.4f}")

    solar = SolarModel(max_kw=config.SOLAR_MAX_KW, noise_std=config.SOLAR_NOISE_STD)

    try:
        mqtt = MqttClient(host=config.MQTT_HOST, port=config.MQTT_PORT)
    except Exception as e:
        print(f"  MQTT unavailable ({e}), running without broker")
        mqtt = None

    pv_topic = f"site/{config.SITE_ID}/pv/power"
    pv_kw = solar.generate(clock.time_of_day_fraction)
    if mqtt:
        mqtt.publish(pv_topic, {"pv_power_kw": round(pv_kw, 2), "simulated_time": clock.simulated_time})
        print(f"  Solar published: {pv_kw:.2f} kW -> {pv_topic}")
        mqtt.disconnect()
    else:
        print(f"  Solar generated: {pv_kw:.2f} kW (not published, no broker)")
