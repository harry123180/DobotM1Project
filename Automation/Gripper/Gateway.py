#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合式RS485 Gateway for DH-Robotics Grippers
===========================================

支援的產品及Modbus地址對照表:

PGE系列 (工業型平行電爪) - Slave ID: 4
========================================
控制地址:
- 0x0100: 初始化 (1:回零, 0xA5:完全初始化)
- 0x0101: 力道設定 (20-100%)
- 0x0103: 位置設定 (0-1000‰)
- 0x0104: 速度設定 (1-100%)

狀態地址:
- 0x0200: 初始化狀態 (0:未初始化, 1:成功, 2:初始化中)
- 0x0201: 夾持狀態 (0:運動中, 1:到達位置, 2:夾住物體, 3:物體掉落)
- 0x0202: 位置反饋
- 0x0300: 保存設定

PGHL系列 (長行程電缸) - Slave ID: 5
==================================
控制地址:
- 0x0100: 回零控制 (1:回零, 0:停止)
- 0x0101: 推壓力值 (20-100%)
- 0x0102: 推壓段長度 (0-65535, 單位0.01mm)
- 0x0103: 目標位置 (0-65535, 單位0.01mm)
- 0x0104: 最大速度 (50-100%)
- 0x0105: 加速度 (1-100%)
- 0x0106: 相對位置 (-32767~32767, 單位0.01mm)
- 0x0107: 點動控制 (-1:閉合, 0:停止, 1:張開)

狀態地址:
- 0x0200: 回零狀態 (0:未初始化, 1:成功, 2:初始化中)
- 0x0201: 運行狀態 (0:運動中, 1:到達位置, 2:堵轉, 3:掉落, -1:碰撞)
- 0x0202: 位置反饋 (單位0.01mm)
- 0x0204: 電流反饋

配置地址:
- 0x0300: 保存設定
- 0x0301: 回零方向 (0:張開歸零, 1:閉合歸零)
- 0x0309: 推壓速度 (10-40%)
- 0x030A: 推壓方向 (0:張開, 1:閉合, 2:雙向)

