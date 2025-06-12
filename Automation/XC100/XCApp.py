#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XCApp.py - XC100 [U+53EF][U+8996][U+5316][U+63A7][U+5236][U+61C9][U+7528] - [U+4FEE][U+6B63][U+7248][U+672C]
[U+57FA][U+65BC]Flask[U+7684]Web[U+754C][U+9762][U+FF0C][U+901A][U+904E]Modbus TCP[U+8207]XCModule[U+901A][U+8A0A]
[U+4FEE][U+6B63][U+5BC4][U+5B58][U+5668][U+5730][U+5740][U+6620][U+5C04][U+548C][U+9801][U+9762][U+5237][U+65B0][U+554F][U+984C]
"""

import json
import time
import threading
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from pymodbus.client import ModbusTcpClient
import logging

# [U+7981][U+7528]Flask[U+7684][U+65E5][U+8A8C][U+8F38][U+51FA]
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class XCApp:
    """XC100 Web[U+61C9][U+7528] - [U+4FEE][U+6B63][U+7248][U+672C]"""
    
    def __init__(self, config_file="xc_app_config.json"):
        # [U+7372][U+53D6][U+57F7][U+884C][U+6A94][U+6848][U+76EE][U+9304]
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.current_dir, config_file)
        self.config = self.load_config()
        
        # Modbus TCP[U+5BA2][U+6236][U+7AEF]
        self.modbus_client = None
        self.connected = False
        self.connection_retry_count = 0
        self.max_retry_count = 5
        
        # [U+4FEE][U+6B63]: [U+4F7F][U+7528][U+6B63][U+78BA][U+7684][U+57FA][U+5730][U+5740]
        self.base_address = 1000  # [U+8207]XCModule.py[U+4E00][U+81F4]
        
        # [U+8A2D][U+5099][U+72C0][U+614B]
        self.device_status = {
            "state": "[U+672A][U+77E5]",
            "servo_status": False,
            "error_code": 0,
            "current_position": 0,
            "target_position": 0,
            "command_executing": False,
            "position_A": 400,
            "position_B": 2682,
            "module_connected": False,
            "communication_health": 100,
            "last_update": datetime.now().strftime("%H:%M:%S")
        }
        
        # [U+61C9][U+7528][U+72C0][U+614B]
        self.app_stats = {
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0,
            "uptime_start": datetime.now(),
            "communication_errors": 0
        }
        
        # Flask[U+61C9][U+7528]
        self.app = Flask(__name__)
        self.app.secret_key = 'xc100_app_secret_key_v3'
        
        # [U+4FEE][U+6B63]: [U+6DFB][U+52A0]SocketIO[U+652F][U+6301]
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        self.setup_routes()
        self.setup_socketio_events()
        
        # [U+76E3][U+63A7][U+7DDA][U+7A0B][U+63A7][U+5236]
        self.monitor_thread = None
        self.monitor_running = False
        self.auto_refresh_enabled = True  # [U+65B0][U+589E]: [U+81EA][U+52D5][U+5237][U+65B0][U+63A7][U+5236]
        self.manual_refresh_mode = False  # [U+65B0][U+589E]: [U+624B][U+52D5][U+5237][U+65B0][U+6A21][U+5F0F]
        
        print("XCApp[U+521D][U+59CB][U+5316][U+5B8C][U+6210]")
    
    def load_config(self):
        """[U+8F09][U+5165][U+914D][U+7F6E]"""
        default_config = {
            "modbus_tcp": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 3.0,
                "retry_on_failure": True,
                "max_retries": 3
            },
            "web_server": {
                "host": "0.0.0.0",
                "port": 5007,
                "debug": False
            },
            "xc_module": {
                "base_address": 1000,  # [U+4FEE][U+6B63]: [U+660E][U+78BA][U+6307][U+5B9A][U+57FA][U+5730][U+5740]
                "register_count": 50
            },
            "ui_settings": {
                "auto_refresh": True,
                "refresh_interval": 3.0,  # [U+4FEE][U+6B63]: [U+589E][U+52A0][U+5230]3[U+79D2]
                "show_debug_info": True,
                "command_confirmation": False,
                "manual_mode": False  # [U+65B0][U+589E]: [U+624B][U+52D5][U+6A21][U+5F0F]
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # [U+6DF1][U+5EA6][U+5408][U+4F75][U+914D][U+7F6E]
                    for key, value in default_config.items():
                        if key not in loaded_config:
                            loaded_config[key] = value
                        elif isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                if sub_key not in loaded_config[key]:
                                    loaded_config[key][sub_key] = sub_value
                    return loaded_config
            else:
                self.save_config(default_config)
                return default_config
        except Exception as e:
            print(f"[U+8F09][U+5165][U+914D][U+7F6E][U+5931][U+6557]: {e}")
            
        return default_config
    
    def save_config(self, config=None):
        """[U+4FDD][U+5B58][U+914D][U+7F6E]"""
        try:
            config_to_save = config or self.config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
            print(f"[U+914D][U+7F6E][U+5DF2][U+4FDD][U+5B58]: {self.config_file}")
        except Exception as e:
            print(f"[U+4FDD][U+5B58][U+914D][U+7F6E][U+5931][U+6557]: {e}")
    
    def connect_modbus(self):
        """[U+9023][U+7DDA][U+5230]XCModule with retry logic"""
        try:
            modbus_config = self.config["modbus_tcp"]
            
            if self.modbus_client:
                try:
                    self.modbus_client.close()
                except:
                    pass
            
            self.modbus_client = ModbusTcpClient(
                host=modbus_config["host"],
                port=modbus_config["port"],
                timeout=modbus_config["timeout"]
            )
            
            if self.modbus_client.connect():
                self.connected = True
                self.connection_retry_count = 0
                print(f"[U+5DF2][U+9023][U+7DDA][U+5230]XCModule: {modbus_config['host']}:{modbus_config['port']}")
                return True
            else:
                self.connected = False
                self.connection_retry_count += 1
                print(f"[U+9023][U+7DDA]XCModule[U+5931][U+6557] ([U+91CD][U+8A66] {self.connection_retry_count}/{self.max_retry_count})")
                return False
                
        except Exception as e:
            self.connected = False
            self.connection_retry_count += 1
            print(f"[U+9023][U+7DDA]XCModule[U+7570][U+5E38] ([U+91CD][U+8A66] {self.connection_retry_count}/{self.max_retry_count}): {e}")
            return False
    
    def disconnect_modbus(self):
        """[U+65B7][U+958B]Modbus[U+9023][U+7DDA]"""
        try:
            if self.modbus_client and self.connected:
                self.modbus_client.close()
                self.connected = False
                print("[U+5DF2][U+65B7][U+958B]XCModule[U+9023][U+7DDA]")
        except Exception as e:
            print(f"[U+65B7][U+958B][U+9023][U+7DDA][U+7570][U+5E38]: {e}")
    
    def read_device_status(self):
        """[U+8B80][U+53D6][U+8A2D][U+5099][U+72C0][U+614B] - [U+4FEE][U+6B63][U+5BC4][U+5B58][U+5668][U+5730][U+5740]"""
        if not self.connected:
            return False
        
        try:
            unit_id = self.config["modbus_tcp"]["unit_id"]
            
            # [U+4FEE][U+6B63]: [U+4F7F][U+7528][U+6B63][U+78BA][U+7684][U+57FA][U+5730][U+5740][U+8B80][U+53D6][U+72C0][U+614B][U+5BC4][U+5B58][U+5668] (1000-1014)
            result = self.modbus_client.read_holding_registers(
                address=self.base_address, 
                count=15, 
                slave=unit_id
            )
            
            if not result.isError():
                registers = result.registers
                
                # [U+72C0][U+614B][U+6620][U+5C04]
                state_map = {
                    0: "[U+96E2][U+7DDA]", 1: "[U+9592][U+7F6E]", 2: "[U+79FB][U+52D5][U+4E2D]", 3: "[U+539F][U+9EDE][U+5FA9][U+6B78][U+4E2D]", 
                    4: "[U+932F][U+8AA4]", 5: "Servo[U+95DC][U+9589]", 6: "[U+7DCA][U+6025][U+505C][U+6B62]"
                }
                
                # [U+932F][U+8AA4][U+4EE3][U+78BC][U+63CF][U+8FF0]
                error_map = {
                    0: "[U+6B63][U+5E38]",
                    1: "[U+5728][U+52D5][U+4F5C][U+4E2D][U+63A5][U+6536][U+52D5][U+4F5C][U+6307][U+4EE4]",
                    2: "[U+4E0A][U+4E0B][U+9650][U+932F][U+8AA4]", 
                    3: "[U+4F4D][U+7F6E][U+932F][U+8AA4]",
                    4: "[U+683C][U+5F0F][U+932F][U+8AA4]",
                    5: "[U+63A7][U+5236][U+6A21][U+5F0F][U+932F][U+8AA4]",
                    6: "[U+65B7][U+96FB][U+91CD][U+958B]",
                    7: "[U+521D][U+59CB][U+5316][U+672A][U+5B8C][U+6210]",
                    8: "Servo ON/OFF [U+932F][U+8AA4]",
                    9: "LOCK",
                    10: "[U+8EDF][U+9AD4][U+6975][U+9650]",
                    11: "[U+53C3][U+6578][U+5BEB][U+5165][U+6B0A][U+9650][U+4E0D][U+8DB3]",
                    12: "[U+539F][U+9EDE][U+5FA9][U+6B78][U+672A][U+5B8C][U+6210]",
                    13: "[U+524E][U+8ECA][U+5DF2][U+89E3][U+9664]",
                    999: "[U+901A][U+8A0A][U+7570][U+5E38]"
                }
                
                self.device_status.update({
                    "state": state_map.get(registers[0], f"[U+672A][U+77E5]({registers[0]})"),
                    "xc_connected": registers[1] == 1,  # [U+4FEE][U+6B63]: XC[U+8A2D][U+5099][U+9023][U+63A5][U+72C0][U+614B]
                    "servo_status": registers[2] == 1,
                    "error_code": registers[3],
                    "error_description": error_map.get(registers[3], f"[U+672A][U+77E5][U+932F][U+8AA4]({registers[3]})"),
                    "current_position": (registers[5] << 16) | registers[4],  # [U+4FEE][U+6B63]: 32[U+4F4D][U+4F4D][U+7F6E][U+5408][U+4F75]
                    "target_position": (registers[7] << 16) | registers[6],   # [U+4FEE][U+6B63]: 32[U+4F4D][U+4F4D][U+7F6E][U+5408][U+4F75]
                    "command_executing": registers[8] == 1,
                    "comm_errors": registers[9],
                    "position_A": (registers[11] << 16) | registers[10],      # [U+4FEE][U+6B63]: A[U+9EDE][U+4F4D][U+7F6E]
                    "position_B": (registers[13] << 16) | registers[12],      # [U+4FEE][U+6B63]: B[U+9EDE][U+4F4D][U+7F6E]
                    "module_connected": True,  # [U+80FD][U+8B80][U+53D6][U+5230][U+6578][U+64DA][U+8AAA][U+660E][U+6A21][U+7D44][U+5DF2][U+9023][U+63A5]
                    "last_update": datetime.now().strftime("%H:%M:%S")
                })
                
                # [U+8A08][U+7B97][U+901A][U+8A0A][U+5065][U+5EB7][U+5EA6]
                if self.app_stats["communication_errors"] == 0:
                    self.device_status["communication_health"] = 100
                else:
                    health = max(0, 100 - (self.app_stats["communication_errors"] * 10))
                    self.device_status["communication_health"] = health
                
                return True
                
        except Exception as e:
            self.app_stats["communication_errors"] += 1
            print(f"[U+8B80][U+53D6][U+8A2D][U+5099][U+72C0][U+614B][U+7570][U+5E38]: {e}")
            self.device_status["module_connected"] = False
            return False
    
    def send_command(self, command, param1=0, param2=0):
        """[U+767C][U+9001][U+6307][U+4EE4][U+5230]XCModule - [U+4FEE][U+6B63][U+5BC4][U+5B58][U+5668][U+5730][U+5740]"""
        if not self.connected:
            self.app_stats["failed_commands"] += 1
            return False
        
        try:
            self.app_stats["total_commands"] += 1
            unit_id = self.config["modbus_tcp"]["unit_id"]
            
            # [U+5148][U+6AA2][U+67E5][U+662F][U+5426][U+6709][U+6307][U+4EE4][U+6B63][U+5728][U+57F7][U+884C]
            status_result = self.modbus_client.read_holding_registers(
                address=self.base_address + 8, count=1, slave=unit_id
            )
            if not status_result.isError() and status_result.registers[0] == 1:
                print("[U+6709][U+6307][U+4EE4][U+6B63][U+5728][U+57F7][U+884C][U+4E2D][U+FF0C][U+8ACB][U+7A0D][U+5019]")
                self.app_stats["failed_commands"] += 1
                return False
            
            # [U+4FEE][U+6B63]: [U+4F7F][U+7528][U+6B63][U+78BA][U+7684][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668][U+5730][U+5740] (1020-1024)
            command_address = self.base_address + 20  # 1020
            command_id = int(time.time()) % 65536  # [U+751F][U+6210][U+552F][U+4E00]ID
            
            # [U+5BEB][U+5165][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]
            values = [command, param1, param2, command_id, 0]
            result = self.modbus_client.write_registers(
                address=command_address, 
                values=values, 
                slave=unit_id
            )
            
            if not result.isError():
                command_names = {
                    1: 'Servo ON', 2: 'Servo OFF', 3: '[U+539F][U+9EDE][U+5FA9][U+6B78]',
                    4: '[U+7D55][U+5C0D][U+79FB][U+52D5]', 6: '[U+7DCA][U+6025][U+505C][U+6B62]', 7: '[U+932F][U+8AA4][U+91CD][U+7F6E]'
                }
                print(f"[U+6307][U+4EE4][U+767C][U+9001][U+6210][U+529F]: {command_names.get(command, f'[U+6307][U+4EE4]{command}')} (ID: {command_id})")
                self.app_stats["successful_commands"] += 1
                return True
            else:
                print(f"[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]: {result}")
                self.app_stats["failed_commands"] += 1
                return False
                
        except Exception as e:
            print(f"[U+767C][U+9001][U+6307][U+4EE4][U+7570][U+5E38]: {e}")
            self.app_stats["failed_commands"] += 1
            self.app_stats["communication_errors"] += 1
            return False
    
    def update_position(self, pos_type, position):
        """[U+66F4][U+65B0][U+4F4D][U+7F6E][U+8A2D][U+5B9A] - [U+4FEE][U+6B63][U+5BC4][U+5B58][U+5668][U+5730][U+5740]"""
        if not self.connected:
            return False
        
        try:
            # [U+4F4D][U+7F6E][U+7BC4][U+570D][U+6AA2][U+67E5]
            if not (-999999 <= position <= 999999):
                print(f"[U+4F4D][U+7F6E][U+8D85][U+51FA][U+7BC4][U+570D]: {position}")
                return False
            
            unit_id = self.config["modbus_tcp"]["unit_id"]
            
            # 32[U+4F4D][U+4F4D][U+7F6E][U+5206][U+89E3]
            pos_low = position & 0xFFFF
            pos_high = (position >> 16) & 0xFFFF
            
            if pos_type == 'A':
                # [U+4FEE][U+6B63]: [U+66F4][U+65B0]A[U+9EDE][U+4F4D][U+7F6E] (1010-1011)
                address = self.base_address + 10
                result = self.modbus_client.write_registers(
                    address=address, values=[pos_low, pos_high], slave=unit_id
                )
            elif pos_type == 'B':
                # [U+4FEE][U+6B63]: [U+66F4][U+65B0]B[U+9EDE][U+4F4D][U+7F6E] (1012-1013)
                address = self.base_address + 12
                result = self.modbus_client.write_registers(
                    address=address, values=[pos_low, pos_high], slave=unit_id
                )
            else:
                return False
            
            if not result.isError():
                print(f"{pos_type}[U+9EDE][U+4F4D][U+7F6E][U+5DF2][U+66F4][U+65B0][U+70BA]: {position}")
                # [U+66F4][U+65B0][U+672C][U+5730][U+72C0][U+614B]
                if pos_type == 'A':
                    self.device_status["position_A"] = position
                else:
                    self.device_status["position_B"] = position
                return True
            else:
                print(f"[U+4F4D][U+7F6E][U+66F4][U+65B0][U+5931][U+6557]: {result}")
                return False
            
        except Exception as e:
            print(f"[U+66F4][U+65B0][U+4F4D][U+7F6E][U+7570][U+5E38]: {e}")
            return False
    
    def monitor_loop(self):
        """[U+76E3][U+63A7][U+5FAA][U+74B0] - [U+4FEE][U+6B63][U+5237][U+65B0][U+983B][U+7387]"""
        print("[U+958B][U+59CB][U+8A2D][U+5099][U+72C0][U+614B][U+76E3][U+63A7]")
        
        refresh_interval = self.config["ui_settings"]["refresh_interval"]
        
        while self.monitor_running:
            try:
                if self.connected:
                    if not self.read_device_status():
                        # [U+8B80][U+53D6][U+5931][U+6557][U+FF0C][U+53EF][U+80FD][U+9700][U+8981][U+91CD][U+9023]
                        self.connected = False
                else:
                    # [U+5617][U+8A66][U+91CD][U+65B0][U+9023][U+7DDA]
                    if self.connection_retry_count < self.max_retry_count:
                        print(f"[U+5617][U+8A66][U+91CD][U+65B0][U+9023][U+7DDA]... ({self.connection_retry_count + 1}/{self.max_retry_count})")
                        self.connect_modbus()
                    elif self.connection_retry_count >= self.max_retry_count:
                        print("[U+9054][U+5230][U+6700][U+5927][U+91CD][U+8A66][U+6B21][U+6578][U+FF0C][U+505C][U+6B62][U+91CD][U+9023][U+5617][U+8A66]")
                        time.sleep(10)  # [U+7B49][U+5F85]10[U+79D2][U+5F8C][U+91CD][U+7F6E][U+91CD][U+8A66][U+8A08][U+6578]
                        self.connection_retry_count = 0
                
                # [U+4FEE][U+6B63]: [U+53EA][U+6709][U+5728][U+81EA][U+52D5][U+5237][U+65B0][U+6A21][U+5F0F][U+4E0B][U+624D][U+767C][U+9001][U+66F4][U+65B0]
                if self.auto_refresh_enabled and not self.manual_refresh_mode:
                    self.socketio.emit('status_update', self.get_full_status())
                
                time.sleep(refresh_interval)
                
            except Exception as e:
                print(f"[U+76E3][U+63A7][U+5FAA][U+74B0][U+7570][U+5E38]: {e}")
                time.sleep(5)
        
        print("[U+8A2D][U+5099][U+72C0][U+614B][U+76E3][U+63A7][U+505C][U+6B62]")
    
    def start_monitoring(self):
        """[U+958B][U+59CB][U+76E3][U+63A7]"""
        if not self.monitor_running:
            self.monitor_running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """[U+505C][U+6B62][U+76E3][U+63A7]"""
        self.monitor_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=3)
    
    def get_app_statistics(self):
        """[U+7372][U+53D6][U+61C9][U+7528][U+7D71][U+8A08]"""
        uptime = datetime.now() - self.app_stats["uptime_start"]
        success_rate = 0
        if self.app_stats["total_commands"] > 0:
            success_rate = (self.app_stats["successful_commands"] / self.app_stats["total_commands"]) * 100
        
        return {
            "uptime": str(uptime).split('.')[0],
            "total_commands": self.app_stats["total_commands"],
            "successful_commands": self.app_stats["successful_commands"],
            "failed_commands": self.app_stats["failed_commands"],
            "success_rate": f"{success_rate:.1f}%",
            "communication_errors": self.app_stats["communication_errors"]
        }
    
    def get_full_status(self):
        """[U+7372][U+53D6][U+5B8C][U+6574][U+72C0][U+614B]"""
        return {
            "success": True,
            "connected": self.connected,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": self.device_status,
            "statistics": self.get_app_statistics(),
            "config": {
                "base_address": self.base_address,
                "auto_refresh": self.auto_refresh_enabled,
                "manual_mode": self.manual_refresh_mode,
                "refresh_interval": self.config["ui_settings"]["refresh_interval"]
            }
        }
    
    def setup_socketio_events(self):
        """[U+8A2D][U+7F6E]SocketIO[U+4E8B][U+4EF6] - [U+65B0][U+589E][U+624B][U+52D5][U+63A7][U+5236][U+529F][U+80FD]"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """[U+5BA2][U+6236][U+7AEF][U+9023][U+63A5]"""
            print("Web[U+5BA2][U+6236][U+7AEF][U+5DF2][U+9023][U+63A5]")
            emit('status_update', self.get_full_status())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """[U+5BA2][U+6236][U+7AEF][U+65B7][U+958B]"""
            print("Web[U+5BA2][U+6236][U+7AEF][U+5DF2][U+65B7][U+958B]")
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """[U+624B][U+52D5][U+8ACB][U+6C42][U+72C0][U+614B][U+66F4][U+65B0]"""
            emit('status_update', self.get_full_status())
        
        @self.socketio.on('toggle_auto_refresh')
        def handle_toggle_auto_refresh(data):
            """[U+5207][U+63DB][U+81EA][U+52D5][U+5237][U+65B0]"""
            self.auto_refresh_enabled = data.get('enabled', True)
            print(f"[U+81EA][U+52D5][U+5237][U+65B0]: {'[U+958B][U+555F]' if self.auto_refresh_enabled else '[U+95DC][U+9589]'}")
            emit('auto_refresh_status', {'enabled': self.auto_refresh_enabled})
        
        @self.socketio.on('set_manual_mode')
        def handle_manual_mode(data):
            """[U+8A2D][U+7F6E][U+624B][U+52D5][U+6A21][U+5F0F]"""
            self.manual_refresh_mode = data.get('manual', False)
            print(f"[U+624B][U+52D5][U+6A21][U+5F0F]: {'[U+958B][U+555F]' if self.manual_refresh_mode else '[U+95DC][U+9589]'}")
            emit('manual_mode_status', {'manual': self.manual_refresh_mode})
    
    def setup_routes(self):
        """[U+8A2D][U+7F6E]Flask[U+8DEF][U+7531] - [U+589E][U+5F37][U+529F][U+80FD]"""
        
        @self.app.route('/')
        def index():
            """[U+4E3B][U+9801]"""
            return render_template('index.html')
        
        @self.app.route('/api/status')
        def get_status():
            """[U+7372][U+53D6][U+8A2D][U+5099][U+72C0][U+614B]API"""
            return jsonify(self.get_full_status())
        
        @self.app.route('/api/command', methods=['POST'])
        def send_command_api():
            """[U+767C][U+9001][U+6307][U+4EE4]API"""
            try:
                data = request.get_json()
                command = data.get('command', 0)
                param1 = data.get('param1', 0)
                param2 = data.get('param2', 0)
                
                # [U+6307][U+4EE4][U+9A57][U+8B49]
                valid_commands = [1, 2, 3, 4, 6, 7]
                if command not in valid_commands:
                    return jsonify({"success": False, "message": f"[U+7121][U+6548][U+7684][U+6307][U+4EE4][U+4EE3][U+78BC]: {command}"})
                
                if self.send_command(command, param1, param2):
                    # [U+6307][U+4EE4][U+767C][U+9001][U+5F8C][U+7ACB][U+5373][U+66F4][U+65B0][U+72C0][U+614B]
                    time.sleep(0.1)
                    self.read_device_status()
                    return jsonify({"success": True, "message": "[U+6307][U+4EE4][U+767C][U+9001][U+6210][U+529F]"})
                else:
                    return jsonify({"success": False, "message": "[U+6307][U+4EE4][U+767C][U+9001][U+5931][U+6557]"})
                    
            except Exception as e:
                return jsonify({"success": False, "message": f"[U+767C][U+9001][U+6307][U+4EE4][U+7570][U+5E38]: {e}"})
        
        @self.app.route('/api/position', methods=['POST'])
        def update_position_api():
            """[U+66F4][U+65B0][U+4F4D][U+7F6E]API"""
            try:
                data = request.get_json()
                pos_type = data.get('type')  # 'A' or 'B'
                position = int(data.get('position', 0))
                
                if pos_type not in ['A', 'B']:
                    return jsonify({"success": False, "message": "[U+7121][U+6548][U+7684][U+4F4D][U+7F6E][U+985E][U+578B]"})
                
                if self.update_position(pos_type, position):
                    # [U+4F4D][U+7F6E][U+66F4][U+65B0][U+5F8C][U+7ACB][U+5373][U+5237][U+65B0][U+72C0][U+614B]
                    time.sleep(0.1)
                    self.read_device_status()
                    return jsonify({"success": True, "message": f"{pos_type}[U+9EDE][U+4F4D][U+7F6E][U+66F4][U+65B0][U+6210][U+529F]"})
                else:
                    return jsonify({"success": False, "message": "[U+4F4D][U+7F6E][U+66F4][U+65B0][U+5931][U+6557]"})
                    
            except ValueError:
                return jsonify({"success": False, "message": "[U+4F4D][U+7F6E][U+5FC5][U+9808][U+662F][U+6578][U+5B57]"})
            except Exception as e:
                return jsonify({"success": False, "message": f"[U+66F4][U+65B0][U+4F4D][U+7F6E][U+7570][U+5E38]: {e}"})
        
        @self.app.route('/api/connect', methods=['POST'])
        def connect_api():
            """[U+9023][U+7DDA]API"""
            self.connection_retry_count = 0
            if self.connect_modbus():
                return jsonify({"success": True, "message": "[U+9023][U+7DDA][U+6210][U+529F]"})
            else:
                return jsonify({"success": False, "message": "[U+9023][U+7DDA][U+5931][U+6557]"})
        
        @self.app.route('/api/disconnect', methods=['POST'])
        def disconnect_api():
            """[U+65B7][U+958B][U+9023][U+7DDA]API"""
            self.disconnect_modbus()
            return jsonify({"success": True, "message": "[U+5DF2][U+65B7][U+958B][U+9023][U+7DDA]"})
        
        @self.app.route('/api/manual_refresh', methods=['POST'])
        def manual_refresh():
            """[U+624B][U+52D5][U+5237][U+65B0][U+72C0][U+614B]"""
            if self.read_device_status():
                return jsonify(self.get_full_status())
            else:
                return jsonify({"success": False, "message": "[U+8B80][U+53D6][U+72C0][U+614B][U+5931][U+6557]"})
        
        @self.app.route('/api/settings', methods=['GET', 'POST'])
        def settings_api():
            """[U+8A2D][U+7F6E]API"""
            if request.method == 'GET':
                return jsonify({
                    "success": True,
                    "settings": self.config["ui_settings"]
                })
            else:
                try:
                    data = request.get_json()
                    
                    # [U+66F4][U+65B0][U+8A2D][U+7F6E]
                    if 'auto_refresh' in data:
                        self.config["ui_settings"]["auto_refresh"] = data['auto_refresh']
                        self.auto_refresh_enabled = data['auto_refresh']
                    
                    if 'refresh_interval' in data:
                        self.config["ui_settings"]["refresh_interval"] = float(data['refresh_interval'])
                    
                    if 'manual_mode' in data:
                        self.config["ui_settings"]["manual_mode"] = data['manual_mode']
                        self.manual_refresh_mode = data['manual_mode']
                    
                    self.save_config()
                    return jsonify({"success": True, "message": "[U+8A2D][U+7F6E][U+5DF2][U+66F4][U+65B0]"})
                    
                except Exception as e:
                    return jsonify({"success": False, "message": f"[U+66F4][U+65B0][U+8A2D][U+7F6E][U+5931][U+6557]: {e}"})
        
        @self.app.route('/api/debug')
        def debug_info():
            """[U+8ABF][U+8A66][U+4FE1][U+606F]API"""
            return jsonify({
                "success": True,
                "debug_info": {
                    "base_address": self.base_address,
                    "config_file": self.config_file,
                    "current_dir": self.current_dir,
                    "connected": self.connected,
                    "auto_refresh": self.auto_refresh_enabled,
                    "manual_mode": self.manual_refresh_mode,
                    "monitor_running": self.monitor_running
                }
            })
    
    def run(self):
        """[U+904B][U+884C]Web[U+61C9][U+7528]"""
        # [U+6AA2][U+67E5]XCModule[U+662F][U+5426][U+5728][U+904B][U+884C]
        if not self.connect_modbus():
            print("[U+7121][U+6CD5][U+9023][U+7DDA][U+5230]XCModule")
            print("[U+8ACB][U+78BA][U+4FDD]XCModule.py[U+6B63][U+5728][U+904B][U+884C][U+FF0C][U+7136][U+5F8C][U+91CD][U+8A66]")
            print("\n[U+6545][U+969C][U+6392][U+9664][U+6B65][U+9A5F][U+FF1A]")
            print("1. [U+78BA][U+8A8D]XCModule.py[U+5DF2][U+555F][U+52D5][U+4E26][U+986F][U+793A]'[U+6A21][U+7D44][U+555F][U+52D5][U+6210][U+529F]'")
            print("2. [U+6AA2][U+67E5]Modbus TCP Server[U+662F][U+5426][U+5728]127.0.0.1:502[U+904B][U+884C]")
            print("3. [U+78BA][U+8A8D][U+9632][U+706B][U+7246][U+6C92][U+6709][U+963B][U+64CB][U+7AEF][U+53E3]502")
            print("4. [U+6AA2][U+67E5]XC100[U+8A2D][U+5099][U+662F][U+5426][U+6B63][U+78BA][U+9023][U+63A5]")
            print("\n[U+5C07][U+4EE5][U+96E2][U+7DDA][U+6A21][U+5F0F][U+555F][U+52D5]Web[U+754C][U+9762]...")
        
        # [U+6AA2][U+67E5]templates[U+76EE][U+9304]
        templates_dir = os.path.join(self.current_dir, 'templates')
        if not os.path.exists(templates_dir):
            print("[U+627E][U+4E0D][U+5230]templates[U+76EE][U+9304]")
            print(f"[U+8ACB][U+5728] {self.current_dir} [U+76EE][U+9304][U+4E0B][U+5275][U+5EFA]templates[U+6587][U+4EF6][U+593E]")
            return
        
        index_file = os.path.join(templates_dir, 'index.html')
        if not os.path.exists(index_file):
            print("[U+627E][U+4E0D][U+5230]templates/index.html[U+6587][U+4EF6]")
            print("[U+8ACB][U+5C07]index.html[U+653E][U+7F6E][U+5728]templates[U+76EE][U+9304][U+4E2D]")
            return
        
        # [U+958B][U+59CB][U+76E3][U+63A7]
        self.start_monitoring()
        
        try:
            web_config = self.config["web_server"]
            print(f"\nXCApp[U+555F][U+52D5]")
            print(f"Web[U+754C][U+9762]: http://localhost:{web_config['port']}")
            print(f"[U+914D][U+7F6E][U+6587][U+4EF6]: {self.config_file}")
            print(f"[U+5237][U+65B0][U+9593][U+9694]: {self.config['ui_settings']['refresh_interval']}[U+79D2]")
            print(f"[U+5BC4][U+5B58][U+5668][U+57FA][U+5730][U+5740]: {self.base_address}")
            print(f"[U+6A21][U+677F][U+76EE][U+9304]: {templates_dir}")
            print("\n[U+4FEE][U+6B63][U+529F][U+80FD]:")
            print("  [U+4FEE][U+6B63][U+5BC4][U+5B58][U+5668][U+5730][U+5740][U+6620][U+5C04]")
            print("  [U+512A][U+5316][U+9801][U+9762][U+5237][U+65B0][U+983B][U+7387]")
            print("  [U+65B0][U+589E][U+624B][U+52D5][U+5237][U+65B0][U+6A21][U+5F0F]")
            print("  [U+6539][U+5584][U+4F4D][U+7F6E][U+8F38][U+5165][U+9AD4][U+9A57]")
            print("  SocketIO[U+5373][U+6642][U+901A][U+8A0A]")
            print("  [U+914D][U+7F6E][U+6587][U+4EF6][U+81EA][U+52D5][U+4FDD][U+5B58]")
            print("\n[U+6309] Ctrl+C [U+505C][U+6B62][U+61C9][U+7528]")
            
            # [U+555F][U+52D5]Flask[U+61C9][U+7528]
            self.socketio.run(
                self.app,
                host=web_config["host"],
                port=web_config["port"],
                debug=web_config["debug"],
                allow_unsafe_werkzeug=True
            )
            
        except KeyboardInterrupt:
            print("\n[U+6B63][U+5728][U+505C][U+6B62][U+61C9][U+7528]...")
        except Exception as e:
            print(f"\nWeb[U+61C9][U+7528][U+904B][U+884C][U+7570][U+5E38]: {e}")
        finally:
            self.stop_monitoring()
            self.disconnect_modbus()
            print("XCApp[U+5DF2][U+505C][U+6B62]")

def main():
    """[U+4E3B][U+51FD][U+6578]"""
    import argparse
    
    parser = argparse.ArgumentParser(description='XC100 Web[U+63A7][U+5236][U+61C9][U+7528]')
    parser.add_argument('--config', type=str, default="xc_app_config.json", help='[U+914D][U+7F6E][U+6587][U+4EF6][U+8DEF][U+5F91]')
    parser.add_argument('--port', type=int, help='Web[U+670D][U+52D9][U+5668][U+7AEF][U+53E3]')
    parser.add_argument('--host', type=str, help='Web[U+670D][U+52D9][U+5668][U+4E3B][U+6A5F]')
    parser.add_argument('--modbus-host', type=str, help='XCModule[U+4E3B][U+6A5F][U+5730][U+5740]')
    parser.add_argument('--modbus-port', type=int, help='XCModule[U+7AEF][U+53E3]')
    parser.add_argument('--debug', action='store_true', help='[U+555F][U+7528][U+8ABF][U+8A66][U+6A21][U+5F0F]')
    args = parser.parse_args()
    
    print("XCApp - XC100 Web[U+63A7][U+5236][U+61C9][U+7528] [U+4FEE][U+6B63][U+7248][U+672C]")
    print("=" * 50)
    
    # [U+5275][U+5EFA][U+61C9][U+7528][U+5BE6][U+4F8B]
    app = XCApp(args.config)
    
    # [U+8986][U+84CB][U+547D][U+4EE4][U+884C][U+53C3][U+6578]
    if args.port:
        app.config["web_server"]["port"] = args.port
    if args.host:
        app.config["web_server"]["host"] = args.host
    if args.modbus_host:
        app.config["modbus_tcp"]["host"] = args.modbus_host
    if args.modbus_port:
        app.config["modbus_tcp"]["port"] = args.modbus_port
    if args.debug:
        app.config["web_server"]["debug"] = True
    
    # [U+4FDD][U+5B58][U+66F4][U+65B0][U+5F8C][U+7684][U+914D][U+7F6E]
    app.save_config()
    
    # [U+904B][U+884C][U+61C9][U+7528]
    app.run()

if __name__ == "__main__":
    main()