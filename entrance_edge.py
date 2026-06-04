import serial
import time
import json
import threading

from awscrt import mqtt
from awsiot import mqtt_connection_builder

# =========================
# SERIAL CONFIG
# =========================

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600

ENDPOINT = "a23t40n3bsphuc-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "EntranceDashboard"

CERT = "EntrancePi.cert.pem"
KEY = "EntrancePi.private.key"
ROOT_CA = "root-CA.crt"

STATUS_TOPIC = "SWE30011/GP/entrance/status"
COMMAND_TOPIC = "SWE30011/GP/entrance/command"

arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

time.sleep(2)

def parse_arduino_line(line):
    data = {}

    for part in line.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            data[key.strip()] = value.strip()

    return data

def on_command_received(topic, payload, dup, qos, retain, **kwargs):
    command = payload.decode("utf-8").strip().lower()
    print("Command received:", command)

    if command in ["lock", "unlock"]:
        arduino.write((command + "\n").encode())
        print("Sent to Arduino:", command)

def heartbeat_loop():
    while True:
        arduino.write(b"heartbeat\n")
        time.sleep(3)

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT,
    pri_key_filepath=KEY,
    ca_filepath=ROOT_CA,
    client_id=CLIENT_ID,
    clean_session=False,
    keep_alive_secs=30
)

print("Connecting Edge to AWS IoT Core...")
mqtt_connection.connect().result()
print("Edge connected.")

mqtt_connection.subscribe(
    topic=COMMAND_TOPIC,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_command_received
)

threading.Thread(target=heartbeat_loop, daemon=True).start()

while True:
    if arduino.in_waiting > 0:
        line = arduino.readline().decode(errors="ignore").strip()

        if line:
            print("Arduino:", line)

            data = parse_arduino_line(line)
            data["node"] = "Entrance Security Node"
            data["timestamp"] = int(time.time())

            mqtt_connection.publish(
                topic=STATUS_TOPIC,
                payload=json.dumps(data),
                qos=mqtt.QoS.AT_LEAST_ONCE
            )

            print("Published:", data)

    time.sleep(0.1)