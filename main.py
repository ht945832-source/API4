import numpy as np
import threading
import time
import hashlib
import asyncio
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import deque, Counter
from telegram import Bot
from telegram.constants import ParseMode

# --- CẤU HÌNH ---
TOKEN = "8670893641:AAGovRHAo8mIGvOXchbTqxZZIG2KQiwdRcw"
ADMIN_ID = "@tranhoang2286"
GROUP_ID = "-100xxxxxxxxxx"  # Thay ID nhóm của bạn vào đây để bot nhắn tin
bot = Bot(token=TOKEN)

app = FastAPI(title="AI Predictor & Telegram Bot System")

class ToolState:
    def __init__(self):
        self.phien = 10001
        self.raw_data = deque(maxlen=50)
        self.history = {}
        self.win = 0
        self.total = 0
        self.mode = "idle"
        self.last_pred = "N/A"
        self.last_conf = 0.0
        self.virtual_mem = 1250 # Số mem ảo ban đầu

state = ToolState()

# --- HÀM GỬI TIN NHẮN TELEGRAM ---
async def send_tele_msg(msg):
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"Lỗi gửi Tele: {e}")

# --- LOGIC AI ---
def get_ai_logic():
    if len(state.raw_data) < 3: return "Tài", 50.0
    h = hashlib.md5(str(time.time()).encode()).hexdigest()
    prob = (Counter(state.raw_data)["Tài"] / len(state.raw_data) * 0.7) + (int(h[:2], 16)/255 * 0.3)
    if prob >= 0.5: return "Tài", round(prob*100, 2)
    return "Xỉu", round((1-prob)*100, 2)

# --- ADMIN API (NHẬP PHIÊN & BUFF) ---
class AdminUpdate(BaseModel):
    phien_id: int
    ket_qua: str

class BuffMem(BaseModel):
    group_link: str
    amount: int

@app.post("/admin/update", tags=["Admin Control"])
async def update_result(data: AdminUpdate):
    kq = data.ket_qua.strip().capitalize()
    if kq not in ["Tài", "Xỉu"]: raise HTTPException(400, "Chỉ Tài/Xỉu")
    
    # Kiểm tra đúng sai
    status = "N/A"
    if data.phien_id in state.history:
        pred = state.history[data.phien_id]["predict"]
        if pred == kq:
            state.win += 1
            status = "✅ ĐÚNG"
        else:
            status = "❌ SAI"
        state.total += 1
    
    state.raw_data.append(kq)
    
    # Gửi thông báo kết quả lên Bot
    msg = (f"<b>🔔 KẾT QUẢ PHIÊN {data.phien_id}</b>\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"● Kết quả thực tế: <b>{kq}</b>\n"
           f"● Dự đoán AI: <b>{status}</b>\n"
           f"● Tỉ lệ thắng tool: {state.win}/{state.total}\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"🚀 Đang chuẩn bị phân tích phiên tiếp theo...")
    asyncio.run_coroutine_threadsafe(send_tele_msg(msg), asyncio.get_event_loop())
    
    # Nhảy lên 1 phiên và kích hoạt dự đoán tiếp theo
    state.phien = data.phien_id + 1
    state.mode = "analyzing"
    return {"status": "Updated", "next_phien": state.phien}

@app.post("/admin/buff-mem", tags=["Admin Buff"])
def buff_mem_action(data: BuffMem):
    # Logic buff mem ảo (tăng con số hiển thị hoặc add bot nếu có list)
    state.virtual_mem += data.amount
    return {"status": "Success", "current_group_mem": state.virtual_mem}

@app.get("/api/predict")
def user_view():
    return {"phien": state.phien, "du_doan": state.last_pred, "mem_online": state.virtual_mem}

# --- LUỒNG CHẠY NGẦM ---
def core_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        if state.mode == "analyzing":
            # Gửi tin nhắn đang phân tích
            asyncio.run_coroutine_threadsafe(
                send_tele_msg("🔍 <b>ĐANG PHÂN TÍCH DỮ LIỆU...</b>\n⚡ Vui lòng đợi giây lát"), loop)
            
            time.sleep(5) # Giả lập chờ load dữ liệu
            
            pred, conf = get_ai_logic()
            state.last_pred, state.last_conf = pred, conf
            state.history[state.phien] = {"predict": pred}
            
            # Gửi dự đoán CỰC ĐẸP
            msg = (f"<b>💎 AI PREDICTOR PREMIUM 💎</b>\n"
                   f"➖➖➖➖➖➖➖➖➖➖\n"
                   f"🆔 Phiên: <code>#{state.phien}</code>\n"
                   f"🎯 Dự đoán: <b>{pred.upper()}</b>\n"
                   f"📊 Độ tin cậy: <code>{conf}%</code>\n"
                   f"👥 Đang theo dõi: {state.virtual_mem + np.random.randint(10,50)} người\n"
                   f"➖➖➖➖➖➖➖➖➖➖\n"
                   f"⚠️ Lỗi liên hệ: {ADMIN_ID}\n"
                   f"💰 <b>BẢNG GIÁ BUFF MEM:</b>\n"
                   f"• 50k = 45 mem | 100k = 88 mem")
            asyncio.run_coroutine_threadsafe(send_tele_msg(msg), loop)
            
            state.mode = "waiting_admin" # Chờ admin nhập kết quả phiên này mới chạy tiếp
            
        time.sleep(2)

# --- CHẠY SERVER ---
if __name__ == "__main__":
    threading.Thread(target=core_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
