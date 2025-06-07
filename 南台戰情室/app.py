from flask import Flask, jsonify, request, render_template_string
from flask_socketio import SocketIO, emit
import threading
import time
import random
import json
from datetime import datetime
import logging
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MotionControlSystem:
    def __init__(self):
        self.ethercat_status = {
            'card_no': 1,
            'slave_num': 8,
            'initial_status': '就緒',
            'connection_status': True
        }
        
        self.axis_data = {
            'x_axis': {
                'command_pos': 1250.5,
                'feedback_pos': 1250.2,
                'speed': 85.3,
                'status': 'moving',
                'enabled': True
            },
            'y_axis': {
                'command_pos': 890.1,
                'feedback_pos': 890.1,
                'speed': 0.0,
                'status': 'ready',
                'enabled': True
            },
            'z_axis': {
                'command_pos': 156.8,
                'feedback_pos': 156.8,
                'speed': 0.0,
                'status': 'ready',
                'enabled': True
            }
        }
        
        self.plc_status = {
            'z_son': True,
            'z_emg': False,
            'z_dog': False,
            'z_done': True,
            'y_son': True,
            'y_emg': False,
            'x_son': True,
            'x_emg': False
        }
        
        self.system_stats = {
            'total_operations': 1247,
            'success_rate': 98.7,
            'avg_cycle_time': 23.5,
            'uptime_hours': 72.3,
            'temperature': 24,
            'pressure': 1.2,
            'cpu_usage': 15,
            'memory_usage': 892
        }
        
        self.emergency_stop_active = False
        self.current_camera = 1
        
    def update_simulation_data(self):
        """模擬數據更新"""
        if not self.emergency_stop_active:
            # 更新X軸數據
            self.axis_data['x_axis']['command_pos'] = round(random.uniform(0, 2000), 1)
            self.axis_data['x_axis']['feedback_pos'] = round(
                self.axis_data['x_axis']['command_pos'] + random.uniform(-2, 2), 1
            )
            self.axis_data['x_axis']['speed'] = round(random.uniform(0, 150), 1)
            
            # 更新Y軸數據
            self.axis_data['y_axis']['command_pos'] = round(random.uniform(0, 1500), 1)
            self.axis_data['y_axis']['feedback_pos'] = round(
                self.axis_data['y_axis']['command_pos'] + random.uniform(-1.5, 1.5), 1
            )
            self.axis_data['y_axis']['speed'] = round(random.uniform(0, 120), 1)
            
            # 更新Z軸數據
            self.axis_data['z_axis']['command_pos'] = round(random.uniform(0, 300), 1)
            self.axis_data['z_axis']['feedback_pos'] = round(
                self.axis_data['z_axis']['command_pos'] + random.uniform(-0.8, 0.8), 1
            )
            self.axis_data['z_axis']['speed'] = round(random.uniform(0, 80), 1)
            
            # 更新統計數據
            self.system_stats['total_operations'] += random.randint(0, 3)
            self.system_stats['success_rate'] = round(random.uniform(98, 100), 1)
            self.system_stats['avg_cycle_time'] = round(random.uniform(20, 30), 1)
            self.system_stats['temperature'] = round(random.uniform(20, 30))
            self.system_stats['pressure'] = round(random.uniform(1.0, 1.5), 1)
            self.system_stats['cpu_usage'] = round(random.uniform(10, 30))
            
    def execute_emergency_stop(self):
        """執行緊急停止"""
        self.emergency_stop_active = True
        for axis in self.axis_data.values():
            axis['speed'] = 0.0
            axis['status'] = 'emergency_stop'
        logger.warning("緊急停止已啟動！")
        
    def reset_emergency_stop(self):
        """重置緊急停止"""
        self.emergency_stop_active = False
        for axis in self.axis_data.values():
            axis['status'] = 'ready'
        logger.info("緊急停止已重置")

# 創建系統實例
motion_system = MotionControlSystem()

