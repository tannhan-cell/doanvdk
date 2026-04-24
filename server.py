from flask import Flask, request, jsonify
from flask_cors import CORS  # Thêm CORS để gọi được từ trình duyệt
import sqlite3, time, requests, jwt
from functools import wraps

app = Flask(__name__)
CORS(app) # Cho phép Frontend truy cập API
SECRET = "123456"
BOT_TOKEN = "8553903282:AAEjaRU2bFoT04fWAFrUF2cUOeSXmXP4How"

# ===== DB SETUP =====
def get_db():
    conn = sqlite3.connect("db.sqlite", check_same_thread=False)
    return conn

conn = get_db()
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER, name TEXT, chat_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS devices(device_id TEXT, user_id INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS data(sys INT, dia INT, hr INT, device_id TEXT, time TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS admins(username TEXT, password TEXT)")
conn.commit()

# Tạo admin mặc định nếu chưa có
cur.execute("SELECT * FROM admins")
if not cur.fetchone():
    cur.execute("INSERT INTO admins VALUES('admin','123456')")
    conn.commit()

# ===== AUTH MIDDLEWARE =====
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "No token"}), 403
        try:
            jwt.decode(token, SECRET, algorithms=["HS256"])
        except:
            return jsonify({"error": "Invalid token"}), 403
        return f(*args, **kwargs)
    return decorated

# ===== ROUTES =====

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    cur.execute("SELECT * FROM admins WHERE username=? AND password=?",
                (data.get("username"), data.get("password")))
    if cur.fetchone():
        token = jwt.encode({"time": time.time()}, SECRET, algorithm="HS256")
        # Đảm bảo token là chuỗi
        return jsonify({"token": token})
    return "FAIL", 401

def analyze(sys, history):
    avg = sum(history)/len(history) if history else sys
    if sys >= 180 or avg > 160: return "🚨 Nguy hiểm cao"
    if sys >= 140: return "⚠️ Cao huyết áp"
    if sys >= 120: return "📊 Tiền cao huyết áp"
    return "✅ Bình thường"

@app.route("/api/data", methods=["POST"])
def receive_data():
    d = request.json
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Lưu dữ liệu từ ESP32
    cur.execute("INSERT INTO data VALUES(?,?,?,?,?)",
                (d["sys"], d["dia"], d["hr"], d["device_id"], t))
    conn.commit()

    # Phân tích và gửi Telegram
    cur.execute("SELECT sys FROM data WHERE device_id=? ORDER BY time DESC LIMIT 5", (d["device_id"],))
    history = [x[0] for x in cur.fetchall()]
    msg_status = analyze(d["sys"], history)

    cur.execute("SELECT user_id FROM devices WHERE device_id=?", (d["device_id"],))
    row = cur.fetchone()
    if row:
        cur.execute("SELECT chat_id FROM users WHERE id=?", (row[0],))
        user = cur.fetchone()
        if user:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": user[0],
                    "text": f"{msg_status}\nSYS: {d['sys']} | DIA: {d['dia']} | HR: {d['hr']}"
                }
            )
    return "OK"

@app.route("/api/users")
@token_required
def get_users():
    cur.execute("SELECT id, name FROM users")
    return jsonify(cur.fetchall())

@app.route("/api/data", methods=["GET"])
@token_required
def get_monitor_data():
    # Câu lệnh SQL quan trọng: JOIN để biết dữ liệu nào của User nào
    # Trả về: [sys, dia, hr, user_id]
    query = """
    SELECT data.sys, data.dia, data.hr, devices.user_id 
    FROM data 
    JOIN devices ON data.device_id = devices.device_id
    ORDER BY data.time ASC
    """
    cur.execute(query)
    return jsonify(cur.fetchall())

@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.json
    if "message" in data:
        msg = data["message"]
        chat_id = str(msg["chat"]["id"])
        name = msg["from"].get("first_name", "User")
        text = msg.get("text", "")

        cur.execute("SELECT id FROM users WHERE chat_id=?", (chat_id,))
        user = cur.fetchone()

        if not user:
            uid = int(time.time())
            cur.execute("INSERT INTO users VALUES(?,?,?)", (uid, name, chat_id))
            conn.commit()
            uid_final = uid
        else:
            uid_final = user[0]

        if text == "/start":
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": "Chào mừng! Hãy nhập ID thiết bị (Ví dụ: ESP001)"})
        elif text.startswith("ESP"):
            cur.execute("INSERT INTO devices VALUES(?,?)", (text, uid_final))
            conn.commit()
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": f"Đã kết nối thiết bị {text}"})
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
