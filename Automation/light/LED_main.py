#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LED_main.py - LED[U+63A7][U+5236][U+5668]RS232[U+8F49]ModbusTCP Client[U+4E3B][U+7A0B][U+5E8F]
[U+5BE6][U+73FE]LED[U+63A7][U+5236][U+5668]RS232[U+8F49]TCP[U+6A4B][U+63A5][U+FF0C][U+72C0][U+614B][U+6A5F][U+4EA4][U+63E1][U+FF0C][U+81EA][U+52D5][U+91CD][U+9023]
[U+53C3][U+8003]VP_main.py[U+548C]XCModule.py[U+67B6][U+69CB]
"""

import sys
import os
import time
import threading
import json
import signal
import logging
import serial
import serial.tools.list_ports
from typing import Dict, Any, Optional
from datetime import datetime
from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)

class LEDControllerModbusClient:
    """LED[U+63A7][U+5236][U+5668]Modbus TCP Client - RS232[U+8F49]TCP[U+6A4B][U+63A5][U+6A21][U+7D44]"""
    
    def __init__(self, config_file="led_config.json"):
        # [U+8F09][U+5165][U+914D][U+7F6E]
        self.config = self.load_config(config_file)
        
        # [U+6838][U+5FC3][U+7D44][U+4EF6]
        self.serial_connection: Optional[serial.Serial] = None
        self.modbus_client: Optional[ModbusTcpClient] = None
        self.running = False
        
        # [U+72C0][U+614B][U+8B8A][U+6578]
        self.connected_to_server = False
        self.connected_to_device = False
        self.last_command_id = 0
        self.executing_command = False
        
        # LED[U+72C0][U+614B][U+7BA1][U+7406]
        self.led_states = [False, False, False, False]  # L1-L4[U+958B][U+95DC][U+72C0][U+614B]
        self.led_brightness = [0, 0, 0, 0]  # L1-L4[U+4EAE][U+5EA6] (0-511)
        self.device_error_code = 0
        self.last_error_response = ""
        
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
        
        # [U+8A2D][U+7F6E][U+65E5][U+8A8C]
        self.setup_logging()
        
    def setup_logging(self):
        """[U+8A2D][U+7F6E][U+65E5][U+8A8C]"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """[U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848]"""
        default_config = {
            "module_id": "LED[U+63A7][U+5236][U+5668][U+6A21][U+7D44]",
            "serial_connection": {
                "port": "COM6",
                "baudrate": 9600,
                "parity": "N",
                "stopbits": 1,
                "bytesize": 8,
                "timeout": 1.0
            },
            "tcp_server": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 3.0
            },
            "modbus_mapping": {
                "base_address": 600
            },
            "timing": {
                "fast_loop_interval": 0.05,
                "command_delay": 0.1,
                "serial_delay": 0.05
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
        
        # [U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+5340] ([U+53EA][U+8B80]) base+0 ~ base+15
        self.status_registers = {
            'module_status': base + 0,          # [U+6A21][U+7D44][U+72C0][U+614B] (0=[U+96E2][U+7DDA], 1=[U+9592][U+7F6E], 2=[U+57F7][U+884C][U+4E2D], 3=[U+521D][U+59CB][U+5316], 4=[U+932F][U+8AA4])
            'device_connection': base + 1,      # [U+8A2D][U+5099][U+9023][U+63A5][U+72C0][U+614B] (0=[U+65B7][U+958B], 1=[U+5DF2][U+9023][U+63A5])
            'active_channels': base + 2,        # [U+958B][U+555F][U+901A][U+9053][U+6578][U+91CF]
            'error_code': base + 3,             # [U+932F][U+8AA4][U+4EE3][U+78BC]
            'l1_state': base + 4,               # L1[U+72C0][U+614B] (0=OFF, 1=ON)
            'l2_state': base + 5,               # L2[U+72C0][U+614B]
            'l3_state': base + 6,               # L3[U+72C0][U+614B]
            'l4_state': base + 7,               # L4[U+72C0][U+614B]
            'l1_brightness': base + 8,          # L1[U+4EAE][U+5EA6] (0-511)
            'l2_brightness': base + 9,          # L2[U+4EAE][U+5EA6]
            'l3_brightness': base + 10,         # L3[U+4EAE][U+5EA6]
            'l4_brightness': base + 11,         # L4[U+4EAE][U+5EA6]
            'operation_count': base + 12,       # [U+64CD][U+4F5C][U+8A08][U+6578]
            'error_count': base + 13,           # [U+932F][U+8AA4][U+8A08][U+6578]
            'reserved_14': base + 14,           # [U+4FDD][U+7559]
            'timestamp': base + 15              # [U+6642][U+9593][U+6233]
        }
        
        # [U+6307][U+4EE4][U+5BC4][U+5B58][U+5668][U+5340] ([U+8B80][U+5BEB]) base+20 ~ base+24
        self.command_registers = {
            'command_code': base + 20,          # [U+6307][U+4EE4][U+4EE3][U+78BC]
            'param1': base + 21,                # [U+53C3][U+6578]1 ([U+901A][U+9053][U+865F]/[U+4EAE][U+5EA6][U+503C])
            'param2': base + 22,                # [U+53C3][U+6578]2 ([U+4EAE][U+5EA6][U+503C])
            'command_id': base + 23,            # [U+6307][U+4EE4]ID
            'reserved': base + 24               # [U+4FDD][U+7559]
        }
        
        # [U+6240][U+6709][U+5BC4][U+5B58][U+5668]
        self.all_registers = {**self.status_registers, **self.command_registers}
        
        logger.info(f"[U+5BC4][U+5B58][U+5668][U+6620][U+5C04][U+521D][U+59CB][U+5316][U+5B8C][U+6210] - [U+57FA][U+5730][U+5740]: {base}")
        print(f"LED[U+63A7][U+5236][U+5668][U+6A21][U+7D44][U+5BC4][U+5B58][U+5668][U+6620][U+5C04]:")
        print(f"  [U+57FA][U+5730][U+5740]: {base}")
        print(f"  [U+72C0][U+614B][U+5BC4][U+5B58][U+5668]: {base} ~ {base + 15}")
        print(f"  [U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]: {base + 20} ~ {base + 24}")
        print(f"  [U+6307][U+4EE4][U+6620][U+5C04]:")
        print(f"    0: NOP ([U+7121][U+64CD][U+4F5C])")
        print(f"    1: [U+5168][U+90E8][U+958B][U+555F]")
        print(f"    2: [U+5168][U+90E8][U+95DC][U+9589]") 
        print(f"    3: [U+91CD][U+7F6E][U+8A2D][U+5099]")
        print(f"    4: [U+8A2D][U+5B9A][U+55AE][U+4E00][U+901A][U+9053][U+4EAE][U+5EA6] (param1=[U+901A][U+9053]1-4, param2=[U+4EAE][U+5EA6]0-511)")
        print(f"    5: [U+958B][U+555F][U+55AE][U+4E00][U+901A][U+9053] (param1=[U+901A][U+9053]1-4)")
        print(f"    6: [U+95DC][U+9589][U+55AE][U+4E00][U+901A][U+9053] (param1=[U+901A][U+9053]1-4)")
        print(f"    7: [U+932F][U+8AA4][U+91CD][U+7F6E]")
    
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
    
    def connect_serial_device(self) -> bool:
        """[U+9023][U+63A5][U+5230]LED[U+63A7][U+5236][U+5668][U+4E32][U+53E3][U+8A2D][U+5099]"""
        try:
            if self.serial_connection:
                self.serial_connection.close()
            
            serial_config = self.config['serial_connection']
            self.serial_connection = serial.Serial(
                port=serial_config['port'],
                baudrate=serial_config['baudrate'],
                parity=serial_config['parity'],
                stopbits=serial_config['stopbits'],
                bytesize=serial_config['bytesize'],
                timeout=serial_config['timeout']
            )
            
            if self.serial_connection.is_open:
                self.connected_to_device = True
                print(f"[U+9023][U+63A5][U+5230]LED[U+63A7][U+5236][U+5668][U+6210][U+529F]: {serial_config['port']}")
                
                # [U+6E2C][U+8A66][U+901A][U+8A0A] - [U+767C][U+9001]VERSION[U+67E5][U+8A62]
                test_result = self.send_serial_command("VERSION?")
                if test_result:
                    print("LED[U+63A7][U+5236][U+5668][U+901A][U+8A0A][U+6E2C][U+8A66][U+6210][U+529F]")
                else:
                    print("LED[U+63A7][U+5236][U+5668][U+901A][U+8A0A][U+6E2C][U+8A66][U+7121][U+56DE][U+61C9][U+FF0C][U+4F46][U+4FDD][U+6301][U+9023][U+63A5]")
                
                return True
            else:
                print("LED[U+63A7][U+5236][U+5668][U+4E32][U+53E3][U+958B][U+555F][U+5931][U+6557]")
                return False
                
        except Exception as e:
            print(f"[U+9023][U+63A5]LED[U+63A7][U+5236][U+5668][U+7570][U+5E38]: {e}")
            self.connected_to_device = False
            return False
    
    def send_serial_command(self, command: str) -> bool:
        """[U+767C][U+9001]RS232[U+6307][U+4EE4][U+5230]LED[U+63A7][U+5236][U+5668]"""
        if not self.connected_to_device or not self.serial_connection:
            self.logger.error("[U+4E32][U+53E3][U+8A2D][U+5099][U+672A][U+9023][U+63A5]")
            return False
        
        try:
            # [U+6DFB][U+52A0][U+63DB][U+884C][U+7B26] ([U+6839][U+64DA][U+624B][U+518A][U+8981][U+6C42])
            full_command = command + "\r\n"
            self.serial_connection.write(full_command.encode('ascii'))
            
            # [U+8B80][U+53D6][U+56DE][U+61C9]
            time.sleep(self.config['timing']['serial_delay'])
            response = ""
            if self.serial_connection.in_waiting > 0:
                response = self.serial_connection.read(self.serial_connection.in_waiting).decode('ascii', errors='ignore')
                self.logger.debug(f"[U+767C][U+9001]: {command} | [U+56DE][U+61C9]: {response.strip()}")
            else:
                self.logger.debug(f"[U+767C][U+9001]: {command} | [U+7121][U+56DE][U+61C9]")
            
            self.operation_count += 1
            return True
            
        except Exception as e:
            self.logger.error(f"[U+767C][U+9001][U+4E32][U+53E3][U+6307][U+4EE4][U+5931][U+6557]: {e}")
            self.error_count += 1
            return False
    
    def init_status_registers(self):
        """[U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]"""
        try:
            # [U+5BEB][U+5165][U+6A21][U+7D44][U+57FA][U+672C][U+8CC7][U+8A0A]
            self.write_register('module_status', 1)  # [U+9592][U+7F6E][U+72C0][U+614B]
            self.write_register('error_code', 0)     # [U+7121][U+932F][U+8AA4]
            self.write_register('operation_count', self.operation_count)
            self.write_register('error_count', self.error_count)
            
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
                address=address,
                count=1,
                slave=self.config['tcp_server']['unit_id']
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
                address=address,
                value=value,
                slave=self.config['tcp_server']['unit_id']
            )
            
            return not result.isError()
                
        except Exception as e:
            pass  # [U+975C][U+9ED8][U+8655][U+7406][U+5BEB][U+5165][U+932F][U+8AA4]
            return False
    
    def execute_command(self, command: int, param1: int, param2: int) -> bool:
        """[U+57F7][U+884C]LED[U+63A7][U+5236][U+6307][U+4EE4]"""
        if not self.connected_to_device:
            self.logger.error("LED[U+8A2D][U+5099][U+672A][U+9023][U+63A5][U+FF0C][U+7121][U+6CD5][U+57F7][U+884C][U+6307][U+4EE4]")
            return False
        
        try:
            success = False
            
            if command == 0:  # NOP
                success = True
                
            elif command == 1:  # [U+5168][U+90E8][U+958B][U+555F]
                success = True
                for i in range(4):
                    cmd = f"CH{i+1}:255"
                    if self.send_serial_command(cmd):
                        self.led_states[i] = True
                        self.led_brightness[i] = 255
                    else:
                        success = False
                    time.sleep(self.config['timing']['serial_delay'])
                
            elif command == 2:  # [U+5168][U+90E8][U+95DC][U+9589]
                success = True
                for i in range(4):
                    cmd = f"CH{i+1}:0"
                    if self.send_serial_command(cmd):
                        self.led_states[i] = False
                        self.led_brightness[i] = 0
                    else:
                        success = False
                    time.sleep(self.config['timing']['serial_delay'])
                
            elif command == 3:  # [U+91CD][U+7F6E][U+8A2D][U+5099]
                success = self.send_serial_command("RESET")
                if success:
                    # [U+91CD][U+7F6E][U+672C][U+5730][U+72C0][U+614B]
                    for i in range(4):
                        self.led_states[i] = False
                        self.led_brightness[i] = 0
                
            elif command == 4:  # [U+8A2D][U+5B9A][U+55AE][U+4E00][U+901A][U+9053][U+4EAE][U+5EA6]
                if 1 <= param1 <= 4 and 0 <= param2 <= 511:
                    cmd = f"CH{param1}:{param2}"
                    success = self.send_serial_command(cmd)
                    if success:
                        channel_idx = param1 - 1
                        self.led_brightness[channel_idx] = param2
                        self.led_states[channel_idx] = param2 > 0
                
            elif command == 5:  # [U+958B][U+555F][U+55AE][U+4E00][U+901A][U+9053]
                if 1 <= param1 <= 4:
                    channel_idx = param1 - 1
                    brightness = self.led_brightness[channel_idx] if self.led_brightness[channel_idx] > 0 else 255
                    cmd = f"CH{param1}:{brightness}"
                    success = self.send_serial_command(cmd)
                    if success:
                        self.led_states[channel_idx] = True
                        self.led_brightness[channel_idx] = brightness
                
            elif command == 6:  # [U+95DC][U+9589][U+55AE][U+4E00][U+901A][U+9053]
                if 1 <= param1 <= 4:
                    cmd = f"CH{param1}:0"
                    success = self.send_serial_command(cmd)
                    if success:
                        channel_idx = param1 - 1
                        self.led_states[channel_idx] = False
                        self.led_brightness[channel_idx] = 0
                
            elif command == 7:  # [U+932F][U+8AA4][U+91CD][U+7F6E]
                self.error_count = 0
                self.device_error_code = 0
                success = True
            
            if success:
                print(f"[U+6307][U+4EE4][U+57F7][U+884C][U+6210][U+529F]: cmd={command}, p1={param1}, p2={param2}")
            else:
                self.error_count += 1
                print(f"[U+6307][U+4EE4][U+57F7][U+884C][U+5931][U+6557]: cmd={command}, p1={param1}, p2={param2}")
                
            return success
            
        except Exception as e:
            print(f"[U+57F7][U+884C][U+6307][U+4EE4][U+7570][U+5E38]: {e}")
            self.error_count += 1
            return False
    
    def update_status_registers(self):
        """[U+66F4][U+65B0][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]"""
        try:
            # [U+66F4][U+65B0][U+9023][U+63A5][U+72C0][U+614B]
            self.write_register('device_connection', 1 if self.connected_to_device else 0)
            
            # [U+66F4][U+65B0]LED[U+72C0][U+614B]
            for i in range(4):
                self.write_register(f'l{i+1}_state', 1 if self.led_states[i] else 0)
                self.write_register(f'l{i+1}_brightness', self.led_brightness[i])
            
            # [U+66F4][U+65B0][U+6D3B][U+52D5][U+901A][U+9053][U+6578][U+91CF]
            active_count = sum(1 for state in self.led_states if state)
            self.write_register('active_channels', active_count)
            
            # [U+66F4][U+65B0][U+6A21][U+7D44][U+72C0][U+614B]
            if self.executing_command:
                self.write_register('module_status', 2)  # [U+57F7][U+884C][U+4E2D]
            elif not self.connected_to_device:
                self.write_register('module_status', 0)  # [U+96E2][U+7DDA]
            elif self.error_count > 10:
                self.write_register('module_status', 4)  # [U+932F][U+8AA4]
            else:
                self.write_register('module_status', 1)  # [U+9592][U+7F6E]
            
            # [U+66F4][U+65B0][U+7D71][U+8A08][U+4FE1][U+606F]
            self.write_register('operation_count', self.operation_count % 65536)
            self.write_register('error_count', self.error_count % 65536)
            self.write_register('error_code', self.device_error_code)
            self.write_register('timestamp', int(time.time()) % 65536)
            
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
            
            # [U+57F7][U+884C][U+6307][U+4EE4]
            success = self.execute_command(command_code, param1 or 0, param2 or 0)
            
            # [U+66F4][U+65B0][U+932F][U+8AA4][U+72C0][U+614B]
            if not success:
                self.device_error_code = 1  # [U+6307][U+4EE4][U+57F7][U+884C][U+5931][U+6557]
            else:
                self.device_error_code = 0  # [U+57F7][U+884C][U+6210][U+529F]
            
            # [U+6E05][U+9664][U+57F7][U+884C][U+72C0][U+614B]
            self.executing_command = False
            
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
                        if not self.connect_serial_device():
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
            
            if not self.connect_serial_device():
                print("[U+7121][U+6CD5][U+9023][U+63A5][U+5230]LED[U+8A2D][U+5099][U+FF0C][U+5C07][U+5728][U+4E3B][U+5FAA][U+74B0][U+4E2D][U+91CD][U+8A66]")
            
            # [U+555F][U+52D5][U+4E3B][U+5FAA][U+74B0]
            self.running = True
            self.main_loop_thread = threading.Thread(target=self.main_loop, daemon=True)
            self.main_loop_thread.start()
            
            print("LED[U+63A7][U+5236][U+5668][U+6A21][U+7D44][U+555F][U+52D5][U+6210][U+529F]")
            return True
            
        except Exception as e:
            print(f"[U+555F][U+52D5][U+6A21][U+7D44][U+5931][U+6557]: {e}")
            return False
    
    def stop(self):
        """[U+505C][U+6B62][U+6A21][U+7D44]"""
        print("[U+6B63][U+5728][U+505C][U+6B62]LED[U+63A7][U+5236][U+5668][U+6A21][U+7D44]...")
        
        self.running = False
        
        # [U+95DC][U+9589]LED ([U+5982][U+679C][U+9023][U+63A5])
        if self.connected_to_device:
            try:
                for i in range(4):
                    self.send_serial_command(f"CH{i+1}:0")
                    time.sleep(0.05)
            except:
                pass
        
        # [U+66F4][U+65B0][U+72C0][U+614B][U+70BA][U+96E2][U+7DDA]
        if self.connected_to_server:
            try:
                self.write_register('module_status', 0)  # [U+96E2][U+7DDA]
                self.write_register('device_connection', 0)
            except:
                pass
        
        # [U+95DC][U+9589][U+9023][U+63A5]
        if self.serial_connection:
            try:
                self.serial_connection.close()
            except:
                pass
        
        if self.modbus_client:
            try:
                self.modbus_client.close()
            except:
                pass
        
        # [U+7B49][U+5F85][U+7DDA][U+7A0B][U+7D50][U+675F]
        if self.main_loop_thread and self.main_loop_thread.is_alive():
            self.main_loop_thread.join(timeout=2)
        
        print("LED[U+63A7][U+5236][U+5668][U+6A21][U+7D44][U+5DF2][U+505C][U+6B62]")
    
    def get_status(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+6A21][U+7D44][U+72C0][U+614B]"""
        uptime = time.time() - self.start_time
        
        status = {
            'module_id': self.config['module_id'],
            'running': self.running,
            'connected_to_server': self.connected_to_server,
            'connected_to_device': self.connected_to_device,
            'executing_command': self.executing_command,
            'led_states': self.led_states.copy(),
            'led_brightness': self.led_brightness.copy(),
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'connection_count': self.connection_count,
            'uptime_seconds': int(uptime),
            'last_command_id': self.last_command_id,
            'device_error_code': self.device_error_code,
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
    print("LED[U+63A7][U+5236][U+5668]Modbus TCP Client[U+555F][U+52D5][U+4E2D]...")
    print(f"[U+57F7][U+884C][U+76EE][U+9304]: {current_dir}")
    
    # [U+5275][U+5EFA][U+6A21][U+7D44][U+5BE6][U+4F8B]
    led_client = LEDControllerModbusClient()
    
    # [U+4FE1][U+865F][U+8655][U+7406]
    def signal_handler(sig, frame):
        print("[U+6536][U+5230][U+505C][U+6B62][U+4FE1][U+865F]")
        led_client.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # [U+555F][U+52D5][U+6A21][U+7D44]
        if led_client.start():
            print(f"LED[U+63A7][U+5236][U+5668][U+6A21][U+7D44][U+904B][U+884C][U+4E2D] - [U+57FA][U+5730][U+5740]: {led_client.base_address}")
            print("[U+5BC4][U+5B58][U+5668][U+6620][U+5C04]:")
            print(f"  [U+72C0][U+614B][U+5BC4][U+5B58][U+5668]: {led_client.base_address} ~ {led_client.base_address + 15}")
            print(f"  [U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]: {led_client.base_address + 20} ~ {led_client.base_address + 24}")
            print("[U+6309] Ctrl+C [U+505C][U+6B62][U+7A0B][U+5E8F]")
            
            # [U+4FDD][U+6301][U+904B][U+884C]
            while led_client.running:
                time.sleep(1)
        else:
            print("[U+6A21][U+7D44][U+555F][U+52D5][U+5931][U+6557]")
            
    except KeyboardInterrupt:
        print("\n[U+6536][U+5230][U+4E2D][U+65B7][U+4FE1][U+865F]")
    except Exception as e:
        print(f"[U+904B][U+884C][U+7570][U+5E38]: {e}")
    finally:
        led_client.stop()


if __name__ == '__main__':
    main()