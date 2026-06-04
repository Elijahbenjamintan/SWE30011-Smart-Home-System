import sqlite3

DB_NAME = "entrance_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entrance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            distance INTEGER,
            pir INTEGER,
            ultrasonic INTEGER,
            presence INTEGER,
            lock_status TEXT,
            failsafe INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def insert_log(data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO entrance_logs 
        (distance, pir, ultrasonic, presence, lock_status, failsafe)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        int(data.get("distance", -1)),
        int(data.get("pir", 0)),
        int(data.get("ultrasonic", 0)),
        int(data.get("presence", 0)),
        data.get("lock", "unknown"),
        int(data.get("failsafe", 0))
    ))

    conn.commit()
    conn.close()

def get_recent_logs(limit=10):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM entrance_logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

def get_analytics():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM entrance_logs")
    total_logs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entrance_logs WHERE presence = 1")
    total_presence = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entrance_logs WHERE failsafe = 1")
    total_failsafe = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entrance_logs WHERE lock_status = 'unlocked'")
    total_unlocked = cursor.fetchone()[0]

    conn.close()

    return {
        "total_logs": total_logs,
        "total_presence": total_presence,
        "total_failsafe": total_failsafe,
        "total_unlocked": total_unlocked
    }


def get_chart_data(limit=20):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, distance, presence
        FROM entrance_logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    rows = list(reversed(rows))
    return [dict(row) for row in rows]