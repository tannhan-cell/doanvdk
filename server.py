from flask import Flask, request, jsonify
import sqlite3, time, requests, jwt
from functools import wraps

app = Flask(**name**)
SECRET = "123456"
BOT_TOKEN = "8553903282:AAEjaRU2bFoT04fWAFrUF2cUOeSXmXP4How"

# ===== DB =====

conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER, name TEXT, chat_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS devices(device_id TEXT, user_id INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS data(sys INT, dia INT, hr INT, device_id TEXT, time TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS admins(username TEXT, password TEXT)")
conn.commit()

# tạo admin mặc định

cur.execute("SELECT * FROM admins")
if not cur.fetchone():
cur.execute("INSERT INTO admins VALUES('admin','123456')")
conn.commit()

# ===== AUTH =====

def token_required(f):
@wraps(f)
def decorated(*args, **kwargs):
token = request.headers.get("Authorization")
if not token:
return "No token", 403
try:
jwt.decode(token, SECRET, algorithms=["HS256"])
except:
return "Invalid token", 403
return f(*args, **kwargs)
return decorated

@app.route("/api/login", methods=["POST"])
def login():
data = request.json
cur.execute("SELECT * FROM admins WHERE username=? AND password=?",
(data["username"], data["password"]))
if cur.fetchone():
token = jwt.encode({"time":time.time()}, SECRET, algorithm="HS256")
return jsonify({"token":token})
return "FAIL",401

# ===== AI =====

def analyze(sys, history):
avg = sum(history)/len(history) if history else sys

```
if sys >= 180 or avg > 160:
    return "🚨 Nguy hiểm cao"
if sys >= 140:
    return "⚠️ Cao huyết áp"
if sys >= 120:
    return "📊 Tiền cao huyết áp"
return "✅ Bình thường"
```

# ===== ESP32 =====

@app.route("/api/data", methods=["POST"])
def receive_data():
d = request.json
t = time.strftime("%Y-%m-%d %H:%M:%S")

```
cur.execute("INSERT INTO data VALUES(?,?,?,?,?)",
    (d["sys"], d["dia"], d["hr"], d["device_id"], t))
conn.commit()

# lấy history 5 mẫu gần nhất
cur.execute("SELECT sys FROM data WHERE device_id=? ORDER BY time DESC LIMIT 5",(d["device_id"],))
history = [x[0] for x in cur.fetchall()]

msg = analyze(d["sys"], history)

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
                "text": f"{msg}\nSYS:{d['sys']} DIA:{d['dia']} HR:{d['hr']}"
            }
        )

return "OK"
```

# ===== TELEGRAM =====

@app.route("/telegram", methods=["POST"])
def telegram():
data = request.json

```
if "message" in data:
    msg = data["message"]
    chat_id = str(msg["chat"]["id"])
    name = msg["from"]["first_name"]
    text = msg.get("text","")

    cur.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,))
    user = cur.fetchone()

    if not user:
        uid = int(time.time())
        cur.execute("INSERT INTO users VALUES(?,?,?)",(uid,name,chat_id))
        conn.commit()
    else:
        uid = user[0]

    if text == "/start":
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":"Nhập ID thiết bị (ESP001)"}
        )
    elif text.startswith("ESP"):
        cur.execute("INSERT INTO devices VALUES(?,?)",(text,uid))
        conn.commit()

return "OK"
```

# ===== API =====

@app.route("/api/users")
@token_required
def users():
cur.execute("SELECT * FROM users")
return jsonify(cur.fetchall())

@app.route("/api/data")
@token_required
def data():
cur.execute("SELECT * FROM data")
return jsonify(cur.fetchall())

app.run(host="0.0.0.0", port=3000)
