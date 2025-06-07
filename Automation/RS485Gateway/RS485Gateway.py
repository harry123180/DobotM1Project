#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RS485 Gateway Server for DH-Robotics Grippers
==============================================

支援的產品及Modbus地址對照表:

PGC系列 (協作型平行電爪) - Slave ID: 6
==========================================
基礎控制地址:
- 0x0100 (256): 初始化夾爪 (寫入1:回零位, 0xA5:重新標定)
- 0x0101 (257): 力值設定 (20-100, 百分比)
- 0x0103 (259): 位置設定 (0-1000, 千分比)
- 0x0104 (260): 速度設定 (1-100, 百分比)
- 0x0200 (512): 初始化狀態反饋 (0:未初始化, 1:初始化成功)
- 0x0201 (513): 夾持狀態反饋 (0:運動中, 1:到達位置, 2:夾住物體, 3:物體掉落)
- 0x0202 (514): 位置反饋 (當前實時位置)

參數配置地址:
- 0x0300 (768): 寫入保存 (1:保存參數到flash)
- 0x0301 (769): 初始化方向 (0:打開, 1:關閉)
- 0x0302 (770): 設備ID設定 (1-255)
- 0x0303 (771): 波特率設定 (0-5對應不同波特率)
- 0x0304 (772): 停止位設定 (0:1停止位, 1:2停止位)
- 0x0305 (773): 校驗位設定 (0:無校驗, 1:奇校驗, 2:偶校驗)
- 0x0400 (1024): IO參數測試 (1-4: 對應4組IO)
- 0x0402 (1026): IO模式開關 (0:關閉, 1:開啟)
- 0x0405-0x0410 (1029-1040): IO參數配置 (位置、力值、速度各4組)

PGE系列 (工業型平行電爪) - Slave ID: 4
========================================
基礎控制地址:
- 0x0100 (256): 初始化夾爪 (寫入1:回零位, 0xA5:重新標定)
- 0x0101 (257): 力值設定 (20-100, 百分比)
- 0x0103 (259): 位置設定 (0-1000, 千分比)
- 0x0104 (260): 速度設定 (1-100, 百分比)
- 0x0200 (512): 初始化狀態反饋 (0:未初始化, 1:初始化成功, 2:初始化中)
- 0x0201 (513): 夾持狀態反饋 (0:運動中, 1:到達位置, 2:夾住物體, 3:物體掉落)
- 0x0202 (514): 位置反饋 (當前實時位置)

參數配置地址:
- 0x0300 (768): 寫入保存 (1:保存參數到flash)
- 0x0301 (769): 初始化方向 (0:打開, 1:關閉)
- 0x0302 (770): 設備ID設定 (1-255)
- 0x0303 (771): 波特率設定 (0-5對應不同波特率)
- 0x0304 (772): 停止位設定 (0:1停止位, 1:2停止位)
- 0x0305 (773): 校驗位設定 (0:無校驗, 1:奇校驗, 2:偶校驗)
- 0x0400 (1024): IO參數測試 (1-4: 對應4組IO)
- 0x0402 (1026): IO模式開關 (0:關閉, 1:開啟)
- 0x0405-0x0410 (1029-1040): IO參數配置 (位置、力值、速度各4組)
- 0x0504 (1284): 自動初始化 (0:上電不初始化, 1:上電自動初始化)

PGHL系列 (待實作) - Slave ID: 5
===============================
(待PGHL手冊提供後補充地址對照表)

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

