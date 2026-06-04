from flask import Flask, render_template, jsonify, request
from awscrt import mqtt
from awsiot import mqtt_connection_builder
import time
import json
import requests
import threading

from database import init_db, insert_log, get_recent_logs, get_analytics, get_chart_data

app = Flask(__name__)

ENDPOINT = "a23t40n3bsphuc-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "EntranceDashboard"

CERT = "EntrancePi.cert.pem"
KEY = "EntrancePi.private.key"
ROOT_CA = "root-CA.crt"

STATUS_TOPIC = "SWE30011/GP/entrance/status"
COMMAND_TOPIC = "SWE30011/GP/entrance/command"

TELEGRAM_BOT_TOKEN = "oopsie can't show"
TELEGRAM_CHAT_ID = "8855546712"

latest_status = {
    "distance": "--",
    "pir": "0",
    "ultrasonic": "0",
    "presence": "0",
    "lock": "unknown",
    "failsafe": "0",
    "last_update": "No data yet"
}

last_alert_state = {
    "presence": "0",
    "lock": "unknown",
    "failsafe": "0"
}

init_db()

def parse_payload(payload_text):
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError:
        pass

    data = {}
    for part in payload_text.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            data[key.strip()] = value.strip()

    return data

def send_telegram_alert(message):
    url = f"https://api.telegram.org/botoopsie can't show/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print("Telegram alert sent")
        else:
            print("Telegram alert failed:", response.text)
    except Exception as e:
        print("Telegram error:", e)

def process_message(parsed):
    global latest_status, last_alert_state

    latest_status.update({
        "distance": str(parsed.get("distance", "--")),
        "pir": str(parsed.get("pir", "0")),
        "ultrasonic": str(parsed.get("ultrasonic", "0")),
        "presence": str(parsed.get("presence", "0")),
        "lock": str(parsed.get("lock", "unknown")),
        "failsafe": str(parsed.get("failsafe", "0")),
        "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
    })

    # Database insert
    insert_log(latest_status.copy())

    # Telegram alerts
    if latest_status["presence"] == "1" and last_alert_state["presence"] != "1":
        threading.Thread(
            target=send_telegram_alert,
            args=("Security Alert: Presence detected near the entrance.",),
            daemon=True
        ).start()

    if latest_status["lock"] == "unlocked" and last_alert_state["lock"] != "unlocked":
        threading.Thread(
            target=send_telegram_alert,
            args=("Door Alert: Entrance door has been unlocked.",),
            daemon=True
        ).start()

    if latest_status["failsafe"] == "1" and last_alert_state["failsafe"] != "1":
        threading.Thread(
            target=send_telegram_alert,
            args=("Emergency Alert: Fail-safe mode activated. Door unlocked.",),
            daemon=True
        ).start()

    last_alert_state["presence"] = latest_status["presence"]
    last_alert_state["lock"] = latest_status["lock"]
    last_alert_state["failsafe"] = latest_status["failsafe"]


def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    payload_text = payload.decode("utf-8")

    print("Dashboard received:", payload_text)

    parsed = parse_payload(payload_text)

    if not parsed:
        print("Could not parse payload")
        return

    # Process in separate thread
    threading.Thread(
        target=process_message,
        args=(parsed,),
        daemon=True
    ).start()

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT,
    pri_key_filepath=KEY,
    ca_filepath=ROOT_CA,
    client_id=CLIENT_ID,
    clean_session=False,
    keep_alive_secs=30
)

print("Connecting dashboard to AWS IoT Core...")
mqtt_connection.connect().result()
print("Dashboard connected.")

mqtt_connection.subscribe(
    topic=STATUS_TOPIC,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_message_received
)
print("Subscribed to:", STATUS_TOPIC)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def get_status():
    return jsonify(latest_status)

@app.route("/api/history")
def history():
    return jsonify(get_recent_logs(10))

@app.route("/api/command", methods=["POST"])
def send_command():
    data = request.get_json()
    command = data.get("command")

    if command not in ["lock", "unlock"]:
        return jsonify({"success": False, "message": "Invalid command"}), 400

    mqtt_connection.publish(
        topic=COMMAND_TOPIC,
        payload=command,
        qos=mqtt.QoS.AT_LEAST_ONCE
    )

    return jsonify({"success": True, "message": f"Command sent: {command}"})

@app.route("/api/analytics")
def analytics():
    return jsonify(get_analytics())

@app.route("/api/chart-data")
def chart_data():
    return jsonify(get_chart_data(20))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
