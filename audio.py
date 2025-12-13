import threading
import queue
import pyttsx3
import time

class AudioSystem:
    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        # 使用 Daemon thread 確保程式關閉時不會卡住
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        """
        獨立的語音執行緒，避免卡住主程式
        """
        try:
            # 在執行緒內部初始化引擎
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)   # 語速
            engine.setProperty('volume', 1.0) # 音量
        except Exception as e:
            print(f"❌ Audio Init Error: {e}")
            return

        while self.running:
            try:
                # 等待任務，最多等 1 秒以便檢查 running 狀態
                task_type, data = self.queue.get(timeout=1)
                
                if task_type == 'speak':
                    try:
                        engine.say(data)
                        engine.runAndWait()
                    except Exception as e:
                        print(f"❌ TTS Error: {e}")
                
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Audio Worker Error: {e}")

    def speak(self, text):
        """加入語音排程"""
        print(f"🗣️ [Audio]: {text}")
        self.queue.put(('speak', text))

    def system_online(self):
        self.speak("System Online. Sentry Ready.")

    def mode_switched(self, mode):
        text = mode.replace("_", " ").lower()
        if "sentry" in text:
            self.speak("Sentry Mode Engaged. Patrol initiated.")
        elif "idle" in text:
            self.speak("Manual Control.")
        elif "coral" in text:
            self.speak("Auto Tracking Enabled.")
        elif "gemini" in text:
            self.speak("AI Search Protocol Initiated.")
        else:
            self.speak(f"Mode switched to {text}")

    def warning_half_time(self):
        self.speak("Warning. Target stationary. Locking on.")
    
    def target_locked(self):
        self.speak("Target Locked.")