PGC系列 (協作型平行電爪) - Slave ID: 6
====================================
控制地址:
- 0x0100: 初始化 (1:回零, 0xA5:完全初始化)
- 0x0101: 力道設定 (20-100%)
- 0x0103: 位置設定 (0-1000‰)
- 0x0104: 速度設定 (1-100%)
"""

import time
import threading
import json
from flask import Flask, request, jsonify
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
import logging
from typing import Dict, Any, Optional, Tuple

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntegratedGripper:
    """整合式夾爪控制器"""
    
    # 設備配置
    DEVICE_CONFIG = {
        'PGE': {
            'slave_id': 4,
            'description': '工業型平行電爪',
            'type': 'gripper'
        },
        'PGHL': {
            'slave_id': 5,
            'description': '長行程電缸',
            'type': 'actuator'
        },
        'PGC': {
            'slave_id': 6,
            'description': '協作型平行電爪',
            'type': 'gripper'
        }
    }
    
    def __init__(self, port='COM4', baudrate=115200, timeout=1):
        """
        初始化整合式控制器
        
        Args:
            port (str): RS485串口號
            baudrate (int): 波特率
            timeout (float): 通訊超時時間
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.client = None
        self.lock = threading.Lock()
        self.connected = False
        
        # Flask app
        self.app = Flask(__name__)
        self.setup_routes()
        
    def connect(self) -> bool:
        """建立RS485連接"""
        try:
            self.client = ModbusSerialClient(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                parity='N',
                stopbits=1,
                bytesize=8
            )
            
            if self.client.connect():
                self.connected = True
                logger.info(f"✅ 成功連接到 {self.port} @ {self.baudrate}bps")
                return True
            else:
                logger.error(f"❌ 無法連接到 {self.port}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 連接錯誤: {str(e)}")
            return False
    
    def disconnect(self):
        """斷開RS485連接"""
        if self.client and self.connected:
            self.client.close()
            self.connected = False
            logger.info("🔌 RS485連接已關閉")
    
    def write_register(self, slave_id: int, address: int, value: int) -> Tuple[bool, str]:
        """寫入單一寄存器"""
        with self.lock:
            try:
                if not self.connected:
                    return False, "RS485未連接"
                
                result = self.client.write_register(
                    address=address,
                    value=value,
                    slave=slave_id
                )
                
                if result.isError():
                    error_msg = f"寫入失敗: Slave {slave_id}, 地址 0x{address:04X}, 值 {value}"
                    logger.error(error_msg)
                    return False, error_msg
                else:
                    success_msg = f"寫入成功: Slave {slave_id}, 地址 0x{address:04X}, 值 {value}"
                    logger.info(success_msg)
                    return True, success_msg
                    
            except Exception as e:
                error_msg = f"寫入異常: {str(e)}"
                logger.error(error_msg)
                return False, error_msg
    
    def read_register(self, slave_id: int, address: int, count: int = 1) -> Tuple[bool, Any]:
        """讀取寄存器"""
        with self.lock:
            try:
                if not self.connected:
                    return False, "RS485未連接"
                
                result = self.client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=slave_id
                )
                
                if result.isError():
                    error_msg = f"讀取失敗: Slave {slave_id}, 地址 0x{address:04X}"
                    logger.error(error_msg)
                    return False, error_msg
                else:
                    values = result.registers
                    logger.info(f"讀取成功: Slave {slave_id}, 地址 0x{address:04X}, 值 {values}")
                    return True, values[0] if count == 1 else values
                    
            except Exception as e:
                error_msg = f"讀取異常: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

    # ========== PGE/PGC 通用控制函式 ==========
    
    def initialize_gripper(self, device_type: str, mode: int = 1) -> Tuple[bool, str]:
        """初始化夾爪"""
        if device_type not in ['PGE', 'PGC']:
            return False, f"設備 {device_type} 不支援此功能"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0100, mode)
    
    def set_gripper_force(self, device_type: str, force: int) -> Tuple[bool, str]:
        """設定夾爪力值"""
        if device_type not in ['PGE', 'PGC']:
            return False, f"設備 {device_type} 不支援此功能"
        
        if not (20 <= force <= 100):
            return False, "力值必須在20-100之間"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0101, force)
    
    def set_gripper_position(self, device_type: str, position: int) -> Tuple[bool, str]:
        """設定夾爪位置"""
        if device_type not in ['PGE', 'PGC']:
            return False, f"設備 {device_type} 不支援此功能"
        
        if not (0 <= position <= 1000):
            return False, "位置必須在0-1000之間"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0103, position)
    
    def set_gripper_speed(self, device_type: str, speed: int) -> Tuple[bool, str]:
        """設定夾爪速度"""
        if device_type not in ['PGE', 'PGC']:
            return False, f"設備 {device_type} 不支援此功能"
        
        if not (1 <= speed <= 100):
            return False, "速度必須在1-100之間"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0104, speed)
    
    def open_gripper(self, device_type: str) -> Tuple[bool, str]:
        """張開夾爪"""
        return self.set_gripper_position(device_type, 1000)
    
    def close_gripper(self, device_type: str) -> Tuple[bool, str]:
        """閉合夾爪"""
        return self.set_gripper_position(device_type, 0)
    
    def stop_gripper(self, device_type: str) -> Tuple[bool, str]:
        """停止夾爪"""
        if device_type not in ['PGE', 'PGC']:
            return False, f"設備 {device_type} 不支援此功能"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0100, 0)
    
    def get_gripper_status(self, device_type: str) -> Dict[str, Any]:
        """獲取夾爪狀態"""
        if device_type not in ['PGE', 'PGC']:
            return {'success': False, 'message': f"設備 {device_type} 不支援此功能"}
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        
        init_success, init_status = self.read_register(slave_id, 0x0200)
        grip_success, grip_status = self.read_register(slave_id, 0x0201)
        pos_success, position = self.read_register(slave_id, 0x0202)
        
        return {
            'device_type': device_type,
            'init_status': {
                'success': init_success,
                'value': init_status if init_success else None,
                'text': {0: '未初始化', 1: '初始化成功', 2: '初始化中'}.get(init_status if init_success else -1, '未知')
            },
            'grip_status': {
                'success': grip_success,
                'value': grip_status if grip_success else None,
                'text': {0: '運動中', 1: '到達位置', 2: '夾住物體', 3: '物體掉落'}.get(grip_status if grip_success else -1, '未知')
            },
            'position': {
                'success': pos_success,
                'value': position if pos_success else None
            }
        }

    # ========== PGHL 專用控制函式 ==========
    
    def home_pghl(self) -> Tuple[bool, str]:
        """PGHL回零"""
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0100, 1)
    
    def stop_pghl(self) -> Tuple[bool, str]:
        """停止PGHL"""
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0100, 0)
    
    def set_pghl_push_force(self, force: int) -> Tuple[bool, str]:
        """設定PGHL推壓力值 (20-100%)"""
        if not (20 <= force <= 100):
            return False, "推壓力值必須在20-100之間"
        
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0101, force)
    
    def set_pghl_push_length(self, length_mm: float) -> Tuple[bool, str]:
        """設定PGHL推壓段長度 (單位: mm)"""
        length_0_01mm = int(length_mm * 100)
        if not (0 <= length_0_01mm <= 65535):
            return False, "推壓段長度超出範圍 (0-655.35mm)"
        
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0102, length_0_01mm)
    
    def set_pghl_target_position(self, position_mm: float) -> Tuple[bool, str]:
        """設定PGHL目標位置 (單位: mm)"""
        position_0_01mm = int(position_mm * 100)
        if not (0 <= position_0_01mm <= 65535):
            return False, "目標位置超出範圍 (0-655.35mm)"
        
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0103, position_0_01mm)
    
    def set_pghl_max_speed(self, speed: int) -> Tuple[bool, str]:
        """設定PGHL最大速度 (50-100%)"""
        if not (50 <= speed <= 100):
            return False, "最大速度必須在50-100之間"
        
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0104, speed)
    
    def set_pghl_acceleration(self, accel: int) -> Tuple[bool, str]:
        """設定PGHL加速度 (1-100%)"""
        if not (1 <= accel <= 100):
            return False, "加速度必須在1-100之間"
        
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0105, accel)
    
    def set_pghl_relative_position(self, distance_mm: float) -> Tuple[bool, str]:
        """設定PGHL相對位置 (單位: mm)"""
        distance_0_01mm = int(distance_mm * 100)
        if not (-32767 <= distance_0_01mm <= 32767):
            return False, "相對位置超出範圍 (-327.67mm ~ 327.67mm)"
        
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0106, distance_0_01mm)
    
    def pghl_jog_control(self, direction: int) -> Tuple[bool, str]:
        """PGHL點動控制 (-1:閉合, 0:停止, 1:張開)"""
        if direction not in [-1, 0, 1]:
            return False, "方向必須是 -1(閉合), 0(停止), 1(張開)"
        
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        return self.write_register(slave_id, 0x0107, direction)
    
    def get_pghl_status(self) -> Dict[str, Any]:
        """獲取PGHL狀態"""
        slave_id = self.DEVICE_CONFIG['PGHL']['slave_id']
        
        home_success, home_status = self.read_register(slave_id, 0x0200)
        run_success, run_status = self.read_register(slave_id, 0x0201)
        pos_success, position = self.read_register(slave_id, 0x0202)
        current_success, current = self.read_register(slave_id, 0x0204)
        
        return {
            'device_type': 'PGHL',
            'home_status': {
                'success': home_success,
                'value': home_status if home_success else None,
                'text': {0: '未初始化', 1: '初始化成功', 2: '初始化中'}.get(home_status if home_success else -1, '未知')
            },
            'run_status': {
                'success': run_success,
                'value': run_status if run_success else None,
                'text': {0: '運動中', 1: '到達位置', 2: '堵轉', 3: '掉落', -1: '碰撞物體'}.get(run_status if run_success else -2, '未知')
            },
            'position': {
                'success': pos_success,
                'value': position if pos_success else None,
                'value_mm': (position / 100.0) if pos_success and position is not None else None
            },
            'current': {
                'success': current_success,
                'value': current if current_success else None
            }
        }
    
    def save_settings(self, device_type: str) -> Tuple[bool, str]:
        """保存設定到Flash"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0300, 1)

    # ========== Flask API Routes ==========
    
    def setup_routes(self):
        """設定Flask路由"""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'ok',
                'connected': self.connected,
                'port': self.port,
                'baudrate': self.baudrate
            })
        
        @self.app.route('/connect', methods=['POST'])
        def connect_rs485():
            success = self.connect()
            return jsonify({
                'success': success,
                'message': '連接成功' if success else '連接失敗'
            })
        
        @self.app.route('/disconnect', methods=['POST'])
        def disconnect_rs485():
            self.disconnect()
            return jsonify({'success': True, 'message': '已斷開連接'})
        
        @self.app.route('/devices', methods=['GET'])
        def get_devices():
            return jsonify(self.DEVICE_CONFIG)
        
        # ========== 夾爪控制 API (PGE/PGC) ==========
        
        @self.app.route('/gripper/<device_type>/initialize', methods=['POST'])
        def api_initialize_gripper(device_type):
            data = request.get_json() or {}
            mode = data.get('mode', 1)
            success, message = self.initialize_gripper(device_type.upper(), mode)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/force', methods=['POST'])
        def api_set_gripper_force(device_type):
            data = request.get_json() or {}
            force = data.get('force')
            if force is None:
                return jsonify({'success': False, 'message': '缺少force參數'})
            
            success, message = self.set_gripper_force(device_type.upper(), force)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/position', methods=['POST'])
        def api_set_gripper_position(device_type):
            data = request.get_json() or {}
            position = data.get('position')
            if position is None:
                return jsonify({'success': False, 'message': '缺少position參數'})
            
            success, message = self.set_gripper_position(device_type.upper(), position)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/speed', methods=['POST'])
        def api_set_gripper_speed(device_type):
            data = request.get_json() or {}
            speed = data.get('speed')
            if speed is None:
                return jsonify({'success': False, 'message': '缺少speed參數'})
            
            success, message = self.set_gripper_speed(device_type.upper(), speed)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/open', methods=['POST'])
        def api_open_gripper(device_type):
            success, message = self.open_gripper(device_type.upper())
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/close', methods=['POST'])
        def api_close_gripper(device_type):
            success, message = self.close_gripper(device_type.upper())
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/stop', methods=['POST'])
        def api_stop_gripper(device_type):
            success, message = self.stop_gripper(device_type.upper())
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/status', methods=['GET'])
        def api_get_gripper_status(device_type):
            status = self.get_gripper_status(device_type.upper())
            return jsonify(status)
        
        # ========== PGHL控制 API ==========
        
        @self.app.route('/pghl/home', methods=['POST'])
        def api_pghl_home():
            success, message = self.home_pghl()
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/stop', methods=['POST'])
        def api_pghl_stop():
            success, message = self.stop_pghl()
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/push_force', methods=['POST'])
        def api_set_pghl_push_force():
            data = request.get_json() or {}
            force = data.get('force')
            if force is None:
                return jsonify({'success': False, 'message': '缺少force參數'})
            
            success, message = self.set_pghl_push_force(force)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/push_length', methods=['POST'])
        def api_set_pghl_push_length():
            data = request.get_json() or {}
            length = data.get('length_mm')
            if length is None:
                return jsonify({'success': False, 'message': '缺少length_mm參數'})
            
            success, message = self.set_pghl_push_length(length)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/target_position', methods=['POST'])
        def api_set_pghl_target_position():
            data = request.get_json() or {}
            position = data.get('position_mm')
            if position is None:
                return jsonify({'success': False, 'message': '缺少position_mm參數'})
            
            success, message = self.set_pghl_target_position(position)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/max_speed', methods=['POST'])
        def api_set_pghl_max_speed():
            data = request.get_json() or {}
            speed = data.get('speed')
            if speed is None:
                return jsonify({'success': False, 'message': '缺少speed參數'})
            
            success, message = self.set_pghl_max_speed(speed)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/acceleration', methods=['POST'])
        def api_set_pghl_acceleration():
            data = request.get_json() or {}
            accel = data.get('acceleration')
            if accel is None:
                return jsonify({'success': False, 'message': '缺少acceleration參數'})
            
            success, message = self.set_pghl_acceleration(accel)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/relative_position', methods=['POST'])
        def api_set_pghl_relative_position():
            data = request.get_json() or {}
            distance = data.get('distance_mm')
            if distance is None:
                return jsonify({'success': False, 'message': '缺少distance_mm參數'})
            
            success, message = self.set_pghl_relative_position(distance)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/jog', methods=['POST'])
        def api_pghl_jog():
            data = request.get_json() or {}
            direction = data.get('direction')
            if direction is None:
                return jsonify({'success': False, 'message': '缺少direction參數'})
            
            success, message = self.pghl_jog_control(direction)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/pghl/status', methods=['GET'])
        def api_get_pghl_status():
            status = self.get_pghl_status()
            return jsonify(status)
        
        # ========== 通用 API ==========
        
        @self.app.route('/save/<device_type>', methods=['POST'])
        def api_save_settings(device_type):
            success, message = self.save_settings(device_type.upper())
            return jsonify({'success': success, 'message': message})
    
    def run_server(self, host='0.0.0.0', port=5000, debug=False):
        """啟動Flask伺服器"""
        logger.info(f"🚀 啟動整合式Gateway伺服器於 {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)

def main():
    """主程式"""
    # 建立Gateway實例
    gateway = IntegratedGripper(port='COM3', baudrate=115200)
    
    # 連接RS485
    if gateway.connect():
        try:
            # 啟動Flask伺服器
            gateway.run_server(host='0.0.0.0', port=5008, debug=False)
        except KeyboardInterrupt:
            logger.info("收到中斷信號，正在關閉...")
        finally:
            gateway.disconnect()
    else:
        logger.error("無法建立RS485連接，程式結束")

if __name__ == '__main__':
    main()