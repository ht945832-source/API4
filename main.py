import numpy as np
import threading
import time
import hashlib
import math
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import deque, Counter

# --- KHỞI TẠO APP ---
app = FastAPI(title="AI Predictor Final Fixed")

# --- CẤU TRÚC QUẢN LÝ DỮ LIỆU ---
class AIEngine:
    def __init__(self):
        self.phien = 10001
        self.history = {} # Lưu {phien_id: {predict, result, status}}
        self.raw_data = deque(maxlen=50) # Lưu 50 kết quả gần nhất cho AI
        self.win = 0
        self.total = 0
        self.mode = "idle"
        self.current_pred = "N/A"
        self.current_conf = 0.0

    def calculate_logic(self):
        """Thuật toán tổng hợp từ lc79 và 68gb"""
        if len(self.raw_data) < 3:
            return "Tài", 50.0

        # 1. Entropy Logic (lc79)
        h = hashlib.md5(str(time.time()).encode()).hexdigest()
        f = Counter(h)
        entropy = -sum((v/32)*math.log2(v/32) for v in f.values())
        
        # 2. Bayesian Logic (68gb)
        counts = Counter(self.raw_data)
        prob_tai = counts["Tài"] / len(self.raw_data)
        
        # 3. Phân tích cầu (Pattern)
        last_3 = list(self.raw_data)[-3:]
        pattern_score = 0.5
        if last_3 == ["Tài", "Tài", "Tài"]: pattern_score = 0.8
        if last_3 == ["Xỉu", "Xỉu", "Xỉu"]: pattern_score = 0.2

        # Trọng số kết hợp
        score = (prob_tai * 0.4) + (pattern_score * 0.4) + (entropy / 4 * 0.2)
        score = max(0.1, min(0.9, score))
        
        if score >= 0.5:
            return "Tài", round(score * 100, 2)
        else:
            return "Xỉu", round((1 - score) * 100, 2)

# Khởi tạo một đối tượng duy nhất để dùng chung
engine = AIEngine()

# --- API MODELS ---
class AdminInput(BaseModel):
    phien_id: int
    ket_qua: str

# --- CÁC CỔNG API ---

@app.get("/")
def home():
    return {"status": "Online", "author": "@tranhoang2286"}

@app.get("/api/predict")
def get_predict():
    win_rate = (engine.win / engine.total * 100) if engine.total > 0 else 0
    return {
        "phien": engine.phien,
        "du_doan": engine.current_pred,
        "confidence": f"{engine.current_conf}%",
        "trang_thai": engine.mode,
        "ti_le_thang": f"{win_rate:.2f}%"
    }

@app.post("/admin/update")
def admin_update(data: AdminInput):
    kq = data.ket_qua.strip().capitalize()
    if kq not in ["Tài", "Xỉu"]:
        raise HTTPException(400, "Nhập 'Tài' hoặc 'Xỉu'")
    
    p_id = data.phien_id
    if p_id in engine.history:
        engine.history[p_id]["result"] = kq
        if engine.history[p_id]["predict"] == kq:
            engine.history[p_id]["status"] = "ĐÚNG"
            engine.win += 1
        else:
            engine.history[p_id]["status"] = "SAI"
        engine.total += 1
    
    engine.raw_data.append(kq)
    return {"status": "Updated", "check": engine.history.get(p_id, {}).get("status", "N/A")}

# --- LUỒNG CHẠY NGẦM ---
def background_worker():
    while True:
        # Bắt đầu 50s phân tích
        engine.mode = "analyzing"
        res, conf = engine.calculate_logic()
        engine.current_pred = res
        engine.current_conf = conf
        
        # Ghi nhận phiên chờ
        engine.history[engine.phien] = {
            "predict": res, "result": None, "status": "Waiting"
        }
        
        time.sleep(50)
        
        # Nghỉ 15s chờ admin nhập kết quả
        engine.mode = "idle"
        time.sleep(15)
        
        engine.phien += 1
        
        # Tự dọn dẹp bộ nhớ
        if len(engine.history) > 30:
            engine.history.pop(min(engine.history.keys()))

# Chạy Thread (Dòng này phải sát lề trái)
threading.Thread(target=background_worker, daemon=True).start()
