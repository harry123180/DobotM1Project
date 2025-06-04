# -*- coding: utf-8 -*-
"""
整合式主應用程式 - 集成機器人控制、相機控制和ModBus功能
適用於工業自動化環境的統一控制平台
"""

from flask import Flask, render_template, Response, request, jsonify, session
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
import queue
import ast
import importlib.util
import sys
import serial.tools.list_ports
import logging
from datetime import datetime
import uuid
import cv2
import numpy as np
import base64
import io
from ctypes import *

# 導入機器人控制相關模組
try:
    from dobot_api import DobotApiDashboard, DobotApiMove, DobotApi, MyType
    ROBOT_AVAILABLE = True
except ImportError:
    print("機器人控制模組未找到，機器人功能將不可用")
    DobotApiDashboard = DobotApiMove = DobotApi = MyType = None
    ROBOT_AVAILABLE = False

# 導入ModBus相關模組
try:
    from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    from pymodbus.exceptions import ModbusException
    MODBUS_AVAILABLE = True
except ImportError:
    print("ModBus模組未找到，ModBus功能將不可用")
    MODBUS_AVAILABLE = False

# 導入相機控制相關模組
try:
    from Camera_API import create_camera_api, CameraMode, ImageFormat, CameraStatus, CameraParameters
    CAMERA_AVAILABLE = True
except ImportError:
    print("相機控制模組未找到，相機功能將不可用")
    CAMERA_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'integrated_control_system_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ========== ModBus管理類 ==========
