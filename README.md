# IOT-Project -- 聲控驅動 AI 久坐偵測提醒砲台

[YouTube 介紹影片連結](https://youtu.be/vOPqylx6xjQ)

[![Watch the video](https://img.youtube.com/vi/vOPqylx6xjQ/0.jpg)](https://www.youtube.com/watch?v=vOPqylx6xjQ)

## 目錄

- About Author
- 專題簡介與理想
  - 主要功能簡介
- 所需設備
  - 必要硬體
  - 發射系統
  - 其他
- 專案初始化 & 實作歷程記錄
  - Raspberry Pi 4 System Configurations
  - 樹莓派系統初始化
    - 說明
    - 系統設定 (用網路線連接電腦 SSH)
    - Wifi Settings
    - Google Coral 驅動安裝
    - Python 套件安裝
    - AI 模型下載 (Coral + vosk)
    - 硬體設備檢查
  - 硬體串接
  - 程式執行方式
- 程式架構說明
- AI 模型說明
- 網頁說明
- 環境變數說明
- 可以再改進的部分

## About Author

- 學號：112403543
- 修課時年級：資管三
- 姓名：王暐元

## 專題簡介與理想

這是一個基於 Raspberry Pi 4 的 AI 智慧哨兵系統，結合了邊緣運算 (Coral TPU) 與雲端 AI (Google Gemini)，具備物體追蹤、姿態辨識、語音控制與遠端網頁監控功能。會透過鏡頭掃視房間，辨識出人體後會框起來，然後在框的旁邊有個計時器，計時該人多久沒有移動(離開座位)，當時間超過 2 分鐘，會先叫一聲表示提醒，超過三分鐘時就會瞄準那個人發射橡皮筋子彈。

### 主要功能簡介

- **雙重 AI 核心**：
  - **Edge AI (Coral TPU)**：使用 MobileNet SSD v2 進行即時物體偵測 (60+ FPS)，以及 MoveNet 進行人體姿態估計。
  - **Cloud AI (Gemini 2.5 Flash)**：處理複雜的語音意圖分析與模糊視覺搜尋 (如：「尋找綠色的杯子」)。
- **多種運作模式**：
  - **手動模式 (Manual)**：透過網頁介面控制雲台與開火。
  - **自動追蹤 (Auto Track)**：自動鎖定並追蹤畫面中的特定物體 (預設為人)。
  - **哨兵模式 (Sentry Mode)**：偵測到人體靜止超過設定時間即自動開火。
  - **Gemini 輔助**：透過自然語言指令鎖定特定物品與操作設備。
- **投降機制**：透過 MoveNet 偵測「舉手投降」動作，自動停止攻擊。
- **語音控制**：支援離線語音喚醒與指令識別 (Vosk)。
- **Cyberpunk 風格介面**：提供即時影像串流與戰術控制面板。

## 所需設備

### 必要硬體

- Raspberry Pi 4 Computer (Model B 4GB RAM) \* 1
- Coral USB Accelerator (used 2, but at least 1 is ok)
- Raspberry Pi Camera & 排線 \* 1
- MG996R \* 2 + 鋁支架
- PCA9685 \* 1
- 4 節 3 號電池盒(6V) & 一些有電的電池
- USB 麥克風 \* 1

### 發射系統

- SG90 \* 1
- 自製槍管裝置 (竹筷、束帶、保麗龍膠、紙箱)
- 橡皮筋

> (直接買一把玩具槍可能實際一點，拼拼貼貼的時間去打工都能買十幾把了)

### 其他(拿掉也能運作，但很麻煩)

- 木板 (整理硬體與固定支架方便)
- 麵包板 (方便接線)
- 喇叭 (就沒有聲音而已)

## 執行圖片

![執行圖片1](/img/圖片1.png)
![執行圖片1](/img/圖片2.png)
![執行圖片1](/img/圖片3.png)
![執行圖片1](/img/圖片4.png)

## 專案初始化 & 實作歷程記錄

### Raspberry Pi 4 System Configurations

- Storage: SD Card 32 GB
- OS: Raspberry Pi OS (Legacy, 64-bit) (A port of Debian Bullseye)
  - 使用 64-bit 版本的 OS 可以增加效能，並且可以使用 VSCode 的 SSH Extension 進行操作，可以完全不用接螢幕就可以初始化設置樹莓派
- 映像連結：https://downloads.raspberrypi.org/raspios_arm64/images/raspios_arm64-2023-05-03/2023-05-03-raspios-bullseye-arm64.img.xz
- Python: 3.9 (should be built-in with OS)

> 不是用這個版本的作業系統高機率掛掉無法複現，不是 Debian Bullseye 系統相容問題會炸開

### 樹莓派系統初始化

#### 說明

絕對不行用任何 Python 版本大於 3.9 的作業系統，Coral 與 OpenCV 在操作過程中會不斷版本衝突崩潰，修好一個會壞另一個。(已經修了很久，做越多掛越多) 所以使用最新還是 3.9 版本的系統 (Bullseye)，且使用 64-bit 的後續問題也會比較少可以使用 Visual Studio Code 的 SSH Extension 很方便。

新版的 Raspberry Pi Imager V2.0 燒錄這個映像檔無法自定義配置，所以只能用來格式化成 FAT32，燒錄使用還沒更新前的 V1.9 才可以預先設定。(V1.9 在部分 Windows 系統無法順利格式化，要先用 V2.0 格式化完後再換回 V1.9)(我的電腦是這樣)。

#### 系統設定 (用網路線連接電腦 SSH)

```
ssh <使用者名稱>@<主機名稱>.local
```

```
# 更新系統
sudo apt update && sudo apt upgrade -y

sudo raspi-config

# 開啟硬體設定
# 開啟 I2C (馬達)： 3 Interface Options -> I5 I2C -> <Yes> -> <Ok>
# 開啟 Legacy Camera： 3 Interface Options -> I1 Legacy Camera -> <Yes> -> <Ok>
# 開啟後相機就能像 Webcam 直接被 OpenCV 讀取不用任何特殊設定
```

---

#### Wifi Settings (燒錄的設定不知道為什麼沒用)

```bash
sudo raspi-config

# 設定 Wi-Fi 國家 (沒設 5GHz 會被鎖住)
# 5 Localisation Options -> L4 WLAN Country -> TW Taiwan
# 1 System Options -> S1 Wireless LAN -> 輸入 SSID (Wi-Fi 名稱) & 密碼

# 重啟生效
sudo reboot
```

---

#### Google Coral 驅動安裝

1. 加入 Google 軟體源

```bash
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
```

2. 加入金鑰

```bash
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
```

3. 更新並安裝驅動 (不需額外安裝 tflite-runtime)

```bash
sudo apt update
sudo apt install libedgetpu1-std python3-pycoral -y
```

---

#### Python 套件安裝

```python
pip3 install opencv-python flask adafruit-circuitpython-servokit google-generativeai vosk sounddevice
```

- `opencv-python`：影像辨識
- `flask`：網頁伺服器
- `adafruit-circuitpython-servokit`：馬達控制
- `google-generativeai`：接外部 Gemini API
- `vosk`：將語音傳成文字的模型操作
- `sounddevice`：處理音訊

安裝完後需要手動降 Numpy 版本：

```python
pip3 uninstall numpy -y
pip3 install "numpy<2"
```

或者直接從 `requirements.txt` 安裝：

```python
pip install -r requirements.txt
```

---

#### AI 模型下載 (Coral + vosk)

```bash
wget https://github.com/google-coral/test_data/raw/master/ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite
wget https://github.com/google-coral/test_data/raw/master/coco_labels.txt
wget https://github.com/google-coral/test_data/raw/master/movenet_single_pose_lightning_ptq_edgetpu.tflite -O
wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
unzip vosk-model-small-cn-0.22.zip
```

---

#### 硬體設備檢查 (Coral、麥克風、相機)

```bash
# 列出樹莓派看得到的所有 USB 裝置
# Global Unichip Corp. (Coral 還沒運作時的名稱)
# Google Inc. (Coral 運作時的名稱)
lsusb

# 檢查馬達板 (I2C) 看到 40
sudo i2cdetect -y 1

# 檢查相機
# 預期結果： supported=1 detected=1
vcgencmd get_camera

# 檢查 USB 麥克風
sudo alsactl store
arecord -l
```

### 硬體串接

於影片中介紹(3:30)

[YouTube 介紹影片連結](https://youtu.be/vOPqylx6xjQ)

[![Demo圖](/img/demo.jpg)](https://www.youtube.com/watch?v=vOPqylx6xjQ)

### 程式執行方式

如果軟體環境與硬體都與上面一樣，只要執行 `main.py` 就會在 `:5000` 執行 Flask 網頁程式：

```bash
python3 main.py
```

## 程式架構說明

本專案採用模組化設計，各功能獨立於不同檔案中，透過 `SharedState` 進行狀態同步。

**核心程式碼：**

- **`main.py` (主程式入口)**

  - **功能**：專案入口。負責初始化所有子系統 (硬體、視覺、語音、音效、網頁)，並啟動多執行緒 (Threading) 讓各模組同時運作。
  - **職責**：啟動 Vision Loop、Voice Loop 與 Web Server。

- **`hardware.py` (硬體控制)**

  - **功能**：負責與實體硬體溝通。
  - **職責**：
    - 控制 Adafruit PCA9685 馬達板 (Pan/Tilt 雲台與板機)。
    - 實作 PID 控制演算法 (`update_servos`)，將視覺座標轉換為馬達角度。
    - 控制開火動作 (`fire_gun`) 並同步播放音效 (透過 Pygame)。

- **`ai_vision.py` (AI 視覺核心)**

  - **功能**：系統的眼睛與大腦。
  - **職責**：
    - **Edge AI**：呼叫 Coral TPU 執行物件偵測 (MobileNet) 與姿態辨識 (MoveNet)。
    - **Cloud AI**：整合 Google Gemini API 進行模糊搜尋與意圖分析。
    - **邏輯判斷**：實作哨兵模式 (Sentry Mode) 的巡邏、鎖定、計時與投降判定邏輯。
    - **畫面繪製**：將辨識框、骨架與 HUD 資訊疊加在影像上。

- **`web_server.py` (網頁介面)**

  - **功能**：提供使用者操作介面 (GUI)。
  - **職責**：
    - 使用 Flask 架設網頁伺服器。
    - 提供即時影像串流 (MJPEG Stream)。
    - 接收前端指令 (WASD 控制、模式切換、參數調整) 並更新系統狀態。

- **`voice.py` (語音識別)**

  - **功能**：系統的耳朵。
  - **職責**：
    - 使用 Vosk 進行離線語音識別 (Speech-to-Text)。
    - 將識別後的文字傳送給 Gemini 進行意圖分析 (Intent Recognition)。
    - 根據分析結果切換系統模式 (如：「開啟哨兵模式」)。

- **`audio.py` (語音回饋)**

  - **功能**：系統的嘴巴。
  - **職責**：
    - 使用 `pyttsx3` 進行文字轉語音 (TTS)。
    - 維護一個獨立的語音佇列 (Queue) 與執行緒，確保語音播報不會卡住主程式。
    - 提供系統狀態回饋 (如：「System Online」、「Target Locked」)。

- **`config.py` (全域設定)**
  - **功能**：系統的參數中心。
  - **職責**：
    - 讀取 `.env` 環境變數。
    - 定義馬達腳位、PID 參數、追蹤死區 (Deadband) 等常數。
    - 定義 `SharedState` 類別，作為各執行緒間共享資料的橋樑。
- **`/model`**

  - 存放 AI 模型檔案。
  - 包含 Vosk 的語音識別模型 (如 `cn_model`)。

- **`/media`**
  - 存放多媒體資源。
  - 包含開火音效檔 (`shotsound.wav`)。

## AI 模型說明

- MoveNet：用來主要標記影像中的物體，在網頁中用綠色的框標示
- PoseNet：：特別拿來標記人體，可以在環境變數中決定要不要開啟(ENABLE_MOVENET)與掃描率，在網頁中會使用黃色的節點標示(MOVENET_SKIP_FRAMES，數字越小吃越多效能，建議不能超過 10)，開啟後效能會吃很多網頁可能會跑不動。開啟後可以辨識雙手舉高的人，如果發現有雙手舉高的人會出現提示文字並且就不會再開火(開火會被禁用)。
- Vosk-small-cn：輕量的中文語音轉文字模型(效果很差，但堪用，Gemini 有機率可以讀得懂)

## 網頁說明

- 可以使用 WASD 或是拉桿來手動操作機器
- 可以手動按下發射按鈕
- "Auto Track"模式會追縱畫面中最大的人
- 哨兵模式會偵測空間中靜止不動的人，頭上會顯示一個計時器(紅色的數字)，達到特定時間後會發射，(時間可以在環境變數中的 SENTRY_TIMEOUT 設置)
- 使用語音輸入非預設的指令會執行 Gemini，然後鎖定 Gemini 回傳之座標的物件
- 右下方可以看到系統執行紀錄與語音辨識的紀錄

## 環境變數說明

- GEMINI_API_KEY="test_api_key"，語音操作必備
- GEMINI_MODEL_NAME="gemini-2.5-flash"，建議用最簡單回復最快速的模型就可以了
- ENABLE_MOVENET=true，決定使否啟用 Movenet 模型
- MOVENET_SKIP_FRAMES=5，決定 Movenet 的採樣頻率(數字越小，採樣越快，越吃效能)
- SURRENDER_TEXT="Absolute Cinema!"，設置雙手舉高時顯示的文字
- SENTRY_TIMEOUT=5，設置久坐偵測的判定時間
- SENTRY_MOVE_THRESHOLD=5.0，久坐判定的品感度，數字越大容忍程度越大
- FIRE_SOUND_PATH="/home/user/Desktop/media/shotsound.wav"，音效檔案路徑

## 可以再改進的部分

- 模型在追蹤物體時有機率追一追跑掉，或是突然看天花板然後就再也下不來了
- 應該再多做一個開啟麥克風收音的按鈕(現在是無論何時都再收音，只要有人講話程式就會被插斷)
