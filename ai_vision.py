import cv2
import json
import time
import threading
import google.generativeai as genai
from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.edgetpu import make_interpreter, list_edge_tpus
import config

class VisionSystem:
    def __init__(self, state, hardware, audio):
        self.state = state
        self.hardware = hardware
        self.audio = audio
        self.interpreter = None
        self.movenet_interpreter = None
        self.gemini_model = None
        self.tracker = None
        self.labels_map = {}
        self.name_to_id = {}
        
        # Sentry Mode Variables
        self.sentry_timer = 0
        self.sentry_last_check = time.time()
        self.sentry_last_cx = None
        self.sentry_last_cy = None
        self.patrol_direction = 1
        self.patrol_last_move = time.time()
        self.half_time_warned = False # 避免重複警告
        
        self._init_tpus()
        self._init_gemini()
        self._load_labels()

    def _init_tpus(self):
        # 取得所有可用的 TPU
        tpus = list_edge_tpus()
        print(f"🔍 系統偵測到 {len(tpus)} 個 Coral TPU 裝置")

        # 1. 初始化物件偵測 (使用第一個 TPU)
        if len(tpus) > 0:
            try:
                # 嘗試不指定 device path，讓 libedgetpu 自動分配第一個
                # 如果指定 path 失敗，通常是因為 libedgetpu 版本或權限問題
                # 這裡改回最穩定的寫法，但嘗試兩次 make_interpreter
                
                self.interpreter = make_interpreter(config.CORAL_MODEL_PATH)
                self.interpreter.allocate_tensors()
                print(f"✅ TPU #1 (Object) 連線成功")
            except Exception as e:
                print(f"❌ TPU #1 初始化失敗: {e}")
                self.interpreter = None

        # 2. 初始化 MoveNet (使用第二個 TPU)
        if config.ENABLE_MOVENET:
            if len(tpus) > 1:
                try:
                    self.movenet_interpreter = make_interpreter(config.MOVENET_MODEL_PATH)
                    self.movenet_interpreter.allocate_tensors()
                    print(f"✅ TPU #2 (MoveNet) 連線成功")
                except Exception as e:
                    print(f"❌ TPU #2 初始化失敗: {e}")
                    self.movenet_interpreter = None
            elif len(tpus) == 1:
                print("⚠️ 只有 1 個 TPU，MoveNet 功能將停用")
        else:
            print("🚫 MoveNet 功能已在設定中停用")

    # 舊的初始化函式已整合至 _init_tpus，移除 _init_coral 與 _init_posenet
    
    def _init_gemini(self):
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
            # 使用 config 中的模型名稱
            print(f"🧠 Gemini 模型: {config.GEMINI_MODEL_NAME}")
            self.gemini_model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)

    def _load_labels(self):
        try:
            with open(config.LABEL_PATH, 'r') as f:
                for line in f:
                    if line.strip():
                        pid, name = line.strip().split(maxsplit=1)
                        self.labels_map[int(pid)] = name
                        self.name_to_id[name] = int(pid)
        except:
            pass

    def ask_gemini_intent(self, text):
        """
        使用 Gemini 判斷語音指令的意圖，處理諧音或模糊指令
        """
        if not self.gemini_model: return None
        
        prompt = f"""
        你是 AI 哨兵砲台的大腦。使用者說了: "{text}"。
        這可能是語音辨識錯誤 (諧音) 或模糊指令。請推測使用者的意圖並回傳 JSON。
        
        可用指令:
        1. FIRE: 開火、射擊、發射 (常見誤聽: 設計, 涉及, 發癢, 發財)
        2. STOP: 停止、暫停、休息
        3. TRACK_PERSON: 追蹤人、看人
        4. SENTRY_MODE: 哨兵模式、監視模式、開始巡邏
        5. SEARCH: 尋找特定物品 (回傳 target)
        6. UNKNOWN: 無法理解
        
        回傳格式範例:
        {{ "intent": "FIRE" }}
        {{ "intent": "SENTRY_MODE" }}
        {{ "intent": "SEARCH", "target": "杯子" }}
        {{ "intent": "UNKNOWN" }}
        """
        
        try:
            response = self.gemini_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Gemini Intent Error: {e}")
            return None

    def ask_gemini_coordinates(self, frame, prompt):
        try:
            ret, buffer = cv2.imencode('.jpg', frame)
            full_prompt = f"找出畫面中'{prompt}'。回傳純JSON: {{ \"box_2d\": [ymin, xmin, ymax, xmax] }} (0-1000)。找不到回傳 null。"
            response = self.gemini_model.generate_content(
                [full_prompt, {'mime_type': 'image/jpeg', 'data': buffer.tobytes()}],
                generation_config={"response_mime_type": "application/json"}
            )
            data = json.loads(response.text)
            if data.get("box_2d"):
                h, w = frame.shape[:2]
                ymin, xmin, ymax, xmax = data["box_2d"]
                return (int(xmin/1000*w), int(ymin/1000*h), int((xmax-xmin)/1000*w), int((ymax-ymin)/1000*h))
        except Exception as e:
            print(f"Gemini Error: {e}")
        return None

    def _run_movenet(self, frame):
        """
        執行 MoveNet 推論並檢查是否舉手投降
        MoveNet Output: [1, 1, 17, 3] (y, x, score)
        """
        if not self.movenet_interpreter: return False, [], []
        
        try:
            # 1. Resize and set input (MoveNet Lightning is 192x192)
            input_size = (192, 192) 
            resized = cv2.resize(frame, input_size)
            common.set_input(self.movenet_interpreter, resized)
            
            # 2. Inference
            self.movenet_interpreter.invoke()
            
            # 3. Get Output
            # MoveNet output shape: [1, 1, 17, 3] -> [17, 3]
            keypoints_with_scores = common.output_tensor(self.movenet_interpreter, 0)[0][0]
            
            # 4. Parse Keypoints
            # 0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear
            # 5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow
            # 9: left_wrist, 10: right_wrist, ...
            
            keypoints = []
            scores = []
            
            for k in keypoints_with_scores:
                y, x, score = k
                keypoints.append((y, x))
                scores.append(score)
            
            # 5. Check "Hands Up" (Wrists above Ears)
            # Y coordinate: Smaller is higher
            left_wrist_y = keypoints[9][0]
            right_wrist_y = keypoints[10][0]
            left_ear_y = keypoints[3][0]
            right_ear_y = keypoints[4][0]
            
            left_score = scores[9]
            right_score = scores[10]
            
            surrender = False
            if left_score > 0.3 and left_wrist_y < left_ear_y:
                surrender = True
            if right_score > 0.3 and right_wrist_y < right_ear_y:
                surrender = True
                
            return surrender, keypoints, scores
        except Exception as e:
            print(f"MoveNet Error: {e}")
            return False, [], []

    def run_loop(self):
        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)
        
        print("🚀 視覺系統啟動！")
        
        fail_count = 0
        frame_count = 0
        
        while self.state.running:
            success, frame = cap.read()
            if not success: 
                fail_count += 1
                if fail_count % 10 == 0:
                    print(f"⚠️ 攝影機讀取失敗 ({fail_count} 次)，嘗試重啟...")
                    cap.release()
                    time.sleep(1)
                    cap = cv2.VideoCapture(0)
                    cap.set(3, 640)
                    cap.set(4, 480)
                else:
                    time.sleep(0.1)
                continue
            
            fail_count = 0
            frame_count += 1
            
            mode = self.state.current_mode

            # --- MoveNet Logic (每 N 幀跑一次) ---
            if not hasattr(self, 'last_movenet_result'):
                self.last_movenet_result = (False, [], [])

            if self.movenet_interpreter and frame_count % config.MOVENET_SKIP_FRAMES == 0:
                self.last_movenet_result = self._run_movenet(frame)
            
            is_surrender, keypoints, scores = self.last_movenet_result

            if is_surrender:
                cv2.putText(frame, config.SURRENDER_TEXT, (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 4)
                self.state.auto_fire_enabled = False
                
            # 簡單繪製骨架 (Debug)
            if len(keypoints) > 0:
                # MoveNet Lightning input size is fixed at 192x192
                input_w, input_h = 192, 192
                scale_x = frame.shape[1] / input_w
                scale_y = frame.shape[0] / input_h
                
                # Draw connections (skeleton lines)
                # Nose(0), Eyes(1,2), Ears(3,4), Shoulders(5,6), Elbows(7,8), Wrists(9,10), Hips(11,12), Knees(13,14), Ankles(15,16)
                connections = [
                    (5, 7), (7, 9), # Left Arm
                    (6, 8), (8, 10), # Right Arm
                    (5, 6), # Shoulders
                    (5, 11), (6, 12), # Body
                    (11, 13), (13, 15), # Left Leg
                    (12, 14), (14, 16), # Right Leg
                    (11, 12) # Hips
                ]

                for i, (y, x) in enumerate(keypoints):
                    if scores[i] > 0.3:
                        # MoveNet output is normalized [0, 1] if using float model, 
                        # but we are using quantized model? Let's check.
                        # Actually, common.output_tensor returns raw values.
                        # For MoveNet Lightning (int8), output is NOT normalized, it is pixel coordinates relative to 192x192?
                        # Wait, MoveNet output is usually normalized [0,1].
                        # Let's assume normalized first. If points are all at top-left, then it's normalized.
                        
                        # Correction: MoveNet TFLite output is usually [y, x, score].
                        # If it's normalized, values are 0-1. If not, they are 0-192.
                        # Let's try to detect. If max value <= 1.0, it's normalized.
                        
                        cx, cy = int(x * frame.shape[1]), int(y * frame.shape[0])
                        
                        # If points are weird, maybe it's not normalized?
                        # But standard MoveNet TFLite is normalized.
                        
                        cv2.circle(frame, (cx, cy), 5, (0, 255, 255), -1)

                # Draw lines
                for a, b in connections:
                    if scores[a] > 0.3 and scores[b] > 0.3:
                        y1, x1 = keypoints[a]
                        y2, x2 = keypoints[b]
                        pt1 = (int(x1 * frame.shape[1]), int(y1 * frame.shape[0]))
                        pt2 = (int(x2 * frame.shape[1]), int(y2 * frame.shape[0]))
                        cv2.line(frame, pt1, pt2, (0, 255, 255), 2)
            # ---------------------
            # ---------------------
            
            # Draw UI
            cv2.putText(frame, f"MODE: {mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            if self.state.auto_fire_enabled:
                 cv2.putText(frame, "AUTO-FIRE: ON", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # --- Object Detection (Always Run for Visualization) ---
            coral_target = None
            if self.interpreter:
                common.set_input(self.interpreter, cv2.resize(frame, (300, 300)))
                self.interpreter.invoke()
                objs = detect.get_objects(self.interpreter, 0.5)
                
                h, w = frame.shape[:2]
                for obj in objs:
                    bbox = obj.bbox
                    xmin, ymin = int(bbox.xmin*w/300), int(bbox.ymin*h/300)
                    xmax, ymax = int(bbox.xmax*w/300), int(bbox.ymax*h/300)
                    
                    # Draw Box & Label
                    label = self.labels_map.get(obj.id, str(obj.id))
                    
                    # Visualization Filter: Only show person in IDLE/SENTRY modes
                    show_box = True
                    if mode in ["IDLE", "SENTRY_MODE"] and obj.id != 0:
                        show_box = False
                        
                    if show_box:
                        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
                        cv2.putText(frame, f"{label} {obj.score:.2f}", (xmin, ymin-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                    # Check if this is the target we want to track
                    if mode == "CORAL_TRACK" and obj.id == self.state.target_config['id']:
                        # Pick the first one (highest score)
                        if coral_target is None:
                            coral_target = (xmin, ymin, xmax, ymax)
                    
                    # Sentry Mode: Track Person (ID 0 is usually person in COCO)
                    if mode == "SENTRY_MODE" and obj.id == 0:
                         if coral_target is None:
                            coral_target = (xmin, ymin, xmax, ymax)

            # --- Control Logic ---
            if mode == "CORAL_TRACK" and coral_target:
                xmin, ymin, xmax, ymax = coral_target
                # Highlight the target being tracked with a different color
                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 0, 255), 3)
                self.hardware.update_servos((xmin+xmax)//2, (ymin+ymax)//2)

            elif mode == "SENTRY_MODE":
                if coral_target:
                    # 1. Get coordinates (Don't move servos yet)
                    xmin, ymin, xmax, ymax = coral_target
                    cx, cy = (xmin+xmax)//2, (ymin+ymax)//2
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 0, 255), 3)
                    
                    # 2. Check Stationary Status (Pixel based)
                    now = time.time()
                    if now - self.sentry_last_check >= 1.0: # Check every second
                        # Calculate distance from last check
                        if self.sentry_last_cx is None:
                             dist = 0 
                             self.sentry_timer = 0
                        else:
                             dist = ((cx - self.sentry_last_cx)**2 + (cy - self.sentry_last_cy)**2)**0.5
                        
                        # Threshold: config.SENTRY_MOVE_THRESHOLD is in degrees. 
                        # Approx conversion: 1 degree ~ 10 pixels
                        pixel_threshold = config.SENTRY_MOVE_THRESHOLD * 10
                        
                        if self.sentry_last_cx is not None and dist < pixel_threshold:
                            self.sentry_timer += 1
                        else:
                            self.sentry_timer = 0 # Reset if moved
                            self.half_time_warned = False # 重置警告標記
                            
                        self.sentry_last_cx = cx
                        self.sentry_last_cy = cy
                        self.sentry_last_check = now
                    
                    # 3. Draw Timer
                    color = (0, 255, 0)
                    if self.sentry_timer > config.SENTRY_TIMEOUT / 2: 
                        color = (0, 255, 255)
                        # 播放警告音效 (只播放一次)
                        if not self.half_time_warned:
                            self.audio.warning_half_time()
                            self.half_time_warned = True
                            
                    if self.sentry_timer > config.SENTRY_TIMEOUT - 10: color = (0, 0, 255)
                    
                    timer_text = f"STATIONARY: {self.sentry_timer}s / {config.SENTRY_TIMEOUT}s"
                    cv2.putText(frame, timer_text, (xmin, ymin - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    # 4. Fire if timeout
                    if self.sentry_timer >= config.SENTRY_TIMEOUT:
                        cv2.putText(frame, "ELIMINATING TARGET...", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                        
                        # AIM NOW (Quickly center the target)
                        # Estimate move: 1 pixel ~ 0.1 degrees
                        # Fix: Changed to (CY - cy) to match Positive KP (Negative Delta = Look Down)
                        pan_delta = (cx - config.CX) * -0.1 
                        tilt_delta = (config.CY - cy) * 0.1
                        self.hardware.manual_move(pan_delta, tilt_delta)
                        time.sleep(0.5) # Wait for servo
                        
                        self.hardware.fire_gun()
                        self.sentry_timer = 0 
                        self.state.current_mode = "IDLE" # Switch to IDLE
                        print("✅ 任務完成，切換回閒置模式")
                else:
                    # No person found -> Patrol Mode (Slow Pan)
                    self.sentry_timer = 0
                    self.sentry_last_cx = None # Reset tracking
                    cv2.putText(frame, "SCANNING AREA...", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                    
                    now = time.time()
                    if now - self.patrol_last_move > 0.1: # Move every 100ms
                        # Simple patrol: Pan between MIN and MAX
                        # We need to access hardware pan limits, assuming they are in config or hardware
                        # Let's use safe limits 30-110
                        current_pan = self.hardware.pan_angle
                        
                        if current_pan >= 110: self.patrol_direction = -1
                        if current_pan <= 30: self.patrol_direction = 1
                        
                        self.hardware.manual_move(self.patrol_direction * 1.0, 0) # Move 1 degree
                        self.patrol_last_move = now

            elif mode == "GEMINI_SEARCH":
                cv2.putText(frame, "AI ANALYZING...", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                # Update output frame so user sees "Analyzing"
                with self.state.lock: self.state.output_frame = frame.copy()
                
                bbox = self.ask_gemini_coordinates(frame, self.state.gemini_prompt)
                if bbox:
                    # Shrink bbox by 20% to avoid background tracking drift
                    x, y, w, h = bbox
                    shrink_factor = 0.2
                    new_x = int(x + w * shrink_factor / 2)
                    new_y = int(y + h * shrink_factor / 2)
                    new_w = int(w * (1 - shrink_factor))
                    new_h = int(h * (1 - shrink_factor))
                    bbox = (new_x, new_y, new_w, new_h)

                    # OpenCV 4.5+ moved trackers to legacy or contrib
                    try:
                        self.tracker = cv2.TrackerCSRT_create()
                    except AttributeError:
                        # Fallback for newer OpenCV versions
                        try:
                            self.tracker = cv2.legacy.TrackerCSRT_create()
                        except AttributeError:
                             # Fallback to a simpler tracker if CSRT is missing
                             print("⚠️ CSRT Tracker not found, using MIL")
                             self.tracker = cv2.TrackerMIL_create()
                             
                    self.tracker.init(frame, bbox)
                    self.state.current_mode = "GEMINI_TRACK"
                else:
                    self.state.current_mode = "IDLE"

            elif mode == "GEMINI_TRACK" and self.tracker:
                success, bbox = self.tracker.update(frame)
                if success:
                    x, y, w, h = [int(v) for v in bbox]
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 255), 2)
                    self.hardware.update_servos(x+w//2, y+h//2)
                else:
                    self.state.current_mode = "IDLE"

            # Crosshair
            cv2.line(frame, (config.CX-20, config.CY), (config.CX+20, config.CY), (200, 200, 200), 1)
            cv2.line(frame, (config.CX, config.CY-20), (config.CX, config.CY+20), (200, 200, 200), 1)
            
            with self.state.lock: self.state.output_frame = frame.copy()
        
        cap.release()
