from flask import Flask, render_template, request, jsonify, session
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
from dobot_api import DobotApiDashboard, DobotApiMove, DobotApi, MyType
import numpy as np
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dobot_m1_pro_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system.log'),
        logging.StreamHandler()
    ]
)

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
            logging.error(f"載入Modbus註解失敗: {e}")
    
    def save_comments(self):
        """保存暫存器註解"""
        try:
            with open('modbus_comments.json', 'w', encoding='utf-8') as f:
                json.dump(self.register_comments, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存Modbus註解失敗: {e}")
    
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
        """斷開ModbusTCP"""
        if self.tcp_client:
            self.tcp_client.close()
            self.tcp_connected = False
            logging.info("ModbusTCP已斷開")
    
    def disconnect_rtu(self):
        """斷開ModbusRTU"""
        if self.rtu_client:
            self.rtu_client.close()
            self.rtu_connected = False
            logging.info("ModbusRTU已斷開")
    
    def read_coils(self, client_type, address, count, slave_id):
        """讀取線圈"""
        client = self.tcp_client if client_type == 'tcp' else self.rtu_client
        if not client:
            return None
        
        try:
            response = client.read_coils(address, count, slave=slave_id)
            if not response.isError():
                return response.bits[:count]
            else:
                logging.error(f"讀取線圈錯誤: {response}")
                return None
        except Exception as e:
            logging.error(f"讀取線圈異常: {e}")
            return None
    
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
                logging.info(f"寫入暫存器成功: 地址{address} = {value}")
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
                logging.info(f"批量寫入暫存器成功: 地址{address}, 數量{len(values)}")
                return True
            else:
                logging.error(f"批量寫入暫存器錯誤: {response}")
                return False
        except Exception as e:
            logging.error(f"批量寫入暫存器異常: {e}")
            return False
    
    def get_serial_ports(self):
        """獲取可用的串口列表"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports

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
        self.current_waypoint = None
        
        # 動作腳本管理
        self.action_scripts = {f'action_{i}': None for i in range(1, 6)}
        self.action_threads = {}
        
        # 指令隊列
        self.command_queue = queue.Queue()
        self.command_thread = None
        
        # JOG模式 (joint/cartesian)
        self.jog_mode = 'joint'
        
        # 反饋線程
        self.feedback_thread = None
        self.feedback_running = False

    def connect(self, ip=None, dashboard_port=None, move_port=None, feed_port=None):
        """連接機器人"""
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
            
            # 啟動指令處理線程
            self.start_command_thread()
            
            # 啟動反饋線程
            self.start_feedback_thread()
            
            logging.info(f"機器人連接成功: {self.ip}")
            return True
        except Exception as e:
            logging.error(f"機器人連接失敗: {e}")
            return False

    def disconnect(self):
        """斷開連接"""
        try:
            self.feedback_running = False
            self.connected = False
            
            if self.dashboard:
                self.dashboard.close()
            if self.move:
                self.move.close()
            if self.feed:
                self.feed.close()
                
            # 停止所有動作線程
            for thread_id in list(self.action_threads.keys()):
                self.stop_action(thread_id)
                
            logging.info("機器人連接已斷開")
            return True
        except Exception as e:
            logging.error(f"斷開機器人連接失敗: {e}")
            return False

    def start_command_thread(self):
        """啟動指令處理線程"""
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
        """啟動反饋線程"""
        if not self.feedback_thread or not self.feedback_thread.is_alive():
            self.feedback_running = True
            self.feedback_thread = threading.Thread(target=self._feedback_processor)
            self.feedback_thread.daemon = True
            self.feedback_thread.start()

    def _feedback_processor(self):
        """反饋處理器"""
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
                    
                    # 通過WebSocket發送更新
                    socketio.emit('robot_state_update', self.robot_state)
                    
                time.sleep(0.008)  # 8ms更新頻率
                
            except Exception as e:
                logging.error(f"反饋處理錯誤: {e}")
                time.sleep(0.1)

    def add_command(self, command):
        """添加指令到隊列"""
        self.command_queue.put(command)

    def enable_robot(self):
        """使能機器人"""
        self.add_command({'type': 'enable'})

    def disable_robot(self):
        """下使能機器人"""
        self.add_command({'type': 'disable'})

    def jog_joint(self, axis, direction):
        """關節點動 - 修正軸編號映射"""
        # 正確的軸編號映射 (axis: 0=J1, 1=J2, 2=J3, 3=J4)
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
        """復位機器人"""
        self.add_command({'type': 'reset_robot'})

    def save_waypoint(self, name):
        """保存當前位置為點位"""
        self.waypoints[name] = {
            'joint': self.robot_state['joint_positions'].copy(),
            'cartesian': self.robot_state['cartesian_position'].copy(),
            'timestamp': datetime.now().isoformat()
        }
        
        # 保存到文件
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
        """載入動作腳本 - 直接從內容載入"""
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
            # 創建安全的執行環境
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
            # 注意：Python線程無法強制停止，這裡只是標記
            del self.action_threads[action_id]
            return True
        return False

# 全局控制器實例
dobot_controller = DobotController()
modbus_manager = ModbusManager()

# 載入點位
dobot_controller.load_waypoints()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/modbus_tcp')
def modbus_tcp():
    return render_template('modbus_tcp.html')

@app.route('/modbus_rtu')
def modbus_rtu():
    return render_template('modbus_rtu.html')

# 機器人API
@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    success = dobot_controller.connect(
        data.get('ip'),
        data.get('dashboard_port'),
        data.get('move_port'),
        data.get('feed_port')
    )
    return jsonify({'success': success})

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    success = dobot_controller.disconnect()
    return jsonify({'success': success})

@app.route('/api/robot/enable', methods=['POST'])
def enable_robot():
    dobot_controller.enable_robot()
    return jsonify({'success': True})

@app.route('/api/robot/disable', methods=['POST'])
def disable_robot():
    dobot_controller.disable_robot()
    return jsonify({'success': True})

@app.route('/api/robot/state')
def get_robot_state():
    return jsonify(dobot_controller.robot_state)

@app.route('/api/robot/reset', methods=['POST'])
def reset_robot():
    dobot_controller.reset_robot()
    return jsonify({'success': True})

@app.route('/api/robot/emergency_stop', methods=['POST'])
def emergency_stop():
    dobot_controller.emergency_stop()
    return jsonify({'success': True})

@app.route('/api/robot/clear_error', methods=['POST'])
def clear_error():
    dobot_controller.clear_error()
    return jsonify({'success': True})

@app.route('/api/robot/do', methods=['POST'])
def control_do():
    data = request.json
    index = data.get('index')
    status = data.get('status')
    dobot_controller.add_command({'type': 'do', 'params': {'index': index, 'status': status}})
    return jsonify({'success': True})

@app.route('/api/jog/start', methods=['POST'])
def start_jog():
    data = request.json
    mode = data.get('mode', 'joint')
    axis = data.get('axis')
    direction = data.get('direction')
    
    if mode == 'joint':
        dobot_controller.jog_joint(axis, direction)
    else:
        dobot_controller.jog_cartesian(axis, direction)
    
    return jsonify({'success': True})

@app.route('/api/jog/stop', methods=['POST'])
def stop_jog():
    dobot_controller.stop_jog()
    return jsonify({'success': True})

@app.route('/api/waypoints', methods=['GET'])
def get_waypoints():
    return jsonify(dobot_controller.waypoints)

@app.route('/api/waypoints', methods=['POST'])
def save_waypoint():
    data = request.json
    name = data.get('name')
    dobot_controller.save_waypoint(name)
    return jsonify({'success': True})

@app.route('/api/waypoints/<name>/move', methods=['POST'])
def move_to_waypoint(name):
    data = request.json
    move_type = data.get('type', 'joint')
    dobot_controller.move_to_waypoint(name, move_type)
    return jsonify({'success': True})

@app.route('/api/waypoints/<name>', methods=['DELETE'])
def delete_waypoint(name):
    if name in dobot_controller.waypoints:
        del dobot_controller.waypoints[name]
        # 保存到文件
        try:
            with open('waypoints.json', 'w', encoding='utf-8') as f:
                json.dump(dobot_controller.waypoints, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存點位失敗: {e}")
    return jsonify({'success': True})

@app.route('/api/actions/<action_id>/load', methods=['POST'])
def load_action_script(action_id):
    data = request.json
    script_content = data.get('script_content')
    success, message = dobot_controller.load_action_script(action_id, script_content)
    return jsonify({'success': success, 'message': message})

@app.route('/api/actions/<action_id>/execute', methods=['POST'])
def execute_action(action_id):
    success, message = dobot_controller.execute_action(action_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/actions/<action_id>/stop', methods=['POST'])
def stop_action(action_id):
    success = dobot_controller.stop_action(action_id)
    return jsonify({'success': success})

# ModbusTCP API
@app.route('/api/modbus/tcp/connect', methods=['POST'])
def connect_modbus_tcp():
    data = request.json
    host = data.get('host')
    port = data.get('port', 502)
    slave_id = data.get('slave_id', 1)
    
    success = modbus_manager.connect_tcp(host, port, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/tcp/disconnect', methods=['POST'])
def disconnect_modbus_tcp():
    modbus_manager.disconnect_tcp()
    return jsonify({'success': True})

@app.route('/api/modbus/tcp/status')
def get_modbus_tcp_status():
    return jsonify({
        'connected': modbus_manager.tcp_connected,
        'config': modbus_manager.tcp_config
    })

@app.route('/api/modbus/tcp/read', methods=['POST'])
def read_modbus_tcp():
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
def write_modbus_tcp():
    data = request.json
    address = data.get('address')
    value = data.get('value')
    slave_id = data.get('slave_id', modbus_manager.tcp_config.get('slave_id', 1))
    
    success = modbus_manager.write_single_register('tcp', address, value, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/tcp/write_multiple', methods=['POST'])
def write_multiple_modbus_tcp():
    data = request.json
    address = data.get('address')
    values = data.get('values')
    slave_id = data.get('slave_id', modbus_manager.tcp_config.get('slave_id', 1))
    
    success = modbus_manager.write_multiple_registers('tcp', address, values, slave_id)
    return jsonify({'success': success})

# ModbusRTU API
@app.route('/api/modbus/rtu/ports')
def get_serial_ports():
    ports = modbus_manager.get_serial_ports()
    return jsonify({'ports': ports})

@app.route('/api/modbus/rtu/connect', methods=['POST'])
def connect_modbus_rtu():
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
def disconnect_modbus_rtu():
    modbus_manager.disconnect_rtu()
    return jsonify({'success': True})

@app.route('/api/modbus/rtu/status')
def get_modbus_rtu_status():
    return jsonify({
        'connected': modbus_manager.rtu_connected,
        'config': modbus_manager.rtu_config
    })

@app.route('/api/modbus/rtu/read', methods=['POST'])
def read_modbus_rtu():
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
def write_modbus_rtu():
    data = request.json
    address = data.get('address')
    value = data.get('value')
    slave_id = data.get('slave_id', modbus_manager.rtu_config.get('slave_id', 1))
    
    success = modbus_manager.write_single_register('rtu', address, value, slave_id)
    return jsonify({'success': success})

@app.route('/api/modbus/rtu/write_multiple', methods=['POST'])
def write_multiple_modbus_rtu():
    data = request.json
    address = data.get('address')
    values = data.get('values')
    slave_id = data.get('slave_id', modbus_manager.rtu_config.get('slave_id', 1))
    
    success = modbus_manager.write_multiple_registers('rtu', address, values, slave_id)
    return jsonify({'success': success})

# 註解管理
@app.route('/api/modbus/comment', methods=['POST'])
def update_modbus_comment():
    data = request.json
    client_type = data.get('type')  # tcp或rtu
    address = data.get('address')
    comment = data.get('comment', '')
    
    key = f'{client_type}_{address}'
    if comment.strip():
        modbus_manager.register_comments[key] = comment.strip()
    else:
        modbus_manager.register_comments.pop(key, None)
    
    modbus_manager.save_comments()
    return jsonify({'success': True})

# 日誌API
@app.route('/api/logs')
def get_logs():
    try:
        with open('system.log', 'r', encoding='utf-8') as f:
            logs = f.readlines()[-100:]  # 最後100行
        return jsonify({'logs': logs})
    except Exception:
        return jsonify({'logs': []})

@socketio.on('connect')
def handle_connect():
    emit('robot_state_update', dobot_controller.robot_state)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5020)