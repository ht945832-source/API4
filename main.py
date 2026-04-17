import numpy as np
import threading
import time
import hashlib
import math
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import deque, Counter

# Khởi tạo FastAPI
app = FastAPI(title="AI Predictor Pro")

# ====== CẤU HÌNH ======
ANALYZE_SECONDS = 50
IDLE_SECONDS = 15

class GameEngine:
    def __init__(self):
        self.current_phien = 10001
        self.history_records = {} # Lưu {id: {predict, result, status}}
        self.raw_results = deque(maxlen=50)
        self.stats = {"win": 0, "total": 0}
        self.mode = "idle"
        self.last_pred = "N/A"
        self.last_conf = 0.0

engine = GameEngine()

# ====== THUẬT TOÁN AI (KẾT HỢP ENTROPY & BAYESIAN) ======
def get_ai_prediction():
    if len(engine.raw_results) < 3:
        return "Tài", 50.0

    # 1. Thuật toán Entropy (từ lc79)
    sample_text = hashlib.md5(str(time.time()).encode()).hexdigest()
    counts = Counter(sample_text)
    n = len(sample_text)
    entropy = -sum((v/n)*math.log2(v/n) for v in counts.values())
    
    # 2. Thuật toán Tần suất (từ tool68gb)
    res_counts = Counter(engine.raw_results)
    prob_tai = res_counts["Tài"] / len(engine.raw_results)
    
    # 3. Kết hợp xác suất
    # Trọng số: 60% Tần suất + 40% Entropy
    final_score = (prob_tai * 0.6) + (entropy / 4 * 0.4)
    
    # Ép về khoảng an toàn
    final_score = max(0.1, min(0.9, final_score))
    
    if final_score >= 0.5:
        return "Tài", round(final_score * 100, 2)
    else:
        return "Xỉu", round((1 - final_score) * 100, 2)

# ====== CÁC API ======

@app.get("/")
def read_root():
    return {"status": "Running", "phien": engine.current_phien}

@app.get("/api/predict")
def get_prediction():
    return {
        "phien": engine.current_phien,
        "du_doan": engine.last_pred,
        "confidence": f"{engine.last_conf}%",
        "trang_thai": engine.mode,
        "ti_le_thang": f"{(engine.stats['win']/engine.stats['total']*100) if engine.stats['total']>0 else 0:.2f}%"
    }

class ResultInput(BaseModel):
    phien_id: int
    ket_qua: str

@app.post("/admin/update")
def update_result(data: ResultInput):
    kq = data.ket_qua.strip().capitalize()
    if kq not in ["Tài", "Xỉu"]:
        raise HTTPException(status_code=400, detail="Chỉ nhập Tài hoặc Xỉu")
    
    p_id = data.phien_id
    if p_id in engine.history_records:
        engine.history_records[p_id]["result"] = kq
        if engine.history_records[p_id]["predict"] == kq:
            engine.history_records[p_id]["status"] = "ĐÚNG"
            engine.stats["win"] += 1
        else:
            engine.history_records[p_id]["status"] = "SAI"
        engine.stats["total"] += 1
    
    engine.raw_results.append(kq)
    return {"status": "success", "check": engine.history_records.get(p_id, {}).get("status", "No Data")}

# ====== LUỒNG XỬ LÝ NGẦM (BACKGROUND WORKER) ======
def run_loop():
    while True:
        # Giai đoạn phân tích
        engine.mode = "analyzing"
        pred, conf = get_ai_prediction()
        engine.last_pred = pred
        engine.last_conf = conf
        
        # Lưu phiên chờ
        engine.history_records[engine.current_phien] = {
            "predict": pred, "result": None, "status": "Waiting"
        }
        
        time.sleep(ANALYZE_SECONDS)
        
        # Giai đoạn nghỉ
        engine.mode = "idle"
        time.sleep(IDLE_SECONDS)
        
        # Tăng phiên và dọn dẹp RAM
        engine.current_phien += 1
        if len(engine.history_records) > 50:
            first = min(engine.history_records.keys())
            engine.history_records.pop(first)

# Khởi chạy thread (Đảm bảo code này thụt lề sát lề trái)
thread = threading.Thread(target=run_loop, daemon=True)
thread.start()
