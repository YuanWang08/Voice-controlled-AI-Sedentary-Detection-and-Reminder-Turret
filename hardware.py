import time
import threading
import os
from adafruit_servokit import ServoKit
import config

# 嘗試匯入 pygame 用於音效播放
try:
    import pygame
    pygame.mixer.init()
    HAS_AUDIO = True
except ImportError:
    print("⚠️ 未安裝 pygame，音效功能將停用")
    HAS_AUDIO = False

class SentryHardware:
    def __init__(self, state):
        self.state = state
        self.pan_angle = config.PAN_CENTER
        self.tilt_angle = config.TILT_LEVEL
        self.kit = None
        self.fire_sound = None
        
        # 初始化音效
        if HAS_AUDIO and os.path.exists(config.FIRE_SOUND_PATH):
            try:
                self.fire_sound = pygame.mixer.Sound(config.FIRE_SOUND_PATH)
                print(f"✅ 音效載入成功: {config.FIRE_SOUND_PATH}")
            except Exception as e:
                print(f"❌ 音效載入失敗: {e}")
        
        try:
            self.kit = ServoKit(channels=16)
            self.reset_servos()
            print("✅ 馬達板: 連線成功")
        except:
            print("⚠️ 馬達板未連接 (模擬模式)")

    def reset_servos(self):
        if self.kit:
            self.kit.servo[config.PAN_CH].angle = self.pan_angle
            self.kit.servo[config.TILT_CH].angle = self.tilt_angle
            self.kit.servo[config.GUN_CH].angle = config.GUN_SAFE

    def fire_gun(self):
        if self.kit:
            print("🔥🔥🔥 FIRE! 🔥🔥🔥")
            
            # 播放音效 (非阻塞)
            if self.fire_sound:
                self.fire_sound.play()
                
            self.kit.servo[config.GUN_CH].angle = config.GUN_FIRE
            time.sleep(0.3)
            self.kit.servo[config.GUN_CH].angle = config.GUN_SAFE

    def manual_move(self, pan_delta, tilt_delta):
        self.pan_angle += pan_delta
        self.tilt_angle += tilt_delta
        self._constrain_and_move()

    def set_angles(self, pan, tilt):
        if pan is not None: self.pan_angle = pan
        if tilt is not None: self.tilt_angle = tilt
        self._constrain_and_move()

    def update_servos(self, cx, cy):
        if not self.kit: return

        err_x = config.CX - cx
        err_y = config.CY - cy

        if abs(err_x) < config.DEADBAND: err_x = 0
        if abs(err_y) < config.DEADBAND: err_y = 0

        delta_pan = err_x * config.KP_PAN
        delta_tilt = err_y * config.KP_TILT

        # Limit speed
        delta_pan = max(min(delta_pan, config.MAX_STEP), -config.MAX_STEP)
        delta_tilt = max(min(delta_tilt, config.MAX_STEP), -config.MAX_STEP)

        self.pan_angle += delta_pan
        self.tilt_angle += delta_tilt 
        
        self._constrain_and_move()

        # Auto fire logic
        if self.state.auto_fire_enabled and abs(err_x) < (config.DEADBAND - 10) and abs(err_y) < (config.DEADBAND - 10):
            print("🎯 鎖定確認！執行自動開火！")
            self.fire_gun()
            self.state.auto_fire_enabled = False

    def _constrain_and_move(self):
        self.pan_angle = max(config.PAN_MIN, min(config.PAN_MAX, self.pan_angle))
        self.tilt_angle = max(config.TILT_MIN, min(config.TILT_MAX, self.tilt_angle))
        
        if self.kit:
            self.kit.servo[config.PAN_CH].angle = self.pan_angle
            self.kit.servo[config.TILT_CH].angle = self.tilt_angle
