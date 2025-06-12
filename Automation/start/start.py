#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import psutil
import socket
import subprocess
import threading
import time
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import serial.tools.list_ports

# 配置檔案路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

class ConfigManager:
    """配置檔案管理器"""
    
    @staticmethod
    def read_com_port(config_path, module_type):
        """讀取config檔案中的COM口設定"""
        try:
            if not os.path.exists(config_path):
                return None
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            com_port_mappings = {
                "Gripper": ['rtu_connection', 'port'],
                "LED": ['serial_connection', 'port'],
                "XC100": ['xc_connection', 'port']
            }
            
            if module_type in com_port_mappings:
                keys = com_port_mappings[module_type]
                data = config
                for key in keys:
                    if key in data:
                        data = data[key]
                    else:
                        return None
                return data
            return None
            
        except Exception as e:
            print(f"讀取配置檔案錯誤: {e}")
            return None
    
    @staticmethod
    def update_com_port(config_path, module_type, new_com):
        """更新config檔案中的COM口設定"""
        try:
            if not os.path.exists(config_path):
                return False
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            com_port_mappings = {
                "Gripper": ['rtu_connection', 'port'],
                "LED": ['serial_connection', 'port'],
                "XC100": ['xc_connection', 'port']
            }
            
            if module_type in com_port_mappings:
                keys = com_port_mappings[module_type]
                data = config
                for key in keys[:-1]:
                    if key not in data:
                        data[key] = {}
                    data = data[key]
                data[keys[-1]] = new_com
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                return True
            return False
            
        except Exception as e:
            print(f"更新配置檔案錯誤: {e}")
            return False

