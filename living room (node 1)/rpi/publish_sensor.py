#!/usr/bin/env python3
"""
MQTT Publisher for Raspberry Pi - LivingRoomPi
Publishes sensor data to AWS IoT Core
"""

from awscrt import mqtt
from awsiot import mqtt_connection_builder
import json
import time
import sys
import os
import serial
import threading

# ==================== CONFIGURATION ====================
# AWS IoT Core Endpoint (YOUR ENDPOINT - already provided)
ENDPOINT = "a23t40n3bsphuc-ats.iot.us-east-1.amazonaws.com"

# Thing Name (must match the thing in IoT Core)
CLIENT_ID = "LivingRoomPi"

# Certificate and Key Files
CERT_DIR = "/home/pi/aws_iot_project/certs"
CERT_FILE = f"{CERT_DIR}/LivingRoomPi.cert.pem"
KEY_FILE = f"{CERT_DIR}/LivingRoomPi.private.key"
ROOT_CA_FILE = f"{CERT_DIR}/AmazonRootCA1.pem"

# MQTT Topics
PUB_TOPIC = "SWE30011/GP/LivingRoomPi/sensors"
SUB_TOPIC = "SWE30011/GP/LivingRoomPi/control"

# Serial port for Arduino (adjust if needed)
SERIAL_PORT = '/dev/tty'  # or /dev/ttyACM0
BAUD_RATE = 9600

# ==================== GLOBAL VARIABLES ====================
current_sensor_data = {
    "source": "LivingRoomPi",
    "temperature": 0,
    "humidity": 0,
    "motion": 0,
    "light": 0,
    "servo": 0,
    "relay_ac": "OFF",
    "relay_light": "OFF"
}

serial_connection = None

# ==================== SERIAL READER FUNCTION ====================
def read_arduino_serial():
    """Continuously read sensor data from Arduino"""
    global current_sensor_data, serial_connection
    
    try:
        serial_connection = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)
        print(f"✅ Connected to Arduino on {SERIAL_PORT}")
    except Exception as e:
        print(f"⚠️ Arduino not found: {e}")
        print("   Using simulated sensor data...")
        serial_connection = None
        # Continue with simulated data
        return
    
    while True:
        try:
            if serial_connection and serial_connection.in_waiting:
                line = serial_connection.readline().decode('utf-8').strip()
                if line:
                    try:
                        import json as json_module
                        data = json_module.loads(line)
                        
                        current_sensor_data["temperature"] = data.get('temp', 0)
                        current_sensor_data["humidity"] = data.get('hum', 0)
                        current_sensor_data["motion"] = data.get('motion', 0)
                        current_sensor_data["light"] = data.get('light', 0)
                        current_sensor_data["servo"] = data.get('servo', 0)
                        
                    except:
                        pass
        except Exception as e:
            print(f"Serial read error: {e}")
        time.sleep(1)

# ==================== SIMULATED DATA (FALLBACK) ====================
def get_simulated_data():
    """Generate simulated sensor data if Arduino not connected"""
    current_sensor_data["temperature"] = round(22 + (time.time() % 5), 1)
    current_sensor_data["humidity"] = 55 + (int(time.time()) % 10)
    # Simulate motion every 30 seconds for testing
    current_sensor_data["motion"] = 1 if (int(time.time()) % 30) < 5 else 0
    current_sensor_data["light"] = 300 + (int(time.time()) % 200)
    return current_sensor_data

# ==================== CALLBACK FOR INCOMING MESSAGES ====================
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    """Handle incoming messages from IoT Core (Cloud to Device)"""
    print("\n" + "="*60)
    print("📨 COMMAND RECEIVED FROM CLOUD!")
    print(f"Topic: {topic}")
    try:
        message = payload.decode('utf-8')
        data = json.loads(message)
        print(f"Command: {json.dumps(data, indent=2)}")
        
        # Process control commands
        if 'relay_ac' in data:
            print(f"   ❄️ AC Relay: {data['relay_ac']}")
            # TODO: Add code to control actual relay
            
        if 'relay_light' in data:
            print(f"   💡 Light Relay: {data['relay_light']}")
            # TODO: Add code to control actual relay
            
        if 'servo' in data:
            print(f"   🔄 Servo Position: {data['servo']}°")
            # TODO: Add code to control actual servo
            
    except Exception as e:
        print(f"Error parsing command: {e}")
    print("="*60)

# ==================== MAIN ====================
def main():
    print("="*60)
    print("🌐 MQTT Publisher for LivingRoomPi")
    print("="*60)
    print(f"Endpoint: {ENDPOINT}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Publish Topic: {PUB_TOPIC}")
    print(f"Subscribe Topic: {SUB_TOPIC}")
    print("="*60)
    
    # Check if certificate files exist
    missing_files = []
    if not os.path.isfile(CERT_FILE):
        missing_files.append(CERT_FILE)
    if not os.path.isfile(KEY_FILE):
        missing_files.append(KEY_FILE)
    if not os.path.isfile(ROOT_CA_FILE):
        missing_files.append(ROOT_CA_FILE)
    
    if missing_files:
        print("\n❌ ERROR: Missing certificate files:")
        for f in missing_files:
            print(f"   - {f}")
        print("\nPlease transfer your certificate files to ~/aws_iot_project/certs/")
        sys.exit(1)
    
    print("\n✅ Certificate files found")
    
    # Start serial reader thread
    serial_thread = threading.Thread(target=read_arduino_serial, daemon=True)
    serial_thread.start()
    print("📡 Serial reader thread started")
    
    # Build MQTT Connection
    print("\n🔌 Connecting to AWS IoT Core...")
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=ENDPOINT,
        cert_filepath=CERT_FILE,
        pri_key_filepath=KEY_FILE,
        ca_filepath=ROOT_CA_FILE,
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30
    )
    
    # Connect
    try:
        connect_future = mqtt_connection.connect()
        connect_future.result()
        print("✅ Connected to AWS IoT Core!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
    
    # Subscribe to control topic
    print(f"\n📡 Subscribing to topic: {SUB_TOPIC}")
    subscribe_future = mqtt_connection.subscribe(
        topic=SUB_TOPIC,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received
    )
    subscribe_future.result()
    print(f"✅ Subscribed to {SUB_TOPIC}")
    
    # Main publishing loop
    print("\n🔄 Starting publish loop (Ctrl+C to stop)...\n")
    
    try:
        while True:
            # Get current sensor data (from Arduino or simulated)
            sensor_data = current_sensor_data.copy()
            sensor_data["timestamp"] = int(time.time())
            sensor_data["source"] = "LivingRoomPi"
            
            # If no Arduino, use simulated data
            if serial_connection is None:
                sensor_data = get_simulated_data()
                sensor_data["timestamp"] = int(time.time())
                sensor_data["source"] = "LivingRoomPi (Simulated)"
            
            # Convert to JSON
            payload = json.dumps(sensor_data)
            
            # Publish to IoT Core
            mqtt_connection.publish(
                topic=PUB_TOPIC,
                payload=payload,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            
            # Display status
            motion_icon = "🔴" if sensor_data["motion"] else "⚪"
            print(f"📤 [{time.strftime('%H:%M:%S')}] {motion_icon} Temp: {sensor_data['temperature']}°C | Hum: {sensor_data['humidity']}% | Light: {sensor_data['light']}")
            
            # Wait 5 seconds before next publish
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping...")
    finally:
        print("Disconnecting from AWS IoT Core...")
        mqtt_connection.disconnect().result()
        print("✅ Disconnected.")
        if serial_connection:
            serial_connection.close()

if __name__ == "__main__":
    main()
