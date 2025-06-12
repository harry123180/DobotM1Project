# -*- coding: utf-8 -*-
"""
VP_app.py - [U+9707][U+52D5][U+76E4]Web UI[U+63A7][U+5236][U+61C9][U+7528]
[U+4F5C][U+70BA][U+7D14]Modbus TCP Client[U+9023][U+63A5][U+4E3B][U+670D][U+52D9][U+5668][U+FF0C][U+901A][U+904E]VP_main[U+6A21][U+7D44][U+63A7][U+5236][U+9707][U+52D5][U+76E4]
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
    """[U+9707][U+52D5][U+76E4]Web[U+63A7][U+5236][U+61C9][U+7528] - [U+7D14]Modbus TCP Client"""
    
    def __init__(self):
        # [U+8F09][U+5165][U+914D][U+7F6E]
        self.config = self.load_config()
        
        # Modbus TCP Client ([U+9023][U+63A5][U+4E3B][U+670D][U+52D9][U+5668])
        self.modbus_client: Optional[ModbusTcpClient] = None
        self.connected_to_server = False
        
        # [U+72C0][U+614B][U+76E3][U+63A7]
        self.status_monitor_thread = None
        self.monitoring = False
        
        # [U+5BC4][U+5B58][U+5668][U+6620][U+5C04] ([U+8207]VP_main.py[U+4E00][U+81F4] - [U+57FA][U+5730][U+5740]300)
        self.base_address = self.config['modbus_mapping']['base_address']
        self.init_register_mapping()
        
        # [U+72C0][U+614B][U+5FEB][U+53D6][U+548C][U+6307][U+4EE4][U+8A08][U+6578]
        self.command_id_counter = 1
        
        # [U+521D][U+59CB][U+5316]Flask[U+61C9][U+7528]
        self.init_flask_app()
        
    def load_config(self) -> Dict[str, Any]:
        """[U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848]"""
        default_config = {
            "module_id": "[U+9707][U+52D5][U+76E4]Web UI",
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
                print(f"[U+5DF2][U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848]: {config_path}")
            else:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                print(f"[U+5DF2][U+5275][U+5EFA][U+9810][U+8A2D][U+914D][U+7F6E][U+6A94][U+6848]: {config_path}")
        except Exception as e:
            print(f"[U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848][U+5931][U+6557]: {e}")
            
        return default_config
    
    def init_register_mapping(self):
        """[U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668][U+6620][U+5C04] ([U+8207]VP_main.py[U+4E00][U+81F4])"""
        base = self.base_address  # 300
        
        # [U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+5340] ([U+53EA][U+8B80]) base+0 ~ base+14
        self.status_registers = {
            'module_status': base + 0,          # [U+6A21][U+7D44][U+72C0][U+614B]
            'device_connection': base + 1,      # [U+8A2D][U+5099][U+9023][U+63A5][U+72C0][U+614B]
            'device_status': base + 2,          # [U+8A2D][U+5099][U+72C0][U+614B]
            'error_code': base + 3,             # [U+932F][U+8AA4][U+4EE3][U+78BC]
            'current_action_low': base + 4,     # [U+7576][U+524D][U+52D5][U+4F5C][U+4F4E][U+4F4D]
            'current_action_high': base + 5,    # [U+7576][U+524D][U+52D5][U+4F5C][U+9AD8][U+4F4D]
            'target_action_low': base + 6,      # [U+76EE][U+6A19][U+52D5][U+4F5C][U+4F4E][U+4F4D]
            'target_action_high': base + 7,     # [U+76EE][U+6A19][U+52D5][U+4F5C][U+9AD8][U+4F4D]
            'command_status': base + 8,         # [U+6307][U+4EE4][U+57F7][U+884C][U+72C0][U+614B]
            'comm_error_count': base + 9,       # [U+901A][U+8A0A][U+932F][U+8AA4][U+8A08][U+6578]
            'brightness_status': base + 10,     # [U+80CC][U+5149][U+4EAE][U+5EA6][U+72C0][U+614B]
            'backlight_status': base + 11,      # [U+80CC][U+5149][U+958B][U+95DC][U+72C0][U+614B]
            'vibration_status': base + 12,      # [U+9707][U+52D5][U+72C0][U+614B]
            'reserved_13': base + 13,           # [U+4FDD][U+7559]
            'timestamp': base + 14              # [U+6642][U+9593][U+6233]
        }
        
        # [U+6307][U+4EE4][U+5BC4][U+5B58][U+5668][U+5340] ([U+8B80][U+5BEB]) base+20 ~ base+24
        self.command_registers = {
            'command_code': base + 20,          # [U+6307][U+4EE4][U+4EE3][U+78BC] (320)
            'param1': base + 21,                # [U+53C3][U+6578]1
            'param2': base + 22,                # [U+53C3][U+6578]2
            'command_id': base + 23,            # [U+6307][U+4EE4]ID
            'reserved': base + 24               # [U+4FDD][U+7559]
        }
        
        # VP_main[U+6307][U+4EE4][U+6620][U+5C04]
        self.command_map = {
            'nop': 0,                # [U+7121][U+64CD][U+4F5C]
            'enable_device': 1,      # [U+8A2D][U+5099][U+555F][U+7528] ([U+80CC][U+5149][U+958B][U+555F])
            'disable_device': 2,     # [U+8A2D][U+5099][U+505C][U+7528] ([U+80CC][U+5149][U+95DC][U+9589])
            'stop_all': 3,           # [U+505C][U+6B62][U+6240][U+6709][U+52D5][U+4F5C] [U+2605]
            'set_brightness': 4,     # [U+8A2D][U+5B9A][U+80CC][U+5149][U+4EAE][U+5EA6]
            'execute_action': 5,     # [U+57F7][U+884C][U+52D5][U+4F5C]
            'emergency_stop': 6,     # [U+7DCA][U+6025][U+505C][U+6B62] [U+2605]
            'reset_error': 7,        # [U+932F][U+8AA4][U+91CD][U+7F6E]
        }
        
        # [U+52D5][U+4F5C][U+7DE8][U+78BC][U+6620][U+5C04] ([U+7528][U+65BC]execute_action[U+6307][U+4EE4][U+7684]param1)
        self.action_map = {
            'stop': 0, 'up': 1, 'down': 2, 'left': 3, 'right': 4,
            'upleft': 5, 'downleft': 6, 'upright': 7, 'downright': 8,
            'horizontal': 9, 'vertical': 10, 'spread': 11
        }
        
        print(f"[U+9707][U+52D5][U+76E4]Web UI[U+5BC4][U+5B58][U+5668][U+6620][U+5C04][U+521D][U+59CB][U+5316]:")
        print(f"  [U+4E3B][U+670D][U+52D9][U+5668]: {self.config['tcp_server']['host']}:{self.config['tcp_server']['port']}")
        print(f"  [U+57FA][U+5730][U+5740]: {base}")
        print(f"  [U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]: {base + 20} ~ {base + 24}")
        print(f"  [U+505C][U+6B62][U+6307][U+4EE4]: [U+6307][U+4EE4][U+4EE3][U+78BC]3[U+5BEB][U+5165][U+5BC4][U+5B58][U+5668]{base + 20}")
        
    def init_flask_app(self):
        """[U+521D][U+59CB][U+5316]Flask[U+61C9][U+7528]"""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'vp_web_app_2024'
        
        # [U+521D][U+59CB][U+5316]SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # [U+932F][U+8AA4][U+8655][U+7406]
        @self.app.errorhandler(404)
        def not_found_error(error):
            return jsonify({'success': False, 'message': '[U+8DEF][U+5F91][U+4E0D][U+5B58][U+5728]'}), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({'success': False, 'message': '[U+5167][U+90E8][U+670D][U+52D9][U+5668][U+932F][U+8AA4]'}), 500
        
        @self.app.errorhandler(405)
        def method_not_allowed(error):
            return jsonify({'success': False, 'message': '[U+8ACB][U+6C42][U+65B9][U+6CD5][U+4E0D][U+88AB][U+5141][U+8A31]'}), 405
        
        # [U+8A3B][U+518A][U+8DEF][U+7531]
        self.register_routes()
        self.register_socketio_events()
        
    def register_routes(self):
        """[U+8A3B][U+518A]Flask[U+8DEF][U+7531]"""
        
        @self.app.route('/')
        def index():
            """[U+4E3B][U+9801][U+9762]"""
            return render_template('index.html', config=self.config)
        
        @self.app.route('/api/status')
        def get_status():
            """[U+7372][U+53D6][U+7CFB][U+7D71][U+72C0][U+614B]"""
            return jsonify(self.get_current_status())
        
        @self.app.route('/api/connect', methods=['POST'])
        def connect_server():
            """[U+9023][U+63A5][U+5230][U+4E3B]Modbus TCP[U+670D][U+52D9][U+5668]"""
            try:
                data = request.get_json() or {}
                
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
                    'message': f'[U+9023][U+63A5][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/disconnect', methods=['POST'])
        def disconnect_server():
            """[U+65B7][U+958B]Modbus TCP[U+9023][U+63A5]"""
            try:
                result = self.disconnect_modbus_server()
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+65B7][U+958B][U+9023][U+63A5][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/action', methods=['POST'])
        def execute_action():
            """[U+57F7][U+884C][U+9707][U+52D5][U+52D5][U+4F5C]"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                    })
                
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': '[U+7121][U+6548][U+7684][U+8ACB][U+6C42][U+6578][U+64DA]'
                    })
                
                action = data.get('action')
                strength = data.get('strength', 100)
                
                if not action or action not in self.action_map:
                    return jsonify({
                        'success': False,
                        'message': f'[U+672A][U+77E5][U+52D5][U+4F5C]: {action}'
                    })
                
                # [U+767C][U+9001]execute_action[U+6307][U+4EE4] ([U+6307][U+4EE4]5)
                action_code = self.action_map[action]
                result = self.send_command('execute_action', action_code, strength)
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+57F7][U+884C][U+52D5][U+4F5C][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/execute_action', methods=['POST'])
        def execute_action_alt():
            """[U+57F7][U+884C][U+9707][U+52D5][U+52D5][U+4F5C] ([U+5099][U+7528][U+8DEF][U+5F91])"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                    })
                
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': '[U+7121][U+6548][U+7684][U+8ACB][U+6C42][U+6578][U+64DA]'
                    })
                
                action = data.get('action')
                strength = data.get('strength', 100)
                
                if not action or action not in self.action_map:
                    return jsonify({
                        'success': False,
                        'message': f'[U+672A][U+77E5][U+52D5][U+4F5C]: {action}'
                    })
                
                # [U+767C][U+9001]execute_action[U+6307][U+4EE4] ([U+6307][U+4EE4]5)
                action_code = self.action_map[action]
                result = self.send_command('execute_action', action_code, strength)
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+57F7][U+884C][U+52D5][U+4F5C][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/stop', methods=['POST'])
        def stop_action():
            """[U+505C][U+6B62][U+52D5][U+4F5C] - [U+767C][U+9001][U+505C][U+6B62][U+6307][U+4EE4][U+5230]VP_main"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                    })
                
                # [U+767C][U+9001]stop_all[U+6307][U+4EE4] ([U+6307][U+4EE4]3) [U+5230]VP_main
                result = self.send_command('stop_all')
                
                if result['success']:
                    result['message'] = '[U+505C][U+6B62][U+6307][U+4EE4][U+767C][U+9001][U+6210][U+529F]'
                else:
                    result['message'] = '[U+505C][U+6B62][U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]'
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+505C][U+6B62][U+52D5][U+4F5C][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/emergency_stop', methods=['POST'])
        def emergency_stop():
            """[U+7DCA][U+6025][U+505C][U+6B62]"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                    })
                
                # [U+767C][U+9001]emergency_stop[U+6307][U+4EE4] ([U+6307][U+4EE4]6) [U+5230]VP_main
                result = self.send_command('emergency_stop')
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+7DCA][U+6025][U+505C][U+6B62][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/set_brightness', methods=['POST'])
        def set_brightness():
            """[U+8A2D][U+5B9A][U+80CC][U+5149][U+4EAE][U+5EA6]"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                    })
                
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': '[U+7121][U+6548][U+7684][U+8ACB][U+6C42][U+6578][U+64DA]'
                    })
                
                brightness = data.get('brightness', 128)
                brightness = max(0, min(255, int(brightness)))
                
                # [U+767C][U+9001]set_brightness[U+6307][U+4EE4] ([U+6307][U+4EE4]4)
                result = self.send_command('set_brightness', brightness)
                
                if result['success']:
                    self.config['defaults']['brightness'] = brightness
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+8A2D][U+5B9A][U+4EAE][U+5EA6][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/set_backlight', methods=['POST'])
        def set_backlight():
            """[U+8A2D][U+5B9A][U+80CC][U+5149][U+958B][U+95DC]"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                    })
                
                data = request.get_json()
                if not data:
                    return jsonify({
                        'success': False,
                        'message': '[U+7121][U+6548][U+7684][U+8ACB][U+6C42][U+6578][U+64DA]'
                    })
                
                state = data.get('state', True)
                
                # [U+767C][U+9001][U+80CC][U+5149][U+63A7][U+5236][U+6307][U+4EE4]
                command = 'enable_device' if state else 'disable_device'
                result = self.send_command(command)
                
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+8A2D][U+5B9A][U+80CC][U+5149][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/reset_error', methods=['POST'])
        def reset_error():
            """[U+91CD][U+7F6E][U+932F][U+8AA4]"""
            try:
                if not self.connected_to_server:
                    return jsonify({
                        'success': False,
                        'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                    })
                
                result = self.send_command('reset_error')
                return jsonify(result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+91CD][U+7F6E][U+932F][U+8AA4][U+6642][U+767C][U+751F][U+932F][U+8AA4]: {str(e)}'
                })
        
        @self.app.route('/api/get_register_values', methods=['GET'])
        def get_register_values():
            """[U+7372][U+53D6][U+5BC4][U+5B58][U+5668][U+6578][U+503C]"""
            if not self.connected_to_server:
                return jsonify({
                    'success': False,
                    'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
                })
            
            try:
                # [U+8B80][U+53D6][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
                status_values = {}
                for name, addr in self.status_registers.items():
                    value = self.read_register(addr)
                    status_values[name] = value
                
                # [U+8B80][U+53D6][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]
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
                    'message': f'[U+8B80][U+53D6][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {str(e)}'
                })
        
        @self.app.route('/api/debug', methods=['GET'])
        def debug_info():
            """[U+8ABF][U+8A66][U+8CC7][U+8A0A]"""
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
                    'command_map': self.command_map,
                    'action_map': self.action_map,
                    'command_counter': self.command_id_counter
                }
                return jsonify(debug_data)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+7372][U+53D6][U+8ABF][U+8A66][U+8CC7][U+8A0A][U+5931][U+6557]: {str(e)}'
                })
        
        @self.app.route('/api/routes', methods=['GET'])
        def list_routes():
            """[U+5217][U+51FA][U+6240][U+6709][U+53EF][U+7528][U+8DEF][U+7531]"""
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
                    'message': f'[U+627E][U+5230] {len(routes)} [U+500B][U+8DEF][U+7531]'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'[U+7372][U+53D6][U+8DEF][U+7531][U+5217][U+8868][U+5931][U+6557]: {str(e)}'
                })
    
    def register_socketio_events(self):
        """[U+8A3B][U+518A]SocketIO[U+4E8B][U+4EF6]"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """[U+5BA2][U+6236][U+7AEF][U+9023][U+63A5]"""
            print("Web[U+5BA2][U+6236][U+7AEF][U+5DF2][U+9023][U+63A5]")
            emit('status_update', self.get_current_status())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """[U+5BA2][U+6236][U+7AEF][U+65B7][U+958B]"""
            print("Web[U+5BA2][U+6236][U+7AEF][U+5DF2][U+65B7][U+958B]")
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """[U+72C0][U+614B][U+8ACB][U+6C42]"""
            emit('status_update', self.get_current_status())
    
    def connect_modbus_server(self) -> Dict[str, Any]:
        """[U+9023][U+63A5][U+5230][U+4E3B]Modbus TCP[U+670D][U+52D9][U+5668]"""
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
                print(f"[U+9023][U+63A5][U+5230][U+4E3B]Modbus[U+670D][U+52D9][U+5668][U+6210][U+529F]: {server_config['host']}:{server_config['port']}")
                
                return {
                    'success': True,
                    'message': '[U+4E3B]Modbus[U+670D][U+52D9][U+5668][U+9023][U+63A5][U+6210][U+529F]',
                    'server_info': server_config
                }
            else:
                self.connected_to_server = False
                return {
                    'success': False,
                    'message': '[U+4E3B]Modbus[U+670D][U+52D9][U+5668][U+9023][U+63A5][U+5931][U+6557]'
                }
                
        except Exception as e:
            self.connected_to_server = False
            print(f"[U+9023][U+63A5][U+4E3B]Modbus[U+670D][U+52D9][U+5668][U+5931][U+6557]: {e}")
            return {
                'success': False,
                'message': f'[U+9023][U+63A5][U+5931][U+6557]: {str(e)}'
            }
    
    def disconnect_modbus_server(self) -> Dict[str, Any]:
        """[U+65B7][U+958B]Modbus TCP[U+9023][U+63A5]"""
        try:
            self.stop_monitoring()
            
            if self.modbus_client:
                self.modbus_client.close()
                self.modbus_client = None
            
            self.connected_to_server = False
            print("[U+4E3B]Modbus[U+670D][U+52D9][U+5668][U+9023][U+63A5][U+5DF2][U+65B7][U+958B]")
            
            return {
                'success': True,
                'message': '[U+4E3B]Modbus[U+670D][U+52D9][U+5668][U+9023][U+63A5][U+5DF2][U+65B7][U+958B]'
            }
            
        except Exception as e:
            print(f"[U+65B7][U+958B][U+9023][U+63A5][U+5931][U+6557]: {e}")
            return {
                'success': False,
                'message': f'[U+65B7][U+958B][U+9023][U+63A5][U+5931][U+6557]: {str(e)}'
            }
    
    def read_register(self, address: int) -> Optional[int]:
        """[U+8B80][U+53D6][U+5BC4][U+5B58][U+5668]"""
        if not self.connected_to_server or not self.modbus_client:
            return None
        
        try:
            result = self.modbus_client.read_holding_registers(
                address, count=1, slave=self.config['tcp_server']['unit_id']
            )
            
            if not result.isError():
                return result.registers[0]
            else:
                return None
                
        except Exception as e:
            self.connected_to_server = False
            return None
    
    def write_register(self, address: int, value: int) -> bool:
        """[U+5BEB][U+5165][U+5BC4][U+5B58][U+5668]"""
        if not self.connected_to_server or not self.modbus_client:
            return False
        
        try:
            result = self.modbus_client.write_register(
                address, value, slave=self.config['tcp_server']['unit_id']
            )
            
            return not result.isError()
                
        except Exception as e:
            self.connected_to_server = False
            return False
    
    def send_command(self, command: str, param1: int = 0, param2: int = 0) -> Dict[str, Any]:
        """[U+767C][U+9001][U+6307][U+4EE4][U+5230]VP_main[U+6A21][U+7D44]"""
        if not self.connected_to_server:
            return {
                'success': False,
                'message': '[U+4E3B][U+670D][U+52D9][U+5668][U+672A][U+9023][U+63A5]'
            }
        
        if command not in self.command_map:
            return {
                'success': False,
                'message': f'[U+672A][U+77E5][U+6307][U+4EE4]: {command}'
            }
        
        try:
            command_code = self.command_map[command]
            self.command_id_counter += 1
            
            # [U+5BEB][U+5165][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668] ([U+72C0][U+614B][U+6A5F][U+4EA4][U+63E1])
            write_results = []
            write_results.append(self.write_register(self.command_registers['command_code'], command_code))
            write_results.append(self.write_register(self.command_registers['param1'], param1))
            write_results.append(self.write_register(self.command_registers['param2'], param2))
            write_results.append(self.write_register(self.command_registers['command_id'], self.command_id_counter))
            
            success = all(write_results)
            
            if success:
                print(f"[U+767C][U+9001][U+6307][U+4EE4][U+6210][U+529F]: {command} (code={command_code}, p1={param1}, p2={param2}, id={self.command_id_counter})")
                return {
                    'success': True,
                    'message': f'[U+6307][U+4EE4] {command} [U+767C][U+9001][U+6210][U+529F]',
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
                    'message': f'[U+6307][U+4EE4] {command} [U+767C][U+9001][U+5931][U+6557][U+FF0C][U+5BEB][U+5165][U+5931][U+6557][U+7684][U+5BC4][U+5B58][U+5668]: {failed_writes}'
                }
                
        except Exception as e:
            print(f"[U+767C][U+9001][U+6307][U+4EE4][U+7570][U+5E38]: {e}")
            return {
                'success': False,
                'message': f'[U+767C][U+9001][U+6307][U+4EE4][U+7570][U+5E38]: {str(e)}'
            }
    
    def start_monitoring(self):
        """[U+958B][U+59CB][U+72C0][U+614B][U+76E3][U+63A7]"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.status_monitor_thread = threading.Thread(target=self.status_monitor_loop, daemon=True)
        self.status_monitor_thread.start()
        print("[U+72C0][U+614B][U+76E3][U+63A7][U+5DF2][U+555F][U+52D5]")
    
    def stop_monitoring(self):
        """[U+505C][U+6B62][U+72C0][U+614B][U+76E3][U+63A7]"""
        self.monitoring = False
        if self.status_monitor_thread and self.status_monitor_thread.is_alive():
            self.status_monitor_thread.join(timeout=1)
        print("[U+72C0][U+614B][U+76E3][U+63A7][U+5DF2][U+505C][U+6B62]")
    
    def status_monitor_loop(self):
        """[U+72C0][U+614B][U+76E3][U+63A7][U+5FAA][U+74B0]"""
        while self.monitoring:
            try:
                if self.connected_to_server:
                    # [U+6AA2][U+67E5][U+9023][U+63A5][U+72C0][U+614B]
                    test_read = self.read_register(self.status_registers['module_status'])
                    if test_read is None:
                        self.connected_to_server = False
                        print("[U+4E3B]Modbus[U+670D][U+52D9][U+5668][U+9023][U+63A5][U+5DF2][U+65B7][U+958B]")
                    
                    # [U+767C][U+9001][U+72C0][U+614B][U+66F4][U+65B0]
                    status = self.get_current_status()
                    self.socketio.emit('status_update', status)
                
                time.sleep(1)  # 1[U+79D2][U+66F4][U+65B0][U+4E00][U+6B21]
                
            except Exception as e:
                print(f"[U+72C0][U+614B][U+76E3][U+63A7][U+7570][U+5E38]: {e}")
                time.sleep(2)
    
    def get_current_status(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+7576][U+524D][U+72C0][U+614B]"""
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
                # [U+8B80][U+53D6]VP[U+6A21][U+7D44][U+72C0][U+614B]
                vp_status = {}
                for name, addr in self.status_registers.items():
                    value = self.read_register(addr)
                    vp_status[name] = value
                
                # [U+8B80][U+53D6][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668][U+72C0][U+614B]
                command_status = {}
                for name, addr in self.command_registers.items():
                    value = self.read_register(addr)
                    command_status[name] = value
                
                status['vp_module_status'] = vp_status
                status['command_status'] = command_status
                
            except Exception as e:
                print(f"[U+7372][U+53D6]VP[U+6A21][U+7D44][U+72C0][U+614B][U+5931][U+6557]: {e}")
                status['connected_to_server'] = False
                self.connected_to_server = False
        
        return status
    
    def create_templates_directory(self):
        """[U+5275][U+5EFA]templates[U+76EE][U+9304]"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(current_dir, 'templates')
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
            print(f"[U+5DF2][U+5275][U+5EFA]templates[U+76EE][U+9304]: {templates_dir}")
    
    def run(self):
        """[U+904B][U+884C]Web[U+61C9][U+7528]"""
        print("[U+9707][U+52D5][U+76E4]Web[U+63A7][U+5236][U+61C9][U+7528][U+555F][U+52D5][U+4E2D]...")
        
        # [U+5275][U+5EFA]templates[U+76EE][U+9304]
        self.create_templates_directory()
        
        web_config = self.config['web_server']
        print(f"Web[U+670D][U+52D9][U+5668][U+555F][U+52D5] - http://{web_config['host']}:{web_config['port']}")
        print(f"[U+4E3B]Modbus[U+670D][U+52D9][U+5668]: {self.config['tcp_server']['host']}:{self.config['tcp_server']['port']}")
        print(f"VP[U+6A21][U+7D44][U+57FA][U+5730][U+5740]: {self.base_address}")
        print("[U+67B6][U+69CB]: VP_app [U+2192] [U+4E3B]Modbus[U+670D][U+52D9][U+5668] [U+2192] VP_main [U+2192] [U+9707][U+52D5][U+76E4](192.168.1.7:1000)")
        print("[U+529F][U+80FD][U+5217][U+8868]:")
        print("  - VP_main[U+6A21][U+7D44][U+5BC4][U+5B58][U+5668][U+76E3][U+63A7]")
        print("  - [U+9707][U+52D5][U+52D5][U+4F5C][U+63A7][U+5236] (11[U+7A2E][U+9707][U+52D5][U+6A21][U+5F0F])")
        print("  - [U+505C][U+6B62][U+529F][U+80FD] ([U+6307][U+4EE4]3[U+2192]VP_main[U+2192][U+9707][U+52D5][U+76E4][U+5BC4][U+5B58][U+5668]4)")
        print("  - [U+80CC][U+5149][U+63A7][U+5236] ([U+4EAE][U+5EA6][U+8ABF][U+7BC0]/[U+958B][U+95DC])")
        print("  - [U+932F][U+8AA4][U+91CD][U+7F6E]")
        print("[U+6309] Ctrl+C [U+505C][U+6B62][U+61C9][U+7528]")
        
        try:
            self.socketio.run(
                self.app,
                host=web_config['host'],
                port=web_config['port'],
                debug=web_config['debug'],
                allow_unsafe_werkzeug=True
            )
        except Exception as e:
            print(f"Web[U+670D][U+52D9][U+5668][U+555F][U+52D5][U+5931][U+6557]: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """[U+6E05][U+7406][U+8CC7][U+6E90]"""
        print("[U+6B63][U+5728][U+6E05][U+7406][U+8CC7][U+6E90]...")
        self.stop_monitoring()
        if self.modbus_client:
            try:
                self.modbus_client.close()
                print("[U+4E3B]Modbus[U+9023][U+63A5][U+5DF2][U+5B89][U+5168][U+65B7][U+958B]")
            except:
                pass
        print("[U+8CC7][U+6E90][U+6E05][U+7406][U+5B8C][U+6210]")


def create_index_html():
    """[U+5275][U+5EFA]index.html[U+6A94][U+6848] ([U+5982][U+679C][U+4E0D][U+5B58][U+5728])"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(current_dir, 'templates')
    index_path = os.path.join(templates_dir, 'index.html')
    
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    if not os.path.exists(index_path):
        print(f"[U+6CE8][U+610F]: [U+672A][U+627E][U+5230] {index_path}")
        print("[U+8ACB][U+78BA][U+4FDD][U+5C07] index.html [U+6A94][U+6848][U+653E][U+7F6E][U+5728] templates/ [U+76EE][U+9304][U+4E2D]")
        return False
    
    return True


def main():
    """[U+4E3B][U+51FD][U+6578]"""
    print("=" * 60)
    print("[U+9707][U+52D5][U+76E4]Web[U+63A7][U+5236][U+61C9][U+7528] ([U+7D14]Modbus TCP Client)")
    print("=" * 60)
    
    # [U+6AA2][U+67E5]HTML[U+6A21][U+677F]
    if not create_index_html():
        print("[U+8B66][U+544A]: HTML[U+6A21][U+677F][U+6A94][U+6848][U+7F3A][U+5931][U+FF0C]Web[U+4ECB][U+9762][U+53EF][U+80FD][U+7121][U+6CD5][U+6B63][U+5E38][U+986F][U+793A]")
        print("[U+7E7C][U+7E8C][U+555F][U+52D5][U+61C9][U+7528]...")
    
    # [U+5275][U+5EFA][U+61C9][U+7528][U+5BE6][U+4F8B]
    app = VibrationPlateWebApp()
    
    try:
        # [U+904B][U+884C][U+61C9][U+7528]
        app.run()
    except KeyboardInterrupt:
        print("\n[U+6536][U+5230][U+4E2D][U+65B7][U+4FE1][U+865F][U+FF0C][U+6B63][U+5728][U+95DC][U+9589]...")
    except Exception as e:
        print(f"[U+61C9][U+7528][U+904B][U+884C][U+7570][U+5E38]: {e}")
    finally:
        app.cleanup()
        print("[U+61C9][U+7528][U+5DF2][U+5B89][U+5168][U+95DC][U+9589]")


if __name__ == '__main__':
    main()