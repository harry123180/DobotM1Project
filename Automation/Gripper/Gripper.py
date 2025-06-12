# -*- coding: utf-8 -*-
# Gripper.py - [U+593E][U+722A][U+4E3B][U+6A21][U+7D44]
import os
import json
import time
import threading
from datetime import datetime
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException

class GripperModule:
    def __init__(self, config_file="gripper_config.json"):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.current_dir, config_file)
        self.config = self.load_config()
        
        # [U+9023][U+63A5][U+72C0][U+614B]
        self.main_server_client = None
        self.rtu_client = None
        self.is_running = False
        
        # [U+7DDA][U+7A0B][U+9396]
        self.state_lock = threading.Lock()
        
        # [U+593E][U+722A][U+72C0][U+614B]
        self.gripper_states = {
            'PGC': {'connected': False, 'last_error': 0, 'error_count': 0},
            'PGHL': {'connected': False, 'last_error': 0, 'error_count': 0},
            'PGE': {'connected': False, 'last_error': 0, 'error_count': 0}
        }
        
        # [U+6307][U+4EE4]ID[U+8FFD][U+8E64]
        self.last_command_ids = {'PGC': 0, 'PGHL': 0, 'PGE': 0}
        
        # [U+5BC4][U+5B58][U+5668][U+57FA][U+5730][U+5740][U+914D][U+7F6E]
        self.register_mapping = {
            'PGC': {'status_base': 500, 'command_base': 520, 'unit_id': 6},
            'PGHL': {'status_base': 530, 'command_base': 550, 'unit_id': 5},
            'PGE': {'status_base': 560, 'command_base': 580, 'unit_id': 4}
        }
        
        print(f"[U+593E][U+722A][U+6A21][U+7D44][U+555F][U+52D5] - [U+57FA][U+5730][U+5740]: 500-589")
        print("[U+5BC4][U+5B58][U+5668][U+6620][U+5C04]:")
        for gripper, mapping in self.register_mapping.items():
            print(f"  {gripper}: [U+72C0][U+614B] {mapping['status_base']}-{mapping['status_base']+19}, [U+6307][U+4EE4] {mapping['command_base']}-{mapping['command_base']+9}")

    def load_config(self):
        default_config = {
            "module_id": "[U+593E][U+722A][U+6A21][U+7D44]",
            "rtu_connection": {
                "port": "COM5",
                "baudrate": 115200,
                "parity": "N",
                "stopbits": 1,
                "timeout": 1.0
            },
            "tcp_server": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 1.0
            },
            "modbus_mapping": {
                "base_address": 500
            },
            "timing": {
                "fast_loop_interval": 0.05,
                "command_delay": 0.02,
                "reconnect_interval": 5.0
            },
            "grippers": {
                "PGC": {"unit_id": 6, "enabled": True},
                "PGHL": {"unit_id": 5, "enabled": True}, 
                "PGE": {"unit_id": 4, "enabled": True}
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

    def connect_main_server(self):
        try:
            if self.main_server_client and self.main_server_client.connected:
                return True
                
            self.main_server_client = ModbusTcpClient(
                host=self.config["tcp_server"]["host"],
                port=self.config["tcp_server"]["port"],
                timeout=self.config["tcp_server"]["timeout"]
            )
            
            if self.main_server_client.connect():
                print(f"[U+5DF2][U+9023][U+63A5][U+4E3B][U+670D][U+52D9][U+5668]: {self.config['tcp_server']['host']}:{self.config['tcp_server']['port']}")
                return True
            else:
                print("[U+4E3B][U+670D][U+52D9][U+5668][U+9023][U+63A5][U+5931][U+6557]")
                return False
        except Exception as e:
            print(f"[U+4E3B][U+670D][U+52D9][U+5668][U+9023][U+63A5][U+932F][U+8AA4]: {e}")
            return False

    def connect_rtu_devices(self):
        try:
            if self.rtu_client and self.rtu_client.connected:
                return True
                
            self.rtu_client = ModbusSerialClient(
                port=self.config["rtu_connection"]["port"],
                baudrate=self.config["rtu_connection"]["baudrate"],
                parity=self.config["rtu_connection"]["parity"],
                stopbits=self.config["rtu_connection"]["stopbits"],
                timeout=self.config["rtu_connection"]["timeout"]
            )
            
            if self.rtu_client.connect():
                print(f"[U+5DF2][U+9023][U+63A5]RTU[U+8A2D][U+5099]: {self.config['rtu_connection']['port']}")
                return True
            else:
                print("RTU[U+8A2D][U+5099][U+9023][U+63A5][U+5931][U+6557]")
                return False
        except Exception as e:
            print(f"RTU[U+8A2D][U+5099][U+9023][U+63A5][U+932F][U+8AA4]: {e}")
            return False

    def test_gripper_connection(self, gripper_type):
        """[U+6E2C][U+8A66][U+55AE][U+500B][U+593E][U+722A][U+9023][U+63A5]"""
        try:
            if not self.rtu_client or not self.rtu_client.connected:
                self.gripper_states[gripper_type]['connected'] = False
                return False
                
            unit_id = self.register_mapping[gripper_type]['unit_id']
            
            # [U+5617][U+8A66][U+8B80][U+53D6][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+FF0C][U+4F7F][U+7528][U+6B63][U+78BA][U+7684]PyModbus 3.x[U+8A9E][U+6CD5]
            result = self.rtu_client.read_holding_registers(address=0x0200, count=1, slave=unit_id)
            
            if result and not result.isError():
                self.gripper_states[gripper_type]['connected'] = True
                #print(f"{gripper_type}[U+593E][U+722A][U+9023][U+63A5][U+6B63][U+5E38] (unit_id={unit_id})")
                return True
            else:
                self.gripper_states[gripper_type]['connected'] = False
                print(f"{gripper_type}[U+593E][U+722A][U+9023][U+63A5][U+5931][U+6557] (unit_id={unit_id})")
                return False
                
        except Exception as e:
            self.gripper_states[gripper_type]['connected'] = False
            self.gripper_states[gripper_type]['error_count'] += 1
            print(f"{gripper_type}[U+593E][U+722A][U+9023][U+63A5][U+6E2C][U+8A66][U+7570][U+5E38]: {e}")
            return False

    def read_gripper_status(self, gripper_type):
        """[U+8B80][U+53D6][U+593E][U+722A][U+72C0][U+614B]"""
        try:
            if not self.rtu_client or not self.rtu_client.connected:
                return None
                
            unit_id = self.register_mapping[gripper_type]['unit_id']
            status_data = {}
            
            if gripper_type == 'PGC':
                # PGC[U+72C0][U+614B][U+8B80][U+53D6] - [U+4F7F][U+7528][U+6B63][U+78BA][U+7684]PyModbus 3.x[U+8A9E][U+6CD5]
                init_status = self.rtu_client.read_holding_registers(address=0x0200, count=1, slave=unit_id)
                if init_status.isError():
                    return None
                    
                grip_status = self.rtu_client.read_holding_registers(address=0x0201, count=1, slave=unit_id) 
                if grip_status.isError():
                    return None
                    
                position = self.rtu_client.read_holding_registers(address=0x0202, count=1, slave=unit_id)
                if position.isError():
                    return None
                    
                status_data = {
                    'init_status': init_status.registers[0],
                    'grip_status': grip_status.registers[0],
                    'position': position.registers[0],
                    'connected': True
                }
                
            elif gripper_type == 'PGHL':
                # PGHL[U+72C0][U+614B][U+8B80][U+53D6] - [U+4F7F][U+7528][U+6B63][U+78BA][U+7684]PyModbus 3.x[U+8A9E][U+6CD5]
                home_status = self.rtu_client.read_holding_registers(address=0x0200, count=1, slave=unit_id)
                if home_status.isError():
                    return None
                    
                running_status = self.rtu_client.read_holding_registers(address=0x0201, count=1, slave=unit_id)
                if running_status.isError():
                    return None
                    
                position = self.rtu_client.read_holding_registers(address=0x0202, count=1, slave=unit_id)
                if position.isError():
                    return None
                    
                current = self.rtu_client.read_holding_registers(address=0x0204, count=1, slave=unit_id)
                if current.isError():
                    return None
                    
                status_data = {
                    'home_status': home_status.registers[0],
                    'running_status': running_status.registers[0], 
                    'position': position.registers[0],
                    'current': current.registers[0],
                    'connected': True
                }
                
            elif gripper_type == 'PGE':
                # PGE[U+72C0][U+614B][U+8B80][U+53D6] - [U+4F7F][U+7528][U+6B63][U+78BA][U+7684]PyModbus 3.x[U+8A9E][U+6CD5]
                init_status = self.rtu_client.read_holding_registers(address=0x0200, count=1, slave=unit_id)
                if init_status.isError():
                    return None
                    
                grip_status = self.rtu_client.read_holding_registers(address=0x0201, count=1, slave=unit_id)
                if grip_status.isError():
                    return None
                    
                position = self.rtu_client.read_holding_registers(address=0x0202, count=1, slave=unit_id)
                if position.isError():
                    return None
                    
                status_data = {
                    'init_status': init_status.registers[0],
                    'grip_status': grip_status.registers[0],
                    'position': position.registers[0],
                    'connected': True
                }
            
            return status_data
            
        except Exception as e:
            self.gripper_states[gripper_type]['error_count'] += 1
            return None

    def execute_gripper_command(self, gripper_type, command, param1=0, param2=0):
        """[U+57F7][U+884C][U+593E][U+722A][U+6307][U+4EE4]"""
        try:
            if not self.rtu_client or not self.rtu_client.connected:
                return False
                
            unit_id = self.register_mapping[gripper_type]['unit_id']
            success = False
            
            if gripper_type == 'PGC':
                success = self.execute_pgc_command(unit_id, command, param1, param2)
            elif gripper_type == 'PGHL':
                success = self.execute_pghl_command(unit_id, command, param1, param2)
            elif gripper_type == 'PGE':
                success = self.execute_pge_command(unit_id, command, param1, param2)
                
            if not success:
                self.gripper_states[gripper_type]['error_count'] += 1
                
            return success
            
        except Exception as e:
            self.gripper_states[gripper_type]['error_count'] += 1
            return False

    def execute_pgc_command(self, unit_id, command, param1, param2):
        """[U+57F7][U+884C]PGC[U+593E][U+722A][U+6307][U+4EE4]"""
        try:
            if command == 1:  # [U+521D][U+59CB][U+5316]
                result = self.rtu_client.write_register(address=0x0100, value=0x01, slave=unit_id)
            elif command == 2:  # [U+505C][U+6B62]
                result = self.rtu_client.write_register(address=0x0100, value=0, slave=unit_id)
            elif command == 3:  # [U+8A2D][U+5B9A][U+4F4D][U+7F6E]([U+7D55][U+5C0D])
                result = self.rtu_client.write_register(address=0x0103, value=param1, slave=unit_id)
            elif command == 5:  # [U+8A2D][U+5B9A][U+529B][U+9053]
                result = self.rtu_client.write_register(address=0x0101, value=param1, slave=unit_id)
            elif command == 6:  # [U+8A2D][U+5B9A][U+901F][U+5EA6]
                result = self.rtu_client.write_register(address=0x0104, value=param1, slave=unit_id)
            elif command == 7:  # [U+958B][U+555F]
                result = self.rtu_client.write_register(address=0x0103, value=1000, slave=unit_id)
            elif command == 8:  # [U+95DC][U+9589]
                result = self.rtu_client.write_register(address=0x0103, value=0, slave=unit_id)
            else:
                return True  # NOP[U+6216][U+672A][U+77E5][U+6307][U+4EE4]
                
            return not result.isError() if result else False
            
        except Exception:
            return False

    def execute_pghl_command(self, unit_id, command, param1, param2):
        """[U+57F7][U+884C]PGHL[U+593E][U+722A][U+6307][U+4EE4]"""
        try:
            if command == 1:  # [U+521D][U+59CB][U+5316]
                result = self.rtu_client.write_register(address=0x0100, value=1, slave=unit_id)
            elif command == 2:  # [U+505C][U+6B62]
                result = self.rtu_client.write_register(address=0x0100, value=0, slave=unit_id)
            elif command == 3:  # [U+8A2D][U+5B9A][U+4F4D][U+7F6E]([U+7D55][U+5C0D])
                result = self.rtu_client.write_register(address=0x0103, value=param1, slave=unit_id)
            elif command == 4:  # [U+8A2D][U+5B9A][U+4F4D][U+7F6E]([U+76F8][U+5C0D])
                result = self.rtu_client.write_register(address=0x0106, value=param1, slave=unit_id)
            elif command == 5:  # [U+8A2D][U+5B9A][U+529B][U+9053]
                result = self.rtu_client.write_register(address=0x0101, value=param1, slave=unit_id)
            elif command == 6:  # [U+8A2D][U+5B9A][U+901F][U+5EA6]
                result = self.rtu_client.write_register(address=0x0104, value=param1, slave=unit_id)
            elif command == 7:  # [U+958B][U+555F]
                result = self.rtu_client.write_register(address=0x0103, value=param1 if param1 > 0 else 5000, slave=unit_id)
            elif command == 8:  # [U+95DC][U+9589]
                result = self.rtu_client.write_register(address=0x0103, value=0, slave=unit_id)
            else:
                return True  # NOP[U+6216][U+672A][U+77E5][U+6307][U+4EE4]
                
            return not result.isError() if result else False
            
        except Exception:
            return False

    def execute_pge_command(self, unit_id, command, param1, param2):
        """[U+57F7][U+884C]PGE[U+593E][U+722A][U+6307][U+4EE4]"""
        try:
            if command == 1:  # [U+521D][U+59CB][U+5316]
                result = self.rtu_client.write_register(address=0x0100, value=0x01, slave=unit_id)
            elif command == 2:  # [U+505C][U+6B62]
                result = self.rtu_client.write_register(address=0x0100, value=0, slave=unit_id)
            elif command == 3:  # [U+8A2D][U+5B9A][U+4F4D][U+7F6E]([U+7D55][U+5C0D])
                result = self.rtu_client.write_register(address=0x0103, value=param1, slave=unit_id)
            elif command == 5:  # [U+8A2D][U+5B9A][U+529B][U+9053]
                result = self.rtu_client.write_register(address=0x0101, value=param1, slave=unit_id)
            elif command == 6:  # [U+8A2D][U+5B9A][U+901F][U+5EA6]
                result = self.rtu_client.write_register(address=0x0104, value=param1, slave=unit_id)
            elif command == 7:  # [U+958B][U+555F]
                result = self.rtu_client.write_register(address=0x0103, value=1000, slave=unit_id)
            elif command == 8:  # [U+95DC][U+9589]
                result = self.rtu_client.write_register(address=0x0103, value=0, slave=unit_id)
            else:
                return True  # NOP[U+6216][U+672A][U+77E5][U+6307][U+4EE4]
                
            return not result.isError() if result else False
            
        except Exception:
            return False

    def update_status_registers(self):
        """[U+66F4][U+65B0][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+5230][U+4E3B][U+670D][U+52D9][U+5668]"""
        try:
            if not self.main_server_client or not self.main_server_client.connected:
                return
                
            for gripper_type in ['PGC', 'PGHL', 'PGE']:
                mapping = self.register_mapping[gripper_type]
                status_base = mapping['status_base']
                
                # [U+8B80][U+53D6][U+593E][U+722A][U+72C0][U+614B]
                status_data = self.read_gripper_status(gripper_type)
                
                # [U+6E96][U+5099][U+5BC4][U+5B58][U+5668][U+6578][U+64DA]
                registers = [0] * 20  # 20[U+500B][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
                
                if status_data:
                    # [U+901A][U+7528][U+72C0][U+614B]
                    registers[0] = 1  # [U+6A21][U+7D44][U+72C0][U+614B] - [U+5728][U+7DDA]
                    registers[1] = 1  # [U+9023][U+63A5][U+72C0][U+614B] - [U+5DF2][U+9023][U+63A5]
                    registers[3] = self.gripper_states[gripper_type]['error_count']  # [U+932F][U+8AA4][U+8A08][U+6578]
                    registers[14] = int(time.time()) & 0xFFFF  # [U+6642][U+9593][U+6233]
                    
                    # [U+578B][U+865F][U+7279][U+5B9A][U+72C0][U+614B]
                    if gripper_type == 'PGC':
                        registers[2] = status_data.get('init_status', 0)      # [U+521D][U+59CB][U+5316][U+72C0][U+614B]
                        registers[4] = status_data.get('grip_status', 0)      # [U+593E][U+6301][U+72C0][U+614B]  
                        registers[5] = status_data.get('position', 0)         # [U+4F4D][U+7F6E]
                    elif gripper_type == 'PGHL':
                        registers[2] = status_data.get('home_status', 0)      # [U+56DE][U+96F6][U+72C0][U+614B]
                        registers[4] = status_data.get('running_status', 0)   # [U+904B][U+884C][U+72C0][U+614B]
                        registers[5] = status_data.get('position', 0)         # [U+4F4D][U+7F6E]
                        registers[6] = status_data.get('current', 0)          # [U+96FB][U+6D41]
                    elif gripper_type == 'PGE':
                        registers[2] = status_data.get('init_status', 0)      # [U+521D][U+59CB][U+5316][U+72C0][U+614B]
                        registers[4] = status_data.get('grip_status', 0)      # [U+593E][U+6301][U+72C0][U+614B]
                        registers[5] = status_data.get('position', 0)         # [U+4F4D][U+7F6E]
                    
                    #print(f"[U+66F4][U+65B0]{gripper_type}[U+72C0][U+614B][U+5230][U+5730][U+5740]{status_base}: [U+9023][U+63A5]={registers[1]}, [U+72C0][U+614B]={registers[2]}, [U+4F4D][U+7F6E]={registers[5]}")
                else:
                    # [U+8A2D][U+5099][U+96E2][U+7DDA][U+72C0][U+614B]
                    registers[0] = 0  # [U+6A21][U+7D44][U+72C0][U+614B] - [U+96E2][U+7DDA]
                    registers[1] = 0  # [U+9023][U+63A5][U+72C0][U+614B] - [U+65B7][U+958B]
                    registers[3] = self.gripper_states[gripper_type]['error_count']
                    #print(f"[U+66F4][U+65B0]{gripper_type}[U+72C0][U+614B][U+5230][U+5730][U+5740]{status_base}: [U+96E2][U+7DDA]")
                
                # [U+5BEB][U+5165][U+4E3B][U+670D][U+52D9][U+5668]
                result = self.main_server_client.write_registers(
                    address=status_base,
                    values=registers,
                    slave=self.config["tcp_server"]["unit_id"]
                )
                
                if result.isError():
                    print(f"[U+5BEB][U+5165]{gripper_type}[U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {result}")
                    
        except Exception as e:
            print(f"[U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+66F4][U+65B0][U+932F][U+8AA4]: {e}")

    def process_commands(self):
        """[U+8655][U+7406][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]"""
        try:
            if not self.main_server_client or not self.main_server_client.connected:
                return
                
            for gripper_type in ['PGC', 'PGHL', 'PGE']:
                mapping = self.register_mapping[gripper_type]
                command_base = mapping['command_base']
                
                # [U+8B80][U+53D6][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]
                result = self.main_server_client.read_holding_registers(
                    address=command_base,
                    count=10,
                    slave=self.config["tcp_server"]["unit_id"]
                )
                
                if result.isError():
                    continue
                    
                command_id = result.registers[3]  # [U+6307][U+4EE4]ID
                
                # [U+6AA2][U+67E5][U+65B0][U+6307][U+4EE4]
                if command_id != 0 and command_id != self.last_command_ids[gripper_type]:
                    self.last_command_ids[gripper_type] = command_id
                    
                    command = result.registers[0]  # [U+6307][U+4EE4][U+4EE3][U+78BC]
                    param1 = result.registers[1]   # [U+53C3][U+6578]1
                    param2 = result.registers[2]   # [U+53C3][U+6578]2
                    
                    print(f"[U+6536][U+5230]{gripper_type}[U+6307][U+4EE4]: [U+4EE3][U+78BC]={command}, [U+53C3][U+6578]1={param1}, [U+53C3][U+6578]2={param2}, ID={command_id}")
                    
                    # [U+57F7][U+884C][U+6307][U+4EE4]
                    success = self.execute_gripper_command(gripper_type, command, param1, param2)
                    
                    if success:
                        print(f"{gripper_type}[U+6307][U+4EE4][U+57F7][U+884C][U+6210][U+529F]")
                    else:
                        print(f"{gripper_type}[U+6307][U+4EE4][U+57F7][U+884C][U+5931][U+6557]")
                    
                    # [U+6E05][U+9664][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]
                    clear_values = [0] * 10
                    self.main_server_client.write_registers(
                        address=command_base,
                        values=clear_values,
                        slave=self.config["tcp_server"]["unit_id"]
                    )
                    
                    time.sleep(self.config["timing"]["command_delay"])
                    
        except Exception as e:
            print(f"[U+6307][U+4EE4][U+8655][U+7406][U+932F][U+8AA4]: {e}")

    def fast_loop(self):
        """[U+4E3B][U+5FAA][U+74B0]"""
        print("[U+593E][U+722A][U+4E3B][U+5FAA][U+74B0][U+555F][U+52D5]")
        
        while self.is_running:
            try:
                start_time = time.time()
                
                # [U+6AA2][U+67E5][U+9023][U+63A5]
                if not self.connect_main_server():
                    print("[U+4E3B][U+670D][U+52D9][U+5668][U+9023][U+63A5][U+5931][U+6557][U+FF0C][U+7B49][U+5F85][U+91CD][U+8A66]...")
                    time.sleep(1)
                    continue
                    
                if not self.connect_rtu_devices():
                    print("RTU[U+8A2D][U+5099][U+9023][U+63A5][U+5931][U+6557][U+FF0C][U+7B49][U+5F85][U+91CD][U+8A66]...")
                    time.sleep(1)
                    continue
                
                # [U+6E2C][U+8A66][U+593E][U+722A][U+9023][U+63A5][U+FF08][U+6BCF]10[U+500B][U+5FAA][U+74B0][U+6E2C][U+8A66][U+4E00][U+6B21][U+FF0C][U+6E1B][U+5C11][U+8CA0][U+8F09][U+FF09]
                loop_count = getattr(self, 'loop_count', 0)
                if loop_count % 10 == 0:
                    for gripper_type in ['PGC', 'PGHL', 'PGE']:
                        if self.config["grippers"][gripper_type]["enabled"]:
                            self.test_gripper_connection(gripper_type)
                
                self.loop_count = loop_count + 1
                
                # [U+8655][U+7406][U+6307][U+4EE4]
                self.process_commands()
                
                # [U+66F4][U+65B0][U+72C0][U+614B]
                self.update_status_registers()
                
                # [U+63A7][U+5236][U+5FAA][U+74B0][U+983B][U+7387]
                elapsed = time.time() - start_time
                sleep_time = self.config["timing"]["fast_loop_interval"] - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except KeyboardInterrupt:
                print("[U+6536][U+5230][U+4E2D][U+65B7][U+4FE1][U+865F][U+FF0C][U+505C][U+6B62][U+4E3B][U+5FAA][U+74B0]")
                break
            except Exception as e:
                print(f"[U+4E3B][U+5FAA][U+74B0][U+932F][U+8AA4]: {e}")
                time.sleep(1)

    def start(self):
        """[U+555F][U+52D5][U+6A21][U+7D44]"""
        self.is_running = True
        
        # [U+555F][U+52D5][U+4E3B][U+5FAA][U+74B0][U+7DDA][U+7A0B]
        self.main_thread = threading.Thread(target=self.fast_loop, daemon=True)
        self.main_thread.start()
        
        print("[U+593E][U+722A][U+6A21][U+7D44][U+5DF2][U+555F][U+52D5]")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """[U+505C][U+6B62][U+6A21][U+7D44]"""
        print("[U+6B63][U+5728][U+505C][U+6B62][U+593E][U+722A][U+6A21][U+7D44]...")
        self.is_running = False
        
        if self.main_server_client:
            self.main_server_client.close()
        if self.rtu_client:
            self.rtu_client.close()
            
        print("[U+593E][U+722A][U+6A21][U+7D44][U+5DF2][U+505C][U+6B62]")

if __name__ == "__main__":
    gripper_module = GripperModule()
    gripper_module.start()