#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XC100 [U+8D85][U+9AD8][U+901F][U+52D5][U+4F5C][U+6A21][U+7D44] - [U+7A69][U+5B9A][U+4FEE][U+5FA9][U+7248][U+672C]
[U+4FEE][U+5FA9][U+4E86][U+7AF6][U+722D][U+689D][U+4EF6][U+548C][U+72C0][U+614B][U+7BA1][U+7406][U+554F][U+984C]
"""

import os
import time
import threading
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import serial.tools.list_ports
from pymodbus.client import ModbusSerialClient, ModbusTcpClient

# [U+78BA][U+4FDD]XC100[U+76EE][U+9304][U+5B58][U+5728]
XC100_DIR = "XC100"
if not os.path.exists(XC100_DIR):
    os.makedirs(XC100_DIR)

class XCState(Enum):
    """XC100[U+72C0][U+614B][U+679A][U+8209]"""
    OFFLINE = 0
    IDLE = 1
    MOVING = 2
    HOMING = 3
    ERROR = 4
    SERVO_OFF = 5
    EMERGENCY = 6

class XCCommand(Enum):
    """XC100[U+6307][U+4EE4][U+679A][U+8209]"""
    NOP = 0
    SERVO_ON = 1
    SERVO_OFF = 2
    HOME = 3
    MOVE_ABS = 4
    MOVE_REL = 5
    EMERGENCY_STOP = 6
    RESET_ERROR = 7

class UltraFastXCModule:
    """[U+8D85][U+9AD8][U+901F]XC100[U+6A21][U+7D44]"""
    
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = os.path.join(XC100_DIR, "xc_ultrafast_config.json")
        self.config_file = config_file
        self.config = self.load_config()
        
        self.setup_logging()
        self.module_id = self.config.get("module_id", "XC100_FAST")
        
        # [U+9023][U+63A5][U+5BA2][U+6236][U+7AEF]
        self.xc_client: Optional[ModbusSerialClient] = None
        self.tcp_client: Optional[ModbusTcpClient] = None
        self.xc_connected = False
        self.tcp_connected = False
        
        # [U+72C0][U+614B][U+8B8A][U+91CF] - [U+4F7F][U+7528][U+9396][U+4FDD][U+8B77]
        self._state_lock = threading.Lock()
        self.current_state = XCState.OFFLINE
        self.servo_status = False
        self.error_code = 0
        self.current_position = 0
        self.target_position = 0
        self.command_executing = False
        self.command_start_time = 0
        
        # [U+4F4D][U+7F6E][U+8A2D][U+5B9A]
        self.position_A = self.config.get("positions", {}).get("A", 400)
        self.position_B = self.config.get("positions", {}).get("B", 2682)
        
        # [U+8D85][U+9AD8][U+901F][U+7DDA][U+7A0B]
        self.fast_loop_thread = None
        self.fast_loop_running = False
        
        # [U+6307][U+4EE4][U+7BA1][U+7406]
        self.last_command_id = 0
        self.modbus_base_address = self.config.get("modbus_mapping", {}).get("base_address", 1000)
        
        # [U+9023][U+63A5][U+91CD][U+8A66][U+8A08][U+6578][U+5668]
        self.tcp_retry_count = 0
        self.xc_retry_count = 0
        self.max_retry = 3
        
        self.logger.info(f"[U+8D85][U+9AD8][U+901F]XC100[U+6A21][U+7D44][U+521D][U+59CB][U+5316]: {self.module_id}")
    
    def load_config(self) -> Dict[str, Any]:
        """[U+8F09][U+5165][U+8D85][U+9AD8][U+901F][U+914D][U+7F6E]"""
        default_config = {
            "module_id": "XC100_FAST",
            "description": "XC100[U+8D85][U+9AD8][U+901F][U+6A21][U+7D44]",
            "xc_connection": {
                "port": "COM5",
                "baudrate": 115200,
                "unit_id": 2,
                "timeout": 0.2,
                "retry_count": 2,
                "retry_delay": 0.01
            },
            "tcp_server": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1,
                "timeout": 1.0
            },
            "modbus_mapping": {
                "base_address": 1000,
                "register_count": 50
            },
            "positions": {
                "A": 400,
                "B": 2682
            },
            "timing": {
                "fast_loop_interval": 0.02,  # [U+8ABF][U+6574][U+70BA]20ms[U+FF0C][U+66F4][U+7A69][U+5B9A]
                "movement_delay": 0.1,       # [U+8ABF][U+6574][U+70BA]100ms
                "command_delay": 0.02,       # [U+8ABF][U+6574][U+70BA]20ms
                "register_delay": 0.01,      # [U+8ABF][U+6574][U+70BA]10ms
                "no_wait_mode": True
            }
        }
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                for key, value in default_config.items():
                    if key not in loaded_config:
                        loaded_config[key] = value
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if sub_key not in loaded_config[key]:
                                loaded_config[key][sub_key] = sub_value
                return loaded_config
        except FileNotFoundError:
            self.save_config(default_config)
        except Exception as e:
            print(f"[U+8F09][U+5165][U+914D][U+7F6E][U+5931][U+6557]: {e}")
            
        return default_config
    
    def save_config(self, config=None):
        """[U+4FDD][U+5B58][U+914D][U+7F6E]"""
        try:
            config_to_save = config or self.config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[U+4FDD][U+5B58][U+914D][U+7F6E][U+5931][U+6557]: {e}")
    
    def setup_logging(self):
        """[U+8A2D][U+7F6E][U+7CBE][U+7C21][U+65E5][U+8A8C]"""
        log_file = os.path.join(XC100_DIR, f'xc_fast_{datetime.now().strftime("%Y%m%d")}.log')
        logging.basicConfig(
            level=logging.ERROR,  # [U+53EA][U+8A18][U+9304][U+932F][U+8AA4]
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(f'FastXC.{self.config.get("module_id", "XC100")}')
    
    def safe_modbus_operation(self, operation_func, *args, **kwargs):
        """[U+5B89][U+5168][U+7684]Modbus[U+64CD][U+4F5C][U+5305][U+88DD][U+5668]"""
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Modbus[U+64CD][U+4F5C][U+5931][U+6557]: {e}")
            return None
    
    def connect_main_server(self) -> bool:
        """[U+9023][U+63A5][U+4E3B][U+670D][U+52D9][U+5668] - [U+589E][U+52A0][U+932F][U+8AA4][U+8655][U+7406]"""
        try:
            if self.tcp_client:
                try:
                    self.tcp_client.close()
                except:
                    pass
            
            tcp_config = self.config["tcp_server"]
            self.tcp_client = ModbusTcpClient(
                host=tcp_config["host"],
                port=tcp_config["port"],
                timeout=tcp_config["timeout"]
            )
            
            if self.tcp_client.connect():
                self.tcp_connected = True
                self.tcp_retry_count = 0
                return True
            return False
        except Exception as e:
            self.logger.error(f"TCP[U+9023][U+63A5][U+5931][U+6557]: {e}")
            self.tcp_connected = False
            return False
    
    def connect_xc100(self) -> bool:
        """[U+9023][U+63A5]XC100 - [U+589E][U+52A0][U+932F][U+8AA4][U+8655][U+7406]"""
        try:
            if self.xc_client:
                try:
                    self.xc_client.close()
                except:
                    pass
            
            xc_config = self.config["xc_connection"]
            self.xc_client = ModbusSerialClient(
                port=xc_config["port"],
                baudrate=xc_config["baudrate"],
                stopbits=1,
                parity='N',
                timeout=xc_config["timeout"]
            )
            
            if self.xc_client.connect():
                self.xc_connected = True
                self.xc_retry_count = 0
                with self._state_lock:
                    self.current_state = XCState.IDLE
                return True
            return False
        except Exception as e:
            self.logger.error(f"XC100[U+9023][U+63A5][U+5931][U+6557]: {e}")
            self.xc_connected = False
            return False
    
    def ultra_fast_rtu_write(self, address, values):
        """[U+8D85][U+9AD8][U+901F]RTU[U+5BEB][U+5165] - [U+589E][U+52A0][U+5B89][U+5168][U+6AA2][U+67E5]"""
        if not self.xc_connected or not self.xc_client:
            return False
        
        try:
            unit_id = self.config["xc_connection"]["unit_id"]
            
            if isinstance(values, list):
                result = self.xc_client.write_registers(
                    address=address, 
                    values=values, 
                    slave=unit_id
                )
            else:
                result = self.xc_client.write_register(
                    address=address, 
                    value=values, 
                    slave=unit_id
                )
            
            if result.isError():
                self.logger.error(f"RTU[U+5BEB][U+5165][U+5931][U+6557]: {result}")
                return False
            return True
            
        except Exception as e:
            self.logger.error(f"RTU[U+5BEB][U+5165][U+7570][U+5E38]: {e}")
            return False
    
    def execute_xc_command_fast(self, command: XCCommand, param1=0, param2=0) -> bool:
        """[U+8D85][U+9AD8][U+901F][U+6307][U+4EE4][U+57F7][U+884C] - [U+6539][U+9032][U+72C0][U+614B][U+7BA1][U+7406]"""
        with self._state_lock:
            if not self.xc_connected or self.command_executing:
                return False
            
            # [U+8A2D][U+7F6E][U+57F7][U+884C][U+72C0][U+614B]
            self.command_executing = True
            self.command_start_time = time.time()
        
        try:
            success = False
            
            if command == XCCommand.SERVO_ON:
                success = self.ultra_fast_rtu_write(0x2011, 0)
                if success:
                    with self._state_lock:
                        self.current_state = XCState.IDLE
                        self.servo_status = True
                
            elif command == XCCommand.SERVO_OFF:
                success = self.ultra_fast_rtu_write(0x2011, 1)
                if success:
                    with self._state_lock:
                        self.current_state = XCState.SERVO_OFF
                        self.servo_status = False
                
            elif command == XCCommand.HOME:
                success = self.ultra_fast_rtu_write(0x201E, 3)
                if success:
                    with self._state_lock:
                        self.current_state = XCState.HOMING
                
            elif command == XCCommand.MOVE_ABS:
                position = (param2 << 16) | param1
                with self._state_lock:
                    self.target_position = position
                
                position_high = (position >> 16) & 0xFFFF
                position_low = position & 0xFFFF
                
                # [U+7B2C][U+4E00][U+500B][U+6307][U+4EE4][U+FF1A][U+5BEB][U+5165][U+4F4D][U+7F6E]
                success1 = self.ultra_fast_rtu_write(0x2002, [position_high, position_low])
                
                if success1:
                    # [U+5EF6][U+9072][U+63A7][U+5236]
                    if not self.config["timing"].get("no_wait_mode", False):
                        time.sleep(self.config["timing"]["command_delay"])
                    
                    # [U+7B2C][U+4E8C][U+500B][U+6307][U+4EE4][U+FF1A][U+57F7][U+884C][U+79FB][U+52D5]
                    success2 = self.ultra_fast_rtu_write(0x201E, 1)
                    if success2:
                        with self._state_lock:
                            self.current_state = XCState.MOVING
                        success = True
                        # [U+79FB][U+52D5][U+6307][U+4EE4][U+9700][U+8981][U+7B49][U+5F85][U+5B8C][U+6210][U+FF0C][U+4E0D][U+5728][U+9019][U+88E1][U+6E05][U+9664][U+57F7][U+884C][U+72C0][U+614B]
                        return True
                
            elif command == XCCommand.EMERGENCY_STOP:
                success = self.ultra_fast_rtu_write(0x2020, 1)
                if success:
                    with self._state_lock:
                        self.current_state = XCState.EMERGENCY
            
            # [U+5C0D][U+65BC][U+975E][U+79FB][U+52D5][U+6307][U+4EE4][U+FF0C][U+7ACB][U+5373][U+6E05][U+9664][U+57F7][U+884C][U+72C0][U+614B]
            if command != XCCommand.MOVE_ABS:
                with self._state_lock:
                    self.command_executing = False
                    self.command_start_time = 0
            
            return success
            
        except Exception as e:
            self.logger.error(f"[U+6307][U+4EE4][U+57F7][U+884C][U+5931][U+6557]: {e}")
            with self._state_lock:
                self.command_executing = False
                self.command_start_time = 0
            return False
    
    def ultra_fast_loop(self):
        """[U+8D85][U+9AD8][U+901F][U+4E3B][U+5FAA][U+74B0] - [U+6539][U+9032][U+7A69][U+5B9A][U+6027]"""
        print("[U+8D85][U+9AD8][U+901F][U+5FAA][U+74B0][U+958B][U+59CB]")
        
        loop_interval = self.config["timing"]["fast_loop_interval"]
        movement_delay = self.config["timing"]["movement_delay"]
        
        error_count = 0
        max_errors = 10
        
        while self.fast_loop_running:
            try:
                start_time = time.time()
                
                # 1. [U+6AA2][U+67E5][U+9023][U+63A5][U+72C0][U+614B]
                if not self.tcp_connected and self.tcp_retry_count < self.max_retry:
                    if self.connect_main_server():
                        print("TCP[U+91CD][U+65B0][U+9023][U+63A5][U+6210][U+529F]")
                    else:
                        self.tcp_retry_count += 1
                
                # 2. [U+8B80][U+53D6][U+6307][U+4EE4] - [U+589E][U+52A0][U+932F][U+8AA4][U+8655][U+7406]
                if self.tcp_connected and self.tcp_client:
                    try:
                        base_addr = self.modbus_base_address + 20
                        unit_id = self.config["tcp_server"]["unit_id"]
                        
                        result = self.tcp_client.read_holding_registers(
                            address=base_addr, count=5, slave=unit_id
                        )
                        
                        if not result.isError() and len(result.registers) >= 4:
                            command_code = result.registers[0]
                            param1 = result.registers[1]
                            param2 = result.registers[2]
                            command_id = result.registers[3]
                            
                            # [U+6AA2][U+67E5][U+65B0][U+6307][U+4EE4]
                            if command_code != 0 and command_id != self.last_command_id:
                                self.last_command_id = command_id
                                
                                try:
                                    command = XCCommand(command_code)
                                    
                                    # [U+57F7][U+884C][U+6307][U+4EE4]
                                    if self.execute_xc_command_fast(command, param1, param2):
                                        # [U+6E05][U+9664][U+6307][U+4EE4]
                                        self.safe_modbus_operation(
                                            self.tcp_client.write_registers,
                                            address=base_addr,
                                            values=[0, 0, 0, 0, 0],
                                            slave=unit_id
                                        )
                                        
                                except ValueError:
                                    pass
                                except Exception as e:
                                    self.logger.error(f"[U+6307][U+4EE4][U+8655][U+7406][U+5931][U+6557]: {e}")
                        else:
                            if result.isError():
                                error_count += 1
                                if error_count > max_errors:
                                    self.tcp_connected = False
                                    error_count = 0
                                    
                    except Exception as e:
                        self.logger.error(f"[U+6307][U+4EE4][U+8B80][U+53D6][U+5931][U+6557]: {e}")
                        error_count += 1
                        if error_count > max_errors:
                            self.tcp_connected = False
                            error_count = 0
                
                # 3. [U+6AA2][U+67E5][U+79FB][U+52D5][U+5B8C][U+6210]
                with self._state_lock:
                    if (self.command_executing and 
                        self.command_start_time > 0 and 
                        time.time() - self.command_start_time > movement_delay):
                        self.command_executing = False
                        if self.current_state == XCState.MOVING:
                            self.current_state = XCState.IDLE
                        self.command_start_time = 0
                
                # 4. [U+66F4][U+65B0][U+72C0][U+614B][U+5230][U+4E3B][U+670D][U+52D9][U+5668]
                if self.tcp_connected and self.tcp_client:
                    try:
                        base_addr = self.modbus_base_address
                        unit_id = self.config["tcp_server"]["unit_id"]
                        
                        with self._state_lock:
                            key_data = [
                                self.current_state.value,
                                1 if self.xc_connected else 0,
                                1 if self.servo_status else 0,
                                self.error_code,
                                self.current_position & 0xFFFF,
                                (self.current_position >> 16) & 0xFFFF,
                                1 if self.command_executing else 0
                            ]
                        
                        self.safe_modbus_operation(
                            self.tcp_client.write_registers,
                            address=base_addr,
                            values=key_data,
                            slave=unit_id
                        )
                        
                    except Exception as e:
                        self.logger.error(f"[U+72C0][U+614B][U+66F4][U+65B0][U+5931][U+6557]: {e}")
                
                # 5. [U+7CBE][U+78BA][U+8A08][U+6642]
                elapsed = time.time() - start_time
                if elapsed < loop_interval:
                    time.sleep(loop_interval - elapsed)
                    
            except Exception as e:
                self.logger.error(f"[U+4E3B][U+5FAA][U+74B0][U+7570][U+5E38]: {e}")
                time.sleep(loop_interval)
        
        print("[U+8D85][U+9AD8][U+901F][U+5FAA][U+74B0][U+505C][U+6B62]")
    
    def start_fast_loop(self):
        """[U+555F][U+52D5][U+8D85][U+9AD8][U+901F][U+5FAA][U+74B0]"""
        if not self.fast_loop_running:
            self.fast_loop_running = True
            self.fast_loop_thread = threading.Thread(target=self.ultra_fast_loop, daemon=True)
            self.fast_loop_thread.start()
    
    def stop_fast_loop(self):
        """[U+505C][U+6B62][U+8D85][U+9AD8][U+901F][U+5FAA][U+74B0]"""
        self.fast_loop_running = False
        if self.fast_loop_thread:
            self.fast_loop_thread.join(timeout=2)
    
    def start(self):
        """[U+555F][U+52D5][U+8D85][U+9AD8][U+901F][U+6A21][U+7D44]"""
        print(f"[U+555F][U+52D5][U+8D85][U+9AD8][U+901F]XC100[U+6A21][U+7D44]: {self.module_id}")
        
        if not self.connect_main_server():
            print("[U+4E3B][U+670D][U+52D9][U+5668][U+9023][U+63A5][U+5931][U+6557]")
            return False
        
        if not self.connect_xc100():
            print("XC100[U+9023][U+63A5][U+5931][U+6557][U+FF0C][U+4F46][U+7E7C][U+7E8C][U+904B][U+884C]")
        
        self.start_fast_loop()
        print(f"[U+8D85][U+9AD8][U+901F][U+6A21][U+7D44][U+555F][U+52D5][U+6210][U+529F] ([U+5FAA][U+74B0][U+9593][U+9694]: {self.config['timing']['fast_loop_interval']*1000}ms)")
        return True
    
    def stop(self):
        """[U+505C][U+6B62][U+6A21][U+7D44]"""
        print(f"[U+505C][U+6B62][U+8D85][U+9AD8][U+901F][U+6A21][U+7D44]: {self.module_id}")
        self.stop_fast_loop()
        
        try:
            if self.xc_client and self.xc_connected:
                self.xc_client.close()
        except:
            pass
            
        try:
            if self.tcp_client and self.tcp_connected:
                self.tcp_client.close()
        except:
            pass
    
    def get_status(self):
        """[U+7372][U+53D6][U+72C0][U+614B]"""
        with self._state_lock:
            return {
                "module_id": self.module_id,
                "tcp_connected": self.tcp_connected,
                "xc_connected": self.xc_connected,
                "current_state": self.current_state.name,
                "current_position": self.current_position,
                "command_executing": self.command_executing,
                "fast_mode": True
            }

def main():
    """[U+8D85][U+9AD8][U+901F][U+4E3B][U+51FD][U+6578]"""
    import argparse
    
    parser = argparse.ArgumentParser(description='XC100[U+8D85][U+9AD8][U+901F][U+52D5][U+4F5C][U+6A21][U+7D44]')
    parser.add_argument('--config', type=str, help='[U+914D][U+7F6E][U+6587][U+4EF6][U+8DEF][U+5F91]')
    parser.add_argument('--port', type=str, help='XC100[U+4E32][U+53E3][U+865F]')
    args = parser.parse_args()
    
    print("XC100[U+8D85][U+9AD8][U+901F][U+52D5][U+4F5C][U+6A21][U+7D44] - [U+7A69][U+5B9A][U+4FEE][U+5FA9][U+7248][U+672C]")
    print("=" * 50)
    
    module = UltraFastXCModule(args.config)
    
    if args.port:
        module.config["xc_connection"]["port"] = args.port
        module.save_config()
    
    try:
        if module.start():
            print(f"[U+8D85][U+9AD8][U+901F][U+6A21][U+7D44][U+904B][U+884C][U+4E2D]: {module.module_id}")
            print(f"[U+5FAA][U+74B0][U+9593][U+9694]: {module.config['timing']['fast_loop_interval']*1000}ms")
            print(f"[U+79FB][U+52D5][U+5EF6][U+9072]: {module.config['timing']['movement_delay']*1000}ms")
            print("[U+6309] Ctrl+C [U+505C][U+6B62]")
            
            while True:
                status = module.get_status()
                print(f"\r[U+8D85][U+9AD8][U+901F][U+6A21][U+7D44]: {status['current_state']} | "
                      f"TCP: {'[U+9023][U+63A5]' if status['tcp_connected'] else '[U+65B7][U+958B]'} | "
                      f"XC100: {'[U+9023][U+63A5]' if status['xc_connected'] else '[U+65B7][U+958B]'} | "
                      f"[U+57F7][U+884C][U+4E2D]: {'[U+662F]' if status['command_executing'] else '[U+5426]'}", end="")
                time.sleep(0.2)  # [U+8ABF][U+6574][U+70BA]200ms[U+FF0C][U+6E1B][U+5C11][U+8F38][U+51FA][U+983B][U+7387]
        else:
            print("[U+6A21][U+7D44][U+555F][U+52D5][U+5931][U+6557]")
            
    except KeyboardInterrupt:
        print("\n[U+6B63][U+5728][U+505C][U+6B62][U+8D85][U+9AD8][U+901F][U+6A21][U+7D44]...")
        module.stop()
        print("[U+5DF2][U+505C][U+6B62]")

if __name__ == "__main__":
    main()