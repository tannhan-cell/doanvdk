from flask import Flask, request, jsonify
import sqlite3, time, requests

app = Flask(**name**)

BOT_TOKEN = "8553903282:AAEjaRU2bFoT04fWAFrUF2cUOeSXmXP4How"

# ===== DB INIT =====

conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER, name TEXT, chat_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS devices(device_id TEXT, user_id INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS data(sys INT, dia INT, hr INT, device_id TEXT, time TEXT)")
conn.commit()

# ===== AI =====

def analyze(sys):
if sys >= 180: return "🚨 NGUY HIỂM"
if sys >= 140: return "⚠️ CAO"
if sys >= 120: return "📊 TIỀN CAO"
return "✅ BÌNH THƯỜNG"

# ===== ESP32 =====

@app.route("/api/data", methods=["POST"])
def receive_data():
d = request.json
t = time.strftime("%Y-%m-%d %H:%M:%S")

```
cur.execute("INSERT INTO data VALUES(?,?,?,?,?)",
    (d["sys"], d["dia"], d["hr"], d["device_id"], t))
conn.commit()

cur.execute("SELECT user_id FROM devices WHERE device_id=?", (d["device_id"],))
row = cur.fetchone()

if row:
    user_id = row[0]
    cur.execute("SELECT chat_id FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()

    if user:
        msg = analyze(d["sys"])
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": user[0],
                "text": f"{msg}\nDevice:{d['device_id']}\nSYS:{d['sys']}\nDIA:{d['dia']}\nHR:{d['hr']}"
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
        cur.execute("INSERT INTO users VALUES(?,?,?)", (uid, name, chat_id))
        conn.commit()
    else:
        uid = user[0]

    if text == "/start":
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":"Nhập ID thiết bị (VD: ESP001)"})

    elif text.startswith("ESP"):
        cur.execute("INSERT INTO devices VALUES(?,?)", (text, uid))
        conn.commit()

        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":"Đã liên kết!"})

return "OK"
```

# ===== API =====

@app.route("/api/users")
def users():
cur.execute("SELECT * FROM users")
return jsonify(cur.fetchall())

@app.route("/api/data")
def data():
cur.execute("SELECT * FROM data")
return jsonify(cur.fetchall())

@app.route("/api/devices")
def devices():
cur.execute("SELECT * FROM devices")
return jsonify(cur.fetchall())

# ===== RUN =====

app.run(host="0.0.0.0", port=3000)
