# -*- coding: utf-8 -*-
"""
VP_main.py - [U+9707][U+52D5][U+76E4]Modbus TCP Client[U+4E3B][U+7A0B][U+5E8F]
[U+5BE6][U+73FE][U+9707][U+52D5][U+76E4]RTU[U+8F49]TCP[U+6A4B][U+63A5][U+FF0C][U+72C0][U+614B][U+6A5F][U+4EA4][U+63E1][U+FF0C][U+81EA][U+52D5][U+91CD][U+9023]
[U+9069][U+7528][U+65BC][U+81EA][U+52D5][U+5316][U+8A2D][U+5099][U+5C0D][U+63A5][U+6D41][U+7A0B]
"""

import sys
import os
import time
import threading
import json
import signal
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pymodbus.client import ModbusTcpClient
from vibration_plate import VibrationPlate

logger = logging.getLogger(__name__)

class VibrationPlateModbusClient:
    """[U+9707][U+52D5][U+76E4]Modbus TCP Client - RTU[U+8F49]TCP[U+6A4B][U+63A5][U+6A21][U+7D44]"""
    
    def __init__(self, config_file="vp_config.json"):
        # [U+8F09][U+5165][U+914D][U+7F6E]
        self.config = self.load_config(config_file)
        
        # [U+6838][U+5FC3][U+7D44][U+4EF6]
        self.vibration_plate: Optional[VibrationPlate] = None
        self.modbus_client: Optional[ModbusTcpClient] = None
        self.running = False
        
        # [U+72C0][U+614B][U+8B8A][U+6578]
        self.connected_to_server = False
        self.connected_to_device = False
        self.last_command_id = 0
        self.executing_command = False
        
        # [U+57F7][U+884C][U+7DD2][U+63A7][U+5236]
        self.main_loop_thread = None
        self.loop_lock = threading.Lock()
        
        # [U+7D71][U+8A08][U+8A08][U+6578]
        self.operation_count = 0
        self.error_count = 0
        self.connection_count = 0
        self.start_time = time.time()
        
        # [U+5BC4][U+5B58][U+5668][U+6620][U+5C04] ([U+57FA][U+5730][U+5740] + [U+504F][U+79FB])
        self.base_address = self.config['modbus_mapping']['base_address']
        self.init_register_mapping()
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """[U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848]"""
        default_config = {
            "module_id": "[U+9707][U+52D5][U+76E4][U+6A21][U+7D44]",
            "device_connection": {
                "ip": "192.168.1.7",
                "port": 1000,
                "slave_id": 10,
                "timeout": 0.2
            },
            "tcp_server": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 1.0
            },
            "modbus_mapping": {
                "base_address": 300
            },
            "timing": {
                "fast_loop_interval": 0.02,
                "movement_delay": 0.1,
                "command_delay": 0.02
            }
        }
        
        try:
            # [U+53D6][U+5F97][U+7576][U+524D][U+57F7][U+884C][U+6A94][U+6848][U+7684][U+76EE][U+9304]
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, config_file)
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # [U+5408][U+4F75][U+914D][U+7F6E]
                    default_config.update(loaded_config)
                print(f"[U+5DF2][U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848]: {config_path}")
            else:
                # [U+5275][U+5EFA][U+9810][U+8A2D][U+914D][U+7F6E][U+6A94][U+6848][U+5728][U+57F7][U+884C][U+6A94][U+6848][U+540C][U+5C64][U+76EE][U+9304]
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                print(f"[U+5DF2][U+5275][U+5EFA][U+9810][U+8A2D][U+914D][U+7F6E][U+6A94][U+6848]: {config_path}")
        except Exception as e:
            print(f"[U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848][U+5931][U+6557]: {e}")
            
        return default_config
    
    def init_register_mapping(self):
        """[U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668][U+6620][U+5C04]"""
        base = self.base_address
        
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
            'command_code': base + 20,          # [U+6307][U+4EE4][U+4EE3][U+78BC]
            'param1': base + 21,                # [U+53C3][U+6578]1 ([U+5F37][U+5EA6]/[U+4EAE][U+5EA6])
            'param2': base + 22,                # [U+53C3][U+6578]2 ([U+983B][U+7387])
            'command_id': base + 23,            # [U+6307][U+4EE4]ID
            'reserved': base + 24               # [U+4FDD][U+7559]
        }
        
        # [U+6240][U+6709][U+5BC4][U+5B58][U+5668]
        self.all_registers = {**self.status_registers, **self.command_registers}
        
        logger.info(f"[U+5BC4][U+5B58][U+5668][U+6620][U+5C04][U+521D][U+59CB][U+5316][U+5B8C][U+6210] - [U+57FA][U+5730][U+5740]: {base}")
        print(f"[U+9707][U+52D5][U+76E4][U+6A21][U+7D44][U+5BC4][U+5B58][U+5668][U+6620][U+5C04]:")
        print(f"  [U+57FA][U+5730][U+5740]: {base}")
        print(f"  [U+72C0][U+614B][U+5BC4][U+5B58][U+5668]: {base} ~ {base + 14}")
        print(f"  [U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]: {base + 20} ~ {base + 24}")
        print(f"  [U+6A21][U+7D44][U+72C0][U+614B]({base}): 0=[U+96E2][U+7DDA], 1=[U+9592][U+7F6E], 2=[U+57F7][U+884C][U+4E2D], 3=[U+521D][U+59CB][U+5316], 4=[U+932F][U+8AA4]")
        print(f"  [U+8A2D][U+5099][U+9023][U+63A5]({base + 1}): 0=[U+65B7][U+958B], 1=[U+5DF2][U+9023][U+63A5]")
        print(f"  [U+6307][U+4EE4][U+57F7][U+884C][U+72C0][U+614B]({base + 8}): 0=[U+7A7A][U+9592], 1=[U+57F7][U+884C][U+4E2D]")
    
    def connect_main_server(self) -> bool:
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
                self.connection_count += 1
                print(f"[U+9023][U+63A5][U+5230][U+4E3B][U+670D][U+52D9][U+5668][U+6210][U+529F]: {server_config['host']}:{server_config['port']}")
                
                # [U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668]
                self.init_status_registers()
                return True
            else:
                print("[U+9023][U+63A5][U+5230][U+4E3B][U+670D][U+52D9][U+5668][U+5931][U+6557]")
                return False
                
        except Exception as e:
            print(f"[U+9023][U+63A5][U+4E3B][U+670D][U+52D9][U+5668][U+7570][U+5E38]: {e}")
            self.connected_to_server = False
            return False
    
    def connect_device(self) -> bool:
        """[U+9023][U+63A5][U+5230][U+9707][U+52D5][U+76E4][U+8A2D][U+5099]"""
        try:
            if self.vibration_plate:
                self.vibration_plate.disconnect()
            
            device_config = self.config['device_connection']
            self.vibration_plate = VibrationPlate(
                ip=device_config['ip'],
                port=device_config['port'],
                slave_id=device_config['slave_id'],
                auto_connect=True
            )
            
            if self.vibration_plate.is_connected():
                self.connected_to_device = True
                print(f"[U+9023][U+63A5][U+5230][U+9707][U+52D5][U+76E4][U+6210][U+529F]: {device_config['ip']}:{device_config['port']}")
                
                # [U+521D][U+59CB][U+5316][U+8A2D][U+5099]
                self.vibration_plate.set_backlight_brightness(128)
                self.vibration_plate.set_backlight(True)
                
                return True
            else:
                print("[U+9023][U+63A5][U+5230][U+9707][U+52D5][U+76E4][U+5931][U+6557]")
                return False
                
        except Exception as e:
            print(f"[U+9023][U+63A5][U+9707][U+52D5][U+76E4][U+7570][U+5E38]: {e}")
            self.connected_to_device = False
            return False
    
    def init_status_registers(self):
        """[U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]"""
        try:
            # [U+5BEB][U+5165][U+6A21][U+7D44][U+57FA][U+672C][U+8CC7][U+8A0A]
            self.write_register('module_status', 1)  # [U+9592][U+7F6E][U+72C0][U+614B]
            self.write_register('error_code', 0)     # [U+7121][U+932F][U+8AA4]
            self.write_register('command_status', 0) # [U+7A7A][U+9592]
            self.write_register('comm_error_count', self.error_count)
            
            print("[U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+521D][U+59CB][U+5316][U+5B8C][U+6210]")
        except Exception as e:
            print(f"[U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {e}")
    
    def read_register(self, register_name: str) -> Optional[int]:
        """[U+8B80][U+53D6][U+5BC4][U+5B58][U+5668]"""
        if not self.connected_to_server or register_name not in self.all_registers:
            return None
        
        try:
            address = self.all_registers[register_name]
            result = self.modbus_client.read_holding_registers(
                address, count=1, slave=self.config['tcp_server']['unit_id']
            )
            
            if not result.isError():
                return result.registers[0]
            else:
                return None
                
        except Exception as e:
            pass  # [U+975C][U+9ED8][U+8655][U+7406][U+8B80][U+53D6][U+932F][U+8AA4]
    
    def write_register(self, register_name: str, value: int) -> bool:
        """[U+5BEB][U+5165][U+5BC4][U+5B58][U+5668]"""
        if not self.connected_to_server or register_name not in self.all_registers:
            return False
        
        try:
            address = self.all_registers[register_name]
            result = self.modbus_client.write_register(
                address, value, slave=self.config['tcp_server']['unit_id']
            )
            
            return not result.isError()
                
        except Exception as e:
            pass  # [U+975C][U+9ED8][U+8655][U+7406][U+5BEB][U+5165][U+932F][U+8AA4]
            return False
    
    def execute_command(self, command: int, param1: int, param2: int) -> bool:
        """[U+57F7][U+884C][U+6307][U+4EE4]"""
        if not self.connected_to_device:
            print("[U+8A2D][U+5099][U+672A][U+9023][U+63A5][U+FF0C][U+7121][U+6CD5][U+57F7][U+884C][U+6307][U+4EE4]")
            return False
        
        try:
            success = False
            
            if command == 0:  # NOP
                success = True
                
            elif command == 1:  # [U+8A2D][U+5099][U+555F][U+7528] ([U+80CC][U+5149][U+958B][U+555F])
                success = self.vibration_plate.set_backlight(True)
                
            elif command == 2:  # [U+8A2D][U+5099][U+505C][U+7528] ([U+80CC][U+5149][U+95DC][U+9589])
                success = self.vibration_plate.set_backlight(False)
                
            elif command == 3:  # [U+505C][U+6B62][U+6240][U+6709][U+52D5][U+4F5C]
                success = self.vibration_plate.stop()
                
            elif command == 4:  # [U+8A2D][U+5B9A][U+80CC][U+5149][U+4EAE][U+5EA6]
                success = self.vibration_plate.set_backlight_brightness(param1)
                
            elif command == 5:  # [U+57F7][U+884C][U+52D5][U+4F5C] (param1=[U+52D5][U+4F5C][U+78BC], param2=[U+5F37][U+5EA6])
                actions = ['stop', 'up', 'down', 'left', 'right', 'upleft', 'downleft',
                          'upright', 'downright', 'horizontal', 'vertical', 'spread']
                if 0 <= param1 < len(actions):
                    action = actions[param1]
                    if action == 'stop':
                        success = self.vibration_plate.stop()
                    else:
                        success = self.vibration_plate.execute_action(action, param2, param2)
                
            elif command == 6:  # [U+7DCA][U+6025][U+505C][U+6B62]
                success = self.vibration_plate.stop()
                
            elif command == 7:  # [U+932F][U+8AA4][U+91CD][U+7F6E]
                self.error_count = 0
                success = True
                
            # [U+9707][U+52D5][U+76E4][U+5C08][U+7528][U+6307][U+4EE4] (11-30)
            elif 11 <= command <= 30:
                success = self.execute_vp_specific_command(command, param1, param2)
            
            if success:
                self.operation_count += 1
                print(f"[U+6307][U+4EE4][U+57F7][U+884C][U+6210][U+529F]: cmd={command}, p1={param1}, p2={param2}")
            else:
                self.error_count += 1
                print(f"[U+6307][U+4EE4][U+57F7][U+884C][U+5931][U+6557]: cmd={command}, p1={param1}, p2={param2}")
                
            return success
            
        except Exception as e:
            print(f"[U+57F7][U+884C][U+6307][U+4EE4][U+7570][U+5E38]: {e}")
            self.error_count += 1
            return False
    
    def execute_vp_specific_command(self, command: int, param1: int, param2: int) -> bool:
        """[U+57F7][U+884C][U+9707][U+52D5][U+76E4][U+5C08][U+7528][U+6307][U+4EE4]"""
        try:
            if command == 11:  # [U+8A2D][U+5B9A][U+52D5][U+4F5C][U+53C3][U+6578]
                actions = ['up', 'down', 'left', 'right', 'upleft', 'downleft',
                          'upright', 'downright', 'horizontal', 'vertical', 'spread']
                if 0 <= param1 < len(actions):
                    return self.vibration_plate.set_action_parameters(actions[param1], param2)
                    
            elif command == 12:  # [U+80CC][U+5149][U+5207][U+63DB]
                return self.vibration_plate.set_backlight(bool(param1))
                
            elif command == 13:  # [U+57F7][U+884C][U+7279][U+5B9A][U+52D5][U+4F5C][U+4E26][U+8A2D][U+5B9A][U+53C3][U+6578]
                actions = ['up', 'down', 'left', 'right', 'upleft', 'downleft',
                          'upright', 'downright', 'horizontal', 'vertical', 'spread']
                if 0 <= param1 < len(actions) and param1 > 0:
                    action = actions[param1]
                    return self.vibration_plate.execute_action(action, param2, param2)
                    
            return False
            
        except Exception as e:
            print(f"[U+9707][U+52D5][U+76E4][U+5C08][U+7528][U+6307][U+4EE4][U+57F7][U+884C][U+5931][U+6557]: {e}")
            return False
    
    def update_status_registers(self):
        """[U+66F4][U+65B0][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]"""
        try:
            # [U+66F4][U+65B0][U+9023][U+63A5][U+72C0][U+614B]
            self.write_register('device_connection', 1 if self.connected_to_device else 0)
            
            # [U+66F4][U+65B0][U+8A2D][U+5099][U+72C0][U+614B]
            if self.connected_to_device:
                vp_status = self.vibration_plate.get_status()
                self.write_register('device_status', 1 if vp_status['connected'] else 0)
                self.write_register('vibration_status', 1 if vp_status['vibration_active'] else 0)
                self.write_register('brightness_status', vp_status.get('backlight_brightness', 0))
            else:
                self.write_register('device_status', 0)
                self.write_register('vibration_status', 0)
            
            # [U+66F4][U+65B0][U+6A21][U+7D44][U+72C0][U+614B]
            if self.executing_command:
                self.write_register('module_status', 2)  # [U+57F7][U+884C][U+4E2D]
            elif not self.connected_to_device:
                self.write_register('module_status', 0)  # [U+96E2][U+7DDA]
            elif self.error_count > 10:
                self.write_register('module_status', 4)  # [U+932F][U+8AA4]
            else:
                self.write_register('module_status', 1)  # [U+9592][U+7F6E]
            
            # [U+66F4][U+65B0][U+932F][U+8AA4][U+8A08][U+6578][U+548C][U+6642][U+9593][U+6233]
            self.write_register('comm_error_count', self.error_count)
            self.write_register('timestamp', int(time.time()) & 0xFFFF)
            
        except Exception as e:
            pass  # [U+975C][U+9ED8][U+8655][U+7406][U+72C0][U+614B][U+66F4][U+65B0][U+932F][U+8AA4]
    
    def process_commands(self):
        """[U+8655][U+7406][U+6307][U+4EE4] ([U+72C0][U+614B][U+6A5F][U+4EA4][U+63E1])"""
        try:
            # [U+8B80][U+53D6][U+65B0][U+6307][U+4EE4]ID
            new_command_id = self.read_register('command_id')
            if new_command_id is None or new_command_id == self.last_command_id:
                return
            
            # [U+6AA2][U+6E2C][U+5230][U+65B0][U+6307][U+4EE4]
            command_code = self.read_register('command_code')
            param1 = self.read_register('param1')
            param2 = self.read_register('param2')
            
            if command_code is None:
                return
            
            print(f"[U+6536][U+5230][U+65B0][U+6307][U+4EE4]: ID={new_command_id}, CMD={command_code}, P1={param1}, P2={param2}")
            
            # [U+8A2D][U+7F6E][U+57F7][U+884C][U+72C0][U+614B]
            self.executing_command = True
            self.write_register('command_status', 1)  # [U+57F7][U+884C][U+4E2D]
            
            # [U+57F7][U+884C][U+6307][U+4EE4]
            success = self.execute_command(command_code, param1 or 0, param2 or 0)
            
            # [U+66F4][U+65B0][U+7D50][U+679C]
            if success:
                self.write_register('error_code', 0)
            else:
                self.write_register('error_code', 1)  # [U+57F7][U+884C][U+5931][U+6557]
            
            # [U+6E05][U+9664][U+57F7][U+884C][U+72C0][U+614B]
            self.executing_command = False
            self.write_register('command_status', 0)  # [U+7A7A][U+9592]
            
            # [U+6E05][U+9664][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]
            self.write_register('command_code', 0)
            self.write_register('param1', 0)
            self.write_register('param2', 0)
            self.write_register('command_id', 0)
            
            # [U+66F4][U+65B0][U+6307][U+4EE4]ID
            self.last_command_id = new_command_id
            
        except Exception as e:
            print(f"[U+8655][U+7406][U+6307][U+4EE4][U+5931][U+6557]: {e}")
            self.executing_command = False
            self.write_register('command_status', 0)
            self.error_count += 1
    
    def main_loop(self):
        """[U+4E3B][U+5FAA][U+74B0]"""
        loop_interval = self.config['timing']['fast_loop_interval']
        
        while self.running:
            try:
                with self.loop_lock:
                    # [U+6AA2][U+67E5][U+9023][U+63A5][U+72C0][U+614B]
                    if not self.connected_to_server:
                        if not self.connect_main_server():
                            time.sleep(1)
                            continue
                    
                    if not self.connected_to_device:
                        if not self.connect_device():
                            time.sleep(1)
                            continue
                    
                    # [U+8655][U+7406][U+6307][U+4EE4]
                    self.process_commands()
                    
                    # [U+66F4][U+65B0][U+72C0][U+614B]
                    self.update_status_registers()
                
                time.sleep(loop_interval)
                
            except Exception as e:
                print(f"[U+4E3B][U+5FAA][U+74B0][U+7570][U+5E38]: {e}")
                self.error_count += 1
                time.sleep(0.5)
    
    def start(self) -> bool:
        """[U+555F][U+52D5][U+6A21][U+7D44]"""
        if self.running:
            print("[U+6A21][U+7D44][U+5DF2][U+5728][U+904B][U+884C][U+4E2D]")
            return False
        
        try:
            # [U+9023][U+63A5][U+670D][U+52D9][U+5668][U+548C][U+8A2D][U+5099]
            if not self.connect_main_server():
                print("[U+7121][U+6CD5][U+9023][U+63A5][U+5230][U+4E3B][U+670D][U+52D9][U+5668]")
                return False
            
            if not self.connect_device():
                print("[U+7121][U+6CD5][U+9023][U+63A5][U+5230][U+9707][U+52D5][U+76E4][U+8A2D][U+5099][U+FF0C][U+5C07][U+5728][U+4E3B][U+5FAA][U+74B0][U+4E2D][U+91CD][U+8A66]")
            
            # [U+555F][U+52D5][U+4E3B][U+5FAA][U+74B0]
            self.running = True
            self.main_loop_thread = threading.Thread(target=self.main_loop, daemon=True)
            self.main_loop_thread.start()
            
            print("[U+9707][U+52D5][U+76E4][U+6A21][U+7D44][U+555F][U+52D5][U+6210][U+529F]")
            return True
            
        except Exception as e:
            print(f"[U+555F][U+52D5][U+6A21][U+7D44][U+5931][U+6557]: {e}")
            return False
    
    def stop(self):
        """[U+505C][U+6B62][U+6A21][U+7D44]"""
        print("[U+6B63][U+5728][U+505C][U+6B62][U+9707][U+52D5][U+76E4][U+6A21][U+7D44]...")
        
        self.running = False
        
        # [U+505C][U+6B62][U+9707][U+52D5][U+76E4]
        if self.vibration_plate:
            try:
                self.vibration_plate.stop()
                self.vibration_plate.disconnect()
            except:
                pass
        
        # [U+66F4][U+65B0][U+72C0][U+614B][U+70BA][U+96E2][U+7DDA]
        if self.connected_to_server:
            try:
                self.write_register('module_status', 0)  # [U+96E2][U+7DDA]
                self.write_register('device_connection', 0)
                self.write_register('command_status', 0)
            except:
                pass
        
        # [U+95DC][U+9589][U+9023][U+63A5]
        if self.modbus_client:
            try:
                self.modbus_client.close()
            except:
                pass
        
        # [U+7B49][U+5F85][U+7DDA][U+7A0B][U+7D50][U+675F]
        if self.main_loop_thread and self.main_loop_thread.is_alive():
            self.main_loop_thread.join(timeout=2)
        
        print("[U+9707][U+52D5][U+76E4][U+6A21][U+7D44][U+5DF2][U+505C][U+6B62]")
    
    def get_status(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+6A21][U+7D44][U+72C0][U+614B]"""
        uptime = time.time() - self.start_time
        
        status = {
            'module_id': self.config['module_id'],
            'running': self.running,
            'connected_to_server': self.connected_to_server,
            'connected_to_device': self.connected_to_device,
            'executing_command': self.executing_command,
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'connection_count': self.connection_count,
            'uptime_seconds': int(uptime),
            'last_command_id': self.last_command_id,
            'config': self.config,
            'register_mapping': {
                'base_address': self.base_address,
                'status_registers': self.status_registers,
                'command_registers': self.command_registers
            }
        }
        
        return status


def main():
    """[U+4E3B][U+51FD][U+6578]"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print("[U+9707][U+52D5][U+76E4]Modbus TCP Client[U+555F][U+52D5][U+4E2D]...")
    print(f"[U+57F7][U+884C][U+76EE][U+9304]: {current_dir}")
    
    # [U+5275][U+5EFA][U+6A21][U+7D44][U+5BE6][U+4F8B]
    vp_client = VibrationPlateModbusClient()
    
    # [U+4FE1][U+865F][U+8655][U+7406]
    def signal_handler(sig, frame):
        print("[U+6536][U+5230][U+505C][U+6B62][U+4FE1][U+865F]")
        vp_client.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # [U+555F][U+52D5][U+6A21][U+7D44]
        if vp_client.start():
            print(f"[U+9707][U+52D5][U+76E4][U+6A21][U+7D44][U+904B][U+884C][U+4E2D] - [U+57FA][U+5730][U+5740]: {vp_client.base_address}")
            print("[U+5BC4][U+5B58][U+5668][U+6620][U+5C04]:")
            print(f"  [U+72C0][U+614B][U+5BC4][U+5B58][U+5668]: {vp_client.base_address} ~ {vp_client.base_address + 14}")
            print(f"  [U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]: {vp_client.base_address + 20} ~ {vp_client.base_address + 24}")
            print("[U+6309] Ctrl+C [U+505C][U+6B62][U+7A0B][U+5E8F]")
            
            # [U+4FDD][U+6301][U+904B][U+884C]
            while vp_client.running:
                time.sleep(1)
        else:
            print("[U+6A21][U+7D44][U+555F][U+52D5][U+5931][U+6557]")
            
    except KeyboardInterrupt:
        print("\n[U+6536][U+5230][U+4E2D][U+65B7][U+4FE1][U+865F]")
    except Exception as e:
        print(f"[U+904B][U+884C][U+7570][U+5E38]: {e}")
    finally:
        vp_client.stop()


if __name__ == '__main__':
    main()