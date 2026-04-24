from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, time, requests, jwt
from functools import wraps

app = Flask(__name__)
CORS(app)
SECRET = "123456"
BOT_TOKEN = "8553903282:AAEjaRU2bFoT04fWAFrUF2cUOeSXmXP4How"

def get_db():
    return sqlite3.connect("db.sqlite", check_same_thread=False)

conn = get_db()
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(id TEXT, name TEXT, chat_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS devices(device_id TEXT, user_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS data(sys INT, dia INT, hr INT, device_id TEXT, time TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS admins(username TEXT, password TEXT)")
# Đảm bảo mật khẩu luôn đúng
cur.execute("DELETE FROM admins WHERE username='admin'")
cur.execute("INSERT INTO admins VALUES('admin','123456')")
conn.commit()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token: return jsonify({"error": "No token"}), 403
        try: jwt.decode(token, SECRET, algorithms=["HS256"])
        except: return jsonify({"error": "Invalid token"}), 403
        return f(*args, **kwargs)
    return decorated

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    cur.execute("SELECT * FROM admins WHERE username=? AND password=?", (data.get("username"), data.get("password")))
    if cur.fetchone():
        token = jwt.encode({"time": time.time()}, SECRET, algorithm="HS256")
        return jsonify({"token": token})
    return "FAIL", 401

@app.route("/api/update_name", methods=["POST"])
@token_required
def update_name():
    d = request.json
    cur.execute("UPDATE users SET name=? WHERE id=?", (d["new_name"], d["id"]))
    conn.commit()
    return "OK"

@app.route("/api/data", methods=["POST"])
def receive_data():
    d = request.json
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO data VALUES(?,?,?,?,?)", (d["sys"], d["dia"], d["hr"], d["device_id"], t))
    conn.commit()
    
    # Gửi tin nhắn cho chủ sở hữu thiết bị
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                  json={"chat_id": d["device_id"], "text": f"Dữ liệu mới: SYS:{d['sys']} DIA:{d['dia']} HR:{d['hr']}"})
    return "OK"

@app.route("/api/users")
@token_required
def get_users():
    cur.execute("SELECT id, name FROM users")
    return jsonify(cur.fetchall())

@app.route("/api/data", methods=["GET"])
@token_required
def get_monitor_data():
    cur.execute("SELECT sys, dia, hr, device_id, time FROM data ORDER BY time ASC")
    return jsonify(cur.fetchall())

@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.json
    if "message" in data:
        msg = data["message"]
        chat_id = str(msg["chat"]["id"])
        name = msg["from"].get("first_name", "User")
        text = msg.get("text", "")

        if text == "/start":
            # Tự động lấy chat_id làm ID User và ID Thiết bị
            cur.execute("SELECT id FROM users WHERE chat_id=?", (chat_id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO users VALUES(?,?,?)", (chat_id, name, chat_id))
                cur.execute("INSERT INTO devices VALUES(?,?)", (chat_id, chat_id))
                conn.commit()
            
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": chat_id, "text": f"Chào {name}! Thiết bị của bạn đã được tự động kết nối. ID của bạn là: {chat_id}. Hãy nhập ID này vào code ESP32 của bạn."})
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