class ModuleController:
    """單一模組控制器"""
    
    def __init__(self, name, script_path, config_path=None, needs_com=False):
        self.name = name
        self.script_path = script_path
        self.config_path = config_path
        self.needs_com = needs_com
        self.process = None
        
    def start(self, com_port=None):
        """啟動模組"""
        try:
            if self.is_running():
                return False, "模組已運行中"
            
            # 如果需要COM口，先更新配置
            if self.needs_com and com_port and self.config_path:
                module_type = self.name.replace("_app", "")
                success = ConfigManager.update_com_port(self.config_path, module_type, com_port)
                if not success:
                    return False, f"COM口配置更新失敗: {com_port}"
            
            # 啟動程序
            script_full_path = os.path.join(PROJECT_ROOT, self.script_path)
            if not os.path.exists(script_full_path):
                return False, f"腳本檔案不存在: {script_full_path}"
            
            self.process = subprocess.Popen(
                [sys.executable, script_full_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(script_full_path)
            )
            
            # 等待一小段時間確認啟動成功
            time.sleep(1)
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                return False, f"程序啟動失敗: {stderr.decode('utf-8', errors='ignore')}"
            
            return True, "模組啟動成功"
            
        except Exception as e:
            return False, f"啟動異常: {str(e)}"
    
    def stop(self):
        """停止模組"""
        try:
            if not self.is_running():
                return True, "模組未運行"
            
            self.process.terminate()
            
            # 等待程序結束
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            
            self.process = None
            return True, "模組停止成功"
            
        except Exception as e:
            return False, f"停止異常: {str(e)}"
    
    def is_running(self):
        """檢查模組是否運行中"""
        if self.process is None:
            return False
        
        return self.process.poll() is None
    
    def get_status(self):
        """獲取模組狀態"""
        if self.is_running():
            return "運行中"
        else:
            return "停止"

class StatusMonitor:
    """狀態監控器"""
    
    def __init__(self, socketio, startup_manager):
        self.socketio = socketio
        self.startup_manager = startup_manager
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """開始狀態監控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止狀態監控"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
    
    def _monitor_loop(self):
        """監控循環"""
        while self.monitoring:
            try:
                status_data = self._collect_status()
                self.socketio.emit('status_update', status_data)
                time.sleep(3)  # 3秒間隔
            except Exception as e:
                print(f"狀態監控錯誤: {e}")
                time.sleep(3)
    
    def _collect_status(self):
        """收集所有狀態"""
        status = {
            'modbus_server': self._check_modbus_server(),
            'modules': {},
            'web_apps': {},
            'com_ports': self._scan_com_ports(),
            'timestamp': time.time()
        }
        
        # 檢查主模組狀態
        for name, controller in self.startup_manager.modules.items():
            status['modules'][name] = {
                'status': controller.get_status(),
                'running': controller.is_running()
            }
        
        # 檢查WebUI狀態
        for name, controller in self.startup_manager.web_apps.items():
            status['web_apps'][name] = {
                'status': controller.get_status(),
                'running': controller.is_running(),
                'port_active': self._check_port(self.startup_manager.web_ports.get(name.replace('_app', ''), 0))
            }
        
        return status
    
    def _check_modbus_server(self):
        """檢查ModbusTCP服務器狀態"""
        return self._check_port(502)
    
    def _check_port(self, port):
        """檢查端口是否被佔用"""
        if port == 0:
            return False
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                return result == 0
        except Exception:
            return False
    
    def _scan_com_ports(self):
        """掃描可用COM口"""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception:
            return []

class StartupManager:
    """啟動管理器主類別"""
    
    def __init__(self):
        self.modbus_server = None
        self.modules = {}
        self.web_apps = {}
        self.web_ports = {
            'CCD1': 5051,
            'CCD3': 5052,
            'VP': 5053,
            'Gripper': 5054,
            'XC100': 5007,
            'LED': 5008
        }
        
        self._initialize_modules()
    
    def _initialize_modules(self):
        """初始化模組控制器"""
        # 主模組配置
        module_configs = {
            'CCD1': {
                'script': 'Automation/CCD1/CCD1VisionCode_Enhanced.py',
                'config': None,
                'needs_com': False
            },
            'CCD3': {
                'script': 'Automation/CCD3/CCD3AngleDetection.py',
                'config': None,
                'needs_com': False
            },
            'Gripper': {
                'script': 'Automation/Gripper/Gripper.py',
                'config': 'Automation/Gripper/gripper_config.json',
                'needs_com': True
            },
            'LED': {
                'script': 'Automation/light/LED_main.py',
                'config': 'Automation/light/led_config.json',
                'needs_com': True
            },
            'VP': {
                'script': 'Automation/VP/VP_main.py',
                'config': 'Automation/VP/vp_config.json',
                'needs_com': False
            },
            'XC100': {
                'script': 'Automation/XC100/XCModule.py',
                'config': 'Automation/XC100/xc_module_config.json',
                'needs_com': True
            }
        }
        
        # WebUI模組配置
        web_configs = {
            'Gripper_app': {
                'script': 'Automation/Gripper/Gripper_app.py',
                'config': 'Automation/Gripper/gripper_app_config.json',
                'needs_com': False
            },
            'LED_app': {
                'script': 'Automation/light/LED_app.py',
                'config': None,
                'needs_com': False
            },
            'VP_app': {
                'script': 'Automation/VP/VP_app.py',
                'config': 'Automation/VP/vp_app_config.json',
                'needs_com': False
            },
            'XC_app': {
                'script': 'Automation/XC100/XCApp.py',
                'config': None,
                'needs_com': False
            }
        }
        
        # 創建主模組控制器
        for name, config in module_configs.items():
            config_path = os.path.join(PROJECT_ROOT, config['config']) if config['config'] else None
            self.modules[name] = ModuleController(
                name, config['script'], config_path, config['needs_com']
            )
        
        # 創建WebUI控制器
        for name, config in web_configs.items():
            config_path = os.path.join(PROJECT_ROOT, config['config']) if config['config'] else None
            self.web_apps[name] = ModuleController(
                name, config['script'], config_path, config['needs_com']
            )
        
        # ModbusTCP服務器控制器
        self.modbus_server = ModuleController(
            'ModbusTCP_Server', 'ModbusServer/TCPServer.py'
        )
    
    def start_modbus_server(self):
        """啟動ModbusTCP服務器"""
        if self._check_port_occupied(502):
            return False, "端口502已被佔用"
        
        return self.modbus_server.start()
    
    def stop_modbus_server(self):
        """停止ModbusTCP服務器"""
        return self.modbus_server.stop()
    
    def start_module(self, module_name, com_port=None):
        """啟動模組"""
        if module_name in self.modules:
            return self.modules[module_name].start(com_port)
        elif module_name in self.web_apps:
            return self.web_apps[module_name].start(com_port)
        else:
            return False, f"未知模組: {module_name}"
    
    def stop_module(self, module_name):
        """停止模組"""
        if module_name in self.modules:
            return self.modules[module_name].stop()
        elif module_name in self.web_apps:
            return self.web_apps[module_name].stop()
        else:
            return False, f"未知模組: {module_name}"
    
    def get_module_status(self, module_name):
        """獲取模組狀態"""
        if module_name in self.modules:
            return self.modules[module_name].get_status()
        elif module_name in self.web_apps:
            return self.web_apps[module_name].get_status()
        else:
            return "未知"
    
    def get_com_port_config(self, module_name):
        """獲取模組COM口配置"""
        if module_name in self.modules:
            controller = self.modules[module_name]
            if controller.config_path and controller.needs_com:
                return ConfigManager.read_com_port(controller.config_path, module_name)
        return None
    
    def scan_com_ports(self):
        """掃描可用COM口"""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception:
            return []
    
    def _check_port_occupied(self, port):
        """檢查端口是否被佔用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                return result == 0
        except Exception:
            return False

# Flask應用
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'dobot_m1_startup_tool_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局管理器
startup_manager = StartupManager()
status_monitor = StatusMonitor(socketio, startup_manager)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/modbus_server/start', methods=['POST'])
def start_modbus_server():
    success, message = startup_manager.start_modbus_server()
    return jsonify({'success': success, 'message': message})

@app.route('/api/modbus_server/stop', methods=['POST'])
def stop_modbus_server():
    success, message = startup_manager.stop_modbus_server()
    return jsonify({'success': success, 'message': message})

@app.route('/api/modbus_server/status', methods=['GET'])
def get_modbus_server_status():
    return jsonify({
        'running': startup_manager.modbus_server.is_running(),
        'status': startup_manager.modbus_server.get_status()
    })

@app.route('/api/modules/<module_name>/start', methods=['POST'])
def start_module(module_name):
    data = request.json or {}
    com_port = data.get('com_port')
    
    success, message = startup_manager.start_module(module_name, com_port)
    return jsonify({'success': success, 'message': message})

@app.route('/api/modules/<module_name>/stop', methods=['POST'])
def stop_module(module_name):
    success, message = startup_manager.stop_module(module_name)
    return jsonify({'success': success, 'message': message})

@app.route('/api/modules/<module_name>/status', methods=['GET'])
def get_module_status(module_name):
    status = startup_manager.get_module_status(module_name)
    com_config = startup_manager.get_com_port_config(module_name)
    
    return jsonify({
        'status': status,
        'com_port': com_config
    })

@app.route('/api/com_ports', methods=['GET'])
def get_com_ports():
    ports = startup_manager.scan_com_ports()
    return jsonify({'ports': ports})

@app.route('/api/config/<module_name>/com', methods=['PUT'])
def update_com_config(module_name):
    data = request.json
    new_com = data.get('com_port')
    
    if module_name in startup_manager.modules:
        controller = startup_manager.modules[module_name]
        if controller.config_path and controller.needs_com:
            success = ConfigManager.update_com_port(controller.config_path, module_name, new_com)
            return jsonify({
                'success': success,
                'message': f'COM口配置{"更新成功" if success else "更新失敗"}'
            })
    
    return jsonify({'success': False, 'message': '模組不支援COM口配置'})

@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'DobotM1專案啟動工具已連接'})

@socketio.on('start_monitoring')
def handle_start_monitoring():
    status_monitor.start_monitoring()
    emit('monitoring_started', {'message': '狀態監控已啟動'})

@socketio.on('stop_monitoring')
def handle_stop_monitoring():
    status_monitor.stop_monitoring()
    emit('monitoring_stopped', {'message': '狀態監控已停止'})

if __name__ == '__main__':
    print("DobotM1專案啟動工具啟動中...")
    print(f"專案根目錄: {PROJECT_ROOT}")
    print(f"Web介面: http://localhost:8081")
    
    try:
        socketio.run(app, host='0.0.0.0', port=8081, debug=False)
    except KeyboardInterrupt:
        print("\n正在關閉啟動工具...")
        status_monitor.stop_monitoring()
    except Exception as e:
        print(f"啟動工具錯誤: {e}")
        status_monitor.stop_monitoring()