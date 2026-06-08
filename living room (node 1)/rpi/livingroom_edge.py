#!/usr/bin/env python3
"""
Living Room Edge Node - Connects to AWS IoT Core
Publishes to: SWE30011/GP/node1/status
Subscribes to: SWE30011/GP/node1/command
"""

import serial
import time
import json
import threading

from awscrt import mqtt
from awsiot import mqtt_connection_builder

# =========================
# SERIAL CONFIG
# =========================
SERIAL_PORT = "/dev/ttyUSB0"  # Change to /dev/ttyUSB0 if needed
BAUD_RATE = 9600

# =========================
# AWS IoT CONFIG
# =========================
ENDPOINT = "a23t40n3bsphuc-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "LivingRoomPi"

# Certificate paths (UPDATE THESE TO YOUR ACTUAL PATHS)
CERT = "/home/pi/certs/LivingRoomPi.cert.pem"
KEY = "/home/pi/certs/LivingRoomPi.private.key"
ROOT_CA = "/home/pi/certs/AmazonRootCA1.pem"

# MQTT Topics (MUST MATCH YOUR FRIEND'S DASHBOARD)
STATUS_TOPIC = "SWE30011/GP/node1/status"
COMMAND_TOPIC = "SWE30011/GP/node1/command"

# =========================
# SERIAL CONNECTION
# =========================
try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print(f"? Connected to Arduino on {SERIAL_PORT}")
except Exception as e:
    print(f"? Arduino error: {e}")
    exit(1)

# =========================
# MQTT CALLBACK
# =========================
def on_command_received(topic, payload, dup, qos, retain, **kwargs):
    command = payload.decode("utf-8").strip().lower()
    print(f"?? Command received: {command}")
    
    # Forward command to Arduino
    arduino.write((command + "\n").encode())
    print(f"?? Sent to Arduino: {command}")

# =========================
# MQTT CONNECTION
# =========================
print("?? Connecting to AWS IoT Core...")
mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT,
    pri_key_filepath=KEY,
    ca_filepath=ROOT_CA,
    client_id=CLIENT_ID,
    clean_session=False,
    keep_alive_secs=30
)

try:
    mqtt_connection.connect().result()
    print("? Connected to AWS IoT Core")
except Exception as e:
    print(f"? Connection failed: {e}")
    exit(1)

# Subscribe to command topic
mqtt_connection.subscribe(
    topic=COMMAND_TOPIC,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_command_received
)
print(f"? Subscribed to {COMMAND_TOPIC}")

# =========================
# MAIN LOOP - READ ARDUINO AND PUBLISH
# =========================
print("?? Starting main loop...")

while True:
    if arduino.in_waiting > 0:
        line = arduino.readline().decode(errors="ignore").strip()
        
        if line:
            print(f"Arduino: {line}")
            
            # Parse key=value format into JSON for cloud
            data = {}
            for part in line.split(","):
                if "=" in part:
                    key, value = part.split("=", 1)
                    data[key.strip()] = value.strip()
            
            # Add metadata
            data["node"] = "Living Room Comfort Node"
            data["timestamp"] = int(time.time())
            
            # Publish to AWS IoT Core
            mqtt_connection.publish(
                topic=STATUS_TOPIC,
                payload=json.dumps(data),
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            print(f"?? Published to {STATUS_TOPIC}: {data}")
    
    time.sleep(0.1)
