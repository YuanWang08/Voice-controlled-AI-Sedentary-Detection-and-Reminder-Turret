from flask import Flask, Response, render_template_string, request
import threading
import cv2
import config

def create_app(state, hardware, audio):
    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SENTRY COMMAND CENTER</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #0a0a0a;
            color: #00ff00;
            font-family: 'Courier New', Courier, monospace;
            overflow: hidden;
            display: flex;
            height: 100vh;
        }
        
        /* Left Panel: Video Stream (70%) */
        #video-panel {
            flex: 7;
            border-right: 2px solid #333;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #000;
            position: relative;
        }
        
        #video-stream {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        .overlay-text {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.5);
            padding: 5px 10px;
            border: 1px solid #00ff00;
            font-size: 18px;
            text-shadow: 0 0 5px #00ff00;
            z-index: 10;
        }

        /* --- CYBERPUNK BUTTONS --- */
        .btn {
            background: #000;
            color: #00ff00;
            border: 1px solid #00ff00;
            padding: 10px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 14px;
            cursor: pointer;
            text-transform: uppercase;
            transition: all 0.2s;
            box-shadow: 0 0 5px #004400;
            text-shadow: 0 0 2px #00ff00;
        }

        .btn:hover {
            background: #00ff00;
            color: #000;
            box-shadow: 0 0 15px #00ff00;
            text-shadow: none;
        }

        .btn:active {
            transform: scale(0.95);
        }

        .btn-danger {
            border-color: #ff0000;
            color: #ff0000;
            box-shadow: 0 0 5px #550000;
            text-shadow: 0 0 2px #ff0000;
        }

        .btn-danger:hover {
            background: #ff0000;
            color: #000;
            box-shadow: 0 0 20px #ff0000;
        }

        .mode-btn {
            font-weight: bold;
            letter-spacing: 1px;
        }

        .fire-btn {
            background: #200;
            border-color: #ff0000;
            color: #ff0000;
            box-shadow: 0 0 5px #550000;
            font-size: 18px;
            font-weight: bold;
            width: 100%;
            margin-top: 10px;
            margin-bottom: 10px;
            animation: pulse-red 2s infinite;
        }

        .fire-btn:hover {
            background: #ff0000;
            color: #000;
            box-shadow: 0 0 20px #ff0000;
            animation: none;
        }

        @keyframes pulse-red {
            0% { box-shadow: 0 0 5px #550000; }
            50% { box-shadow: 0 0 15px #ff0000; }
            100% { box-shadow: 0 0 5px #550000; }
        }

        .d-pad {
            display: grid;
            grid-template-columns: repeat(3, 50px);
            grid-template-rows: repeat(2, 50px);
            gap: 5px;
            justify-content: center;
            margin-bottom: 20px;
        }

        .btn-up { grid-column: 2; grid-row: 1; }
        .btn-left { grid-column: 1; grid-row: 2; }
        .btn-down { grid-column: 2; grid-row: 2; }
        .btn-right { grid-column: 3; grid-row: 2; }


        /* Right Panel: Controls (30%) */
        #control-panel {
            flex: 3;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            background: #111;
        }

        h1 {
            text-align: center;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 24px;
            text-shadow: 0 0 10px #00ff00;
        }

        .status-box {
            border: 1px solid #333;
            padding: 10px;
            background: #000;
        }

        .slider-container {
            display: none; /* Hidden by default */
            flex-direction: column;
            gap: 15px;
            width: 100%;
        }

        .slider-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .slider-label {
            font-size: 14px;
            display: flex;
            justify-content: space-between;
        }

        input[type=range] {
            -webkit-appearance: none;
            width: 100%;
            background: transparent;
        }

        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 20px;
            width: 20px;
            background: #00ff00;
            cursor: pointer;
            margin-top: -8px;
            border: 1px solid #000;
        }

        input[type=range]::-webkit-slider-runnable-track {
            width: 100%;
            height: 4px;
            cursor: pointer;
            background: #333;
            border: 1px solid #00ff00;
        }
        .log-container {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            border: 1px solid #333;
            background: #000;
            height: 150px;
        }

        .tab-header {
            display: flex;
            border-bottom: 1px solid #333;
        }

        .tab-btn {
            flex: 1;
            background: #111;
            color: #888;
            border: none;
            padding: 5px;
            cursor: pointer;
            font-family: inherit;
            font-size: 12px;
        }

        .tab-btn.active {
            background: #000;
            color: #00ff00;
            font-weight: bold;
        }

        .tab-content {
            flex-grow: 1;
            padding: 5px;
            font-size: 12px;
            color: #888;
            overflow-y: auto;
            display: none;
        }

        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>

    <!-- Left Panel -->
    <div id="video-panel">
        <img id="video-stream" src="/video_feed">
        <div class="overlay-text">SYSTEM ONLINE</div>
    </div>

    <!-- Right Panel -->
    <div id="control-panel">
        <h1>HYBRID SENTRY</h1>
        
        <div class="status-box">
            <div>STATUS: <span id="status-text" style="color: #00ff00">ACTIVE</span></div>
            <div>MODE: <span id="mode-text">MANUAL</span></div>
        </div>

        <button class="btn mode-btn" onclick="toggleControlMode()">SWITCH TO SLIDERS</button>

        <div class="control-group" id="dpad-controls">
            <div class="d-pad">
                <button class="btn btn-up" id="btn-w" onmousedown="startMove('up')" onmouseup="stopMove()" onmouseleave="stopMove()">W</button>
                <button class="btn btn-left" id="btn-a" onmousedown="startMove('left')" onmouseup="stopMove()" onmouseleave="stopMove()">A</button>
                <button class="btn btn-down" id="btn-s" onmousedown="startMove('down')" onmouseup="stopMove()" onmouseleave="stopMove()">S</button>
                <button class="btn btn-right" id="btn-d" onmousedown="startMove('right')" onmouseup="stopMove()" onmouseleave="stopMove()">D</button>
            </div>
        </div>

        <div class="slider-container" id="slider-controls">
            <div class="slider-group">
                <div class="slider-label"><span>PAN (Horizontal)</span><span id="pan-val">70</span></div>
                <input type="range" min="0" max="140" value="70" id="pan-slider" oninput="updateSlider('pan', this.value)">
            </div>
            <div class="slider-group">
                <div class="slider-label"><span>TILT (Vertical)</span><span id="tilt-val">76</span></div>
                <input type="range" min="56" max="180" value="76" id="tilt-slider" oninput="updateSlider('tilt', this.value)">
            </div>
        </div>

        <button class="btn fire-btn" id="btn-space" onclick="fire()">FIRE (SPACE)</button>

        <div style="margin-top: 20px; display: flex; flex-wrap: wrap; gap: 10px;">
            <button class="btn mode-btn" style="flex: 1;" onclick="setMode('IDLE')">STOP / MANUAL</button>
            <button class="btn mode-btn" style="flex: 1;" onclick="setMode('CORAL_TRACK')">AUTO TRACK</button>
            <button class="btn mode-btn btn-danger" style="flex: 1;" onclick="setMode('SENTRY_MODE')">SENTRY MODE</button>
        </div>

        <div class="log-container">
            <div class="tab-header">
                <button class="tab-btn active" onclick="switchTab('sys')">SYSTEM LOG</button>
                <button class="tab-btn" onclick="switchTab('voice')">VOICE COMMS</button>
            </div>
            <div id="tab-sys" class="tab-content active">
                > System initialized...<br>
            </div>
            <div id="tab-voice" class="tab-content">
                > Listening...<br>
            </div>
        </div>
    </div>

    <script>
        let moveInterval = null;
        let isSliderMode = false;

        // Voice Log Polling
        setInterval(() => {
            fetch('/voice_log').then(r => r.json()).then(data => {
                const box = document.getElementById('tab-voice');
                box.innerHTML = data.map(l => `> ${l}`).join('<br>');
                box.scrollTop = box.scrollHeight;
            }).catch(() => {});
        }, 1000);

        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            document.querySelector(`button[onclick="switchTab('${tab}')"]`).classList.add('active');
            document.getElementById(`tab-${tab}`).classList.add('active');
        }

        function log(msg) {
            const box = document.getElementById('tab-sys');
            box.innerHTML += `> ${msg}<br>`;
            box.scrollTop = box.scrollHeight;
        }

        function sendCmd(endpoint) {
            fetch(endpoint).catch(e => console.error(e));
        }

        function toggleControlMode() {
            isSliderMode = !isSliderMode;
            const dpad = document.getElementById('dpad-controls');
            const sliders = document.getElementById('slider-controls');
            const btn = document.querySelector('button[onclick="toggleControlMode()"]');

            if (isSliderMode) {
                dpad.style.display = 'none';
                sliders.style.display = 'flex';
                btn.innerText = "SWITCH TO KEYBOARD";
            } else {
                dpad.style.display = 'flex';
                sliders.style.display = 'none';
                btn.innerText = "SWITCH TO SLIDERS";
            }
        }

        function updateSlider(axis, val) {
            document.getElementById(axis + '-val').innerText = val;
            // Debounce could be added here if needed, but for local network it's usually fine
            sendCmd(`/cmd?mode=set_angle&axis=${axis}&val=${val}`);
        }

        function setMode(mode) {
            sendCmd('/cmd?mode=mode&val=' + mode);
            document.getElementById('mode-text').innerText = mode;
            log(`Mode set to ${mode}`);
        }

        function fire() {
            sendCmd('/cmd?mode=fire&val=1');
            log('FIRING!');
            const btn = document.getElementById('btn-space');
            btn.classList.add('active');
            setTimeout(() => btn.classList.remove('active'), 200);
        }

        function move(dir) {
            sendCmd('/cmd?mode=move&val=' + dir);
        }

        function startMove(dir) {
            if (moveInterval) clearInterval(moveInterval);
            move(dir); // Immediate move
            moveInterval = setInterval(() => move(dir), 100); // Continuous move
        }

        function stopMove() {
            if (moveInterval) {
                clearInterval(moveInterval);
                moveInterval = null;
            }
        }

        // Keyboard Control
        document.addEventListener('keydown', (e) => {
            if (isSliderMode) return; // Disable WASD in slider mode
            if (e.repeat) return;
            const key = e.key.toLowerCase();
            
            if (key === 'w') {
                document.getElementById('btn-w').classList.add('active');
                startMove('up');
            } else if (key === 'a') {
                document.getElementById('btn-a').classList.add('active');
                startMove('left');
            } else if (key === 's') {
                document.getElementById('btn-s').classList.add('active');
                startMove('down');
            } else if (key === 'd') {
                document.getElementById('btn-d').classList.add('active');
                startMove('right');
            } else if (key === ' ') {
                fire();
            }
        });

        document.addEventListener('keyup', (e) => {
            if (isSliderMode) return;
            const key = e.key.toLowerCase();
            if (['w', 'a', 's', 'd'].includes(key)) {
                document.getElementById('btn-' + key).classList.remove('active');
                stopMove();
            }
        });
    </script>
