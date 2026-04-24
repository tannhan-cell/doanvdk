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
cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER, name TEXT, chat_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS devices(device_id TEXT, user_id INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS data(sys INT, dia INT, hr INT, device_id TEXT, time TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS admins(username TEXT, password TEXT)")
conn.commit()

# --- FORCE UPDATE ADMIN PASSWORD ---
# Dòng này đảm bảo dù database cũ có gì, mật khẩu sẽ luôn là 123456 khi bạn restart server
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

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    u = data.get("username")
    p = data.get("password")
    
    cur.execute("SELECT * FROM admins WHERE username=? AND password=?", (u, p))
    if cur.fetchone():
        # Xử lý Token để tương thích mọi phiên bản thư viện
        encoded_jwt = jwt.encode({"time": time.time()}, SECRET, algorithm="HS256")
        if isinstance(encoded_jwt, bytes):
            encoded_jwt = encoded_jwt.decode('utf-8')
            
        return jsonify({"token": encoded_jwt})
    
    return jsonify({"error": "Wrong username or password"}), 401

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
    
    cur.execute("SELECT user_id FROM devices WHERE device_id=?", (d["device_id"],))
    row = cur.fetchone()
    if row:
        cur.execute("SELECT chat_id FROM users WHERE id=?", (row[0],))
        user = cur.fetchone()
        if user:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": user[0], "text": f"Dữ liệu mới: SYS:{d['sys']} DIA:{d['dia']} HR:{d['hr']}"})
    return "OK"

@app.route("/api/users")
@token_required
def get_users():
    cur.execute("SELECT id, name FROM users")
    return jsonify(cur.fetchall())

@app.route("/api/data", methods=["GET"])
@token_required
def get_monitor_data():
    query = """
    SELECT data.sys, data.dia, data.hr, devices.user_id, data.time 
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
        text = msg.get("text", "")
        name = msg["from"].get("first_name", "User")
        
        cur.execute("SELECT id FROM users WHERE chat_id=?", (chat_id,))
        user = cur.fetchone()
        
        if not user:
            uid = int(time.time())
            cur.execute("INSERT INTO users VALUES(?,?,?)", (uid, name, chat_id))
            conn.commit()
        else:
            uid = user[0]
            
        if text.startswith("ESP"):
            cur.execute("INSERT INTO devices VALUES(?,?)", (text, uid))
            conn.commit()
            
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
