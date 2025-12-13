import os
import threading

# 嘗試載入 .env，如果不依賴 python-dotenv，這裡寫個簡單的讀取
def load_env_file(filepath='.env'):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")

load_env_file()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")
ENABLE_MOVENET = os.getenv("ENABLE_MOVENET", "true").lower() == "true"
MOVENET_SKIP_FRAMES = int(os.getenv("MOVENET_SKIP_FRAMES", "3"))
SURRENDER_TEXT = os.getenv("SURRENDER_TEXT", "SURRENDER DETECTED!")
SENTRY_TIMEOUT = int(os.getenv("SENTRY_TIMEOUT", "120"))
SENTRY_MOVE_THRESHOLD = float(os.getenv("SENTRY_MOVE_THRESHOLD", "2.0"))

# 檔案路徑
CORAL_MODEL_PATH = 'model/ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite'
# 改用 MoveNet，相容性更好且速度更快
MOVENET_MODEL_PATH = 'model/movenet_single_pose_lightning_ptq_edgetpu.tflite'
LABEL_PATH = 'model/coco_labels.txt'
VOSK_MODEL_PATH = "model/cn_model"
# 音效路徑 (優先讀取環境變數，預設為桌面 media 資料夾下的 wav)
FIRE_SOUND_PATH = os.getenv("FIRE_SOUND_PATH", "/home/s112403543/Desktop/media/shotsound.wav")

# 馬達孔位
PAN_CH, TILT_CH, GUN_CH = 0, 1, 2
PAN_MIN, PAN_MAX, PAN_CENTER = 0, 140, 70
TILT_MIN, TILT_MAX, TILT_LEVEL = 56, 180, 76
GUN_SAFE, GUN_FIRE = 130, 0

# PID 參數 (修正：垂直方向改回正值，但降低數值以求穩定)
KP_PAN = 0.025  # 微調
KP_TILT = 0.025 # 改回正值，因為負值會導致正回授 (看天花板)

# 追蹤限制
MAX_STEP = 3    # 保持 3
DEADBAND = 20   # 保持 20

# 畫面中心
CX, CY = 320, 240

class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.current_mode = "IDLE"  # IDLE, CORAL_TRACK, GEMINI_SEARCH, GEMINI_TRACK
        self.target_config = {"id": 0, "name": "person"}
        self.gemini_prompt = ""
        self.auto_fire_enabled = False
        self.output_frame = None
        self.running = True # 控制程式結束
        self.voice_logs = [] # 儲存語音紀錄
