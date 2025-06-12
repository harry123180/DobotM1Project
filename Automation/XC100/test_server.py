#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[U+4E3B]Modbus Server[U+6E2C][U+8A66][U+5DE5][U+5177]
[U+7528][U+65BC][U+6E2C][U+8A66]XC100[U+6A21][U+7D44][U+7684][U+9023][U+63A5][U+548C][U+5BC4][U+5B58][U+5668][U+8B80][U+5BEB]
"""

import time
import sys
from pymodbus.client import ModbusTcpClient

class ModbusServerTester:
    def __init__(self, host="127.0.0.1", port=502, unit_id=1):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.client = None
        self.connected = False
        
    def connect(self):
        """[U+9023][U+63A5][U+5230][U+4E3B]Modbus Server"""
        try:
            print(f"[U+1F50C] [U+6B63][U+5728][U+9023][U+63A5][U+5230] {self.host}:{self.port}")
            self.client = ModbusTcpClient(host=self.host, port=self.port, timeout=3)
            
            if self.client.connect():
                self.connected = True
                print("[OK] [U+9023][U+63A5][U+6210][U+529F]")
                return True
            else:
                print("[FAIL] [U+9023][U+63A5][U+5931][U+6557]")
                return False
        except Exception as e:
            print(f"[FAIL] [U+9023][U+63A5][U+7570][U+5E38]: {e}")
            return False
    
    def disconnect(self):
        """[U+65B7][U+958B][U+9023][U+63A5]"""
        if self.client and self.connected:
            self.client.close()
            self.connected = False
            print("[U+1F50C] [U+9023][U+63A5][U+5DF2][U+65B7][U+958B]")
    
    def read_xc_status(self, base_address=1000):
        """[U+8B80][U+53D6]XC100[U+6A21][U+7D44][U+72C0][U+614B]"""
        if not self.connected:
            print("[FAIL] [U+672A][U+9023][U+63A5][U+5230][U+670D][U+52D9][U+5668]")
            return None
        
        try:
            # [U+8B80][U+53D6][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
            result = self.client.read_holding_registers(
                address=base_address, 
                count=15, 
                slave=self.unit_id
            )
            
            if result.isError():
                print(f"[FAIL] [U+8B80][U+53D6][U+5931][U+6557]: {result}")
                return None
            
            registers = result.registers
            
            # [U+89E3][U+6790][U+72C0][U+614B]
            state_map = {
                0: "[U+96E2][U+7DDA]", 1: "[U+9592][U+7F6E]", 2: "[U+79FB][U+52D5][U+4E2D]", 3: "[U+539F][U+9EDE][U+5FA9][U+6B78][U+4E2D]",
                4: "[U+932F][U+8AA4]", 5: "Servo[U+95DC][U+9589]", 6: "[U+7DCA][U+6025][U+505C][U+6B62]"
            }
            
            status = {
                "module_state": state_map.get(registers[0], f"[U+672A][U+77E5]({registers[0]})"),
                "xc_connected": "[U+662F]" if registers[1] == 1 else "[U+5426]",
                "servo_status": "ON" if registers[2] == 1 else "OFF",
                "error_code": registers[3],
                "current_position": (registers[5] << 16) | registers[4],
                "target_position": (registers[7] << 16) | registers[6],
                "command_executing": "[U+662F]" if registers[8] == 1 else "[U+5426]",
                "comm_errors": registers[9],
                "position_A": (registers[11] << 16) | registers[10],
                "position_B": (registers[13] << 16) | registers[12],
                "timestamp": registers[14]
            }
            
            return status
            
        except Exception as e:
            print(f"[FAIL] [U+8B80][U+53D6][U+72C0][U+614B][U+7570][U+5E38]: {e}")
            return None
    
    def send_command(self, command, param1=0, param2=0, base_address=1000):
        """[U+767C][U+9001][U+6307][U+4EE4][U+5230]XC100[U+6A21][U+7D44]"""
        if not self.connected:
            print("[FAIL] [U+672A][U+9023][U+63A5][U+5230][U+670D][U+52D9][U+5668]")
            return False
        
        try:
            command_addr = base_address + 20
            command_id = int(time.time()) % 65536  # [U+751F][U+6210][U+552F][U+4E00]ID
            
            # [U+5BEB][U+5165][U+6307][U+4EE4]
            values = [command, param1, param2, command_id, 0]
            result = self.client.write_registers(
                address=command_addr,
                values=values,
                slave=self.unit_id
            )
            
            if result.isError():
                print(f"[FAIL] [U+767C][U+9001][U+6307][U+4EE4][U+5931][U+6557]: {result}")
                return False
            
            command_names = {
                1: "Servo ON", 2: "Servo OFF", 3: "[U+539F][U+9EDE][U+5FA9][U+6B78]",
                4: "[U+7D55][U+5C0D][U+79FB][U+52D5]", 6: "[U+7DCA][U+6025][U+505C][U+6B62]", 7: "[U+932F][U+8AA4][U+91CD][U+7F6E]"
            }
            
            print(f"[OK] [U+6307][U+4EE4][U+767C][U+9001][U+6210][U+529F]: {command_names.get(command, f'[U+6307][U+4EE4]{command}')} (ID: {command_id})")
            return True
            
        except Exception as e:
            print(f"[FAIL] [U+767C][U+9001][U+6307][U+4EE4][U+7570][U+5E38]: {e}")
            return False
    
    def init_registers(self, base_address=1000, register_count=50):
        """[U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668][U+5340][U+57DF]"""
        if not self.connected:
            print("[FAIL] [U+672A][U+9023][U+63A5][U+5230][U+670D][U+52D9][U+5668]")
            return False
        
        try:
            print(f"[U+1F527] [U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668][U+5340][U+57DF]: {base_address} - {base_address + register_count - 1}")
            
            # [U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
            status_values = [0] * 15  # [U+72C0][U+614B][U+5340][U+57DF][U+6E05][U+96F6]
            result1 = self.client.write_registers(
                address=base_address,
                values=status_values,
                slave=self.unit_id
            )
            
            # [U+521D][U+59CB][U+5316][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668]
            command_values = [0] * 5  # [U+6307][U+4EE4][U+5340][U+57DF][U+6E05][U+96F6]
            result2 = self.client.write_registers(
                address=base_address + 20,
                values=command_values,
                slave=self.unit_id
            )
            
            if result1.isError() or result2.isError():
                print(f"[FAIL] [U+521D][U+59CB][U+5316][U+5931][U+6557]: [U+72C0][U+614B]={result1}, [U+6307][U+4EE4]={result2}")
                return False
            
            print("[OK] [U+5BC4][U+5B58][U+5668][U+521D][U+59CB][U+5316][U+6210][U+529F]")
            return True
            
        except Exception as e:
            print(f"[FAIL] [U+521D][U+59CB][U+5316][U+7570][U+5E38]: {e}")
            return False
    
    def send_move_to_position(self, position, base_address=1000):
        """[U+767C][U+9001][U+79FB][U+52D5][U+5230][U+6307][U+5B9A][U+4F4D][U+7F6E][U+7684][U+6307][U+4EE4]"""
        # [U+5C07]32[U+4F4D][U+4F4D][U+7F6E][U+5206][U+89E3][U+70BA][U+5169][U+500B]16[U+4F4D][U+53C3][U+6578]
        param1 = position & 0xFFFF          # [U+4F4E]16[U+4F4D]
        param2 = (position >> 16) & 0xFFFF  # [U+9AD8]16[U+4F4D]
        
        print(f"[U+1F3AF] [U+767C][U+9001][U+79FB][U+52D5][U+6307][U+4EE4]: [U+4F4D][U+7F6E]={position}, [U+53C3][U+6578]=({param1}, {param2})")
        return self.send_command(4, param1, param2, base_address)  # 4 = MOVE_ABS
    
    def send_servo_on(self, base_address=1000):
        """[U+767C][U+9001]Servo ON[U+6307][U+4EE4]"""
        return self.send_command(1, 0, 0, base_address)
    
    def send_servo_off(self, base_address=1000):
        """[U+767C][U+9001]Servo OFF[U+6307][U+4EE4]"""
        return self.send_command(2, 0, 0, base_address)
    
    def send_home(self, base_address=1000):
        """[U+767C][U+9001][U+539F][U+9EDE][U+5FA9][U+6B78][U+6307][U+4EE4]"""
        return self.send_command(3, 0, 0, base_address)
    
    def send_emergency_stop(self, base_address=1000):
        """[U+767C][U+9001][U+7DCA][U+6025][U+505C][U+6B62][U+6307][U+4EE4]"""
        return self.send_command(6, 0, 0, base_address)
    
    def quick_commands_menu(self, base_address=1000):
        """[U+5FEB][U+6377][U+6307][U+4EE4][U+9078][U+55AE]"""
        print("\n[U+1F3AE] XC100[U+5FEB][U+6377][U+63A7][U+5236][U+9078][U+55AE]")
        print("=" * 30)
        
        while True:
            print("\n[U+53EF][U+7528][U+6307][U+4EE4]:")
            print("1. Servo ON")
            print("2. Servo OFF") 
            print("3. [U+539F][U+9EDE][U+5FA9][U+6B78] (HOME)")
            print("4. [U+79FB][U+52D5][U+5230]A[U+9EDE] (400)")
            print("5. [U+79FB][U+52D5][U+5230]B[U+9EDE] (2682)")
            print("6. [U+81EA][U+5B9A][U+7FA9][U+4F4D][U+7F6E][U+79FB][U+52D5]")
            print("7. [U+7DCA][U+6025][U+505C][U+6B62]")
            print("8. [U+67E5][U+770B][U+7576][U+524D][U+72C0][U+614B]")
            print("9. [U+76E3][U+63A7][U+6A21][U+5F0F]")
            print("0. [U+9000][U+51FA]")
            
            try:
                choice = input("\n[U+8ACB][U+9078][U+64C7] (0-9): ").strip()
                
                if choice == '0':
                    print("[U+1F44B] [U+9000][U+51FA][U+63A7][U+5236][U+9078][U+55AE]")
                    break
                elif choice == '1':
                    print("[U+1F7E2] [U+57F7][U+884C] Servo ON...")
                    self.send_servo_on(base_address)
                elif choice == '2':
                    print("[U+1F534] [U+57F7][U+884C] Servo OFF...")
                    self.send_servo_off(base_address)
                elif choice == '3':
                    print("[U+1F3E0] [U+57F7][U+884C][U+539F][U+9EDE][U+5FA9][U+6B78]...")
                    self.send_home(base_address)
                elif choice == '4':
                    print("[U+1F4CD] [U+79FB][U+52D5][U+5230]A[U+9EDE] (400)...")
                    self.send_move_to_position(400, base_address)
                elif choice == '5':
                    print("[U+1F4CD] [U+79FB][U+52D5][U+5230]B[U+9EDE] (2682)...")
                    self.send_move_to_position(2682, base_address)
                elif choice == '6':
                    try:
                        position = int(input("[U+8ACB][U+8F38][U+5165][U+76EE][U+6A19][U+4F4D][U+7F6E]: "))
                        print(f"[U+1F4CD] [U+79FB][U+52D5][U+5230][U+81EA][U+5B9A][U+7FA9][U+4F4D][U+7F6E] ({position})...")
                        self.send_move_to_position(position, base_address)
                    except ValueError:
                        print("[FAIL] [U+8ACB][U+8F38][U+5165][U+6709][U+6548][U+7684][U+6578][U+5B57]")
                elif choice == '7':
                    print("[U+1F6D1] [U+57F7][U+884C][U+7DCA][U+6025][U+505C][U+6B62]...")
                    self.send_emergency_stop(base_address)
                elif choice == '8':
                    print("[U+1F4CA] [U+8B80][U+53D6][U+7576][U+524D][U+72C0][U+614B]...")
                    status = self.read_xc_status(base_address)
                    if status:
                        print("\n[U+7576][U+524D][U+72C0][U+614B]:")
                        print(f"  [U+6A21][U+7D44][U+72C0][U+614B]: {status['module_state']}")
                        print(f"  XC100[U+9023][U+63A5]: {status['xc_connected']}")
                        print(f"  Servo[U+72C0][U+614B]: {status['servo_status']}")
                        print(f"  [U+7576][U+524D][U+4F4D][U+7F6E]: {status['current_position']}")
                        print(f"  [U+76EE][U+6A19][U+4F4D][U+7F6E]: {status['target_position']}")
                        print(f"  [U+6307][U+4EE4][U+57F7][U+884C][U+4E2D]: {status['command_executing']}")
                        print(f"  [U+932F][U+8AA4][U+4EE3][U+78BC]: {status['error_code']}")
                elif choice == '9':
                    print("[U+1F4CA] [U+9032][U+5165][U+76E3][U+63A7][U+6A21][U+5F0F] ([U+6309]Ctrl+C[U+8FD4][U+56DE][U+9078][U+55AE])...")
                    try:
                        self.monitor_loop(base_address, 1)
                    except KeyboardInterrupt:
                        print("\n[U+1F519] [U+8FD4][U+56DE][U+9078][U+55AE]")
                else:
                    print("[FAIL] [U+7121][U+6548][U+9078][U+64C7][U+FF0C][U+8ACB][U+91CD][U+65B0][U+8F38][U+5165]")
                
                # [U+57F7][U+884C][U+6307][U+4EE4][U+5F8C][U+7B49][U+5F85][U+4E00][U+4E0B][U+518D][U+986F][U+793A][U+72C0][U+614B]
                if choice in ['1', '2', '3', '4', '5', '6', '7']:
                    time.sleep(0.5)
                    status = self.read_xc_status(base_address)
                    if status:
                        print(f"[OK] [U+6307][U+4EE4][U+5B8C][U+6210] | [U+72C0][U+614B]: {status['module_state']} | [U+57F7][U+884C][U+4E2D]: {status['command_executing']}")
                        
            except KeyboardInterrupt:
                print("\n[U+1F519] [U+8FD4][U+56DE][U+9078][U+55AE]")
            except Exception as e:
                print(f"[FAIL] [U+64CD][U+4F5C][U+7570][U+5E38]: {e}")
    
    def batch_test(self, base_address=1000):
        """[U+6279][U+91CF][U+6E2C][U+8A66][U+529F][U+80FD]"""
        print("\n[U+1F9EA] [U+57F7][U+884C][U+6279][U+91CF][U+6E2C][U+8A66]...")
        
        tests = [
            ("Servo ON", lambda: self.send_servo_on(base_address)),
            ("[U+79FB][U+52D5][U+5230]A[U+9EDE](400)", lambda: self.send_move_to_position(400, base_address)),
            ("[U+7B49][U+5F85][U+79FB][U+52D5][U+5B8C][U+6210]", lambda: time.sleep(3)),
            ("[U+79FB][U+52D5][U+5230]B[U+9EDE](2682)", lambda: self.send_move_to_position(2682, base_address)),
            ("[U+7B49][U+5F85][U+79FB][U+52D5][U+5B8C][U+6210]", lambda: time.sleep(3)),
            ("[U+539F][U+9EDE][U+5FA9][U+6B78]", lambda: self.send_home(base_address)),
            ("[U+7B49][U+5F85][U+5FA9][U+6B78][U+5B8C][U+6210]", lambda: time.sleep(3)),
            ("Servo OFF", lambda: self.send_servo_off(base_address))
        ]
        
        for i, (desc, action) in enumerate(tests, 1):
            print(f"[U+6B65][U+9A5F] {i}/{len(tests)}: {desc}")
            try:
                action()
                if "[U+7B49][U+5F85]" not in desc:
                    time.sleep(0.5)  # [U+77ED][U+66AB][U+7B49][U+5F85]
                    status = self.read_xc_status(base_address)
                    if status:
                        print(f"  [OK] {desc} [U+5B8C][U+6210] | [U+72C0][U+614B]: {status['module_state']}")
            except Exception as e:
                print(f"  [FAIL] {desc} [U+5931][U+6557]: {e}")
                break
        
        print("[U+1F389] [U+6279][U+91CF][U+6E2C][U+8A66][U+5B8C][U+6210][U+FF01]")
        """[U+76E3][U+63A7][U+5FAA][U+74B0]"""
        print(f"[U+1F4CA] [U+958B][U+59CB][U+76E3][U+63A7]XC100[U+6A21][U+7D44] ([U+5730][U+5740]: {base_address}, [U+9593][U+9694]: {interval}[U+79D2])")
        print("[U+6309] Ctrl+C [U+505C][U+6B62][U+76E3][U+63A7]")
        
        try:
            while True:
                status = self.read_xc_status(base_address)
                if status:
                    print(f"\r[{time.strftime('%H:%M:%S')}] "
                          f"[U+72C0][U+614B]:{status['module_state']} | "
                          f"XC100:{status['xc_connected']} | "
                          f"Servo:{status['servo_status']} | "
                          f"[U+4F4D][U+7F6E]:{status['current_position']} | "
                          f"[U+932F][U+8AA4]:{status['error_code']}", end="")
                else:
                    print(f"\r[{time.strftime('%H:%M:%S')}] [FAIL] [U+8B80][U+53D6][U+5931][U+6557]", end="")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[U+1F6D1] [U+76E3][U+63A7][U+505C][U+6B62]")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='[U+4E3B]Modbus Server[U+6E2C][U+8A66][U+5DE5][U+5177]')
    parser.add_argument('--host', default='127.0.0.1', help='[U+670D][U+52D9][U+5668][U+5730][U+5740]')
    parser.add_argument('--port', type=int, default=502, help='[U+670D][U+52D9][U+5668][U+7AEF][U+53E3]')
    parser.add_argument('--unit-id', type=int, default=1, help='[U+55AE][U+5143]ID')
    parser.add_argument('--base-address', type=int, default=1000, help='XC100[U+6A21][U+7D44][U+57FA][U+5730][U+5740]')
    parser.add_argument('--action', choices=['test', 'monitor', 'init', 'command', 'menu', 'move-a', 'move-b', 'servo-on', 'servo-off', 'home', 'stop', 'batch'], 
                       default='menu', help='[U+64CD][U+4F5C][U+985E][U+578B]')
    parser.add_argument('--command', type=int, help='[U+767C][U+9001][U+7684][U+6307][U+4EE4][U+4EE3][U+78BC]')
    parser.add_argument('--param1', type=int, default=0, help='[U+6307][U+4EE4][U+53C3][U+6578]1')
    parser.add_argument('--param2', type=int, default=0, help='[U+6307][U+4EE4][U+53C3][U+6578]2')
    parser.add_argument('--position', type=int, help='[U+79FB][U+52D5][U+76EE][U+6A19][U+4F4D][U+7F6E]')
    
    args = parser.parse_args()
    
    print("[U+1F9EA] [U+4E3B]Modbus Server[U+6E2C][U+8A66][U+5DE5][U+5177] - [U+589E][U+5F37][U+7248]")
    print("=" * 50)
    
    tester = ModbusServerTester(args.host, args.port, args.unit_id)
    
    if not tester.connect():
        sys.exit(1)
    
    try:
        if args.action == 'test':
            # [U+57FA][U+672C][U+6E2C][U+8A66]
            print("\n[U+1F4CB] [U+57F7][U+884C][U+57FA][U+672C][U+6E2C][U+8A66]...")
            
            # 1. [U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668]
            tester.init_registers(args.base_address)
            
            # 2. [U+8B80][U+53D6][U+72C0][U+614B]
            status = tester.read_xc_status(args.base_address)
            if status:
                print("\n[U+1F4CA] [U+7576][U+524D][U+72C0][U+614B]:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
            
        elif args.action == 'monitor':
            # [U+76E3][U+63A7][U+6A21][U+5F0F]
            tester.monitor_loop(args.base_address)
            
        elif args.action == 'init':
            # [U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668]
            tester.init_registers(args.base_address)
            
        elif args.action == 'command':
            # [U+767C][U+9001][U+6307][U+4EE4]
            if args.command is None:
                print("[FAIL] [U+8ACB][U+6307][U+5B9A] --command [U+53C3][U+6578]")
                print("[U+53EF][U+7528][U+6307][U+4EE4]: 1=Servo ON, 2=Servo OFF, 3=[U+539F][U+9EDE][U+5FA9][U+6B78], 4=[U+7D55][U+5C0D][U+79FB][U+52D5], 6=[U+7DCA][U+6025][U+505C][U+6B62]")
            else:
                tester.send_command(args.command, args.param1, args.param2, args.base_address)
                
                # [U+7B49][U+5F85][U+4E00][U+4E0B][U+7136][U+5F8C][U+6AA2][U+67E5][U+72C0][U+614B]
                time.sleep(1)
                status = tester.read_xc_status(args.base_address)
                if status:
                    print(f"[U+6307][U+4EE4][U+5F8C][U+72C0][U+614B]: {status['module_state']}, [U+57F7][U+884C][U+4E2D]: {status['command_executing']}")
        
        elif args.action == 'menu':
            # [U+4EA4][U+4E92][U+5F0F][U+9078][U+55AE][U+6A21][U+5F0F]
            tester.quick_commands_menu(args.base_address)
            
        elif args.action == 'move-a':
            # [U+5FEB][U+6377][U+79FB][U+52D5][U+5230]A[U+9EDE]
            print("[U+1F4CD] [U+79FB][U+52D5][U+5230]A[U+9EDE] (400)")
            tester.send_move_to_position(400, args.base_address)
            
        elif args.action == 'move-b':
            # [U+5FEB][U+6377][U+79FB][U+52D5][U+5230]B[U+9EDE]
            print("[U+1F4CD] [U+79FB][U+52D5][U+5230]B[U+9EDE] (2682)")
            tester.send_move_to_position(2682, args.base_address)
            
        elif args.action == 'servo-on':
            # [U+5FEB][U+6377]Servo ON
            print("[U+1F7E2] Servo ON")
            tester.send_servo_on(args.base_address)
            
        elif args.action == 'servo-off':
            # [U+5FEB][U+6377]Servo OFF
            print("[U+1F534] Servo OFF")
            tester.send_servo_off(args.base_address)
            
        elif args.action == 'home':
            # [U+5FEB][U+6377][U+539F][U+9EDE][U+5FA9][U+6B78]
            print("[U+1F3E0] [U+539F][U+9EDE][U+5FA9][U+6B78]")
            tester.send_home(args.base_address)
            
        elif args.action == 'stop':
            # [U+5FEB][U+6377][U+7DCA][U+6025][U+505C][U+6B62]
            print("[U+1F6D1] [U+7DCA][U+6025][U+505C][U+6B62]")
            tester.send_emergency_stop(args.base_address)
            
        elif args.action == 'batch':
            # [U+6279][U+91CF][U+6E2C][U+8A66]
            tester.batch_test(args.base_address)
        
        # [U+5C0D][U+65BC][U+5FEB][U+6377][U+6307][U+4EE4][U+FF0C][U+986F][U+793A][U+57F7][U+884C][U+5F8C][U+7684][U+72C0][U+614B]
        if args.action in ['move-a', 'move-b', 'servo-on', 'servo-off', 'home', 'stop']:
            time.sleep(0.5)
            status = tester.read_xc_status(args.base_address)
            if status:
                print(f"[OK] [U+6307][U+4EE4][U+5B8C][U+6210] | [U+72C0][U+614B]: {status['module_state']} | [U+4F4D][U+7F6E]: {status['current_position']}")
        
    finally:
        tester.disconnect()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()