import numpy as np
import threading
import time
import hashlib
import math
import uvicorn
import os
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from collections import deque, Counter

# --- KHỞI TẠO APP VỚI CẤU TRÚC PHÂN TÁCH ---
app = FastAPI(
    title="Hệ Thống AI Điều Khiển",
    description="API dành cho User và API điều khiển dành riêng cho Admin",
    version="3.0.0"
)

# --- QUẢN LÝ TRẠNG THÁI HỆ THỐNG ---
class SystemEngine:
    def __init__(self):
        self.phien = 10001
        self.history = {} 
        self.raw_data = deque(maxlen=50) 
        self.win = 0
        self.total = 0
        self.mode = "idle"
        self.current_pred = "N/A"
        self.current_conf = 0.0
        # Lệnh từ admin
        self.admin_command = "Chưa có lệnh"

    def calculate_logic(self):
        """Thuật toán lai từ lc79 và tool68gb"""
        if len(self.raw_data) < 3:
            return "Tài", 50.0
        h = hashlib.md5(str(time.time()).encode()).hexdigest()
        f = Counter(h)
        entropy = -sum((v/32)*math.log2(v/32) for v in f.values())
        counts = Counter(self.raw_data)
        prob_tai = counts["Tài"] / len(self.raw_data)
        score = (prob_tai * 0.5) + (entropy / 4 * 0.5)
        score = max(0.1, min(0.9, score))
        if score >= 0.5: return "Tài", round(score * 100, 2)
        else: return "Xỉu", round((1 - score) * 100, 2)

# Đối tượng engine duy nhất
engine = SystemEngine()

# --- MODELS ---
class AdminCommand(BaseModel):
    phien_id: int
    ket_qua_thuc_te: str
    ghi_chu: str = "Không có"

# --- [ KHU VỰC USER API ] ---

@app.get("/api/predict", tags=["User API"])
def user_get_prediction():
    """
    User gọi API này để xem dự đoán hiện tại 
    và xem lệnh mới nhất từ Admin.
    """
    win_rate = (engine.win / engine.total * 100) if engine.total > 0 else 0
    return {
        "phien": engine.phien,
        "du_doan_ai": engine.current_pred,
        "do_tin_cay": f"{engine.current_conf}%",
        "trang_thai": engine.mode,
        "lenh_admin_moi_nhat": engine.admin_command,
        "thong_ke": f"Thắng {engine.win}/{engine.total} ({win_rate:.2f}%)"
    }

# --- [ KHU VỰC ADMIN API ] ---

@app.post("/admin/send-command", tags=["Admin API"])
def admin_issue_command(data: AdminCommand):
    """
    API DÀNH RIÊNG CHO ADMIN: Phát lệnh nhập kết quả.
    Lệnh này sẽ được User nhìn thấy tại /api/predict
    """
    kq = data.ket_qua_thuc_te.strip().capitalize()
    if kq not in ["Tài", "Xỉu"]:
        raise HTTPException(status_code=400, detail="Kết quả phải là Tài hoặc Xỉu")

    # Cập nhật lệnh vào hệ thống
    engine.admin_command = f"Phiên {data.phien_id} về {kq} (Ghi chú: {data.ghi_chu})"
    
    # Đối chiếu đúng sai nếu phiên trùng khớp
    p_id = data.phien_id
    if p_id in engine.history:
        engine.history[p_id]["result"] = kq
        if engine.history[p_id]["predict"] == kq:
            engine.history[p_id]["status"] = "ĐÚNG"
            engine.win += 1
        else:
            engine.history[p_id]["status"] = "SAI"
        engine.total += 1
        check_res = engine.history[p_id]["status"]
    else:
        check_res = "Phiên không tồn tại trong bộ nhớ"

    engine.raw_data.append(kq)
    
    return {
        "status": "Lệnh đã phát thành công",
        "phien": p_id,
        "ket_qua": kq,
        "so_khop": check_res
    }

# --- LUỒNG CHẠY NGẦM ---
def background_loop():
    while True:
        engine.mode = "analyzing"
        pred, conf = engine.calculate_logic()
        engine.current_pred = pred
        engine.current_conf = conf
        engine.history[engine.phien] = {"predict": pred, "result": None, "status": "Waiting"}
        
        time.sleep(50) # Chờ 50s
        
        engine.mode = "idle"
        time.sleep(15) # Chờ 15s
        engine.phien += 1
        
        # Dọn dẹp records cũ tránh đầy RAM
        if len(engine.history) > 30:
            engine.history.pop(min(engine.history.keys()))

# --- KHỞI CHẠY SERVER ---
if __name__ == "__main__":
    # Chạy luồng AI
    threading.Thread(target=background_loop, daemon=True).start()
    
    # Lấy Port từ môi trường (Render) hoặc mặc định 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
