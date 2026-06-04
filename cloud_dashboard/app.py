from flask import Flask, render_template, jsonify, request
from awscrt import mqtt
from awsiot import mqtt_connection_builder
import time
import json
import requests

from database import init_db, insert_node_log, get_recent_logs

app = Flask(__name__)

ENDPOINT = "a23t40n3bsphuc-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "UnifiedSmartHomeDashboard"

CERT = "EntrancePi.cert.pem"
KEY = "EntrancePi.private.key"
ROOT_CA = "root-CA.crt"

NODE1_STATUS_TOPIC = "SWE30011/GP/node1/status"
NODE1_COMMAND_TOPIC = "SWE30011/GP/node1/command"

NODE2_STATUS_TOPIC = "SWE30011/GP/entrance/status"
NODE2_COMMAND_TOPIC = "SWE30011/GP/entrance/command"

TELEGRAM_BOT_TOKEN = "8889860547:AAEtfOvCC44pMERBtZUHX3KWGtOR7cKg3_w"
TELEGRAM_CHAT_ID = "8855546712"

latest_nodes = {
    "node1": {
        "node_id": "node1",
        "node_name": "Living Room Comfort Node",
        "temperature": "--",
        "light": "--",
        "motion": "0",
        "fan": "unknown",
        "led": "unknown",
        "last_update": "No data yet"
    },
    "node2": {
        "node_id": "node2",
        "node_name": "Entrance Security Node",
        "distance": "--",
        "pir": "0",
        "ultrasonic": "0",
        "presence": "0",
        "lock": "unknown",
        "failsafe": "0",
        "last_update": "No data yet"
    }
}

last_node2_alert = {
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
    if TELEGRAM_BOT_TOKEN == "8889860547:AAEtfOvCC44pMERBtZUHX3KWGtOR7cKg3_w":
        return

    url = f"https://api.telegram.org/bot{8889860547:AAEtfOvCC44pMERBtZUHX3KWGtOR7cKg3_w}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Telegram error:", e)

def handle_node2_alerts(data):
    global last_node2_alert

    presence = str(data.get("presence", "0"))
    lock = str(data.get("lock", "unknown"))
    failsafe = str(data.get("failsafe", "0"))

    if presence == "1" and last_node2_alert["presence"] != "1":
        send_telegram_alert("Security Alert: Presence detected near the entrance.")

    if lock == "unlocked" and last_node2_alert["lock"] != "unlocked":
        send_telegram_alert("Door Alert: Entrance door has been unlocked.")

    if failsafe == "1" and last_node2_alert["failsafe"] != "1":
        send_telegram_alert("Emergency Alert: Fail-safe mode activated. Door unlocked.")

    last_node2_alert["presence"] = presence
    last_node2_alert["lock"] = lock
    last_node2_alert["failsafe"] = failsafe

def update_node(node_id, node_name, payload_text):
    data = parse_payload(payload_text)

    if not data:
        print("Could not parse payload:", payload_text)
        return

    data["node_id"] = node_id
    data["node_name"] = node_name
    data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")

    latest_nodes[node_id].update(data)

    insert_node_log(
        node_id=node_id,
        node_name=node_name,
        payload=json.dumps(data)
    )

    if node_id == "node2":
        handle_node2_alerts(data)

def on_node1_message(topic, payload, dup, qos, retain, **kwargs):
    payload_text = payload.decode("utf-8")
    print("Node 1 received:", payload_text)
    update_node("node1", "Living Room Comfort Node", payload_text)

def on_node2_message(topic, payload, dup, qos, retain, **kwargs):
    payload_text = payload.decode("utf-8")
    print("Node 2 received:", payload_text)
    update_node("node2", "Entrance Security Node", payload_text)

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT,
    pri_key_filepath=KEY,
    ca_filepath=ROOT_CA,
    client_id=CLIENT_ID,
    clean_session=False,
    keep_alive_secs=30
)

print("Connecting unified dashboard to AWS IoT Core...")
mqtt_connection.connect().result()
print("Connected.")

mqtt_connection.subscribe(
    topic=NODE1_STATUS_TOPIC,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_node1_message
)

mqtt_connection.subscribe(
    topic=NODE2_STATUS_TOPIC,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_node2_message
)

print("Subscribed to Node 1 and Node 2 topics.")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/nodes")
def get_nodes():
    return jsonify(latest_nodes)

@app.route("/api/status/<node_id>")
def get_node_status(node_id):
    if node_id not in latest_nodes:
        return jsonify({"error": "Node not found"}), 404

    return jsonify(latest_nodes[node_id])

@app.route("/api/history")
def history():
    return jsonify(get_recent_logs(20))

@app.route("/api/command/<node_id>", methods=["POST"])
def send_command(node_id):
    data = request.get_json()
    command = data.get("command")

    if node_id == "node1":
        topic = NODE1_COMMAND_TOPIC
        allowed_commands = ["fan_on", "fan_off", "light_on", "light_off"]
    elif node_id == "node2":
        topic = NODE2_COMMAND_TOPIC
        allowed_commands = ["lock", "unlock"]
    else:
        return jsonify({"success": False, "message": "Invalid node"}), 400

    if command not in allowed_commands:
        return jsonify({"success": False, "message": "Invalid command"}), 400

    mqtt_connection.publish(
        topic=topic,
        payload=command,
        qos=mqtt.QoS.AT_LEAST_ONCE
    )

    return jsonify({
        "success": True,
        "message": f"Command sent to {node_id}: {command}"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)