import numpy as np
import threading
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import deque

app = FastAPI(title="AI Tài Xỉu - Advanced Engine v3")

# ====== CẤU HÌNH ======
ANALYZE_SECONDS = 50
IDLE_SECONDS = 15
MAX_HISTORY = 100  # Lưu tối đa 100 phiên gần nhất trong bộ nhớ

# ====== HỆ THỐNG LƯU TRỮ ======
class GameState:
    def __init__(self):
        self.current_phien = 1001
        self.history_data = {}  # {id: {predict, result, status}}
        self.results_only = []  # Chỉ lưu kết quả "T" hoặc "X"
        self.stats = {"win": 0, "total": 0}
        self.engine_mode = "idle"
        self.last_prediction = "N/A"
        self.last_confidence = 0.0

state = GameState()

# ====== THUẬT TOÁN NÂNG CẤP ======
class AdvancedAI:
    def __init__(self):
        self.weights = np.array([0.2, 0.3, 0.5]) # [Tần suất, Markov, Pattern]

    def analyze_patterns(self, current_results):
        """Dò tìm chuỗi cầu tương tự trong lịch sử (Pattern Matching)"""
        if len(current_results) < 3: return 0.5
        
        last_3 = "".join(["T" if x == "Tài" else "X" for x in current_results[-3:]])
        # Giả lập logic tìm kiếm từ file cau.txt (Bạn có thể nạp thêm data vào đây)
        # Nếu chuỗi cuối là 'TXX' -> Thường về 'T'
        patterns = {"TXX": 0.7, "XTT": 0.3, "TXT": 0.6, "XTX": 0.4}
        return patterns.get(last_3, 0.5)

    def get_prediction(self, results):
        if len(results) < 5:
            return "Tài", 0.51
        
        # 1. Logic Tần suất (Frequency)
        freq = results[-10:].count("Tài") / len(results[-10:])
        
        # 2. Logic Pattern (Dò cầu)
        pattern_score = self.analyze_patterns(results)
        
        # 3. Logic Bayesian (Điều chỉnh theo xác suất thắng hiện tại)
        win_rate = (state.stats["win"] / state.stats["total"]) if state.stats["total"] > 0 else 0.5
        
        # Kết hợp trọng số
        final_score = (freq * 0.3) + (pattern_score * 0.7)
        
        # Làm mượt xác suất (Smoothing)
        if win_rate < 0.4: # Nếu AI đang thua, đảo cầu nhẹ hoặc giảm confidence
            final_score = 1 - final_score if final_score > 0.6 else final_score

        pred = "Tài" if final_score >= 0.5 else "Xỉu"
        conf = final_score if pred == "Tài" else 1 - final_score
        return pred, float(conf)

ai_engine = AdvancedAI()

# ====== API MODELS ======
class AdminUpdate(BaseModel):
    phien_id: int
    ket_qua: str

# ====== API ENDPOINTS ======

@app.get("/api/predict")
def predict():
    return {
        "phien": state.current_phien,
        "du_doan": state.last_prediction,
        "confidence": f"{state.last_confidence * 100:.2f}%",
        "trang_thai": state.engine_mode,
        "phien_truoc": list(state.history_data.values())[-1:] if state.history_data else "No data"
    }

@app.post("/admin/update")
def update(data: AdminUpdate):
    kq = data.ket_qua.strip().capitalize()
    if kq not in ["Tài", "Xỉu"]:
        raise HTTPException(400, "Kết quả sai định dạng")

    p_id = data.phien_id
    
    # Cập nhật kết quả thực tế
    if p_id in state.history_data:
        state.history_data[p_id]["result"] = kq
        if state.history_data[p_id]["predict"] == kq:
            state.history_data[p_id]["status"] = "ĐÚNG"
            state.stats["win"] += 1
        else:
            state.history_data[p_id]["status"] = "SAI"
        state.stats["total"] += 1
    
    state.results_only.append(kq)
    if len(state.results_only) > MAX_HISTORY:
        state.results_only.pop(0)

    return {"status": "Updated", "check": state.history_data.get(p_id, {}).get("status")}

# ====== CORE LOOP ======
def core_loop():
    while True:
        # Giai đoạn 1: Phân tích (50 giây)
        state.engine_mode = "analyzing"
        pred, conf = ai_engine.get_prediction(state.results_only)
        state.last_prediction = pred
        state.last_confidence = conf
        
        # Lưu bản ghi dự đoán vào lịch sử
        state.history_data[state.current_phien] = {
            "phien": state.current_phien,
            "predict": pred,
            "result": None,
            "status": "Waiting"
        }
        
        time.sleep(ANALYZE_SECONDS)

        # Giai đoạn 2: Nghỉ (15 giây)
        state.engine_mode = "idle"
        time.sleep(IDLE_SECONDS)
        
        # Chuyển phiên
        state.current_phien += 1
        
        # Dọn dẹp bộ nhớ (giữ 50 bản ghi gần nhất)
        if len(state.history_data) > 50:
            first_key = next(iter(state.history_data))
            state.history_data.pop(first_key)

threading.Thread(target=core_loop, daemon=True).start()
