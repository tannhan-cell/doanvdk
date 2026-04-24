from flask import Flask, request, jsonify
import json
import time
import requests

# 1. Sửa lỗi khởi tạo Flask (phải là __name__)
app = Flask(__name__)
BOT_TOKEN = "8553903282:AAEjaRU2bFoT04fWAFrUF2cUOeSXmXP4How"

# ===== LOAD DB =====
try:
    with open("db.json", "r") as f:
        db = json.load(f)
except:
    db = {"users": [], "data": []}

# ===== SAVE =====
def save():
    with open("db.json", "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

# ===== AI ANALYZE =====
def analyze(sys):
    if sys >= 180:
        return "🚨 NGUY HIỂM (Huyết áp cao độ 3)"
    elif sys >= 140:
        return "⚠️ CAO (Huyết áp cao độ 1-2)"
    elif sys >= 120:
        return "📊 TIỀN CAO HUYẾT ÁP"
    else:
        return "✅ BÌNH THƯỜNG"

# ===== ESP32 ENDPOINT =====
@app.route("/api/data", methods=["POST"])
def receive_data():
    d = request.json
    if not d:
        return "No data", 400
    
    d["time"] = time.strftime("%d/%m/%Y %H:%M:%S")
    db["data"].append(d)
    save()

    # Tìm user dựa trên user_id gửi từ ESP32
    user = next((u for u in db["users"] if u["id"] == d.get("user_id")), None)

    if user:
        status_msg = analyze(d["sys"])
        # Gửi thông báo về Telegram
        telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": user["chat_id"],
            "text": f"{status_msg}\n───\nSYS: {d['sys']} mmHg\nDIA: {d['dia']} mmHg\nHR: {d['hr']} bpm"
        }
        try:
            requests.post(telegram_url, json=payload)
        except Exception as e:
            print(f"Lỗi gửi Telegram: {e}")

    return "OK"

# ===== TELEGRAM WEBHOOK =====
@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.json
    if "message" in data:
        msg = data["message"]
        text = msg.get("text")
        chat_id = msg["chat"]["id"]
        first_name = msg["from"].get("first_name", "User")

        if text == "/start":
            # Kiểm tra nếu user chưa tồn tại thì thêm mới
            if not any(u["chat_id"] == chat_id for u in db["users"]):
                new_id = int(time.time())
                db["users"].append({
                    "id": new_id,
                    "name": first_name,
                    "chat_id": chat_id
                })
                save()
                
                welcome_text = f"Chào {first_name}! ID của bạn là: {new_id}\nHãy nhập ID này vào thiết bị ESP32 của bạn."
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                              json={"chat_id": chat_id, "text": welcome_text})
    return "OK"

# ===== API GET DATA =====
@app.route("/api/users", methods=["GET"])
def get_users():
    return jsonify(db["users"])

@app.route("/api/data", methods=["GET"])
def get_all_data():
    return jsonify(db["data"])

# ===== RUN =====
if __name__ == "__main__":
    # Chạy ở port 3000
    app.run(host="0.0.0.0", port=3000)
