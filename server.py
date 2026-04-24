from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, time, requests, jwt
from functools import wraps
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)
SECRET = "123456"
BOT_TOKEN = "8553903282:AAEjaRU2bFoT04fWAFrUF2cUOeSXmXP4How"

def get_db():
    return sqlite3.connect("medical_system.sqlite", check_same_thread=False)

conn = get_db()
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT, chat_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS data(sys INT, dia INT, hr INT, device_id TEXT, user_id TEXT, time TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS sessions(device_id TEXT PRIMARY KEY, user_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS admins(username TEXT, password TEXT)")

# Đảm bảo có tài khoản admin
cur.execute("DELETE FROM admins WHERE username='admin'")
cur.execute("INSERT INTO admins VALUES('admin','123456')")
conn.commit()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token: return jsonify({"error": "No token"}), 403
        try: 
            jwt.decode(token, SECRET, algorithms=["HS256"])
        except: 
            return jsonify({"error": "Invalid token"}), 403
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def home():
    return "Server ICU doanvdk is Online!"

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    cur.execute("SELECT * FROM admins WHERE username=? AND password=?", (data.get("username"), data.get("password")))
    if cur.fetchone():
        token = jwt.encode({"time": time.time()}, SECRET, algorithm="HS256")
        token_str = token.decode('utf-8') if isinstance(token, bytes) else token
        return jsonify({"token": token_str})
    return jsonify({"error": "Unauthorized"}), 401

@app.route("/api/users")
@token_required
def get_users():
    cur.execute("SELECT id, name FROM users")
    return jsonify(cur.fetchall())

@app.route("/api/update_name", methods=["POST"])
@token_required
def update_name():
    d = request.json
    cur.execute("UPDATE users SET name=? WHERE id=?", (d["new_name"], d["id"]))
    conn.commit()
    return "OK"

@app.route("/api/history")
@token_required
def get_history():
    user_id = request.args.get("user_id")
    cur.execute("SELECT sys, dia, hr, time, device_id FROM data WHERE user_id=? ORDER BY time DESC", (user_id,))
    return jsonify(cur.fetchall())

@app.route("/api/data", methods=["POST"])
def receive_data():
    d = request.json
    # FIX GIỜ VIỆT NAM: Lấy giờ UTC + 7 tiếng
    now_vn = datetime.utcnow() + timedelta(hours=7)
    t = now_vn.strftime("%Y-%m-%d %H:%M:%S")
    
    cur.execute("SELECT user_id FROM sessions WHERE device_id=?", (d["device_id"],))
    row = cur.fetchone()
    user_id = row[0] if row else "Unknown"

    cur.execute("INSERT INTO data VALUES(?,?,?,?,?,?)", (d["sys"], d["dia"], d["hr"], d["device_id"], user_id, t))
    conn.commit()
    
    if user_id != "Unknown":
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      json={"chat_id": user_id, "text": f"🩺 Kết quả mới ({t}):\nSYS: {d['sys']} | DIA: {d['dia']} | HR: {d['hr']}"})
    return "OK"

@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.json
    if "message" in data:
        msg = data["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "").strip()
        cur.execute("SELECT id FROM users WHERE id=?", (chat_id,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users VALUES(?,?,?)", (chat_id, msg["from"].get("first_name", "User"), chat_id))
            conn.commit()
        if text.startswith("MAY_"):
            cur.execute("INSERT OR REPLACE INTO sessions VALUES(?,?)", (text, chat_id))
            conn.commit()
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": chat_id, "text": f"✅ Đã nhận máy {text}."})
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
