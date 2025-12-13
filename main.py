import threading
import config
from hardware import SentryHardware
from ai_vision import VisionSystem
from voice import VoiceSystem
from web_server import create_app
from audio import AudioSystem

def main():
    # 1. 初始化狀態
    state = config.SharedState()
    
    # 2. 初始化音效系統
    audio = AudioSystem()
    audio.system_online()
    
    # 3. 初始化硬體
    hardware = SentryHardware(state)
    
    # 4. 初始化視覺 (傳入 audio)
    vision = VisionSystem(state, hardware, audio)
    
    # 5. 初始化語音 (傳入 audio)
    voice = VoiceSystem(state, hardware, vision) # VoiceSystem 暫時不需要 audio，或之後再加
    
    # 6. 初始化網頁 (傳入 audio)
    app = create_app(state, hardware, audio)

    # 7. 啟動執行緒
    threads = []
    
    t_vision = threading.Thread(target=vision.run_loop, daemon=True)
    t_vision.start()
    threads.append(t_vision)
    
    t_voice = threading.Thread(target=voice.run_loop, daemon=True)
    t_voice.start()
    threads.append(t_voice)
    
    print("✅ 系統全模組啟動完成")
    
    # 7. 啟動網頁伺服器 (Blocking)
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        state.running = False
        print("系統關閉中...")

if __name__ == "__main__":
    main()