class ModbusManager:
    def __init__(self):
        self.tcp_client = None
        self.rtu_client = None
        self.tcp_connected = False
        self.rtu_connected = False
        self.tcp_config = {}
        self.rtu_config = {}
        self.register_comments = {}
        self.auto_refresh = False
        self.load_comments()
        
    def load_comments(self):
        """載入暫存器註解"""
        try:
            if os.path.exists('modbus_comments.json'):
                with open('modbus_comments.json', 'r', encoding='utf-8') as f:
                    self.register_comments = json.load(f)
        except Exception as e:
            logging.error(f"載入ModBus註解失敗: {e}")
    
    def save_comments(self):
        """保存暫存器註解"""
        try:
            with open('modbus_comments.json', 'w', encoding='utf-8') as f:
                json.dump(self.register_comments, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存ModBus註解失敗: {e}")
    
    def connect_tcp(self, host, port, slave_id):
        """連接ModbusTCP"""
        try:
            self.tcp_client = ModbusTcpClient(host, port)
            if self.tcp_client.connect():
                self.tcp_connected = True
                self.tcp_config = {'host': host, 'port': port, 'slave_id': slave_id}
                logging.info(f"ModbusTCP連接成功: {host}:{port}")
                return True
            else:
                logging.error("ModbusTCP連接失敗")
                return False
        except Exception as e:
            logging.error(f"ModbusTCP連接錯誤: {e}")
            return False
    
    def connect_rtu(self, port, baudrate, bytesize, parity, stopbits, slave_id):
        """連接ModbusRTU"""
        try:
            self.rtu_client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=1
            )
            if self.rtu_client.connect():
                self.rtu_connected = True
                self.rtu_config = {
                    'port': port, 'baudrate': baudrate, 'bytesize': bytesize,
                    'parity': parity, 'stopbits': stopbits, 'slave_id': slave_id
                }
                logging.info(f"ModbusRTU連接成功: {port}")
                return True
            else:
                logging.error("ModbusRTU連接失敗")
                return False
        except Exception as e:
            logging.error(f"ModbusRTU連接錯誤: {e}")
            return False
    
    def disconnect_tcp(self):
        """中斷ModbusTCP連接"""
        if self.tcp_client:
            self.tcp_client.close()
            self.tcp_connected = False
            logging.info("ModbusTCP已中斷連接")
    
    def disconnect_rtu(self):
        """中斷ModbusRTU連接"""
        if self.rtu_client:
            self.rtu_client.close()
            self.rtu_connected = False
            logging.info("ModbusRTU已中斷連接")
    
    def read_holding_registers(self, client_type, address, count, slave_id):
        """讀取保持暫存器"""
        client = self.tcp_client if client_type == 'tcp' else self.rtu_client
        if not client:
            return None
        
        try:
            response = client.read_holding_registers(address, count, slave=slave_id)
            if not response.isError():
                return response.registers
            else:
                logging.error(f"讀取暫存器錯誤: {response}")
                return None
        except Exception as e:
            logging.error(f"讀取暫存器異常: {e}")
            return None
    
    def write_single_register(self, client_type, address, value, slave_id):
        """寫入單個暫存器"""
        client = self.tcp_client if client_type == 'tcp' else self.rtu_client
        if not client:
            return False
        
        try:
            response = client.write_register(address, value, slave=slave_id)
            if not response.isError():
                logging.info(f"寫入暫存器成功: 位址{address} = {value}")
                return True
            else:
                logging.error(f"寫入暫存器錯誤: {response}")
                return False
        except Exception as e:
            logging.error(f"寫入暫存器異常: {e}")
            return False
    
    def write_multiple_registers(self, client_type, address, values, slave_id):
        """寫入多個暫存器"""
        client = self.tcp_client if client_type == 'tcp' else self.rtu_client
        if not client:
            return False
        
        try:
            response = client.write_registers(address, values, slave=slave_id)
            if not response.isError():
                logging.info(f"批次寫入暫存器成功: 位址{address}, 數量{len(values)}")
                return True
            else:
                logging.error(f"批次寫入暫存器錯誤: {response}")
                return False
        except Exception as e:
            logging.error(f"批次寫入暫存器異常: {e}")
            return False
    
    def get_serial_ports(self):
        """取得可用的串列埠清單"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports

# ========== 機器人控制類 ==========
class DobotController:
    def __init__(self):
        self.dashboard = None
        self.move = None
        self.feed = None
        self.connected = False
        self.ip = "192.168.1.6"
        self.dashboard_port = 29999
        self.move_port = 30003
        self.feed_port = 30004
        
        # 機器人狀態
        self.robot_state = {
            'robot_mode': 0,
            'joint_positions': [0, 0, 0, 0],
            'cartesian_position': [0, 0, 0, 0],
            'joint_currents': [0, 0, 0, 0],
            'digital_inputs': [0] * 16,
            'digital_outputs': [0] * 16,
            'speed_scaling': 0,
            'error_status': 0,
            'enabled': False
        }
        
        # 點位管理
        self.waypoints = {}
        
        # 動作腳本管理
        self.action_scripts = {f'action_{i}': None for i in range(1, 6)}
        self.action_threads = {}
        
        # 指令佇列
        self.command_queue = queue.Queue()
        self.command_thread = None
        
        # 回饋執行緒
        self.feedback_thread = None
        self.feedback_running = False

    def connect(self, ip=None, dashboard_port=None, move_port=None, feed_port=None):
        """連接機器人"""
        if not ROBOT_AVAILABLE:
            return False
            
        try:
            if ip:
                self.ip = ip
            if dashboard_port:
                self.dashboard_port = dashboard_port
            if move_port:
                self.move_port = move_port
            if feed_port:
                self.feed_port = feed_port
                
            self.dashboard = DobotApiDashboard(self.ip, self.dashboard_port)
            self.move = DobotApiMove(self.ip, self.move_port)
            self.feed = DobotApi(self.ip, self.feed_port)
            
            self.connected = True
            
            # 啟動指令處理執行緒
            self.start_command_thread()
            
            # 啟動回饋執行緒
            self.start_feedback_thread()
            
            logging.info(f"機器人連接成功: {self.ip}")
            return True
        except Exception as e:
            logging.error(f"機器人連接失敗: {e}")
            return False

    def disconnect(self):
        """中斷連接"""
        try:
            self.feedback_running = False
            self.connected = False
            
            if self.dashboard:
                self.dashboard.close()
            if self.move:
                self.move.close()
            if self.feed:
                self.feed.close()
                
            # 停止所有動作執行緒
            for thread_id in list(self.action_threads.keys()):
                self.stop_action(thread_id)
                
            logging.info("機器人連接已中斷")
            return True
        except Exception as e:
            logging.error(f"中斷機器人連接失敗: {e}")
            return False

    def start_command_thread(self):
        """啟動指令處理執行緒"""
        if not self.command_thread or not self.command_thread.is_alive():
            self.command_thread = threading.Thread(target=self._command_processor)
            self.command_thread.daemon = True
            self.command_thread.start()

    def _command_processor(self):
        """指令處理器"""
        while self.connected:
            try:
                if not self.command_queue.empty():
                    command = self.command_queue.get(timeout=1)
                    self._execute_command(command)
                time.sleep(0.01)
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"指令處理錯誤: {e}")

    def _execute_command(self, command):
        """執行指令"""
        if not ROBOT_AVAILABLE:
            return
            
        try:
            cmd_type = command['type']
            params = command.get('params', {})
            
            if cmd_type == 'enable':
                self.dashboard.EnableRobot()
            elif cmd_type == 'disable':
                self.dashboard.DisableRobot()
            elif cmd_type == 'movj':
                self.move.MovJ(**params)
            elif cmd_type == 'movl':
                self.move.MovL(**params)
            elif cmd_type == 'joint_movj':
                self.move.JointMovJ(**params)
            elif cmd_type == 'jog':
                self.move.MoveJog(params.get('axis_id'))
            elif cmd_type == 'jog_stop':
                self.move.MoveJog()
            elif cmd_type == 'do':
                self.dashboard.DOExecute(params['index'], params['status'])
            elif cmd_type == 'emergency_stop':
                self.dashboard.EmergencyStop()
            elif cmd_type == 'clear_error':
                self.dashboard.ClearError()
            elif cmd_type == 'reset_robot':
                self.dashboard.ResetRobot()
            
            logging.info(f"執行指令: {cmd_type}")
            
        except Exception as e:
            logging.error(f"執行指令失敗: {e}")

    def start_feedback_thread(self):
        """啟動回饋執行緒"""
        if not ROBOT_AVAILABLE:
            return
            
        if not self.feedback_thread or not self.feedback_thread.is_alive():
            self.feedback_running = True
            self.feedback_thread = threading.Thread(target=self._feedback_processor)
            self.feedback_thread.daemon = True
            self.feedback_thread.start()

    def _feedback_processor(self):
        """回饋處理器"""
        hasRead = 0
        while self.feedback_running and self.connected:
            try:
                data = bytes()
                while hasRead < 1440:
                    temp = self.feed.socket_dobot.recv(1440 - hasRead)
                    if len(temp) > 0:
                        hasRead += len(temp)
                        data += temp
                hasRead = 0

                a = np.frombuffer(data, dtype=MyType)
                
                if hex((a['test_value'][0])) == '0x123456789abcdef':
                    # 更新機器人狀態
                    self.robot_state.update({
                        'robot_mode': int(a["robot_mode"][0]),
                        'joint_positions': [round(float(x), 4) for x in a["q_actual"][0][:4]],
                        'cartesian_position': [round(float(x), 4) for x in a["tool_vector_actual"][0][:4]],
                        'joint_currents': [round(float(x), 4) for x in a["i_actual"][0][:4]],
                        'speed_scaling': round(float(a["speed_scaling"][0]), 4),
                        'error_status': int(a["ErrorStatus"][0]),
                        'enabled': int(a["EnableStatus"][0]) == 1
                    })
                    
                    # 更新DI狀態
                    di_bits = format(int(a["digital_input_bits"][0]), '016b')
                    self.robot_state['digital_inputs'] = [int(x) for x in di_bits[::-1]][:16]
                    
                    # 更新DO狀態
                    do_bits = format(int(a["digital_outputs"][0]), '016b')
                    self.robot_state['digital_outputs'] = [int(x) for x in do_bits[::-1]][:16]
                    
                    # 透過WebSocket發送更新
                    socketio.emit('robot_state_update', self.robot_state)
                    
                time.sleep(0.008)  # 8ms更新頻率
                
            except Exception as e:
                logging.error(f"回饋處理錯誤: {e}")
                time.sleep(0.1)

    def add_command(self, command):
        """新增指令到佇列"""
        self.command_queue.put(command)

    def enable_robot(self):
        """啟用機器人"""
        self.add_command({'type': 'enable'})

    def disable_robot(self):
        """停用機器人"""
        self.add_command({'type': 'disable'})

    def jog_joint(self, axis, direction):
        """關節點動"""
        axis_mapping = {0: 'J1', 1: 'J2', 2: 'J3', 3: 'J4'}
        direction_str = '+' if direction > 0 else '-'
        axis_id = f"{axis_mapping[axis]}{direction_str}"
        self.add_command({'type': 'jog', 'params': {'axis_id': axis_id}})

    def jog_cartesian(self, axis, direction):
        """笛卡爾點動"""
        axes = ['X', 'Y', 'Z', 'R']
        direction_str = '+' if direction > 0 else '-'
        axis_id = f"{axes[axis]}{direction_str}"
        self.add_command({'type': 'jog', 'params': {'axis_id': axis_id}})

    def stop_jog(self):
        """停止點動"""
        self.add_command({'type': 'jog_stop'})

    def emergency_stop(self):
        """緊急停止機器人"""
        self.add_command({'type': 'emergency_stop'})

    def clear_error(self):
        """清除機器人錯誤"""
        self.add_command({'type': 'clear_error'})

    def reset_robot(self):
        """重設機器人"""
        self.add_command({'type': 'reset_robot'})

    def save_waypoint(self, name):
        """保存目前位置為點位"""
        self.waypoints[name] = {
            'joint': self.robot_state['joint_positions'].copy(),
            'cartesian': self.robot_state['cartesian_position'].copy(),
            'timestamp': datetime.now().isoformat()
        }
        
        # 保存到檔案
        try:
            with open('waypoints.json', 'w', encoding='utf-8') as f:
                json.dump(self.waypoints, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存點位失敗: {e}")

    def load_waypoints(self):
        """載入點位"""
        try:
            if os.path.exists('waypoints.json'):
                with open('waypoints.json', 'r', encoding='utf-8') as f:
                    self.waypoints = json.load(f)
        except Exception as e:
            logging.error(f"載入點位失敗: {e}")

    def move_to_waypoint(self, name, move_type='joint'):
        """移動到指定點位"""
        if name in self.waypoints:
            waypoint = self.waypoints[name]
            if move_type == 'joint':
                self.add_command({
                    'type': 'joint_movj',
                    'params': {
                        'j1': waypoint['joint'][0],
                        'j2': waypoint['joint'][1],
                        'j3': waypoint['joint'][2],
                        'j4': waypoint['joint'][3]
                    }
                })
            else:
                self.add_command({
                    'type': 'movj',
                    'params': {
                        'x': waypoint['cartesian'][0],
                        'y': waypoint['cartesian'][1],
                        'z': waypoint['cartesian'][2],
                        'r': waypoint['cartesian'][3]
                    }
                })

    def validate_script(self, script_content):
        """驗證腳本內容"""
        try:
            tree = ast.parse(script_content)
            
            allowed_modules = ['dobot_api', 'time', 'modbus_tk', 'pymodbus']
            allowed_functions = ['sleep', 'EnableRobot', 'DisableRobot', 'MovJ', 'MovL', 
                               'JointMovJ', 'DO', 'DOExecute', 'DI', 'GetAngle', 'GetPose']
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not any(allowed in alias.name for allowed in allowed_modules):
                            return False, f"不允許的模組: {alias.name}"
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and not any(allowed in node.module for allowed in allowed_modules):
                        return False, f"不允許的模組: {node.module}"
            
            return True, "腳本驗證通過"
            
        except SyntaxError as e:
            return False, f"語法錯誤: {e}"
        except Exception as e:
            return False, f"驗證失敗: {e}"

    def load_action_script(self, action_id, script_content):
        """載入動作腳本"""
        try:
            is_valid, message = self.validate_script(script_content)
            if not is_valid:
                return False, message
            
            self.action_scripts[action_id] = {
                'content': script_content,
                'name': f'動作腳本{action_id}'
            }
            
            return True, "腳本載入成功"
            
        except Exception as e:
            return False, f"載入腳本失敗: {e}"

    def execute_action(self, action_id):
        """執行動作腳本"""
        if action_id not in self.action_scripts or not self.action_scripts[action_id]:
            return False, "未載入腳本"
        
        if action_id in self.action_threads and self.action_threads[action_id].is_alive():
            return False, "動作正在執行中"
        
        script_info = self.action_scripts[action_id]
        thread = threading.Thread(
            target=self._execute_script,
            args=(action_id, script_info['content'])
        )
        thread.daemon = True
        self.action_threads[action_id] = thread
        thread.start()
        
        return True, "動作開始執行"

    def _execute_script(self, action_id, script_content):
        """執行腳本內容"""
        try:
            # 建立安全的執行環境
            safe_globals = {
                '__builtins__': {},
                'dobot_controller': self,
                'time': __import__('time'),
                'print': print
            }
            
            exec(script_content, safe_globals)
            
        except Exception as e:
            logging.error(f"腳本執行錯誤 ({action_id}): {e}")
        finally:
            if action_id in self.action_threads:
                del self.action_threads[action_id]

    def stop_action(self, action_id):
        """停止動作執行"""
        if action_id in self.action_threads and self.action_threads[action_id].is_alive():
            del self.action_threads[action_id]
            return True
        return False

# ========== 相機管理類 ==========
class CameraManager:
    def __init__(self):
        self.camera_api = None
        self.stream_thread = None
        self.latest_frame = None
        self.stream_running = False
        self.frame_lock = threading.Lock()
        
        if CAMERA_AVAILABLE:
            self.camera_api = create_camera_api()
            self.camera_api.set_error_callback(lambda msg: print(f"[Camera Error] {msg}"))
    
    def get_raw_frame(self, timeout=1000):
        """從相機取得原始影像"""
        if not CAMERA_AVAILABLE or not self.camera_api.is_connected() or not self.camera_api.is_streaming():
            return None
        
        # 這裡需要實作具體的影像取得邏輯
        # 簡化版本，回傳None
        return None
    
    def grab_frames(self):
        """持續擷取影像的執行緒函數"""
        frame_count = 0
        error_count = 0
        
        time.sleep(1.0)
        
        while self.stream_running:
            try:
                raw = self.get_raw_frame(timeout=100)
                
                if raw is not None:
                    error_count = 0
                    
                    if raw.shape[0] > 0 and raw.shape[1] > 0:
                        if raw.shape[1] > 1920:
                            scale = 1920.0 / raw.shape[1]
                            new_width = int(raw.shape[1] * scale)
                            new_height = int(raw.shape[0] * scale)
                            raw = cv2.resize(raw, (new_width, new_height))
                        
                        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                        ret, jpeg = cv2.imencode('.jpg', raw, encode_param)
                        
                        if ret:
                            jpeg_bytes = jpeg.tobytes()
                            
                            with self.frame_lock:
                                self.latest_frame = jpeg_bytes
                            
                            frame_count += 1
                            if frame_count % 30 == 0:
                                print(f"已成功處理 {frame_count} 格畫面")
                else:
                    error_count += 1
                    if error_count > 50:
                        print("連續多次無法取得有效影像")
                        error_count = 0
                        time.sleep(0.5)
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"擷取影像異常: {str(e)}")
                time.sleep(0.1)
        
        print("影像擷取執行緒已結束")

    def generate_mjpeg(self):
        """產生 MJPEG 串流"""
        no_frame_count = 0
        
        while self.stream_running:
            with self.frame_lock:
                frame = self.latest_frame
            
            if frame:
                no_frame_count = 0
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            else:
                no_frame_count += 1
                if no_frame_count > 100:
                    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    ret, jpeg = cv2.imencode('.jpg', black_frame)
                    if ret:
                        yield (b"--frame\r\n"
                               b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                
                time.sleep(0.01)

    def enumerate_devices(self):
        """列舉裝置"""
        if not CAMERA_AVAILABLE:
            return []
        return self.camera_api.enumerate_devices()
    
    def connect(self, device_index):
        """連接相機"""
        if not CAMERA_AVAILABLE:
            return False
        return self.camera_api.connect(device_index)
    
    def disconnect(self):
        """中斷相機連接"""
        if not CAMERA_AVAILABLE:
            return False
        
        self.stream_running = False
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2.0)
        
        return self.camera_api.disconnect()
    
    def start_streaming(self):
        """開始串流"""
        if not CAMERA_AVAILABLE or not self.camera_api.is_connected():
            return False
        
        if self.camera_api.start_streaming():
            with self.frame_lock:
                self.latest_frame = None
            
            self.stream_running = True
            self.stream_thread = threading.Thread(target=self.grab_frames, daemon=True)
            self.stream_thread.start()
            
            return True
        return False
    
    def stop_streaming(self):
        """停止串流"""
        if not CAMERA_AVAILABLE:
            return False
        
        self.stream_running = False
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=2.0)
        
        return self.camera_api.stop_streaming()

# ========== 全域控制器實例 ==========
if ROBOT_AVAILABLE:
    dobot_controller = DobotController()
    dobot_controller.load_waypoints()
else:
    dobot_controller = None

if MODBUS_AVAILABLE:
    modbus_manager = ModbusManager()
else:
    modbus_manager = None

if CAMERA_AVAILABLE:
    camera_manager = CameraManager()
else:
    camera_manager = None

# ========== 路由設定 ==========
@app.route('/')
def index():
    """主頁面 - 顯示可用功能選單"""
    return render_template('main_index.html', 
                         robot_available=ROBOT_AVAILABLE,
                         modbus_available=MODBUS_AVAILABLE,
                         camera_available=CAMERA_AVAILABLE)

@app.route('/robot')
def robot_control():
    """機器人控制頁面"""
    if not ROBOT_AVAILABLE:
        return render_template('error.html', message="機器人控制功能不可用")
    return render_template('robot_index.html')

@app.route('/camera')
def camera_control():
    """相機控制頁面"""
    if not CAMERA_AVAILABLE:
        return render_template('error.html', message="相機控制功能不可用")
    return render_template('camera_index.html')

@app.route('/modbus_tcp')
def modbus_tcp():
    """ModbusTCP控制頁面"""
    if not MODBUS_AVAILABLE:
        return render_template('error.html', message="ModBus功能不可用")
    return render_template('modbus_tcp.html')

@app.route('/modbus_rtu')
def modbus_rtu():
    """ModbusRTU控制頁面"""
    if not MODBUS_AVAILABLE:
        return render_template('error.html', message="ModBus功能不可用")
    return render_template('modbus_rtu.html')

# ========== 機器人API ==========
@app.route('/api/robot/connect', methods=['POST'])
def robot_connect():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    data = request.json
    success = dobot_controller.connect(
        data.get('ip'),
        data.get('dashboard_port'),
        data.get('move_port'),
        data.get('feed_port')
    )
    return jsonify({'success': success})

@app.route('/api/robot/disconnect', methods=['POST'])
def robot_disconnect():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    success = dobot_controller.disconnect()
    return jsonify({'success': success})

@app.route('/api/robot/enable', methods=['POST'])
def robot_enable():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    dobot_controller.enable_robot()
    return jsonify({'success': True})

@app.route('/api/robot/disable', methods=['POST'])
def robot_disable():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    dobot_controller.disable_robot()
    return jsonify({'success': True})

@app.route('/api/robot/state')
def robot_get_state():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'error': '機器人功能不可用'})
    
    return jsonify(dobot_controller.robot_state)

@app.route('/api/robot/jog', methods=['POST'])
def robot_jog():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    data = request.json
    mode = data.get('mode', 'joint')
    axis = data.get('axis', 0)
    direction = data.get('direction', 1)
    
    if mode == 'joint':
        dobot_controller.jog_joint(axis, direction)
    else:
        dobot_controller.jog_cartesian(axis, direction)
    
    return jsonify({'success': True})

@app.route('/api/robot/jog/stop', methods=['POST'])
def robot_jog_stop():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    dobot_controller.stop_jog()
    return jsonify({'success': True})

@app.route('/api/robot/emergency_stop', methods=['POST'])
def robot_emergency_stop():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    dobot_controller.emergency_stop()
    return jsonify({'success': True})

@app.route('/api/robot/clear_error', methods=['POST'])
def robot_clear_error():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    dobot_controller.clear_error()
    return jsonify({'success': True})

@app.route('/api/robot/reset', methods=['POST'])
def robot_reset():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    dobot_controller.reset_robot()
    return jsonify({'success': True})

@app.route('/api/robot/waypoints', methods=['GET'])
def robot_get_waypoints():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'error': '機器人功能不可用'})
    
    return jsonify({'waypoints': dobot_controller.waypoints})

@app.route('/api/robot/waypoints', methods=['POST'])
def robot_save_waypoint():
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    data = request.json
    name = data.get('name')
    if name:
        dobot_controller.save_waypoint(name)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '點位名稱不能為空'})

@app.route('/api/robot/waypoints/<name>/move', methods=['POST'])
def robot_move_to_waypoint(name):
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    data = request.json
    move_type = data.get('type', 'joint')
    dobot_controller.move_to_waypoint(name, move_type)
    return jsonify({'success': True})

@app.route('/api/robot/scripts/<action_id>', methods=['POST'])
def robot_load_script(action_id):
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    data = request.json
    script_content = data.get('content', '')
    success, message = dobot_controller.load_action_script(action_id, script_content)
    return jsonify({'success': success, 'message': message})

@app.route('/api/robot/scripts/<action_id>/execute', methods=['POST'])
def robot_execute_script(action_id):
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    success, message = dobot_controller.execute_action(action_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/robot/scripts/<action_id>/stop', methods=['POST'])
def robot_stop_script(action_id):
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    success = dobot_controller.stop_action(action_id)
    return jsonify({'success': success})

@app.route('/api/robot/do/<int:index>', methods=['POST'])
def robot_set_do(index):
    if not ROBOT_AVAILABLE or not dobot_controller:
        return jsonify({'success': False, 'error': '機器人功能不可用'})
    
    data = request.json
    status = data.get('status', 0)
    dobot_controller.add_command({
        'type': 'do',
        'params': {'index': index, 'status': status}
    })
    return jsonify({'success': True})

# ========== 相機API ==========
@app.route('/api/camera/devices', methods=["GET"])
def camera_list_devices():
    if not CAMERA_AVAILABLE or not camera_manager:
        return jsonify({'success': False, 'error': '相機功能不可用', 'devices': [], 'count': 0})
    
    try:
        devices = camera_manager.enumerate_devices()
        
        dev_list = []
        for device in devices:
            dev_info = {
                "index": device.index,
                "name": device.device_name,
                "type": device.device_type,
                "serial": device.serial_number,
                "ip": device.ip_address if device.ip_address else "N/A"
            }
            dev_list.append(dev_info)
        
        return jsonify({
            "success": True,
            "devices": dev_list,
            "count": len(dev_list)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "devices": [],
            "count": 0
        })

@app.route('/api/camera/connect', methods=["POST"])
def camera_connect():
    if not CAMERA_AVAILABLE or not camera_manager:
        return jsonify({'success': False, 'error': '相機功能不可用'})
    
    try:
        data = request.get_json()
        idx = int(data.get("index", -1))
        
        if idx < 0:
            return jsonify({"success": False, "error": "無效的裝置索引"})
        
        ok = camera_manager.connect(idx)
        
        if ok:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "連接失敗"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/camera/disconnect', methods=["POST"])
def camera_disconnect():
    if not CAMERA_AVAILABLE or not camera_manager:
        return jsonify({'success': False, 'error': '相機功能不可用'})
    
    try:
        ok = camera_manager.disconnect()
        return jsonify({"success": ok})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/camera/start_stream', methods=["POST"])
def camera_start_stream():
    if not CAMERA_AVAILABLE or not camera_manager:
        return jsonify({'success': False, 'error': '相機功能不可用'})
    
    try:
        ok = camera_manager.start_streaming()
        return jsonify({"success": ok})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/camera/stop_stream', methods=["POST"])
def camera_stop_stream():
    if not CAMERA_AVAILABLE or not camera_manager:
        return jsonify({'success': False, 'error': '相機功能不可用'})
    
    try:
        ok = camera_manager.stop_streaming()
        return jsonify({"success": ok})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/camera/video_feed")
def camera_video_feed():
    if not CAMERA_AVAILABLE or not camera_manager:
        return Response("相機功能不可用", status=503)
    
    return Response(
        camera_manager.generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

# ========== ModBus API ==========
@app.route('/api/modbus/tcp/connect', methods=['POST'])
def modbus_tcp_connect():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    host = data.get('host')
    port = data.get('port', 502)
    slave_id = data.get('slave_id', 1)
    
    success = modbus_manager.connect_tcp(host, port, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/tcp/disconnect', methods=['POST'])
def modbus_tcp_disconnect():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    modbus_manager.disconnect_tcp()
    return jsonify({'success': True})

@app.route('/api/modbus/tcp/status')
def modbus_tcp_status():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'connected': False, 'config': {}})
    
    return jsonify({
        'connected': modbus_manager.tcp_connected,
        'config': modbus_manager.tcp_config
    })

@app.route('/api/modbus/tcp/read', methods=['POST'])
def modbus_tcp_read():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    address = data.get('address', 0)
    count = data.get('count', 1)
    slave_id = data.get('slave_id', modbus_manager.tcp_config.get('slave_id', 1))
    
    registers = modbus_manager.read_holding_registers('tcp', address, count, slave_id)
    if registers is not None:
        result = []
        for i, value in enumerate(registers):
            reg_addr = address + i
            comment = modbus_manager.register_comments.get(f'tcp_{reg_addr}', '')
            result.append({
                'address': reg_addr,
                'value': value,
                'comment': comment
            })
        return jsonify({'success': True, 'registers': result})
    else:
        return jsonify({'success': False, 'error': '讀取失敗'})

@app.route('/api/modbus/tcp/write', methods=['POST'])
def modbus_tcp_write():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    address = data.get('address', 0)
    value = data.get('value', 0)
    slave_id = data.get('slave_id', modbus_manager.tcp_config.get('slave_id', 1))
    
    success = modbus_manager.write_single_register('tcp', address, value, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/tcp/write_multiple', methods=['POST'])
def modbus_tcp_write_multiple():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    address = data.get('address', 0)
    values = data.get('values', [])
    slave_id = data.get('slave_id', modbus_manager.tcp_config.get('slave_id', 1))
    
    success = modbus_manager.write_multiple_registers('tcp', address, values, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/rtu/connect', methods=['POST'])
def modbus_rtu_connect():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    port = data.get('port')
    baudrate = data.get('baudrate', 9600)
    bytesize = data.get('bytesize', 8)
    parity = data.get('parity', 'N')
    stopbits = data.get('stopbits', 1)
    slave_id = data.get('slave_id', 1)
    
    success = modbus_manager.connect_rtu(port, baudrate, bytesize, parity, stopbits, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/rtu/disconnect', methods=['POST'])
def modbus_rtu_disconnect():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    modbus_manager.disconnect_rtu()
    return jsonify({'success': True})

@app.route('/api/modbus/rtu/status')
def modbus_rtu_status():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'connected': False, 'config': {}})
    
    return jsonify({
        'connected': modbus_manager.rtu_connected,
        'config': modbus_manager.rtu_config
    })

@app.route('/api/modbus/rtu/read', methods=['POST'])
def modbus_rtu_read():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    address = data.get('address', 0)
    count = data.get('count', 1)
    slave_id = data.get('slave_id', modbus_manager.rtu_config.get('slave_id', 1))
    
    registers = modbus_manager.read_holding_registers('rtu', address, count, slave_id)
    if registers is not None:
        result = []
        for i, value in enumerate(registers):
            reg_addr = address + i
            comment = modbus_manager.register_comments.get(f'rtu_{reg_addr}', '')
            result.append({
                'address': reg_addr,
                'value': value,
                'comment': comment
            })
        return jsonify({'success': True, 'registers': result})
    else:
        return jsonify({'success': False, 'error': '讀取失敗'})

@app.route('/api/modbus/rtu/write', methods=['POST'])
def modbus_rtu_write():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    address = data.get('address', 0)
    value = data.get('value', 0)
    slave_id = data.get('slave_id', modbus_manager.rtu_config.get('slave_id', 1))
    
    success = modbus_manager.write_single_register('rtu', address, value, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/rtu/write_multiple', methods=['POST'])
def modbus_rtu_write_multiple():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    address = data.get('address', 0)
    values = data.get('values', [])
    slave_id = data.get('slave_id', modbus_manager.rtu_config.get('slave_id', 1))
    
    success = modbus_manager.write_multiple_registers('rtu', address, values, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/rtu/ports')
def modbus_rtu_ports():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'ports': []})
    
    ports = modbus_manager.get_serial_ports()
    return jsonify({'ports': ports})

@app.route('/api/modbus/comment', methods=['POST'])
def modbus_update_comment():
    if not MODBUS_AVAILABLE or not modbus_manager:
        return jsonify({'success': False, 'error': 'ModBus功能不可用'})
    
    data = request.json
    client_type = data.get('type', 'tcp')
    address = data.get('address', 0)
    comment = data.get('comment', '')
    
    key = f'{client_type}_{address}'
    modbus_manager.register_comments[key] = comment
    modbus_manager.save_comments()
    
    return jsonify({'success': True})

# ========== WebSocket事件 ==========
@socketio.on('connect')
def handle_connect():
    if ROBOT_AVAILABLE and dobot_controller:
        emit('robot_state_update', dobot_controller.robot_state)

@socketio.on('disconnect')
def handle_disconnect():
    pass

# ========== 錯誤處理 ==========
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message="頁面未找到"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message="伺服器內部錯誤"), 500

# ========== 主程式 ==========
if __name__ == "__main__":
    print("啟動整合式控制系統...")
    print(f"機器人控制: {'可用' if ROBOT_AVAILABLE else '不可用'}")
    print(f"相機控制: {'可用' if CAMERA_AVAILABLE else '不可用'}")
    print(f"ModBus控制: {'可用' if MODBUS_AVAILABLE else '不可用'}")
    print("請造訪 http://localhost:5000")
    
    # 設置 Flask 組態
    app.config['JSON_AS_ASCII'] = False  # 支援中文
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    # 啟動 Flask
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)