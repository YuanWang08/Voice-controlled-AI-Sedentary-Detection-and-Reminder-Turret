import queue
import json
import threading
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import config

class VoiceSystem:
    def __init__(self, state, hardware, vision_system):
        self.state = state
        self.hardware = hardware
        self.vision_system = vision_system # Need access to name_to_id
        self.q = queue.Queue()

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(f"⚠️ 音訊狀態: {status}", flush=True)
        self.q.put(bytes(indata))

    def parse_command(self, text):
        print(f"指令解析中: {text}")

        # 1. 組合指令
        if any(k in text for k in ["後開火", "然後開火", "並射擊"]):
            self.state.auto_fire_enabled = True
            print("⚠️ 戰術模式：鎖定後自動開火 ON")
        else:
            self.state.auto_fire_enabled = False

        # 2. 直接開火
        if text in ["開火", "發射", "射擊", "fire"]:
            threading.Thread(target=self.hardware.fire_gun).start()
            return

        # 3. 手動移動
        if any(k in text for k in ["轉", "移", "往", "看"]):
            if any(d in text for d in ["左", "右", "上", "下"]):
                self.state.current_mode = "IDLE"
                step = 10
                pan_d, tilt_d = 0, 0
                
                if "左" in text: pan_d = 10
                elif "右" in text: pan_d = -10
                
                if "上" in text: tilt_d = 10
                elif "下" in text: tilt_d = -10
                
                if "最" in text:
                    # Logic for "max" is a bit complex with delta, let's simplify or handle it in hardware
                    # For now, just big step
                    step = 100
                
                self.hardware.manual_move(pan_d * (step/10), tilt_d * (step/10))
                return

        # 4. 模式切換
        if "哨兵模式" in text or "監視模式" in text:
            self.state.current_mode = "SENTRY_MODE"
            print("🛡️ 哨兵模式啟動")
            return
        
        if "停止" in text or "休息" in text or "手動" in text:
            self.state.current_mode = "IDLE"
            print("🛑 系統停止/手動模式")
            return

        # 5. Coral 追蹤
        for name, pid in self.vision_system.name_to_id.items():
            if name in text:
                self.state.target_config = {"id": pid, "name": name}
                self.state.current_mode = "CORAL_TRACK"
                print(f"🚀 Coral 追蹤: [{name}]")
                return

        # 5. Gemini 意圖識別 (Fallback)
        # 如果以上本地指令都沒對中，就問 Gemini
        print("🤔 本地指令未匹配，詢問 Gemini 意圖...")
        intent_data = self.vision_system.ask_gemini_intent(text)
        
        if intent_data:
            intent = intent_data.get("intent")
            print(f"🧠 Gemini 意圖判斷: {intent}")
            
            if intent == "FIRE":
                threading.Thread(target=self.hardware.fire_gun).start()
                return
            elif intent == "STOP":
                self.state.current_mode = "IDLE"
                return
            elif intent == "TRACK_PERSON":
                self.state.target_config = {"id": 0, "name": "person"}
                self.state.current_mode = "CORAL_TRACK"
                return
            elif intent == "SENTRY_MODE":
                self.state.current_mode = "SENTRY_MODE"
                print("🛡️ Gemini: 切換至哨兵模式")
                return
            elif intent == "SEARCH":
                target = intent_data.get("target")
                if target:
                    self.state.gemini_prompt = target
                    self.state.current_mode = "GEMINI_SEARCH"
                    print(f"🧠 Gemini 搜尋目標: [{target}]")
                return

        # 6. 舊的 Gemini 搜尋 (作為最後手段，如果 Gemini Intent 也失敗或回傳 UNKNOWN)
        clean_prompt = text.replace("後開火", "").replace("幫我", "").replace("鎖定", "").replace("找", "").replace("看", "").replace("往", "")
        if clean_prompt and len(clean_prompt) > 1:
            self.state.gemini_prompt = clean_prompt
            self.state.current_mode = "GEMINI_SEARCH"
            print(f"🧠 Gemini 搜尋 (Fallback): [{clean_prompt}]")

    def run_loop(self):
        try:
            model = Model(config.VOSK_MODEL_PATH)
            rec = KaldiRecognizer(model, 16000)
            print("🎤 語音系統啟動...")
            
            # 嘗試自動偵測裝置，不指定 device=9
            # 如果需要指定裝置，請先執行 python -m sounddevice 查看列表
            with sd.InputStream(samplerate=16000, blocksize=8000, 
                                dtype='int16', channels=1, callback=self.audio_callback):
                while self.state.running:
                    data = self.q.get()
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        text = res.get('text', '').replace(' ', '')
                        if text:
                            print(f"👂: {text}")
                            # 記錄到共享狀態，保留最近 10 筆
                            with self.state.lock:
                                self.state.voice_logs.append(text)
                                if len(self.state.voice_logs) > 10:
                                    self.state.voice_logs.pop(0)
                            self.parse_command(text)
        except Exception as e:
            print(f"❌ 語音錯誤: {e}")
