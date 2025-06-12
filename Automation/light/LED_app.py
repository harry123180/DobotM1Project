#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LED_app.py - LED[U+63A7][U+5236][U+5668]Web UI[U+61C9][U+7528]
[U+7D14]ModbusTCP Client[U+5BE6][U+73FE][U+FF0C][U+53C3][U+8003]VP_app.py[U+67B6][U+69CB]
"""

import os
import json
import time
import threading
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from pymodbus.client import ModbusTcpClient
import logging

class LEDWebApp:
    """LED[U+63A7][U+5236][U+5668]Web[U+61C9][U+7528] - [U+7D14]ModbusTCP Client"""
    
    def __init__(self, config_file="led_app_config.json"):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.current_dir, config_file)
        self.load_config()
        
        # Flask[U+61C9][U+7528][U+521D][U+59CB][U+5316] - [U+6A21][U+677F][U+8DEF][U+5F91][U+8A2D][U+70BA][U+57F7][U+884C][U+6A94][U+540C][U+5C64][U+7684]templates[U+76EE][U+9304]
        template_dir = os.path.join(self.current_dir, 'templates')
        self.app = Flask(__name__, template_folder=template_dir)
        self.app.config['SECRET_KEY'] = 'led_controller_web_secret_key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Modbus TCP Client ([U+9023][U+63A5][U+4E3B][U+670D][U+52D9][U+5668])
        self.modbus_client = None
        self.connected_to_server = False
        self.base_address = self.config["modbus_mapping"]["base_address"]
        
        # [U+72C0][U+614B][U+76E3][U+63A7]
        self.monitor_thread = None
        self.monitoring = False
        
        # [U+8A2D][U+7F6E][U+8DEF][U+7531][U+548C][U+4E8B][U+4EF6]
        self.setup_routes()
        self.setup_socketio_events()
        
        # [U+8A2D][U+7F6E][U+65E5][U+8A8C]
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def load_config(self):
        """[U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848]"""
        default_config = {
            "module_id": "LED[U+63A7][U+5236][U+5668]Web UI",
            "tcp_server": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 3.0
            },
            "modbus_mapping": {
                "base_address": 500
            },
            "web_server": {
                "host": "0.0.0.0", 
                "port": 5008,
                "debug": False
            },
            "ui_settings": {
                "refresh_interval": 2.0,
                "auto_refresh": True
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                self.logger.error(f"[U+8F09][U+5165][U+914D][U+7F6E][U+5931][U+6557]: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """[U+4FDD][U+5B58][U+914D][U+7F6E][U+6A94][U+6848]"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"[U+4FDD][U+5B58][U+914D][U+7F6E][U+5931][U+6557]: {e}")
    
    def connect_server(self) -> bool:
        """[U+9023][U+63A5]Modbus TCP[U+670D][U+52D9][U+5668]"""
        try:
            if self.modbus_client and self.modbus_client.connected:
                return True
                
            tcp_config = self.config["tcp_server"]
            self.modbus_client = ModbusTcpClient(
                host=tcp_config["host"],
                port=tcp_config["port"],
                timeout=tcp_config["timeout"]
            )
            
            if self.modbus_client.connect():
                self.connected_to_server = True
                self.logger.info(f"[U+9023][U+63A5][U+670D][U+52D9][U+5668][U+6210][U+529F]: {tcp_config['host']}:{tcp_config['port']}")
                return True
            else:
                self.connected_to_server = False
                return False
                
        except Exception as e:
            self.logger.error(f"[U+9023][U+63A5][U+670D][U+52D9][U+5668][U+5931][U+6557]: {e}")
            self.connected_to_server = False
            return False
    
    def read_status(self) -> dict:
        """[U+8B80][U+53D6]LED[U+72C0][U+614B] ([U+5F9E]LED_main.py[U+7684][U+5BC4][U+5B58][U+5668])"""
        try:
            if not self.connected_to_server:
                if not self.connect_server():
                    return {"error": "[U+7121][U+6CD5][U+9023][U+63A5][U+670D][U+52D9][U+5668]"}
            
            # [U+8B80][U+53D6][U+72C0][U+614B][U+5BC4][U+5B58][U+5668] (500-515)
            result = self.modbus_client.read_holding_registers(
                address=self.base_address,
                count=16,
                slave=self.config["tcp_server"]["unit_id"]
            )
            if result.isError():
                return {"error": "[U+8B80][U+53D6][U+72C0][U+614B][U+5931][U+6557]"}
            
            registers = result.registers
            
            status_map = {
                0: "[U+96E2][U+7DDA]", 1: "[U+9592][U+7F6E]", 2: "[U+57F7][U+884C][U+4E2D]", 3: "[U+521D][U+59CB][U+5316]", 4: "[U+932F][U+8AA4]"
            }
            
            return {
                "module_status": status_map.get(registers[0], "[U+672A][U+77E5]"),
                "device_connection": "[U+5DF2][U+9023][U+63A5]" if registers[1] else "[U+65B7][U+958B]",
                "active_channels": registers[2],
                "error_code": registers[3],
                "channels": {
                    "L1": {"state": bool(registers[4]), "brightness": registers[8]},
                    "L2": {"state": bool(registers[5]), "brightness": registers[9]},
                    "L3": {"state": bool(registers[6]), "brightness": registers[10]},
                    "L4": {"state": bool(registers[7]), "brightness": registers[11]}
                },
                "operation_count": registers[12],
                "error_count": registers[13],
                "timestamp": registers[15],
                "base_address": self.base_address
            }
            
        except Exception as e:
            self.logger.error(f"[U+8B80][U+53D6][U+72C0][U+614B][U+5931][U+6557]: {e}")
            return {"error": str(e)}
    
    def send_command(self, command: int, param1: int = 0, param2: int = 0) -> bool:
        """[U+767C][U+9001][U+6307][U+4EE4][U+5230]LED_main.py"""
        try:
            if not self.connected_to_server:
                if not self.connect_server():
                    return False
            
            command_address = self.base_address + 20  # 520
            command_id = int(time.time() * 1000) % 65536
            
            values = [command, param1, param2, command_id, 0]
            
            result = self.modbus_client.write_registers(
                address=command_address,
                values=values,
                slave=self.config["tcp_server"]["unit_id"]
            )
            
            return not result.isError()
            
        except Exception as e:
            self.logger.error(f"[U+767C][U+9001][U+6307][U+4EE4][U+5931][U+6557]: {e}")
            return False
    
    def setup_routes(self):
        """[U+8A2D][U+7F6E]Flask[U+8DEF][U+7531]"""
        
        @self.app.route('/')
        def index():
            return render_template('led_index.html')
        
        @self.app.route('/api/status')
        def api_status():
            status = self.read_status()
            return jsonify(status)
        
        @self.app.route('/api/connect', methods=['POST'])
        def api_connect():
            success = self.connect_server()
            return jsonify({"success": success})
        
        @self.app.route('/api/channel/brightness', methods=['POST'])
        def api_set_brightness():
            data = request.get_json()
            channel = data.get('channel', 1)
            brightness = data.get('brightness', 0)
            
            if not (1 <= channel <= 4):
                return jsonify({"success": False, "error": "[U+901A][U+9053][U+865F][U+5FC5][U+9808][U+5728]1-4[U+4E4B][U+9593]"})
            if not (0 <= brightness <= 511):
                return jsonify({"success": False, "error": "[U+4EAE][U+5EA6][U+5FC5][U+9808][U+5728]0-511[U+4E4B][U+9593]"})
            
            # [U+6307][U+4EE4]4: [U+8A2D][U+5B9A][U+55AE][U+4E00][U+901A][U+9053][U+4EAE][U+5EA6]
            success = self.send_command(4, channel, brightness)
            return jsonify({"success": success})
        
        @self.app.route('/api/channel/on', methods=['POST'])
        def api_turn_on():
            data = request.get_json()
            channel = data.get('channel', 1)
            
            if not (1 <= channel <= 4):
                return jsonify({"success": False, "error": "[U+901A][U+9053][U+865F][U+5FC5][U+9808][U+5728]1-4[U+4E4B][U+9593]"})
            
            # [U+6307][U+4EE4]5: [U+958B][U+555F][U+55AE][U+4E00][U+901A][U+9053]
            success = self.send_command(5, channel, 0)
            return jsonify({"success": success})
        
        @self.app.route('/api/channel/off', methods=['POST'])
        def api_turn_off():
            data = request.get_json()
            channel = data.get('channel', 1)
            
            if not (1 <= channel <= 4):
                return jsonify({"success": False, "error": "[U+901A][U+9053][U+865F][U+5FC5][U+9808][U+5728]1-4[U+4E4B][U+9593]"})
            
            # [U+6307][U+4EE4]6: [U+95DC][U+9589][U+55AE][U+4E00][U+901A][U+9053]
            success = self.send_command(6, channel, 0)
            return jsonify({"success": success})
        
        @self.app.route('/api/all_on', methods=['POST'])
        def api_all_on():
            # [U+6307][U+4EE4]1: [U+5168][U+90E8][U+958B][U+555F]
            success = self.send_command(1, 0, 0)
            return jsonify({"success": success})
        
        @self.app.route('/api/all_off', methods=['POST'])
        def api_all_off():
            # [U+6307][U+4EE4]2: [U+5168][U+90E8][U+95DC][U+9589]
            success = self.send_command(2, 0, 0)
            return jsonify({"success": success})
        
        @self.app.route('/api/reset', methods=['POST'])
        def api_reset():
            # [U+6307][U+4EE4]3: [U+91CD][U+7F6E][U+8A2D][U+5099]
            success = self.send_command(3, 0, 0)
            return jsonify({"success": success})
        
        @self.app.route('/api/error_reset', methods=['POST'])
        def api_error_reset():
            # [U+6307][U+4EE4]7: [U+932F][U+8AA4][U+91CD][U+7F6E]
            success = self.send_command(7, 0, 0)
            return jsonify({"success": success})
    
    def setup_socketio_events(self):
        """[U+8A2D][U+7F6E]SocketIO[U+4E8B][U+4EF6]"""
        
        @self.socketio.on('connect')
        def handle_connect():
            print('[U+5BA2][U+6236][U+7AEF][U+5DF2][U+9023][U+63A5]')
            emit('status', self.read_status())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            print('[U+5BA2][U+6236][U+7AEF][U+5DF2][U+65B7][U+958B]')
        
        @self.socketio.on('get_status')
        def handle_get_status():
            status = self.read_status()
            emit('status', status)
        
        @self.socketio.on('set_brightness')
        def handle_set_brightness(data):
            channel = data.get('channel', 1)
            brightness = data.get('brightness', 0)
            
            if 1 <= channel <= 4 and 0 <= brightness <= 511:
                success = self.send_command(4, channel, brightness)
                emit('command_result', {"success": success, "command": "set_brightness"})
            else:
                emit('command_result', {"success": False, "error": "[U+53C3][U+6578][U+7BC4][U+570D][U+932F][U+8AA4]"})
        
        @self.socketio.on('channel_control')
        def handle_channel_control(data):
            channel = data.get('channel', 1)
            action = data.get('action', 'off')
            
            if not (1 <= channel <= 4):
                emit('command_result', {"success": False, "error": "[U+901A][U+9053][U+865F][U+932F][U+8AA4]"})
                return
            
            if action == 'on':
                success = self.send_command(5, channel, 0)
            else:
                success = self.send_command(6, channel, 0)
                
            emit('command_result', {"success": success, "command": f"channel_{action}"})
        
        @self.socketio.on('global_control')
        def handle_global_control(data):
            action = data.get('action', 'all_off')
            
            if action == 'all_on':
                success = self.send_command(1, 0, 0)
            elif action == 'all_off':
                success = self.send_command(2, 0, 0)
            elif action == 'reset':
                success = self.send_command(3, 0, 0)
            elif action == 'error_reset':
                success = self.send_command(7, 0, 0)
            else:
                success = False
                
            emit('command_result', {"success": success, "command": action})
    
    def status_monitor(self):
        """[U+72C0][U+614B][U+76E3][U+63A7][U+7DDA][U+7A0B]"""
        while self.monitoring:
            try:
                status = self.read_status()
                self.socketio.emit('status_update', status)
                time.sleep(self.config["ui_settings"]["refresh_interval"])
            except Exception as e:
                self.logger.error(f"[U+72C0][U+614B][U+76E3][U+63A7][U+932F][U+8AA4]: {e}")
                time.sleep(1)
    
    def start_monitoring(self):
        """[U+555F][U+52D5][U+72C0][U+614B][U+76E3][U+63A7]"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.status_monitor, daemon=True)
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """[U+505C][U+6B62][U+72C0][U+614B][U+76E3][U+63A7]"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
    
    def run(self):
        """[U+904B][U+884C]Web[U+61C9][U+7528]"""
        web_config = self.config["web_server"]
        
        print(f"LED[U+63A7][U+5236][U+5668]Web[U+61C9][U+7528][U+555F][U+52D5][U+4E2D]...")
        print(f"[U+6A21][U+7D44]ID: {self.config['module_id']}")
        print(f"Web[U+670D][U+52D9][U+5668]: http://{web_config['host']}:{web_config['port']}")
        print(f"Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740]: {self.config['tcp_server']['host']}:{self.config['tcp_server']['port']}")
        print(f"LED[U+63A7][U+5236][U+5668][U+57FA][U+5730][U+5740]: {self.base_address}")
        print("[U+67B6][U+69CB]: [U+7D14]ModbusTCP Client -> LED_main.py")
        
        # [U+5617][U+8A66][U+9023][U+63A5][U+670D][U+52D9][U+5668]
        self.connect_server()
        
        # [U+555F][U+52D5][U+72C0][U+614B][U+76E3][U+63A7]
        if self.config["ui_settings"]["auto_refresh"]:
            self.start_monitoring()
        
        # [U+904B][U+884C]Flask[U+61C9][U+7528]
        self.socketio.run(
            self.app,
            host=web_config["host"],
            port=web_config["port"],
            debug=web_config["debug"]
        )

def main():
    """[U+4E3B][U+51FD][U+6578]"""
    print("LED[U+63A7][U+5236][U+5668]Web UI[U+555F][U+52D5][U+4E2D]...")
    print("[U+67B6][U+69CB]: Web UI -> ModbusTCP Client -> LED_main.py")
    
    app = LEDWebApp()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[U+6536][U+5230][U+505C][U+6B62][U+4FE1][U+865F]...")
        app.stop_monitoring()
    except Exception as e:
        print(f"[U+61C9][U+7528][U+932F][U+8AA4]: {e}")
        app.stop_monitoring()

if __name__ == "__main__":
    main()