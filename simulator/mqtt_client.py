import json
import paho.mqtt.client as mqtt


class MqttClient:
    """Thin publish/subscribe wrapper around paho-mqtt."""

    def __init__(self, host: str, port: int):
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.connect(host, port)
        self._client.loop_start()

    def publish(self, topic: str, payload: dict):
        self._client.publish(topic, json.dumps(payload))

    def subscribe(self, topic: str, callback):
        """callback(topic, payload_dict) called on each received message."""
        def _on_message(client, userdata, message):
            try:
                data = json.loads(message.payload.decode())
            except Exception:
                data = {}
            callback(message.topic, data)

        self._client.subscribe(topic)
        self._client.on_message = _on_message

    def disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()
