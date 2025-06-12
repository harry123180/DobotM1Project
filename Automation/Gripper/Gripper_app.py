# -*- coding: utf-8 -*-
# Gripper_app.py - [U+593E][U+722A]Web[U+63A7][U+5236][U+61C9][U+7528]
import os
import json
import time
import threading
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

class GripperWebApp:
    def __init__(self, config_file="gripper_app_config.json"):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.current_dir, config_file)
        self.config = self.load_config()
        
        # Flask[U+61C9][U+7528]
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'gripper_secret_key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Modbus[U+5BA2][U+6236][U+7AEF]
        self.modbus_client = None
        self.is_connected = False
        
        # [U+76E3][U+63A7][U+7DDA][U+7A0B][U+63A7][U+5236]
        self.monitoring_active = False
        self.monitor_thread = None
        
        # [U+5BC4][U+5B58][U+5668][U+6620][U+5C04]
        self.register_mapping = {
            'PGC': {'status_base': 500, 'command_base': 520},
            'PGHL': {'status_base': 530, 'command_base': 550},
            'PGE': {'status_base': 560, 'command_base': 580}
        }
        
        # [U+8A2D][U+7F6E][U+8DEF][U+7531]
        self.setup_routes()
        self.setup_socketio()
        
        print("[U+593E][U+722A]Web[U+63A7][U+5236][U+61C9][U+7528][U+555F][U+52D5][U+4E2D]...")
        print(f"Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740]: {self.config['modbus_tcp']['host']}:{self.config['modbus_tcp']['port']}")
        print("[U+593E][U+722A][U+5BC4][U+5B58][U+5668][U+6620][U+5C04]:")
        for gripper, mapping in self.register_mapping.items():
            print(f"  {gripper}: [U+72C0][U+614B] {mapping['status_base']}-{mapping['status_base']+19}, [U+6307][U+4EE4] {mapping['command_base']}-{mapping['command_base']+9}")

    def load_config(self):
        default_config = {
            "module_id": "[U+593E][U+722A]Web UI",
            "modbus_tcp": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 1.0
            },
            "web_server": {
                "host": "0.0.0.0",
                "port": 5054,
                "debug": False
            },
            "ui_settings": {
                "refresh_interval": 3.0,
                "manual_mode": False
            },
            "grippers": {
                "PGC": {
                    "name": "PGC[U+593E][U+722A]",
                    "enabled": True,
                    "positions": {"open": 1000, "close": 0},
                    "max_force": 100,
                    "max_speed": 100
                },
                "PGHL": {
                    "name": "PGHL[U+593E][U+722A]", 
                    "enabled": True,
                    "positions": {"open": 5000, "close": 0},
                    "max_force": 100,
                    "max_speed": 100
                },
                "PGE": {
                    "name": "PGE[U+593E][U+722A]",
                    "enabled": True,
                    "positions": {"open": 1000, "close": 0},
                    "max_force": 100,
                    "max_speed": 100
                }
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[U+914D][U+7F6E][U+6A94][U+6848][U+8B80][U+53D6][U+932F][U+8AA4]: {e}")
                return default_config
        else:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config

    def connect_modbus(self):
        try:
            if self.modbus_client and self.modbus_client.connected:
                return True
                
            self.modbus_client = ModbusTcpClient(
                host=self.config["modbus_tcp"]["host"],
                port=self.config["modbus_tcp"]["port"],
                timeout=self.config["modbus_tcp"]["timeout"]
            )
            
            if self.modbus_client.connect():
                self.is_connected = True
                print(f"[U+5DF2][U+9023][U+63A5]Modbus[U+670D][U+52D9][U+5668]: {self.config['modbus_tcp']['host']}:{self.config['modbus_tcp']['port']}")
                return True
            else:
                self.is_connected = False
                return False
        except Exception as e:
            print(f"Modbus[U+9023][U+63A5][U+932F][U+8AA4]: {e}")
            self.is_connected = False
            return False

    def read_gripper_status(self, gripper_type):
        """[U+8B80][U+53D6][U+593E][U+722A][U+72C0][U+614B]"""
        try:
            if not self.is_connected:
                return None
                
            status_base = self.register_mapping[gripper_type]['status_base']
            
            result = self.modbus_client.read_holding_registers(
                address=status_base,
                count=20,
                slave=self.config["modbus_tcp"]["unit_id"]
            )
            
            if result.isError():
                return None
                
            registers = result.registers
            
            status_data = {
                'module_status': registers[0],
                'connected': bool(registers[1]),
                'device_status': registers[2],
                'error_count': registers[3],
                'grip_status': registers[4],
                'position': registers[5],
                'current': registers[6] if len(registers) > 6 else 0,
                'timestamp': registers[14] if len(registers) > 14 else 0
            }
            
            return status_data
            
        except Exception as e:
            print(f"[U+8B80][U+53D6]{gripper_type}[U+72C0][U+614B][U+932F][U+8AA4]: {e}")
            return None

    def send_gripper_command(self, gripper_type, command, param1=0, param2=0):
        """[U+767C][U+9001][U+593E][U+722A][U+6307][U+4EE4]"""
        try:
            if not self.is_connected:
                return False
                
            command_base = self.register_mapping[gripper_type]['command_base']
            command_id = int(time.time() * 1000) % 65535  # [U+751F][U+6210][U+552F][U+4E00][U+6307][U+4EE4]ID
            
            values = [command, param1, param2, command_id, 0, 0, 0, 0, 0, 0]
            
            result = self.modbus_client.write_registers(
                address=command_base,
                values=values,
                slave=self.config["modbus_tcp"]["unit_id"]
            )
            
            return not result.isError() if result else False
            
        except Exception as e:
            print(f"[U+767C][U+9001]{gripper_type}[U+6307][U+4EE4][U+932F][U+8AA4]: {e}")
            return False

    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html', 
                                 config=self.config,
                                 register_mapping=self.register_mapping)

        @self.app.route('/api/connect', methods=['POST'])
        def connect():
            success = self.connect_modbus()
            return jsonify({
                'success': success,
                'message': '[U+9023][U+63A5][U+6210][U+529F]' if success else '[U+9023][U+63A5][U+5931][U+6557]'
            })

        @self.app.route('/api/status/<gripper_type>')
        def get_status(gripper_type):
            if gripper_type not in self.register_mapping:
                return jsonify({'error': '[U+7121][U+6548][U+7684][U+593E][U+722A][U+985E][U+578B]'}), 400
                
            status = self.read_gripper_status(gripper_type)
            return jsonify({
                'success': status is not None,
                'status': status,
                'connected': self.is_connected
            })

        @self.app.route('/api/command/<gripper_type>', methods=['POST'])
        def send_command(gripper_type):
            if gripper_type not in self.register_mapping:
                return jsonify({'error': '[U+7121][U+6548][U+7684][U+593E][U+722A][U+985E][U+578B]'}), 400
                
            data = request.get_json()
            command = data.get('command', 0)
            param1 = data.get('param1', 0)
            param2 = data.get('param2', 0)
            
            success = self.send_gripper_command(gripper_type, command, param1, param2)
            return jsonify({
                'success': success,
                'message': '[U+6307][U+4EE4][U+767C][U+9001][U+6210][U+529F]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

        @self.app.route('/api/initialize/<gripper_type>', methods=['POST'])
        def initialize_gripper(gripper_type):
            success = self.send_gripper_command(gripper_type, 1)  # [U+6307][U+4EE4]1: [U+521D][U+59CB][U+5316]
            return jsonify({
                'success': success,
                'message': f'{gripper_type}[U+521D][U+59CB][U+5316][U+6307][U+4EE4][U+5DF2][U+767C][U+9001]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

        @self.app.route('/api/stop/<gripper_type>', methods=['POST'])
        def stop_gripper(gripper_type):
            success = self.send_gripper_command(gripper_type, 2)  # [U+6307][U+4EE4]2: [U+505C][U+6B62]
            return jsonify({
                'success': success,
                'message': f'{gripper_type}[U+505C][U+6B62][U+6307][U+4EE4][U+5DF2][U+767C][U+9001]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

        @self.app.route('/api/move/<gripper_type>', methods=['POST'])
        def move_gripper(gripper_type):
            data = request.get_json()
            position = data.get('position', 0)
            
            success = self.send_gripper_command(gripper_type, 3, position)  # [U+6307][U+4EE4]3: [U+7D55][U+5C0D][U+4F4D][U+7F6E]
            return jsonify({
                'success': success,
                'message': f'{gripper_type}[U+79FB][U+52D5][U+6307][U+4EE4][U+5DF2][U+767C][U+9001]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

        @self.app.route('/api/set_force/<gripper_type>', methods=['POST'])
        def set_force(gripper_type):
            data = request.get_json()
            force = data.get('force', 50)
            
            success = self.send_gripper_command(gripper_type, 5, force)  # [U+6307][U+4EE4]5: [U+8A2D][U+5B9A][U+529B][U+9053]
            return jsonify({
                'success': success,
                'message': f'{gripper_type}[U+529B][U+9053][U+8A2D][U+5B9A][U+5DF2][U+767C][U+9001]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

        @self.app.route('/api/set_speed/<gripper_type>', methods=['POST'])
        def set_speed(gripper_type):
            data = request.get_json()
            speed = data.get('speed', 50)
            
            success = self.send_gripper_command(gripper_type, 6, speed)  # [U+6307][U+4EE4]6: [U+8A2D][U+5B9A][U+901F][U+5EA6]
            return jsonify({
                'success': success,
                'message': f'{gripper_type}[U+901F][U+5EA6][U+8A2D][U+5B9A][U+5DF2][U+767C][U+9001]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

        @self.app.route('/api/open/<gripper_type>', methods=['POST'])
        def open_gripper(gripper_type):
            success = self.send_gripper_command(gripper_type, 7)  # [U+6307][U+4EE4]7: [U+958B][U+555F]
            return jsonify({
                'success': success,
                'message': f'{gripper_type}[U+958B][U+555F][U+6307][U+4EE4][U+5DF2][U+767C][U+9001]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

        @self.app.route('/api/close/<gripper_type>', methods=['POST'])
        def close_gripper(gripper_type):
            success = self.send_gripper_command(gripper_type, 8)  # [U+6307][U+4EE4]8: [U+95DC][U+9589]
            return jsonify({
                'success': success,
                'message': f'{gripper_type}[U+95DC][U+9589][U+6307][U+4EE4][U+5DF2][U+767C][U+9001]' if success else '[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
            })

    def setup_socketio(self):
        @self.socketio.on('connect')
        def handle_connect():
            print('[U+5BA2][U+6236][U+7AEF][U+5DF2][U+9023][U+63A5]')
            emit('status', {'connected': True})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            print('[U+5BA2][U+6236][U+7AEF][U+5DF2][U+65B7][U+958B]')

        @self.socketio.on('start_monitoring')
        def handle_start_monitoring():
            self.start_monitoring()
            emit('monitoring_status', {'active': True})

        @self.socketio.on('stop_monitoring')
        def handle_stop_monitoring():
            self.stop_monitoring()
            emit('monitoring_status', {'active': False})

        @self.socketio.on('request_status')
        def handle_request_status():
            self.emit_all_status()

    def start_monitoring(self):
        """[U+555F][U+52D5][U+72C0][U+614B][U+76E3][U+63A7]"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("[U+72C0][U+614B][U+76E3][U+63A7][U+5DF2][U+555F][U+52D5]")

    def stop_monitoring(self):
        """[U+505C][U+6B62][U+72C0][U+614B][U+76E3][U+63A7]"""
        self.monitoring_active = False
        print("[U+72C0][U+614B][U+76E3][U+63A7][U+5DF2][U+505C][U+6B62]")

    def monitor_loop(self):
        """[U+76E3][U+63A7][U+5FAA][U+74B0]"""
        while self.monitoring_active:
            try:
                if self.connect_modbus():
                    self.emit_all_status()
                time.sleep(self.config["ui_settings"]["refresh_interval"])
            except Exception as e:
                print(f"[U+76E3][U+63A7][U+5FAA][U+74B0][U+932F][U+8AA4]: {e}")
                time.sleep(1)

    def emit_all_status(self):
        """[U+767C][U+9001][U+6240][U+6709][U+593E][U+722A][U+72C0][U+614B]"""
        try:
            status_data = {}
            
            for gripper_type in ['PGC', 'PGHL', 'PGE']:
                if self.config["grippers"][gripper_type]["enabled"]:
                    status = self.read_gripper_status(gripper_type)
                    status_data[gripper_type] = status
            
            self.socketio.emit('status_update', {
                'timestamp': time.time(),
                'connected': self.is_connected,
                'grippers': status_data
            })
            
        except Exception as e:
            print(f"[U+72C0][U+614B][U+66F4][U+65B0][U+932F][U+8AA4]: {e}")

    def run(self):
        """[U+555F][U+52D5]Web[U+61C9][U+7528]"""
        print(f"Web[U+670D][U+52D9][U+5668][U+555F][U+52D5] - http://{self.config['web_server']['host']}:{self.config['web_server']['port']}")
        
        # [U+5617][U+8A66][U+9023][U+63A5]Modbus
        self.connect_modbus()
        
        # [U+555F][U+52D5][U+72C0][U+614B][U+76E3][U+63A7]
        if not self.config["ui_settings"]["manual_mode"]:
            self.start_monitoring()
        
        self.socketio.run(
            self.app,
            host=self.config["web_server"]["host"],
            port=self.config["web_server"]["port"],
            debug=self.config["web_server"]["debug"]
        )

if __name__ == "__main__":
    app = GripperWebApp()
    app.run()