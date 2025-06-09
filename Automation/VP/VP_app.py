# -*- coding: utf-8 -*-
"""
VP_app.py - 震動盤Web UI控制應用
作為Modbus TCP Client訪問VP_main模組的寄存器進行監控和控制
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
from datetime import datetime
from pymodbus.client import ModbusTcpClient
from typing import Dict, Any, Optional

class VibrationPlateWebApp:
    """震動盤Web控制應用 - Modbus TCP Client"""
    
    def __init__(self):
        # 載入配置
        self.config = self.load_config()
        
        # Modbus TCP Client
        self.modbus_client: Optional[ModbusTcpClient] = None
        self.connected_to_server = False
        
        # 狀態監控
        self.status_monitor_thread = None
        self.monitoring = False
        
        # 寄存器映射 (與VP_main.py一致)
        self.base_address = self.config['modbus_mapping']['base_address']  # 300
        self.init_register_mapping()
        
        # 狀態快取
        self.last_status = {}
        self.command_id_counter = 1
        
        # 初始化Flask應用
        self.init_flask_app()
        
    def load_config(self) -> Dict[str, Any]:
        """載入配置檔案"""
        default_config = {
            "module_id": "震動盤Web UI",
            "tcp_server": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 1.0
            },
            "modbus_mapping": {
                "base_address": 300
            },
            "web_server": {
                "host": "0.0.0.0",
                "port": 5053,
                "debug": False
            },
            "defaults": {
                "brightness": 128,
                "strength": 100,
                "frequency": 100
            }
        }
        
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "vp_app_config.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
                print(f"已載入配置檔案: {config_path}")
            else:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                print(f"已創建預設配置檔案: {config_path}")
        except Exception as e:
            print(f"載入配置檔案失敗: {e}")
            
        return default_config
    
    def init_register_mapping(self):
        """初始化寄存器映射 (與VP_main.py一致)"""
        base = self.base_address
        
        # 狀態寄存器區 (只讀) base+0 ~ base+14
        self.status_registers = {
            'module_status': base + 0,          # 模組狀態
            'device_connection': base + 1,      # 設備連接狀態
            'device_status': base + 2,          # 設備狀態
            'error_code': base + 3,             # 錯誤代碼
            'current_action_low': base + 4,     # 當前動作低位
            'current_action_high': base + 5,    # 當前動作高位
            'target_action_low': base + 6,      # 目標動作低位
            'target_action_high': base + 7,     # 目標動作高位
            'command_status': base + 8,         # 指令執行狀態
            'comm_error_count': base + 9,       # 通訊錯誤計數
            'brightness_status': base + 10,     # 背光亮度狀態
            'backlight_status': base + 11,      # 背光開關狀態
            'vibration_status': base + 12,      # 震動狀態
            'reserved_13': base + 13,           # 保留
            'timestamp': base + 14              # 時間戳
        }
        
        # 指令寄存器區 (讀寫) base+20 ~ base+24
        self.command_registers = {
            'command_code': base + 20,          # 指令代碼
            'param1': base + 21,                # 參數1 (強度/亮度/動作碼)
            'param2': base + 22,                # 參數2 (頻率)
            'command_id': base + 23,            # 指令ID
            'reserved': base + 24               # 保留
        }
        
        # 指令映射
        self.command_map = {
            'nop': 0,
            'enable_device': 1,      # 背光開啟
            'disable_device': 2,     # 背光關閉
            'stop_all': 3,           # 停止所有動作
            'set_brightness': 4,     # 設定背光亮度
            'execute_action': 5,     # 執行動作
            'emergency_stop': 6,     # 緊急停止
            'reset_error': 7,        # 錯誤重置
            'set_action_params': 11, # 設定動作參數 (VP專用)
            'toggle_backlight': 12,  # 背光切換 (VP專用)
            'execute_with_params': 13 # 執行動作並設定參數 (VP專用)
        }
        
        # 動作映射
        self.action_map = {
            'stop': 0, 'up': 1, 'down': 2, 'left': 3, 'right': 4,
            'upleft': 5, 'downleft': 6, 'upright': 7, 'downright': 8,
            'horizontal': 9, 'vertical': 10, 'spread': 11
        }
        
        print(f"震動盤Web UI寄存器映射 - 基地址: {base}")
        
    def init_flask_app(self):
        """初始化Flask應用"""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'vp_web_app_2024'
        
        # 初始化SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 添加錯誤處理
        @self.app.errorhandler(404)
        def not_found_error(error):
            return jsonify({
                'success': False,
                'message': '請求的路徑不存在',
                'error': 'Not Found'
            }), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({
                'success': False,
                'message': '內部服務器錯誤',
                'error': 'Internal Server Error'
            }), 500
        
        @self.app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify({
                'success': False,
                'message': '請求方法不被允許',
                'error': 'Method Not Allowed'
            }), 405
        
        # 註冊路由
        self.register_routes()
        self.register_socketio_events()
        
    def register_routes(self):
        """註冊Flask路由"""
        
        @self.app.route('/')
        def index():
            """主頁面"""
            return render_template('index.html', config=self.config)
        
        @self.app.route('/api/status')
        def get_status():
            """獲取系統狀態"""
            return jsonify(self.get_current_status())
        
        @self.app.route('/api/connect', methods=['POST'])
        def connect_server():
            """連接到Modbus TCP服務器"""
            try:
                data = request.get_json() or {}
                
                # 更新連接參數
                if 'host' in data:
                    self.config['tcp_server']['host'] = data['host']
                if 'port' in data:
                    self.config['tcp_server']['port'] = int(data['port'])
                
                result = self.connect_modbus_server()
                
                if result['success']:
                    self.start_monitoring()
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'連接時發生錯誤: {str(e)}'
                })
        
        @self.app.route('/api/disconnect', methods=['POST'])
        def disconnect_server():
            """斷開Modbus TCP連接"""
            try:
                result = self.disconnect_modbus_server()
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'斷開連接時發生錯誤: {str(e)}'
                })
        
        @self.app.route('/api/execute_action', methods=['POST'])
        def execute_action():
            """執行震動動作"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': 'Modbus服務器未連接'
                    })
                
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': '無效的請求數據'
                    })
                
                action = data.get('action')
                strength = data.get('strength', 100)
                frequency = data.get('frequency', 100)
                
                if not action or action not in self.action_map:
                    return jsonify({
                        'success': False,
                        'message': f'未知動作: {action}'
                    })
                
                # 執行動作指令
                action_code = self.action_map[action]
                result = self.send_command('execute_action', action_code, strength)
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'執行動作時發生錯誤: {str(e)}'
                })
        
        @self.app.route('/api/stop', methods=['POST'])
        def stop_action():
            """停止動作"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': 'Modbus服務器未連接'
                    })
                
                result = self.send_command('stop_all')
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'停止動作時發生錯誤: {str(e)}'
                })
        
        @self.app.route('/api/stop_all_command', methods=['POST'])
        def stop_all_command():
            """停止所有动作 (备用方法)"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': 'Modbus服务器未连接'
                    })
                
                result = self.send_command('stop_all')
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'停止动作时发生错误: {str(e)}'
                })
        
        @self.app.route('/api/emergency_stop', methods=['POST'])
        def emergency_stop():
            """緊急停止"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': 'Modbus服務器未連接'
                    })
                
                result = self.send_command('emergency_stop')
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'緊急停止時發生錯誤: {str(e)}'
                })
        
        @self.app.route('/api/set_brightness', methods=['POST'])
        def set_brightness():
            """設定背光亮度"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': 'Modbus服務器未連接'
                    })
                
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': '無效的請求數據'
                    })
                
                brightness = data.get('brightness', 128)
                brightness = max(0, min(255, int(brightness)))
                
                result = self.send_command('set_brightness', brightness)
                if result['success']:
                    self.config['defaults']['brightness'] = brightness
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'設定亮度時發生錯誤: {str(e)}'
                })
        
        @self.app.route('/api/set_backlight', methods=['POST'])
        def set_backlight():
            """設定背光開關"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': 'Modbus服務器未連接'
                    })
                
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': '無效的請求數據'
                    })
                
                state = data.get('state', True)
                
                command = 'enable_device' if state else 'disable_device'
                result = self.send_command(command)
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'設定背光時發生錯誤: {str(e)}'
                })
        
        @self.app.route('/api/set_action_params', methods=['POST'])
        def set_action_params():
            """設定動作參數"""
            if not self.connected_to_server:
                return jsonify({
                    'success': False,
                    'message': 'Modbus服務器未連接'
                })
            
            data = request.get_json()
            action = data.get('action')
            strength = data.get('strength')
            frequency = data.get('frequency')
            
            if action not in self.action_map:
                return jsonify({
                    'success': False,
                    'message': f'未知動作: {action}'
                })
            
            action_code = self.action_map[action]
            result = self.send_command('set_action_params', action_code, strength)
            
            return jsonify(result)
        
        @self.app.route('/api/reset_error', methods=['POST'])
        def reset_error():
            """重置錯誤"""
            if not self.connected_to_server:
                return jsonify({
                    'success': False,
                    'message': 'Modbus服務器未連接'
                })
            
            result = self.send_command('reset_error')
            return jsonify(result)
        
        @self.app.route('/api/get_register_values', methods=['GET'])
        def get_register_values():
            """獲取寄存器數值"""
            if not self.connected_to_server:
                return jsonify({
                    'success': False,
                    'message': 'Modbus服務器未連接'
                })
            
            try:
                # 讀取狀態寄存器
                status_values = {}
                for name, addr in self.status_registers.items():
                    value = self.read_register(addr)
                    status_values[name] = value
                
                # 讀取指令寄存器
                command_values = {}
                for name, addr in self.command_registers.items():
                    value = self.read_register(addr)
                    command_values[name] = value
                
                return jsonify({
                    'success': True,
                    'status_registers': status_values,
                    'command_registers': command_values,
                    'base_address': self.base_address
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'讀取寄存器失敗: {str(e)}'
                })
        
        @self.app.route('/api/execute_with_params', methods=['POST'])
        def execute_with_params():
            """執行動作並設定參數"""
            if not self.connected_to_server:
                return jsonify({
                    'success': False,
                    'message': 'Modbus服務器未連接'
                })
            
            data = request.get_json()
            action = data.get('action')
            strength = data.get('strength', 100)
            frequency = data.get('frequency', 100)
            
            if action not in self.action_map:
                return jsonify({
                    'success': False,
                    'message': f'未知動作: {action}'
                })
            
            action_code = self.action_map[action]
            result = self.send_command('execute_with_params', action_code, strength)
            
            return jsonify(result)
        
        @self.app.route('/api/routes', methods=['GET'])
        def list_routes():
            """列出所有可用路由"""
            try:
                routes = []
                for rule in self.app.url_map.iter_rules():
                    if rule.endpoint != 'static':
                        routes.append({
                            'endpoint': rule.endpoint,
                            'methods': list(rule.methods),
                            'path': str(rule.rule)
                        })
                
                return jsonify({
                    'success': True,
                    'routes': routes,
                    'message': f'找到 {len(routes)} 個路由'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'獲取路由列表失敗: {str(e)}'
                })
        
        @self.app.route('/api/debug', methods=['GET'])
        def debug_info():
            """調試資訊"""
            try:
                debug_data = {
                    'success': True,
                    'server_status': {
                        'connected': self.connected_to_server,
                        'server_config': self.config['tcp_server'],
                        'base_address': self.base_address
                    },
                    'register_mapping': {
                        'status_registers': self.status_registers,
                        'command_registers': self.command_registers
                    },
                    'action_map': self.action_map,
                    'command_map': self.command_map,
                    'last_status': self.last_status,
                    'command_counter': self.command_id_counter
                }
                return jsonify(debug_data)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'獲取調試資訊失敗: {str(e)}'
                })
        
        @self.app.route('/api/test', methods=['GET', 'POST'])
        def test_endpoint():
            """測試端點"""
            try:
                method = request.method
                data = request.get_json() if request.method == 'POST' else None
                
                return jsonify({
                    'success': True,
                    'message': f'測試端點正常 - 方法: {method}',
                    'received_data': data,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'測試端點錯誤: {str(e)}'
                })
            """批量執行指令"""
            if not self.connected_to_server:
                return jsonify({
                    'success': False,
                    'message': 'Modbus服務器未連接'
                })
            
            data = request.get_json()
            commands = data.get('commands', [])
            
            results = []
            success_count = 0
            
            for cmd in commands:
                action = cmd.get('action')
                strength = cmd.get('strength', 100)
                frequency = cmd.get('frequency', 100)
                
                if action in self.action_map:
                    action_code = self.action_map[action]
                    result = self.send_command('execute_with_params', action_code, strength)
                    if result['success']:
                        success_count += 1
                    results.append(result)
                else:
                    results.append({
                        'success': False,
                        'message': f'未知動作: {action}'
                    })
            
            return jsonify({
                'success': success_count == len(commands),
                'message': f'批量執行完成: {success_count}/{len(commands)}',
                'results': results,
                'success_count': success_count
            })
    
    def register_socketio_events(self):
        """註冊SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客戶端連接"""
            print("Web客戶端已連接")
            emit('status_update', self.get_current_status())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客戶端斷開"""
            print("Web客戶端已斷開")
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """狀態請求"""
            emit('status_update', self.get_current_status())
        
        @self.socketio.on('execute_command')
        def handle_execute_command(data):
            """執行指令"""
            if not self.connected_to_server:
                emit('command_result', {
                    'success': False,
                    'message': 'Modbus服務器未連接'
                })
                return
            
            command = data.get('command')
            param1 = data.get('param1', 0)
            param2 = data.get('param2', 0)
            
            result = self.send_command(command, param1, param2)
            emit('command_result', result)
    
    def connect_modbus_server(self) -> Dict[str, Any]:
        """連接到Modbus TCP服務器"""
        try:
            if self.modbus_client:
                self.modbus_client.close()
            
            server_config = self.config['tcp_server']
            self.modbus_client = ModbusTcpClient(
                host=server_config['host'],
                port=server_config['port'],
                timeout=server_config['timeout']
            )
            
            if self.modbus_client.connect():
                self.connected_to_server = True
                print(f"連接到Modbus服務器成功: {server_config['host']}:{server_config['port']}")
                
                return {
                    'success': True,
                    'message': 'Modbus服務器連接成功',
                    'server_info': server_config
                }
            else:
                self.connected_to_server = False
                return {
                    'success': False,
                    'message': 'Modbus服務器連接失敗'
                }
                
        except Exception as e:
            self.connected_to_server = False
            print(f"連接Modbus服務器失敗: {e}")
            return {
                'success': False,
                'message': f'連接失敗: {str(e)}'
            }
    
    def disconnect_modbus_server(self) -> Dict[str, Any]:
        """斷開Modbus TCP連接"""
        try:
            self.stop_monitoring()
            
            if self.modbus_client:
                self.modbus_client.close()
                self.modbus_client = None
            
            self.connected_to_server = False
            print("Modbus服務器連接已斷開")
            
            return {
                'success': True,
                'message': 'Modbus服務器連接已斷開'
            }
            
        except Exception as e:
            print(f"斷開連接失敗: {e}")
            return {
                'success': False,
                'message': f'斷開連接失敗: {str(e)}'
            }
    
    def read_register(self, address: int) -> Optional[int]:
        """讀取寄存器"""
        if not self.connected_to_server or not self.modbus_client:
            return None
        
        try:
            result = self.modbus_client.read_holding_registers(
                address, count=1, slave=self.config['tcp_server']['unit_id']
            )
            
            if not result.isError():
                return result.registers[0]
            else:
                print(f"讀取寄存器 {address} 失敗: {result}")
                return None
                
        except Exception as e:
            print(f"讀取寄存器 {address} 異常: {e}")
            self.connected_to_server = False
            return None
    
    def write_register(self, address: int, value: int) -> bool:
        """寫入寄存器"""
        if not self.connected_to_server or not self.modbus_client:
            return False
        
        try:
            result = self.modbus_client.write_register(
                address, value, slave=self.config['tcp_server']['unit_id']
            )
            
            if not result.isError():
                return True
            else:
                print(f"寫入寄存器 {address}={value} 失敗: {result}")
                return False
                
        except Exception as e:
            print(f"寫入寄存器 {address}={value} 異常: {e}")
            self.connected_to_server = False
            return False
    
    def send_command(self, command: str, param1: int = 0, param2: int = 0) -> Dict[str, Any]:
        """發送指令到VP_main模組"""
        if not self.connected_to_server:
            return {
                'success': False,
                'message': 'Modbus服務器未連接'
            }
        
        if command not in self.command_map:
            return {
                'success': False,
                'message': f'未知指令: {command}'
            }
        
        try:
            command_code = self.command_map[command]
            self.command_id_counter += 1
            
            # 檢查Modbus客戶端連接
            if not self.modbus_client or not self.modbus_client.connected:
                self.connected_to_server = False
                return {
                    'success': False,
                    'message': 'Modbus連接已斷開'
                }
            
            # 寫入指令寄存器
            write_results = []
            write_results.append(self.write_register(self.command_registers['command_code'], command_code))
            write_results.append(self.write_register(self.command_registers['param1'], param1))
            write_results.append(self.write_register(self.command_registers['param2'], param2))
            write_results.append(self.write_register(self.command_registers['command_id'], self.command_id_counter))
            
            success = all(write_results)
            
            if success:
                print(f"發送指令成功: {command} (code={command_code}, p1={param1}, p2={param2}, id={self.command_id_counter})")
                return {
                    'success': True,
                    'message': f'指令 {command} 發送成功',
                    'command': command,
                    'command_code': command_code,
                    'param1': param1,
                    'param2': param2,
                    'command_id': self.command_id_counter
                }
            else:
                failed_writes = [i for i, result in enumerate(write_results) if not result]
                return {
                    'success': False,
                    'message': f'指令 {command} 發送失敗，寫入失敗的寄存器: {failed_writes}'
                }
                
        except Exception as e:
            print(f"發送指令異常: {e}")
            return {
                'success': False,
                'message': f'發送指令異常: {str(e)}'
            }
    
    def start_monitoring(self):
        """開始狀態監控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.status_monitor_thread = threading.Thread(target=self.status_monitor_loop, daemon=True)
        self.status_monitor_thread.start()
        print("狀態監控已啟動")
    
    def stop_monitoring(self):
        """停止狀態監控"""
        self.monitoring = False
        if self.status_monitor_thread and self.status_monitor_thread.is_alive():
            self.status_monitor_thread.join(timeout=1)
        print("狀態監控已停止")
    
    def status_monitor_loop(self):
        """狀態監控循環"""
        while self.monitoring:
            try:
                if self.connected_to_server:
                    # 檢查連接狀態
                    test_read = self.read_register(self.status_registers['module_status'])
                    if test_read is None:
                        self.connected_to_server = False
                        print("Modbus服務器連接已斷開")
                    
                    # 發送狀態更新
                    status = self.get_current_status()
                    self.socketio.emit('status_update', status)
                
                time.sleep(1)  # 1秒更新一次
                
            except Exception as e:
                print(f"狀態監控異常: {e}")
                time.sleep(2)
    
    def get_current_status(self) -> Dict[str, Any]:
        """獲取當前狀態"""
        status = {
            'connected_to_server': self.connected_to_server,
            'config': self.config,
            'timestamp': datetime.now().isoformat(),
            'register_mapping': {
                'base_address': self.base_address,
                'status_registers': self.status_registers,
                'command_registers': self.command_registers
            },
            'vp_module_status': None
        }
        
        if self.connected_to_server:
            try:
                # 讀取VP模組狀態
                vp_status = {}
                for name, addr in self.status_registers.items():
                    value = self.read_register(addr)
                    vp_status[name] = value
                
                # 讀取指令寄存器狀態
                command_status = {}
                for name, addr in self.command_registers.items():
                    value = self.read_register(addr)
                    command_status[name] = value
                
                status['vp_module_status'] = vp_status
                status['command_status'] = command_status
                
            except Exception as e:
                print(f"獲取VP模組狀態失敗: {e}")
                status['connected_to_server'] = False
                self.connected_to_server = False
        
        return status
    
    def create_templates_directory(self):
        """創建templates目錄"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(current_dir, 'templates')
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
            print(f"已創建templates目錄: {templates_dir}")
    
    def run(self):
        """運行Web應用"""
        print("震動盤Web控制應用啟動中...")
        
        # 創建templates目錄
        self.create_templates_directory()
        
        web_config = self.config['web_server']
        print(f"Web服務器啟動 - http://{web_config['host']}:{web_config['port']}")
        print(f"Modbus服務器地址: {self.config['tcp_server']['host']}:{self.config['tcp_server']['port']}")
        print(f"震動盤模組基地址: {self.base_address}")
        print("功能列表:")
        print("  - VP_main模組寄存器監控")
        print("  - 震動動作控制 (11種震動模式)")
        print("  - 背光控制 (亮度調節/開關)")
        print("  - 動作參數設定")
        print("  - 指令狀態追蹤")
        print("  - 錯誤重置")
        print("  - 即時寄存器數值顯示")
        print("按 Ctrl+C 停止應用")
        
        try:
            self.socketio.run(
                self.app,
                host=web_config['host'],
                port=web_config['port'],
                debug=web_config['debug'],
                allow_unsafe_werkzeug=True
            )
        except Exception as e:
            print(f"Web服務器啟動失敗: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理資源"""
        print("正在清理資源...")
        self.stop_monitoring()
        if self.modbus_client:
            try:
                self.modbus_client.close()
                print("Modbus連接已安全斷開")
            except:
                pass
        print("資源清理完成")


def create_index_html():
    """創建index.html檔案 (如果不存在)"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(current_dir, 'templates')
    index_path = os.path.join(templates_dir, 'index.html')
    
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    if not os.path.exists(index_path):
        print(f"注意: 未找到 {index_path}")
        print("請確保將 index.html 檔案放置在 templates/ 目錄中")
        print("或者從提供的 HTML 模板創建該檔案")
        return False
    
    return True


def main():
    """主函數"""
    print("=" * 60)
    print("震動盤Web控制應用 (Modbus TCP Client)")
    print("=" * 60)
    
    # 檢查HTML模板
    if not create_index_html():
        print("警告: HTML模板檔案缺失，Web介面可能無法正常顯示")
        print("繼續啟動應用...")
    
    # 創建應用實例
    app = VibrationPlateWebApp()
    
    try:
        # 運行應用
        app.run()
    except KeyboardInterrupt:
        print("\n收到中斷信號，正在關閉...")
    except Exception as e:
        print(f"應用運行異常: {e}")
    finally:
        app.cleanup()
        print("應用已安全關閉")


if __name__ == '__main__':
    main()