class RS485Gateway:
    """RS485 Gateway for DH-Robotics Grippers"""
    
    # 設備配置
    DEVICE_CONFIG = {
        'PGC': {'slave_id': 6, 'description': '協作型平行電爪'},
        'PGE': {'slave_id': 4, 'description': '工業型平行電爪'},
        'PGHL': {'slave_id': 5, 'description': '待實作型號'}
    }
    
    def __init__(self, port='COM3', baudrate=115200, timeout=1):
        """
        初始化RS485 Gateway
        
        Args:
            port (str): RS485串口號
            baudrate (int): 波特率
            timeout (float): 通訊超時時間
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.client = None
        self.lock = threading.Lock()  # 防止並發存取RS485
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
        """
        寫入單一寄存器
        
        Args:
            slave_id (int): 從站ID
            address (int): 寄存器地址
            value (int): 寫入值
            
        Returns:
            Tuple[bool, str]: (成功與否, 訊息)
        """
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
        """
        讀取寄存器
        
        Args:
            slave_id (int): 從站ID
            address (int): 寄存器地址
            count (int): 讀取數量
            
        Returns:
            Tuple[bool, Any]: (成功與否, 讀取值或錯誤訊息)
        """
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

    # ========== PGC/PGE 通用控制函式 ==========
    
    def initialize_gripper(self, device_type: str, mode: int = 1) -> Tuple[bool, str]:
        """
        初始化夾爪
        
        Args:
            device_type (str): 設備類型 ('PGC', 'PGE', 'PGHL')
            mode (int): 初始化模式 (1: 回零位, 0xA5: 重新標定)
        """
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0100, mode)
    
    def set_force(self, device_type: str, force: int) -> Tuple[bool, str]:
        """
        設定夾爪力值
        
        Args:
            device_type (str): 設備類型
            force (int): 力值 (20-100, 百分比)
        """
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        if not (20 <= force <= 100):
            return False, "力值必須在20-100之間"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0101, force)
    
    def set_position(self, device_type: str, position: int) -> Tuple[bool, str]:
        """
        設定夾爪位置
        
        Args:
            device_type (str): 設備類型
            position (int): 位置 (0-1000, 千分比)
        """
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        if not (0 <= position <= 1000):
            return False, "位置必須在0-1000之間"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0103, position)
    
    def set_speed(self, device_type: str, speed: int) -> Tuple[bool, str]:
        """
        設定夾爪速度
        
        Args:
            device_type (str): 設備類型
            speed (int): 速度 (1-100, 百分比)
        """
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        if not (1 <= speed <= 100):
            return False, "速度必須在1-100之間"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0104, speed)
    
    def open_gripper(self, device_type: str) -> Tuple[bool, str]:
        """張開夾爪 (位置1000)"""
        return self.set_position(device_type, 1000)
    
    def close_gripper(self, device_type: str) -> Tuple[bool, str]:
        """閉合夾爪 (位置0)"""
        return self.set_position(device_type, 0)
    
    def stop_gripper(self, device_type: str) -> Tuple[bool, str]:
        """停止夾爪動作"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0100, 0)
    
    def get_init_status(self, device_type: str) -> Tuple[bool, Any]:
        """獲取初始化狀態"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.read_register(slave_id, 0x0200)
    
    def get_grip_status(self, device_type: str) -> Tuple[bool, Any]:
        """獲取夾持狀態"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.read_register(slave_id, 0x0201)
    
    def get_position(self, device_type: str) -> Tuple[bool, Any]:
        """獲取當前位置"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.read_register(slave_id, 0x0202)
    
    def save_parameters(self, device_type: str) -> Tuple[bool, str]:
        """保存參數到Flash"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0300, 1)
    
    def set_io_mode(self, device_type: str, enabled: bool) -> Tuple[bool, str]:
        """設定IO模式開關"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        value = 1 if enabled else 0
        return self.write_register(slave_id, 0x0402, value)
    
    def trigger_io_group(self, device_type: str, group: int) -> Tuple[bool, str]:
        """觸發IO組別 (1-4)"""
        if device_type not in self.DEVICE_CONFIG:
            return False, f"不支援的設備類型: {device_type}"
        
        if not (1 <= group <= 4):
            return False, "IO組別必須在1-4之間"
        
        slave_id = self.DEVICE_CONFIG[device_type]['slave_id']
        return self.write_register(slave_id, 0x0400, group)

    # ========== PGE 特有功能 ==========
    
    def set_auto_init(self, auto_init: bool) -> Tuple[bool, str]:
        """設定PGE自動初始化 (僅PGE支援)"""
        slave_id = self.DEVICE_CONFIG['PGE']['slave_id']
        value = 1 if auto_init else 0
        return self.write_register(slave_id, 0x0504, value)

    # ========== PGHL 特有功能 ==========
    
    def set_push_segment(self, device_type: str, length: int) -> Tuple[bool, str]:
        """設定推壓段長度 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "推壓段長度設定僅支援PGHL系列"
        
        if not (0 <= length <= 65535):
            return False, "推壓段長度必須在0-65535之間(單位0.01mm)"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        return self.write_register(slave_id, 0x0102, length)
    
    def set_acceleration(self, device_type: str, acceleration: int) -> Tuple[bool, str]:
        """設定加/減速度 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "加/減速度設定僅支援PGHL系列"
        
        if not (1 <= acceleration <= 100):
            return False, "加/減速度必須在1-100之間"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        return self.write_register(slave_id, 0x0105, acceleration)
    
    def set_relative_position(self, device_type: str, relative_pos: int) -> Tuple[bool, str]:
        """設定相對位置 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "相對位置設定僅支援PGHL系列"
        
        if not (-32767 <= relative_pos <= 32767):
            return False, "相對位置必須在-32767到32767之間(單位0.01mm)"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        # 處理負數的16位元表示
        if relative_pos < 0:
            relative_pos = 65536 + relative_pos
        
        return self.write_register(slave_id, 0x0106, relative_pos)
    
    def jog_control(self, device_type: str, direction: int) -> Tuple[bool, str]:
        """點動控制 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "點動控制僅支援PGHL系列"
        
        if direction not in [-1, 0, 1]:
            return False, "點動方向必須為 -1(閉合), 0(停止), 1(張開)"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        # 處理負數的16位元表示
        if direction == -1:
            direction = 0xFFFF
        
        return self.write_register(slave_id, 0x0107, direction)
    
    def get_current_feedback(self, device_type: str) -> Tuple[bool, Any]:
        """獲取電流反饋 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "電流反饋讀取僅支援PGHL系列"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        return self.read_register(slave_id, 0x0204)
    
    def set_travel_limit(self, device_type: str, limit: int) -> Tuple[bool, str]:
        """設定行程限制 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "行程限制設定僅支援PGHL系列"
        
        if not (0 <= limit <= 65535):
            return False, "行程限制必須在0-65535之間(單位0.01mm)"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        return self.write_register(slave_id, 0x0306, limit)
    
    def set_origin_offset(self, device_type: str, offset: int) -> Tuple[bool, str]:
        """設定原點偏置 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "原點偏置設定僅支援PGHL系列"
        
        if not (0 <= offset <= 65535):
            return False, "原點偏置必須在0-65535之間(單位0.01mm)"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        return self.write_register(slave_id, 0x0308, offset)
    
    def set_push_speed(self, device_type: str, speed: int) -> Tuple[bool, str]:
        """設定推壓速度 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "推壓速度設定僅支援PGHL系列"
        
        if not (10 <= speed <= 40):
            return False, "推壓速度必須在10-40之間"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        return self.write_register(slave_id, 0x0309, speed)
    
    def set_push_direction(self, device_type: str, direction: int) -> Tuple[bool, str]:
        """設定推壓方向 (PGHL特有)"""
        if device_type.upper() != 'PGHL':
            return False, "推壓方向設定僅支援PGHL系列"
        
        if direction not in [0, 1, 2]:
            return False, "推壓方向必須為 0(張開), 1(閉合), 2(雙向)"
        
        slave_id = self.DEVICE_CONFIG[device_type.upper()]['slave_id']
        return self.write_register(slave_id, 0x030A, direction)
    # ========== Flask API Routes ==========
    
    def setup_routes(self):
        """設定Flask路由"""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """健康檢查"""
            return jsonify({
                'status': 'ok',
                'connected': self.connected,
                'port': self.port,
                'baudrate': self.baudrate
            })
        
        @self.app.route('/connect', methods=['POST'])
        def connect_rs485():
            """建立RS485連接"""
            success = self.connect()
            return jsonify({
                'success': success,
                'message': '連接成功' if success else '連接失敗'
            })
        
        @self.app.route('/disconnect', methods=['POST'])
        def disconnect_rs485():
            """斷開RS485連接"""
            self.disconnect()
            return jsonify({'success': True, 'message': '已斷開連接'})
        
        @self.app.route('/gripper/<device_type>/initialize', methods=['POST'])
        def api_initialize(device_type):
            """初始化夾爪"""
            data = request.get_json() or {}
            mode = data.get('mode', 1)
            success, message = self.initialize_gripper(device_type.upper(), mode)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/force', methods=['POST'])
        def api_set_force(device_type):
            """設定力值"""
            data = request.get_json() or {}
            force = data.get('force')
            if force is None:
                return jsonify({'success': False, 'message': '缺少force參數'})
            
            success, message = self.set_force(device_type.upper(), force)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/position', methods=['POST'])
        def api_set_position(device_type):
            """設定位置"""
            data = request.get_json() or {}
            position = data.get('position')
            if position is None:
                return jsonify({'success': False, 'message': '缺少position參數'})
            
            success, message = self.set_position(device_type.upper(), position)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/speed', methods=['POST'])
        def api_set_speed(device_type):
            """設定速度"""
            data = request.get_json() or {}
            speed = data.get('speed')
            if speed is None:
                return jsonify({'success': False, 'message': '缺少speed參數'})
            
            success, message = self.set_speed(device_type.upper(), speed)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/open', methods=['POST'])
        def api_open(device_type):
            """張開夾爪"""
            success, message = self.open_gripper(device_type.upper())
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/close', methods=['POST'])
        def api_close(device_type):
            """閉合夾爪"""
            success, message = self.close_gripper(device_type.upper())
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/stop', methods=['POST'])
        def api_stop(device_type):
            """停止夾爪"""
            success, message = self.stop_gripper(device_type.upper())
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/status', methods=['GET'])
        def api_get_status(device_type):
            """獲取夾爪狀態"""
            device_type = device_type.upper()
            
            init_success, init_status = self.get_init_status(device_type)
            grip_success, grip_status = self.get_grip_status(device_type)
            pos_success, position = self.get_position(device_type)
            
            return jsonify({
                'device_type': device_type,
                'init_status': {
                    'success': init_success,
                    'value': init_status if init_success else None
                },
                'grip_status': {
                    'success': grip_success,
                    'value': grip_status if grip_success else None
                },
                'position': {
                    'success': pos_success,
                    'value': position if pos_success else None
                }
            })
        
        @self.app.route('/gripper/<device_type>/save', methods=['POST'])
        def api_save_parameters(device_type):
            """保存參數"""
            success, message = self.save_parameters(device_type.upper())
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/io_mode', methods=['POST'])
        def api_set_io_mode(device_type):
            """設定IO模式"""
            data = request.get_json() or {}
            enabled = data.get('enabled', False)
            success, message = self.set_io_mode(device_type.upper(), enabled)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/<device_type>/io_trigger', methods=['POST'])
        def api_trigger_io(device_type):
            """觸發IO組別"""
            data = request.get_json() or {}
            group = data.get('group')
            if group is None:
                return jsonify({'success': False, 'message': '缺少group參數'})
            
            success, message = self.trigger_io_group(device_type.upper(), group)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/gripper/pge/auto_init', methods=['POST'])
        def api_set_auto_init():
            """設定PGE自動初始化"""
            data = request.get_json() or {}
            auto_init = data.get('auto_init', False)
            success, message = self.set_auto_init(auto_init)
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/devices', methods=['GET'])
        def api_get_devices():
            """獲取支援的設備列表"""
            return jsonify(self.DEVICE_CONFIG)
    
    def run_server(self, host='0.0.0.0', port=5000, debug=False):
        """啟動Flask伺服器"""
        logger.info(f"🚀 啟動RS485 Gateway伺服器於 {host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)

def main():
    """主程式"""
    # 建立Gateway實例
    gateway = RS485Gateway(port='COM3', baudrate=115200)
    
    # 連接RS485
    if gateway.connect():
        try:
            # 啟動Flask伺服器
            gateway.run_server(host='0.0.0.0', port=5000, debug=False)
        except KeyboardInterrupt:
            logger.info("收到中斷信號，正在關閉...")
        finally:
            gateway.disconnect()
    else:
        logger.error("無法建立RS485連接，程式結束")

if __name__ == '__main__':
    main()