@app.route('/')
def index():
    """主頁面"""
    try:
        # 讀取HTML文件
        with open('control_room1.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return """
        <h1>找不到 control_room.html 文件</h1>
        <p>請確保 control_room.html 文件在同一目錄下</p>
        <p>當前目錄: {}</p>
        <p>文件列表: {}</p>
        """.format(os.getcwd(), os.listdir('.'))

@app.route('/api/status', methods=['GET'])
def get_system_status():
    """獲取系統狀態"""
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'ethercat': motion_system.ethercat_status,
        'axes': motion_system.axis_data,
        'plc': motion_system.plc_status,
        'stats': motion_system.system_stats,
        'emergency_stop': motion_system.emergency_stop_active,
        'current_camera': motion_system.current_camera
    })

@app.route('/api/emergency_stop', methods=['POST'])
def emergency_stop():
    """緊急停止API"""
    motion_system.execute_emergency_stop()
    socketio.emit('emergency_stop', {'status': True})
    return jsonify({'status': 'success', 'message': '緊急停止已執行'})

@app.route('/api/reset_emergency', methods=['POST'])
def reset_emergency():
    """重置緊急停止"""
    motion_system.reset_emergency_stop()
    socketio.emit('emergency_reset', {'status': False})
    return jsonify({'status': 'success', 'message': '緊急停止已重置'})

@app.route('/api/camera/switch/<int:camera_id>', methods=['POST'])
def switch_camera(camera_id):
    """切換相機"""
    if 1 <= camera_id <= 4:
        motion_system.current_camera = camera_id
        socketio.emit('camera_switched', {'camera_id': camera_id})
        return jsonify({'status': 'success', 'camera_id': camera_id})
    return jsonify({'status': 'error', 'message': '無效的相機ID'})

@app.route('/api/axis/<axis_name>/move', methods=['POST'])
def move_axis(axis_name):
    """軸移動控制"""
    data = request.get_json()
    position = data.get('position')
    speed = data.get('speed', 100)
    
    if axis_name in motion_system.axis_data and not motion_system.emergency_stop_active:
        motion_system.axis_data[axis_name]['command_pos'] = position
        motion_system.axis_data[axis_name]['speed'] = speed
        motion_system.axis_data[axis_name]['status'] = 'moving'
        
        socketio.emit('axis_moving', {
            'axis': axis_name,
            'position': position,
            'speed': speed
        })
        
        return jsonify({'status': 'success', 'message': f'{axis_name}軸開始移動'})
    
    return jsonify({'status': 'error', 'message': '無法執行移動指令'})

@app.route('/api/plc/write', methods=['POST'])
def write_plc():
    """PLC寫入控制"""
    data = request.get_json()
    register = data.get('register')
    value = data.get('value')
    
    if register in motion_system.plc_status:
        motion_system.plc_status[register] = value
        socketio.emit('plc_updated', {'register': register, 'value': value})
        return jsonify({'status': 'success', 'message': f'PLC {register} 已更新'})
    
    return jsonify({'status': 'error', 'message': '無效的PLC暫存器'})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """獲取系統日誌"""
    # 模擬日誌數據
    logs = []
    log_types = ['info', 'warning', 'error']
    messages = [
        'X軸到達目標位置',
        '開始執行移動指令',
        '氣壓值略低，請檢查',
        '系統自檢完成',
        '位置校正完成',
        '感測器讀取完成'
    ]
    
    for i in range(20):
        logs.append({
            'timestamp': (datetime.now()).isoformat(),
            'level': random.choice(log_types),
            'message': random.choice(messages)
        })
    
    return jsonify({'logs': logs})

# WebSocket事件處理
@socketio.on('connect')
def handle_connect():
    """客戶端連接"""
    logger.info('客戶端已連接')
    emit('connected', {'data': '連接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    """客戶端斷線"""
    logger.info('客戶端已斷線')

@socketio.on('request_data')
def handle_data_request():
    """處理數據請求"""
    emit('system_data', {
        'timestamp': datetime.now().isoformat(),
        'ethercat': motion_system.ethercat_status,
        'axes': motion_system.axis_data,
        'plc': motion_system.plc_status,
        'stats': motion_system.system_stats
    })

def background_data_update():
    """背景數據更新線程"""
    while True:
        try:
            motion_system.update_simulation_data()
            
            # 透過WebSocket廣播更新的數據
            socketio.emit('data_update', {
                'timestamp': datetime.now().isoformat(),
                'axes': motion_system.axis_data,
                'stats': motion_system.system_stats,
                'plc': motion_system.plc_status
            })
            
            time.sleep(2)  # 每2秒更新一次
        except Exception as e:
            logger.error(f"數據更新錯誤: {e}")
            time.sleep(5)

def background_log_generator():
    """背景日誌生成線程"""
    messages = [
        '位置校正完成',
        '執行週期性檢查',
        '數據傳輸正常',
        '感測器讀取完成',
        '馬達溫度正常'
    ]
    
    while True:
        try:
            message = random.choice(messages)
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': 'info',
                'message': message
            }
            
            socketio.emit('new_log', log_entry)
            time.sleep(5)  # 每5秒生成一條日誌
        except Exception as e:
            logger.error(f"日誌生成錯誤: {e}")
            time.sleep(10)

# 錯誤處理
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'API端點不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '內部服務器錯誤'}), 500

if __name__ == '__main__':
    try:
        # 啟動背景線程
        data_thread = threading.Thread(target=background_data_update)
        data_thread.daemon = True
        data_thread.start()
        
        log_thread = threading.Thread(target=background_log_generator)
        log_thread.daemon = True
        log_thread.start()
        
        print("=" * 50)
        print("光學檢測自動化產線戰情室系統")
        print("=" * 50)
        print("🚀 服務器啟動中...")
        print("📡 WebSocket 支援已啟用")
        print("🌐 訪問地址: http://localhost:5000")
        print("🔧 API文檔: http://localhost:5000/api/status")
        print("=" * 50)
        
        # 啟動Flask應用
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
        
    except Exception as e:
        print(f"❌ 服務器啟動失敗: {e}")
        print("💡 請檢查:")
        print("   1. 端口5000是否被占用")
        print("   2. 是否安裝了所需依賴")
        print("   3. 防火牆設置")