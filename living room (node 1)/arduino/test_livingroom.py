#!/usr/bin/env python3
"""
Living Room Node - MQTT Publisher
Reads Arduino data from USB serial and publishes to AWS IoT Core
"""

import serial
import json
import time
import sys
import signal
from awscrt import mqtt
from awsiot import mqtt_connection_builder

# ==================== CONFIGURATION ====================
ENDPOINT = "a23t40n3bsphuc-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "LivingRoomPi"

CERT_FILE = "/home/pi/certs/LivingRoomPi.cert.pem"
KEY_FILE = "/home/pi/certs/LivingRoomPi.private.key"
ROOT_CA = "/home/pi/certs/AmazonRootCA1.pem"

SERIAL_PORT = "/dev/ttyS0"
BAUD_RATE = 9600

PUB_TOPIC = "SWE30011/GP/node1/status"
SUB_TOPIC = "SWE30011/GP/node1/command"

# ==================== GLOBAL VARIABLES ====================
mqtt_connection = None
ser = None
running = True
current_data = {}

# ==================== SIGNAL HANDLER ====================
def signal_handler(signum, frame):
    global running
    print("\n⏹️ Shutting down...")
    running = False

signal.signal(signal.SIGINT, signal_handler)

# ==================== MQTT CALLBACKS ====================
def on_message_received(topic, payload, **kwargs):
    """Handle incoming control messages from AWS IoT Core"""
    try:
        message = payload.decode()
        data = json.loads(message)
        print(f"\n📨 Command received: {data}")
        
        if ser and ser.is_open:
            command = json.dumps(data) + "\n"
            ser.write(command.encode())
            print(f"📤 Sent to Arduino: {command.strip()}")
            
    except Exception as e:
        print(f"Error processing message: {e}")

# ==================== SERIAL READER ====================
def read_arduino_serial():
    """Continuously read sensor data from Arduino"""
    global current_data, ser, running
    
    time.sleep(3)
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"✅ Connected to Arduino on {SERIAL_PORT}")
    except Exception as e:
        print(f"⚠️ Arduino error: {e}")
        print("   Will continue with simulated data")
        ser = None
    
    while running:
        try:
            if ser and ser.in_waiting:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    try:
                        data = json.loads(line)
                        current_data = data
                        data["timestamp"] = int(time.time())
                        
                        temp = data.get("temp", 0)
                        motion = data.get("motion", 0)
                        fan = data.get("fan", "OFF")
                        led = data.get("led", "OFF")
                        print(f"📊 T:{temp}°C | Motion:{'YES' if motion else 'NO'} | Fan:{fan} | LED:{led}")
                        
                        if mqtt_connection:
                            mqtt_connection.publish(
                                topic=PUB_TOPIC,
                                payload=json.dumps(data),
                                qos=mqtt.QoS.AT_LEAST_ONCE
                            )
                        
                    except json.JSONDecodeError:
                        if line:
                            print(f"Arduino: {line}")
                            
        except Exception as e:
            print(f"Serial error: {e}")
            
        time.sleep(0.5)
    
    if ser:
        ser.close()
        print("Serial connection closed")

# ==================== MAIN ====================
def main():
    global mqtt_connection
    
    print("=" * 60)
    print("Living Room Node - MQTT Publisher")
    print("=" * 60)
    print(f"Endpoint: {ENDPOINT}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Publish: {PUB_TOPIC}")
    print(f"Subscribe: {SUB_TOPIC}")
    print(f"Serial Port: {SERIAL_PORT}")
    print("=" * 60)
    
    # ==================== CONNECT TO AWS IOT CORE ====================
    print("\n🔌 Connecting to AWS IoT Core...")
    
    try:
        mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=ENDPOINT,
            cert_filepath=CERT_FILE,
            pri_key_filepath=KEY_FILE,
            ca_filepath=ROOT_CA,
            client_id=CLIENT_ID,
            clean_session=True,
            keep_alive_secs=30
        )
        
        # FIXED: Different way to connect (no .result() on tuple)
        print("Connecting...")
        connect_future = mqtt_connection.connect()
        
        # Handle differently based on type
        if hasattr(connect_future, 'result'):
            connect_future.result(timeout=10)
        else:
            # If it's a tuple or already connected
            print("Connection initiated")
            time.sleep(2)
        
        print("✅ Connected to AWS IoT Core")
        
        # Subscribe to control topic
        print(f"📡 Subscribing to {SUB_TOPIC}...")
        subscribe_future = mqtt_connection.subscribe(
            topic=SUB_TOPIC,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_message_received
        )
        
        if hasattr(subscribe_future, 'result'):
            subscribe_future.result()
        
        print(f"✅ Subscribed to {SUB_TOPIC}")
        
    except Exception as e:
        print(f"❌ AWS connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check endpoint is correct")
        print("2. Verify certificate files exist")
        print("3. Check policy allows Connect, Publish, Subscribe")
        print("4. Run: sudo chmod 600 on private key")
        
        # Try to continue without AWS for testing
        print("\n⚠️ Continuing with serial only (AWS disabled)")
        mqtt_connection = None
    
    # ==================== START SERIAL READER ====================
    print("\n🔄 Starting serial reader...")
    
    try:
        read_arduino_serial()
    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")
    finally:
        if mqtt_connection:
            try:
                mqtt_connection.disconnect()
                print("✅ Disconnected from AWS IoT Core")
            except:
                pass
        if ser:
            ser.close()
            print("✅ Serial connection closed")
    
    print("Done.")

if __name__ == "__main__":
    main()