</body>
</html>
        """)

    @app.route('/video_feed')
    def video_feed():
        def gen():
            import time
            while True:
                frame = None
                with state.lock:
                    if state.output_frame is not None:
                        frame = state.output_frame.copy()
                
                if frame is not None:
                    _, enc = cv2.imencode(".jpg", frame)
                    yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(enc) + b'\r\n')
                
                time.sleep(0.05) # Limit FPS to ~20 to prevent network flooding
        return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route('/cmd')
    def cmd():
        mode = request.args.get('mode')
        val = request.args.get('val')
        
        if mode == 'fire': 
            threading.Thread(target=hardware.fire_gun).start()
        
        elif mode == 'mode':
            state.current_mode = val
            audio.mode_switched(val) # 播放模式切換語音
            if val == 'CORAL_TRACK': 
                state.target_config = {"id": 0, "name": "person"}
        
        elif mode == 'set_angle':
            state.current_mode = "IDLE"
            axis = request.args.get('axis')
            try:
                angle = float(val)
                if axis == 'pan':
                    hardware.set_angles(pan=angle, tilt=None)
                elif axis == 'tilt':
                    hardware.set_angles(pan=None, tilt=angle)
            except ValueError:
                pass

        elif mode == 'move':
            # Manual control overrides current mode to IDLE
            state.current_mode = "IDLE"
            step = 5 # Small step for smooth continuous movement
            pan_d, tilt_d = 0, 0
            

            if val == 'left': pan_d = step
            elif val == 'right': pan_d = -step
            elif val == 'up': tilt_d = step
            elif val == 'down': tilt_d = -step
            
            hardware.manual_move(pan_d, tilt_d)
            
        return "OK"

    @app.route('/voice_log')
    def voice_log():
        with state.lock:
            # Flask requires a Response object, dict, or string, not a raw list
            # jsonify is the standard way to return JSON lists
            from flask import jsonify
            return jsonify(list(state.voice_logs))
    
    return app
