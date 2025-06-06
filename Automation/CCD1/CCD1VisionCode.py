# -*- coding: utf-8 -*-
"""
CCD1VisionCode.py - CCD視覺控制系統
基於工業設備控制架構的視覺辨識Web控制介面
支援Modbus TCP通訊和外部控制
"""

import sys
import os
import time
import threading
import json
import base64
from typing import Optional, Dict, Any, Tuple, List
import numpy as np
import cv2
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import logging
from dataclasses import dataclass, asdict
from datetime import datetime

# 導入Modbus TCP服務 (適配pymodbus 3.9.2)
try:
    from pymodbus.server import StartTcpServer
    from pymodbus.device import ModbusDeviceIdentification
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
    import asyncio
    MODBUS_AVAILABLE = True
    PYMODBUS_VERSION = "3.9.2"
    print("✅ Modbus模組導入成功 (pymodbus 3.9.2)")
except ImportError as e:
    print(f"⚠️ Modbus模組導入失敗: {e}")
    print("💡 請確認pymodbus版本: pip install pymodbus>=3.0.0")
    MODBUS_AVAILABLE = False
    PYMODBUS_VERSION = "unavailable"

# 導入相機管理模組
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'API'))
try:
    from camera_manager import OptimizedCameraManager, CameraConfig, CameraMode, PixelFormat
    CAMERA_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"❌ 無法導入 camera_manager 模組: {e}")
    CAMERA_MANAGER_AVAILABLE = False


@dataclass
class DetectionParams:
    """檢測參數配置"""
    min_area: float = 50000.0
    min_roundness: float = 0.8
    gaussian_kernel_size: int = 9
    gaussian_sigma: float = 2.0
    canny_low: int = 20
    canny_high: int = 60


@dataclass
class VisionResult:
    """視覺辨識結果"""
    circle_count: int
    circles: List[Dict[str, Any]]
    processing_time: float
    capture_time: float
    total_time: float
    timestamp: str
    success: bool
    error_message: Optional[str] = None


class ModbusService:
    """Modbus TCP服務 (適配pymodbus 3.9.2)"""
    
    def __init__(self, port=502):
        self.port = port
        self.server = None
        self.context = None
        self.running = False
        self.server_task = None
        
        # Modbus寄存器映射 (CCD1專用地址段: 200-299)
        self.REGISTERS = {
            # 控制寄存器 (200-209)
            'EXTERNAL_CONTROL_ENABLE': 200,    # 外部控制啟用 (0=禁用, 1=啟用)
            'CAPTURE_TRIGGER': 201,            # 拍照觸發 (寫入1觸發)
            'DETECT_TRIGGER': 202,             # 拍照+檢測觸發 (寫入1觸發)
            'SYSTEM_STATUS': 203,              # 系統狀態 (0=斷線, 1=已連接, 2=處理中)
            'CAMERA_CONNECTED': 204,           # 相機連接狀態 (0=斷線, 1=已連接)
            'RESET_SYSTEM': 205,               # 系統重置 (寫入1重置)
            
            # 參數設定寄存器 (210-219)
            'MIN_AREA_HIGH': 210,              # 最小面積設定 (高16位)
            'MIN_AREA_LOW': 211,               # 最小面積設定 (低16位)
            'MIN_ROUNDNESS': 212,              # 最小圓度設定 (乘以1000)
            'DETECTION_PARAMS_UPDATE': 213,    # 參數更新觸發 (寫入1更新)
            
            # 結果寄存器 (220-249)
            'CIRCLE_COUNT': 220,               # 檢測到的圓形數量
            'CIRCLE_1_X': 221,                 # 圓形1 X座標
            'CIRCLE_1_Y': 222,                 # 圓形1 Y座標
            'CIRCLE_2_X': 223,                 # 圓形2 X座標
            'CIRCLE_2_Y': 224,                 # 圓形2 Y座標
            'CIRCLE_3_X': 225,                 # 圓形3 X座標
            'CIRCLE_3_Y': 226,                 # 圓形3 Y座標
            'CIRCLE_4_X': 227,                 # 圓形4 X座標
            'CIRCLE_4_Y': 228,                 # 圓形4 Y座標
            'CIRCLE_5_X': 229,                 # 圓形5 X座標
            'CIRCLE_5_Y': 230,                 # 圓形5 Y座標
            
            # 時間統計寄存器 (250-259)
            'LAST_CAPTURE_TIME': 250,          # 最後拍照耗時 (ms)
            'LAST_PROCESS_TIME': 251,          # 最後處理耗時 (ms)
            'LAST_TOTAL_TIME': 252,            # 最後總耗時 (ms)
            'OPERATION_COUNT': 253,            # 操作計數器
            'ERROR_COUNT': 254,                # 錯誤計數器
            
            # 版本與狀態資訊寄存器 (260-269)
            'VERSION_MAJOR': 260,              # 軟體版本主版號
            'VERSION_MINOR': 261,              # 軟體版本次版號
            'UPTIME_HOURS': 262,               # 系統運行時間 (小時)
            'UPTIME_MINUTES': 263,             # 系統運行時間 (分鐘)
        }
        
        self.external_control_enabled = False
        self.vision_controller = None
        
        # 添加狀態追蹤變數
        self.last_register_values = {}
        self.last_update = time.time()
        
    def set_vision_controller(self, controller):
        """設置視覺控制器引用"""
        self.vision_controller = controller
        
    def initialize(self):
        """初始化Modbus服務 (pymodbus 3.9.2)"""
        if not MODBUS_AVAILABLE:
            return False
            
        try:
            # 創建數據存儲 (pymodbus 3.x語法)
            store = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0] * 1000),  # 離散輸入
                co=ModbusSequentialDataBlock(0, [0] * 1000),  # 線圈
                hr=ModbusSequentialDataBlock(0, [0] * 1000),  # 保持寄存器
                ir=ModbusSequentialDataBlock(0, [0] * 1000)   # 輸入寄存器
            )
            
            self.context = ModbusServerContext(slaves=store, single=True)
            
            # 設置初始值
            self.write_register('SYSTEM_STATUS', 0)  # 初始狀態：斷線
            self.write_register('EXTERNAL_CONTROL_ENABLE', 0)  # 禁用外部控制
            self.write_register('CAMERA_CONNECTED', 0)  # 相機未連接
            self.write_register('VERSION_MAJOR', 2)  # 版本號 2.0
            self.write_register('VERSION_MINOR', 0)
            self.write_register('OPERATION_COUNT', 0)  # 操作計數器
            self.write_register('ERROR_COUNT', 0)  # 錯誤計數器
            
            # 設置默認檢測參數
            self.write_register('MIN_AREA_HIGH', 0)  # 50000的高16位
            self.write_register('MIN_AREA_LOW', 50000)  # 50000的低16位
            self.write_register('MIN_ROUNDNESS', 800)  # 0.8 * 1000
            
            print("✅ Modbus服務初始化完成 (pymodbus 3.9.2)")
            return True
            
        except Exception as e:
            print(f"❌ Modbus服務初始化失敗: {e}")
            return False
    
    def start_server(self):
        """啟動Modbus TCP服務器 (pymodbus 3.9.2異步版本)"""
        if not MODBUS_AVAILABLE or not self.context:
            print("❌ Modbus不可用或context未初始化")
            return False
            
        try:
            def run_async_server():
                """在新線程中運行異步服務器"""
                async def start_server():
                    print(f"🚀 啟動Modbus TCP服務器於端口 {self.port} (pymodbus 3.9.2)")
                    
                    # pymodbus 3.x的異步服務器啟動方式
                    await StartTcpServer(
                        context=self.context,
                        address=("0.0.0.0", self.port),
                        allow_reuse_address=True
                    )
                
                # 創建新的事件循環
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    loop.run_until_complete(start_server())
                except Exception as e:
                    print(f"❌ Modbus服務器運行錯誤: {e}")
                finally:
                    loop.close()
            
            # 在後台線程中運行異步服務器
            server_thread = threading.Thread(target=run_async_server, daemon=True)
            server_thread.start()
            
            # 等待一下讓服務器啟動
            time.sleep(1.0)
            
            self.running = True
            print(f"✅ Modbus TCP服務器已啟動 (Port: {self.port}, pymodbus 3.9.2)")
            
            # 啟動監控線程
            monitor_thread = threading.Thread(target=self._monitor_commands, daemon=True)
            monitor_thread.start()
            print("✅ Modbus命令監控線程已啟動")
            
            return True
            
        except Exception as e:
            print(f"❌ Modbus服務器啟動失敗: {e}")
            return False

    def write_register(self, register_name: str, value: int):
        """寫入寄存器 (pymodbus 3.9.2)"""
        if not self.context or register_name not in self.REGISTERS:
            return False
            
        try:
            address = self.REGISTERS[register_name]
            slave_context = self.context[0]  # 單一從設備
            result = slave_context.setValues(3, address, [value])  # 功能碼3 = 保持寄存器
            return True
        except Exception as e:
            print(f"❌ 寄存器寫入異常 {register_name}: {e}")
            return False
    
    def read_register(self, register_name: str) -> int:
        """讀取寄存器 (pymodbus 3.9.2)"""
        if not self.context or register_name not in self.REGISTERS:
            return 0
            
        try:
            address = self.REGISTERS[register_name]
            slave_context = self.context[0]  # 單一從設備
            values = slave_context.getValues(3, address, 1)  # 功能碼3 = 保持寄存器
            result = values[0] if values else 0
            return result
        except Exception as e:
            print(f"❌ 寄存器讀取異常 {register_name}: {e}")
            return 0

    def update_detection_results(self, result: VisionResult):
        """更新檢測結果到Modbus寄存器"""
        if not self.context:
            return
            
        try:
            self.write_register('CIRCLE_COUNT', result.circle_count)
            
            for i in range(5):
                if i < len(result.circles):
                    circle = result.circles[i]
                    x_reg = f'CIRCLE_{i+1}_X'
                    y_reg = f'CIRCLE_{i+1}_Y'
                    self.write_register(x_reg, int(circle['center'][0]))
                    self.write_register(y_reg, int(circle['center'][1]))
                else:
                    x_reg = f'CIRCLE_{i+1}_X'
                    y_reg = f'CIRCLE_{i+1}_Y'
                    self.write_register(x_reg, 0)
                    self.write_register(y_reg, 0)
            
            self.write_register('LAST_CAPTURE_TIME', int(result.capture_time * 1000))
            self.write_register('LAST_PROCESS_TIME', int(result.processing_time * 1000))
            self.write_register('LAST_TOTAL_TIME', int(result.total_time * 1000))
            
        except Exception as e:
            print(f"❌ 更新Modbus結果失敗: {e}")
    
    def _monitor_commands(self):
        """監控外部控制命令 (參考VP成功實現)"""
        start_time = time.time()
        
        while self.running:
            try:
                if not self.vision_controller:
                    time.sleep(0.1)
                    continue
                
                uptime_total_minutes = int((time.time() - start_time) / 60)
                uptime_hours = uptime_total_minutes // 60
                uptime_minutes = uptime_total_minutes % 60
                self.write_register('UPTIME_HOURS', uptime_hours)
                self.write_register('UPTIME_MINUTES', uptime_minutes)
                
                enable_control = self.read_register('EXTERNAL_CONTROL_ENABLE')
                if enable_control is not None:
                    old_external_control = self.external_control_enabled
                    self.external_control_enabled = bool(enable_control)
                    
                    if old_external_control != self.external_control_enabled:
                        print(f"🔄 外部控制狀態變更: {'啟用' if self.external_control_enabled else '停用'}")
                
                reset_trigger = self.read_register('RESET_SYSTEM')
                if reset_trigger is not None and reset_trigger > 0 and reset_trigger != self.last_register_values.get('reset_trigger', -1):
                    self.write_register('RESET_SYSTEM', 0)
                    self._handle_system_reset()
                    self.last_register_values['reset_trigger'] = reset_trigger
                
                params_update = self.read_register('DETECTION_PARAMS_UPDATE')
                if params_update is not None and params_update > 0 and params_update != self.last_register_values.get('params_update', -1):
                    self.write_register('DETECTION_PARAMS_UPDATE', 0)
                    self._handle_params_update()
                    self.last_register_values['params_update'] = params_update
                
                if not self.external_control_enabled:
                    self.update_status_to_modbus()
                    time.sleep(0.1)
                    continue
                
                capture_trigger = self.read_register('CAPTURE_TRIGGER')
                if capture_trigger is not None and capture_trigger > 0 and capture_trigger != self.last_register_values.get('capture_trigger', -1):
                    self.write_register('CAPTURE_TRIGGER', 0)
                    self._handle_external_capture()
                    self.last_register_values['capture_trigger'] = capture_trigger
                
                detect_trigger = self.read_register('DETECT_TRIGGER')
                if detect_trigger is not None and detect_trigger > 0 and detect_trigger != self.last_register_values.get('detect_trigger', -1):
                    self.write_register('DETECT_TRIGGER', 0)
                    self._handle_external_detect()
                    self.last_register_values['detect_trigger'] = detect_trigger
                
                self.update_status_to_modbus()
                
                time.sleep(0.05)
                
            except Exception as e:
                print(f"❌ Modbus命令監控錯誤: {e}")
                error_count = self.read_register('ERROR_COUNT')
                self.write_register('ERROR_COUNT', error_count + 1)
                time.sleep(0.1)

    def _handle_external_capture(self):
        """處理外部拍照命令"""
        if self.vision_controller:
            self.write_register('SYSTEM_STATUS', 2)
            image, capture_time = self.vision_controller.capture_image()
            self.write_register('SYSTEM_STATUS', 1)
            
            op_count = self.read_register('OPERATION_COUNT')
            self.write_register('OPERATION_COUNT', op_count + 1)
            
            if image is not None:
                self.write_register('LAST_CAPTURE_TIME', int(capture_time * 1000))
            else:
                error_count = self.read_register('ERROR_COUNT')
                self.write_register('ERROR_COUNT', error_count + 1)
    
    def _handle_external_detect(self):
        """處理外部檢測命令"""
        if self.vision_controller:
            self.write_register('SYSTEM_STATUS', 2)
            result = self.vision_controller.capture_and_detect()
            self.update_detection_results(result)
            self.write_register('SYSTEM_STATUS', 1)
            
            op_count = self.read_register('OPERATION_COUNT')
            self.write_register('OPERATION_COUNT', op_count + 1)
    
    def _handle_system_reset(self):
        """處理系統重置命令"""
        print("🔄 接收到系統重置命令")
        self.write_register('OPERATION_COUNT', 0)
        self.write_register('ERROR_COUNT', 0)
        
        self.write_register('CIRCLE_COUNT', 0)
        for i in range(5):
            x_reg = f'CIRCLE_{i+1}_X'
            y_reg = f'CIRCLE_{i+1}_Y'
            self.write_register(x_reg, 0)
            self.write_register(y_reg, 0)
    
    def _handle_params_update(self):
        """處理參數更新命令"""
        try:
            area_high = self.read_register('MIN_AREA_HIGH')
            area_low = self.read_register('MIN_AREA_LOW')
            min_area = (area_high << 16) + area_low
            
            roundness_int = self.read_register('MIN_ROUNDNESS')
            min_roundness = roundness_int / 1000.0
            
            if self.vision_controller:
                self.vision_controller.update_detection_params(min_area, min_roundness)
                print(f"📊 Modbus參數更新: 面積>={min_area}, 圓度>={min_roundness}")
                
        except Exception as e:
            print(f"❌ 參數更新失敗: {e}")
            error_count = self.read_register('ERROR_COUNT')
            self.write_register('ERROR_COUNT', error_count + 1)

    def update_status_to_modbus(self):
        """更新狀態到ModbusTCP (參考VP實現)"""
        try:
            if self.vision_controller and self.vision_controller.is_connected:
                self.write_register('CAMERA_CONNECTED', 1)
                self.write_register('SYSTEM_STATUS', 1)
            else:
                self.write_register('CAMERA_CONNECTED', 0)
                self.write_register('SYSTEM_STATUS', 0)
                
            self.write_register('EXTERNAL_CONTROL_ENABLE', int(self.external_control_enabled))
            
        except Exception as e:
            print(f"❌ 更新狀態到Modbus失敗: {e}")
    
    def update_system_status(self, connected: bool):
        """更新系統連接狀態"""
        status = 1 if connected else 0
        self.write_register('SYSTEM_STATUS', status)
        self.write_register('CAMERA_CONNECTED', status)
    
class MockModbusService:
    """Modbus服務的模擬實現 (當pymodbus不可用時使用)"""
    
    def __init__(self, port=502):
        self.port = port
        self.context = None
        self.running = False
        self.external_control_enabled = False
        self.vision_controller = None
        self.last_register_values = {}
        
        # 模擬寄存器存儲
        self.registers = {}
        
        # 寄存器映射
        self.REGISTERS = {
            'EXTERNAL_CONTROL_ENABLE': 200,
            'CAPTURE_TRIGGER': 201,
            'DETECT_TRIGGER': 202,
            'SYSTEM_STATUS': 203,
            'CAMERA_CONNECTED': 204,
            'RESET_SYSTEM': 205,
            'MIN_AREA_HIGH': 210,
            'MIN_AREA_LOW': 211,
            'MIN_ROUNDNESS': 212,
            'DETECTION_PARAMS_UPDATE': 213,
            'CIRCLE_COUNT': 220,
            'CIRCLE_1_X': 221,
            'CIRCLE_1_Y': 222,
            'CIRCLE_2_X': 223,
            'CIRCLE_2_Y': 224,
            'CIRCLE_3_X': 225,
            'CIRCLE_3_Y': 226,
            'CIRCLE_4_X': 227,
            'CIRCLE_4_Y': 228,
            'CIRCLE_5_X': 229,
            'CIRCLE_5_Y': 230,
            'LAST_CAPTURE_TIME': 250,
            'LAST_PROCESS_TIME': 251,
            'LAST_TOTAL_TIME': 252,
            'OPERATION_COUNT': 253,
            'ERROR_COUNT': 254,
            'VERSION_MAJOR': 260,
            'VERSION_MINOR': 261,
            'UPTIME_HOURS': 262,
            'UPTIME_MINUTES': 263,
        }
        
        # 初始化寄存器
        for name, address in self.REGISTERS.items():
            self.registers[address] = 0
    
    def initialize(self):
        """初始化模擬服務"""
        print("⚠️ 使用模擬Modbus服務 (僅支持WebUI控制)")
        self.context = True  # 模擬context存在
        
        # 設置初始值
        self.write_register('VERSION_MAJOR', 2)
        self.write_register('VERSION_MINOR', 0)
        self.write_register('MIN_AREA_LOW', 50000)
        self.write_register('MIN_ROUNDNESS', 800)
        
        return True
    
    def start_server(self):
        """啟動模擬服務器"""
        self.running = True
        print("⚠️ 模擬Modbus TCP服務器已啟動 (僅WebUI功能)")
        return True
    
    def write_register(self, register_name: str, value: int):
        """寫入模擬寄存器"""
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            self.registers[address] = value
            return True
        return False
    
    def read_register(self, register_name: str) -> int:
        """讀取模擬寄存器"""
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            return self.registers.get(address, 0)
        return 0
    
    def set_vision_controller(self, controller):
        """設置視覺控制器"""
        self.vision_controller = controller
    
    def update_detection_results(self, result):
        """更新檢測結果"""
        self.write_register('CIRCLE_COUNT', result.circle_count)
        
        for i in range(5):
            if i < len(result.circles):
                circle = result.circles[i]
                x_reg = f'CIRCLE_{i+1}_X'
                y_reg = f'CIRCLE_{i+1}_Y'
                self.write_register(x_reg, int(circle['center'][0]))
                self.write_register(y_reg, int(circle['center'][1]))
            else:
                x_reg = f'CIRCLE_{i+1}_X'
                y_reg = f'CIRCLE_{i+1}_Y'
                self.write_register(x_reg, 0)
                self.write_register(y_reg, 0)
        
        self.write_register('LAST_CAPTURE_TIME', int(result.capture_time * 1000))
        self.write_register('LAST_PROCESS_TIME', int(result.processing_time * 1000))
        self.write_register('LAST_TOTAL_TIME', int(result.total_time * 1000))
    
    def update_status_to_modbus(self):
        """更新狀態"""
        if self.vision_controller and self.vision_controller.is_connected:
            self.write_register('CAMERA_CONNECTED', 1)
            self.write_register('SYSTEM_STATUS', 1)
        else:
            self.write_register('CAMERA_CONNECTED', 0)
            self.write_register('SYSTEM_STATUS', 0)
    
    def update_system_status(self, connected: bool):
        """更新系統狀態"""
        status = 1 if connected else 0
        self.write_register('SYSTEM_STATUS', status)
        self.write_register('CAMERA_CONNECTED', status)
    
    def set_vision_controller(self, controller):
        """設置視覺控制器"""
        self.vision_controller = controller
    """Modbus服務的模擬實現 (當pymodbus不可用時使用)"""
    
    def __init__(self, port=502):
        self.port = port
        self.context = None
        self.running = False
        self.external_control_enabled = False
        self.vision_controller = None
        self.last_register_values = {}
        
        # 模擬寄存器存儲
        self.registers = {}
        
        # 寄存器映射
        self.REGISTERS = {
            'EXTERNAL_CONTROL_ENABLE': 200,
            'CAPTURE_TRIGGER': 201,
            'DETECT_TRIGGER': 202,
            'SYSTEM_STATUS': 203,
            'CAMERA_CONNECTED': 204,
            'RESET_SYSTEM': 205,
            'MIN_AREA_HIGH': 210,
            'MIN_AREA_LOW': 211,
            'MIN_ROUNDNESS': 212,
            'DETECTION_PARAMS_UPDATE': 213,
            'CIRCLE_COUNT': 220,
            'CIRCLE_1_X': 221,
            'CIRCLE_1_Y': 222,
            'CIRCLE_2_X': 223,
            'CIRCLE_2_Y': 224,
            'CIRCLE_3_X': 225,
            'CIRCLE_3_Y': 226,
            'CIRCLE_4_X': 227,
            'CIRCLE_4_Y': 228,
            'CIRCLE_5_X': 229,
            'CIRCLE_5_Y': 230,
            'LAST_CAPTURE_TIME': 250,
            'LAST_PROCESS_TIME': 251,
            'LAST_TOTAL_TIME': 252,
            'OPERATION_COUNT': 253,
            'ERROR_COUNT': 254,
            'VERSION_MAJOR': 260,
            'VERSION_MINOR': 261,
            'UPTIME_HOURS': 262,
            'UPTIME_MINUTES': 263,
        }
        
        # 初始化寄存器
        for name, address in self.REGISTERS.items():
            self.registers[address] = 0
    
    def initialize(self):
        """初始化模擬服務"""
        print("⚠️ 使用模擬Modbus服務 (僅支持WebUI控制)")
        self.context = True  # 模擬context存在
        
        # 設置初始值
        self.write_register('VERSION_MAJOR', 2)
        self.write_register('VERSION_MINOR', 0)
        self.write_register('MIN_AREA_LOW', 50000)
        self.write_register('MIN_ROUNDNESS', 800)
        
        return True
    
    def start_server(self):
        """啟動模擬服務器"""
        self.running = True
        print("⚠️ 模擬Modbus TCP服務器已啟動 (僅WebUI功能)")
        return True
    
    def write_register(self, register_name: str, value: int):
        """寫入模擬寄存器"""
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            self.registers[address] = value
            # print(f"📝 模擬寫入 {register_name}({address}) = {value}")
            return True
        return False
    
    def read_register(self, register_name: str) -> int:
        """讀取模擬寄存器"""
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            return self.registers.get(address, 0)
        return 0
    
    def set_vision_controller(self, controller):
        """設置視覺控制器"""
        self.vision_controller = controller
    
    def update_detection_results(self, result):
        """更新檢測結果"""
        self.write_register('CIRCLE_COUNT', result.circle_count)
        
        for i in range(5):
            if i < len(result.circles):
                circle = result.circles[i]
                x_reg = f'CIRCLE_{i+1}_X'
                y_reg = f'CIRCLE_{i+1}_Y'
                self.write_register(x_reg, int(circle['center'][0]))
                self.write_register(y_reg, int(circle['center'][1]))
            else:
                x_reg = f'CIRCLE_{i+1}_X'
                y_reg = f'CIRCLE_{i+1}_Y'
                self.write_register(x_reg, 0)
                self.write_register(y_reg, 0)
        
        self.write_register('LAST_CAPTURE_TIME', int(result.capture_time * 1000))
        self.write_register('LAST_PROCESS_TIME', int(result.processing_time * 1000))
        self.write_register('LAST_TOTAL_TIME', int(result.total_time * 1000))
    
    def update_status_to_modbus(self):
        """更新狀態"""
        if self.vision_controller and self.vision_controller.is_connected:
            self.write_register('CAMERA_CONNECTED', 1)
            self.write_register('SYSTEM_STATUS', 1)
        else:
            self.write_register('CAMERA_CONNECTED', 0)
            self.write_register('SYSTEM_STATUS', 0)
    
    def update_system_status(self, connected: bool):
        """更新系統狀態"""
        status = 1 if connected else 0
        self.write_register('SYSTEM_STATUS', status)
        self.write_register('CAMERA_CONNECTED', status)
    """Modbus TCP服務"""
    
    def __init__(self, port=502):
        self.port = port
        self.server = None
        self.context = None
        self.running = False
        
        # Modbus寄存器映射 (CCD1專用地址段: 200-299)
        self.REGISTERS = {
            # 控制寄存器 (200-209)
            'EXTERNAL_CONTROL_ENABLE': 200,    # 外部控制啟用 (0=禁用, 1=啟用)
            'CAPTURE_TRIGGER': 201,            # 拍照觸發 (寫入1觸發)
            'DETECT_TRIGGER': 202,             # 拍照+檢測觸發 (寫入1觸發)
            'SYSTEM_STATUS': 203,              # 系統狀態 (0=斷線, 1=已連接, 2=處理中)
            'CAMERA_CONNECTED': 204,           # 相機連接狀態 (0=斷線, 1=已連接)
            'RESET_SYSTEM': 205,               # 系統重置 (寫入1重置)
            
            # 參數設定寄存器 (210-219)
            'MIN_AREA_HIGH': 210,              # 最小面積設定 (高16位)
            'MIN_AREA_LOW': 211,               # 最小面積設定 (低16位)
            'MIN_ROUNDNESS': 212,              # 最小圓度設定 (乘以1000)
            'DETECTION_PARAMS_UPDATE': 213,    # 參數更新觸發 (寫入1更新)
            
            # 結果寄存器 (220-249)
            'CIRCLE_COUNT': 220,               # 檢測到的圓形數量
            'CIRCLE_1_X': 221,                 # 圓形1 X座標
            'CIRCLE_1_Y': 222,                 # 圓形1 Y座標
            'CIRCLE_2_X': 223,                 # 圓形2 X座標
            'CIRCLE_2_Y': 224,                 # 圓形2 Y座標
            'CIRCLE_3_X': 225,                 # 圓形3 X座標
            'CIRCLE_3_Y': 226,                 # 圓形3 Y座標
            'CIRCLE_4_X': 227,                 # 圓形4 X座標
            'CIRCLE_4_Y': 228,                 # 圓形4 Y座標
            'CIRCLE_5_X': 229,                 # 圓形5 X座標
            'CIRCLE_5_Y': 230,                 # 圓形5 Y座標
            
            # 時間統計寄存器 (250-259)
            'LAST_CAPTURE_TIME': 250,          # 最後拍照耗時 (ms)
            'LAST_PROCESS_TIME': 251,          # 最後處理耗時 (ms)
            'LAST_TOTAL_TIME': 252,            # 最後總耗時 (ms)
            'OPERATION_COUNT': 253,            # 操作計數器
            'ERROR_COUNT': 254,                # 錯誤計數器
            
            # 版本與狀態資訊寄存器 (260-269)
            'VERSION_MAJOR': 260,              # 軟體版本主版號
            'VERSION_MINOR': 261,              # 軟體版本次版號
            'UPTIME_HOURS': 262,               # 系統運行時間 (小時)
            'UPTIME_MINUTES': 263,             # 系統運行時間 (分鐘)
        }
        
        self.external_control_enabled = False
        self.vision_controller = None
        
        # 添加狀態追蹤變數 (參考VP實現)
        self.last_register_values = {}
        self.last_update = time.time()
        
    def initialize(self):
        """初始化Modbus服務"""
        if not MODBUS_AVAILABLE:
            return False
            
        try:
            # 創建數據存儲
            store = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0] * 1000),  # 離散輸入
                co=ModbusSequentialDataBlock(0, [0] * 1000),  # 線圈
                hr=ModbusSequentialDataBlock(0, [0] * 1000),  # 保持寄存器
                ir=ModbusSequentialDataBlock(0, [0] * 1000)   # 輸入寄存器
            )
            
            self.context = ModbusServerContext(slaves=store, single=True)
            
            # 設置初始值
            self.write_register('SYSTEM_STATUS', 0)  # 初始狀態：斷線
            self.write_register('EXTERNAL_CONTROL_ENABLE', 0)  # 禁用外部控制
            self.write_register('CAMERA_CONNECTED', 0)  # 相機未連接
            self.write_register('VERSION_MAJOR', 2)  # 版本號 2.0
            self.write_register('VERSION_MINOR', 0)
            self.write_register('OPERATION_COUNT', 0)  # 操作計數器
            self.write_register('ERROR_COUNT', 0)  # 錯誤計數器
            
            # 設置默認檢測參數
            self.write_register('MIN_AREA_HIGH', 0)  # 50000的高16位
            self.write_register('MIN_AREA_LOW', 50000)  # 50000的低16位
            self.write_register('MIN_ROUNDNESS', 800)  # 0.8 * 1000
            
            print("✅ Modbus服務初始化完成")
            return True
            
        except Exception as e:
            print(f"❌ Modbus服務初始化失敗: {e}")
            return False
    
    def start_server(self):
        """啟動Modbus TCP服務器"""
        if not MODBUS_AVAILABLE or not self.context:
            print("❌ Modbus不可用或context未初始化")
            return False
            
        try:
            def run_server():
                try:
                    print(f"🚀 啟動Modbus TCP服務器於端口 {self.port}")
                    StartTcpServer(self.context, address=("0.0.0.0", self.port))
                except Exception as e:
                    print(f"❌ Modbus服務器運行錯誤: {e}")
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
            # 等待一下讓服務器啟動
            time.sleep(0.5)
            
            self.running = True
            print(f"✅ Modbus TCP服務器已啟動 (Port: {self.port})")
            
            # 啟動監控線程
            monitor_thread = threading.Thread(target=self._monitor_commands, daemon=True)
            monitor_thread.start()
            print("✅ Modbus命令監控線程已啟動")
            
            return True
            
        except Exception as e:
            print(f"❌ Modbus服務器啟動失敗: {e}")
            return False
    
    def write_register(self, register_name: str, value: int):
        """寫入寄存器 (pymodbus 3.9.2)"""
        if not self.context or register_name not in self.REGISTERS:
            # print(f"❌ 寫入失敗: context={self.context is not None}, register={register_name in self.REGISTERS if self.REGISTERS else False}")
            return False
            
        try:
            address = self.REGISTERS[register_name]
            # pymodbus 3.x API變更：直接使用context
            slave_context = self.context[0]  # 單一從設備
            result = slave_context.setValues(3, address, [value])  # 功能碼3 = 保持寄存器
            # print(f"📝 寫入寄存器 {register_name}({address}) = {value}, 結果: {result}")
            return True
        except Exception as e:
            print(f"❌ 寄存器寫入異常 {register_name}: {e}")
            return False
    
    def read_register(self, register_name: str) -> int:
        """讀取寄存器 (pymodbus 3.9.2)"""
        if not self.context or register_name not in self.REGISTERS:
            return 0
            
        try:
            address = self.REGISTERS[register_name]
            # pymodbus 3.x API：直接使用context
            slave_context = self.context[0]  # 單一從設備
            values = slave_context.getValues(3, address, 1)  # 功能碼3 = 保持寄存器
            result = values[0] if values else 0
            # print(f"📖 讀取寄存器 {register_name}({address}) = {result}")
            return result
        except Exception as e:
            print(f"❌ 寄存器讀取異常 {register_name}: {e}")
            return 0
    
    def update_detection_results(self, result: VisionResult):
        """更新檢測結果到Modbus寄存器"""
        if not self.context:
            return
            
        try:
            # 更新圓形數量
            self.write_register('CIRCLE_COUNT', result.circle_count)
            
            # 更新圓形座標 (最多5個)
            for i in range(5):
                if i < len(result.circles):
                    circle = result.circles[i]
                    x_reg = f'CIRCLE_{i+1}_X'
                    y_reg = f'CIRCLE_{i+1}_Y'
                    self.write_register(x_reg, int(circle['center'][0]))
                    self.write_register(y_reg, int(circle['center'][1]))
                else:
                    # 清空未使用的寄存器
                    x_reg = f'CIRCLE_{i+1}_X'
                    y_reg = f'CIRCLE_{i+1}_Y'
                    self.write_register(x_reg, 0)
                    self.write_register(y_reg, 0)
            
            # 更新時間統計
            self.write_register('LAST_CAPTURE_TIME', int(result.capture_time * 1000))
            self.write_register('LAST_PROCESS_TIME', int(result.processing_time * 1000))
            self.write_register('LAST_TOTAL_TIME', int(result.total_time * 1000))
            
        except Exception as e:
            print(f"❌ 更新Modbus結果失敗: {e}")
    
    def _monitor_commands(self):
        """監控外部控制命令 (參考VP成功實現)"""
        start_time = time.time()
        
        while self.running:
            try:
                if not self.vision_controller:
                    time.sleep(0.1)
                    continue
                
                # 更新運行時間
                uptime_total_minutes = int((time.time() - start_time) / 60)
                uptime_hours = uptime_total_minutes // 60
                uptime_minutes = uptime_total_minutes % 60
                self.write_register('UPTIME_HOURS', uptime_hours)
                self.write_register('UPTIME_MINUTES', uptime_minutes)
                
                # 先檢查外部控制狀態變化 (關鍵：同步外部控制狀態)
                enable_control = self.read_register('EXTERNAL_CONTROL_ENABLE')
                if enable_control is not None:
                    old_external_control = self.external_control_enabled
                    self.external_control_enabled = bool(enable_control)
                    
                    # 如果外部控制狀態改變，記錄日誌
                    if old_external_control != self.external_control_enabled:
                        print(f"🔄 外部控制狀態變更: {'啟用' if self.external_control_enabled else '停用'}")
                
                # 檢查系統重置
                reset_trigger = self.read_register('RESET_SYSTEM')
                if reset_trigger is not None and reset_trigger > 0 and reset_trigger != self.last_register_values.get('reset_trigger', -1):
                    self.write_register('RESET_SYSTEM', 0)  # 清除觸發
                    self._handle_system_reset()
                    self.last_register_values['reset_trigger'] = reset_trigger
                
                # 檢查參數更新
                params_update = self.read_register('DETECTION_PARAMS_UPDATE')
                if params_update is not None and params_update > 0 and params_update != self.last_register_values.get('params_update', -1):
                    self.write_register('DETECTION_PARAMS_UPDATE', 0)  # 清除觸發
                    self._handle_params_update()
                    self.last_register_values['params_update'] = params_update
                
                # 只有在外部控制啟用時才處理外部指令
                if not self.external_control_enabled:
                    # 外部控制停用時，仍然更新狀態但不處理控制指令
                    self.update_status_to_modbus()
                    time.sleep(0.1)
                    continue
                
                # 檢查拍照觸發
                capture_trigger = self.read_register('CAPTURE_TRIGGER')
                if capture_trigger is not None and capture_trigger > 0 and capture_trigger != self.last_register_values.get('capture_trigger', -1):
                    self.write_register('CAPTURE_TRIGGER', 0)  # 清除觸發
                    self._handle_external_capture()
                    self.last_register_values['capture_trigger'] = capture_trigger
                
                # 檢查檢測觸發
                detect_trigger = self.read_register('DETECT_TRIGGER')
                if detect_trigger is not None and detect_trigger > 0 and detect_trigger != self.last_register_values.get('detect_trigger', -1):
                    self.write_register('DETECT_TRIGGER', 0)  # 清除觸發
                    self._handle_external_detect()
                    self.last_register_values['detect_trigger'] = detect_trigger
                
                # 同步狀態回寫
                self.update_status_to_modbus()
                
                time.sleep(0.05)  # 50ms週期
                
            except Exception as e:
                print(f"❌ Modbus命令監控錯誤: {e}")
                error_count = self.read_register('ERROR_COUNT')
                self.write_register('ERROR_COUNT', error_count + 1)
                time.sleep(0.1)
    
    def _handle_external_capture(self):
        """處理外部拍照命令"""
        if self.vision_controller:
            self.write_register('SYSTEM_STATUS', 2)  # 處理中
            image, capture_time = self.vision_controller.capture_image()
            self.write_register('SYSTEM_STATUS', 1)  # 已連接
            
            # 更新操作計數器
            op_count = self.read_register('OPERATION_COUNT')
            self.write_register('OPERATION_COUNT', op_count + 1)
            
            if image is not None:
                self.write_register('LAST_CAPTURE_TIME', int(capture_time * 1000))
            else:
                error_count = self.read_register('ERROR_COUNT')
                self.write_register('ERROR_COUNT', error_count + 1)
    
    def _handle_external_detect(self):
        """處理外部檢測命令"""
        if self.vision_controller:
            self.write_register('SYSTEM_STATUS', 2)  # 處理中
            result = self.vision_controller.capture_and_detect()
            self.update_detection_results(result)
            self.write_register('SYSTEM_STATUS', 1)  # 已連接
            
            # 更新操作計數器
            op_count = self.read_register('OPERATION_COUNT')
            self.write_register('OPERATION_COUNT', op_count + 1)
    
    def _handle_system_reset(self):
        """處理系統重置命令"""
        print("🔄 接收到系統重置命令")
        # 重置計數器
        self.write_register('OPERATION_COUNT', 0)
        self.write_register('ERROR_COUNT', 0)
        
        # 清空檢測結果
        self.write_register('CIRCLE_COUNT', 0)
        for i in range(5):
            x_reg = f'CIRCLE_{i+1}_X'
            y_reg = f'CIRCLE_{i+1}_Y'
            self.write_register(x_reg, 0)
            self.write_register(y_reg, 0)
    
    def _handle_params_update(self):
        """處理參數更新命令"""
        try:
            # 讀取新參數
            area_high = self.read_register('MIN_AREA_HIGH')
            area_low = self.read_register('MIN_AREA_LOW')
            min_area = (area_high << 16) + area_low
            
            roundness_int = self.read_register('MIN_ROUNDNESS')
            min_roundness = roundness_int / 1000.0
            
            # 更新視覺控制器參數
            if self.vision_controller:
                self.vision_controller.update_detection_params(min_area, min_roundness)
                print(f"📊 Modbus參數更新: 面積>={min_area}, 圓度>={min_roundness}")
                
        except Exception as e:
            print(f"❌ 參數更新失敗: {e}")
            error_count = self.read_register('ERROR_COUNT')
            self.write_register('ERROR_COUNT', error_count + 1)
    
    def set_vision_controller(self, controller):
        """設置視覺控制器引用"""
        self.vision_controller = controller
    
    def update_status_to_modbus(self):
        """更新狀態到ModbusTCP (參考VP實現)"""
        try:
            if self.vision_controller and self.vision_controller.is_connected:
                self.write_register('CAMERA_CONNECTED', 1)
                self.write_register('SYSTEM_STATUS', 1)
            else:
                self.write_register('CAMERA_CONNECTED', 0)
                self.write_register('SYSTEM_STATUS', 0)
                
            # 同步外部控制狀態到寄存器
            self.write_register('EXTERNAL_CONTROL_ENABLE', int(self.external_control_enabled))
            
        except Exception as e:
            print(f"❌ 更新狀態到Modbus失敗: {e}")
    
    def update_system_status(self, connected: bool):
        """更新系統連接狀態"""
        status = 1 if connected else 0
        self.write_register('SYSTEM_STATUS', status)
        self.write_register('CAMERA_CONNECTED', status)


class CircleDetector:
    """圓形檢測器"""
    
    def __init__(self, params: DetectionParams = None):
        self.params = params or DetectionParams()
    
    def update_params(self, params: DetectionParams):
        """更新檢測參數"""
        self.params = params
    
    def is_circle(self, contour, tolerance=0.2):
        """判斷輪廓是否為圓形"""
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            return False
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        return 1 - tolerance < circularity < 1 + tolerance
    
    def detect_circles(self, image: np.ndarray) -> Tuple[List[Dict], np.ndarray]:
        """檢測圓形並返回結果和標註圖像"""
        if image is None:
            return [], None
        
        try:
            # 確保是灰度圖像
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # 創建彩色輸出圖像
            if len(image.shape) == 3:
                result_image = image.copy()
            else:
                result_image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            
            # 使用參數進行處理
            kernel_size = (self.params.gaussian_kernel_size, self.params.gaussian_kernel_size)
            blurred = cv2.GaussianBlur(gray, kernel_size, self.params.gaussian_sigma)
            
            # Canny 邊緣檢測
            edges = cv2.Canny(blurred, self.params.canny_low, self.params.canny_high)
            
            # 輪廓檢測
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            circles = []
            circle_id = 1
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # 使用設定的參數進行篩選
                if area < self.params.min_area:
                    continue
                
                # 計算圓度
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                    
                roundness = (4 * np.pi * area) / (perimeter ** 2)
                
                # 檢查圓度條件
                if roundness < self.params.min_roundness:
                    continue
                
                if self.is_circle(contour):
                    # 計算圓心和半徑
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    center = (int(x), int(y))
                    radius = int(radius)
                    
                    circle_info = {
                        'id': circle_id,
                        'center': center,
                        'radius': radius,
                        'area': float(area),
                        'roundness': float(roundness)
                    }
                    circles.append(circle_info)
                    
                    # 在圖像上繪製圓形和編號
                    cv2.circle(result_image, center, radius, (0, 255, 0), 3)  # 綠色圓圈
                    cv2.circle(result_image, center, 5, (0, 0, 255), -1)      # 紅色圓心
                    
                    # 繪製編號
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 2.0
                    thickness = 3
                    text = str(circle_id)
                    
                    # 計算文字大小和位置
                    (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
                    text_x = center[0] - text_width // 2
                    text_y = center[1] - radius - 10
                    
                    # 確保文字不會超出圖像邊界
                    text_x = max(10, min(text_x, result_image.shape[1] - text_width - 10))
                    text_y = max(text_height + 10, min(text_y, result_image.shape[0] - 10))
                    
                    # 繪製文字背景
                    cv2.rectangle(result_image, 
                                (text_x - 5, text_y - text_height - 5),
                                (text_x + text_width + 5, text_y + 5),
                                (255, 255, 255), -1)
                    
                    # 繪製文字
                    cv2.putText(result_image, text, (text_x, text_y), 
                              font, font_scale, (0, 0, 0), thickness)
                    
                    circle_id += 1
            
            return circles, result_image
            
        except Exception as e:
            print(f"圓形檢測失敗: {e}")
            return [], image


class CCD1VisionController:
    """CCD1 視覺控制器"""
    
    def __init__(self):
        self.camera_manager: Optional[OptimizedCameraManager] = None
        self.detection_params = DetectionParams()
        self.detector = CircleDetector(self.detection_params)
        self.camera_name = "cam_1"
        self.camera_ip = "192.168.1.8"
        self.is_connected = False
        self.last_image: Optional[np.ndarray] = None
        self.last_result: Optional[VisionResult] = None
        self.lock = threading.Lock()
        
        # 設置日誌
        self.logger = logging.getLogger("CCD1Vision")
        self.logger.setLevel(logging.INFO)
        
        # 選擇合適的Modbus服務
        if MODBUS_AVAILABLE:
            self.modbus_service = ModbusService()
            print("✅ 使用完整Modbus TCP服務")
        else:
            self.modbus_service = MockModbusService()
            print("⚠️ 使用模擬Modbus服務 (功能受限)")
            
        self.modbus_service.set_vision_controller(self)
        
        # 初始化相機配置
        self.camera_config = CameraConfig(
            name=self.camera_name,
            ip=self.camera_ip,
            exposure_time=20000.0,
            gain=200.0,
            frame_rate=30.0,
            pixel_format=PixelFormat.BAYER_GR8,
            width=2592,
            height=1944,
            trigger_mode=CameraMode.CONTINUOUS,
            auto_reconnect=True
        )
    
    def initialize_modbus(self) -> bool:
        """初始化Modbus服務"""
        if not MODBUS_AVAILABLE:
            print("❌ Modbus模組不可用，跳過Modbus初始化")
            return False
            
        try:
            print("🚀 正在初始化Modbus服務...")
            
            # 先初始化Modbus服務
            if self.modbus_service.initialize():
                print("✅ Modbus服務初始化成功")
                
                # 然後啟動TCP服務器
                if self.modbus_service.start_server():
                    print("✅ Modbus TCP服務器啟動成功")
                    return True
                else:
                    print("❌ Modbus TCP服務器啟動失敗")
                    return False
            else:
                print("❌ Modbus服務初始化失敗")
                return False
                
        except Exception as e:
            print(f"❌ Modbus初始化異常: {e}")
            return False
    
    def update_detection_params(self, min_area: float, min_roundness: float):
        """更新檢測參數"""
        self.detection_params.min_area = min_area
        self.detection_params.min_roundness = min_roundness
        self.detector.update_params(self.detection_params)
        
        self.logger.info(f"檢測參數已更新: 最小面積={min_area}, 最小圓度={min_roundness}")
    
    def initialize_camera(self, ip_address: str = None) -> Dict[str, Any]:
        """初始化相機連接"""
        try:
            if ip_address:
                self.camera_ip = ip_address
                self.camera_config.ip = ip_address
            
            self.logger.info(f"正在初始化相機 {self.camera_name} (IP: {self.camera_ip})")
            
            if self.camera_manager:
                self.camera_manager.shutdown()
            
            self.camera_manager = OptimizedCameraManager()
            
            success = self.camera_manager.add_camera(self.camera_name, self.camera_config)
            if not success:
                raise Exception("添加相機失敗")
            
            connect_result = self.camera_manager.connect_camera(self.camera_name)
            if not connect_result:
                raise Exception("相機連接失敗")
            
            stream_result = self.camera_manager.start_streaming([self.camera_name])
            if not stream_result.get(self.camera_name, False):
                raise Exception("開始串流失敗")
            
            # 設置增益為200
            camera = self.camera_manager.cameras[self.camera_name]
            camera.camera.MV_CC_SetFloatValue("Gain", 200.0)
            
            self.is_connected = True
            
            # 連接成功後，將當前設定值寫入Modbus寄存器
            self._sync_current_settings_to_modbus()
            
            self.modbus_service.update_system_status(True)
            self.logger.info(f"相機 {self.camera_name} 初始化成功")
            
            return {
                'success': True,
                'message': f'相機 {self.camera_name} 連接成功，已同步設定值到Modbus',
                'camera_ip': self.camera_ip,
                'gain_set': 200.0
            }
            
        except Exception as e:
            self.is_connected = False
            self.modbus_service.update_system_status(False)
            error_msg = f"相機初始化失敗: {str(e)}"
            self.logger.error(error_msg)
            
            return {
                'success': False,
                'message': error_msg,
                'camera_ip': self.camera_ip
            }
    
    def _sync_current_settings_to_modbus(self):
        """將當前設定值同步到Modbus寄存器"""
        try:
            print("📊 正在同步當前設定值到Modbus寄存器...")
            
            # 同步檢測參數
            min_area = int(self.detection_params.min_area)
            min_roundness = int(self.detection_params.min_roundness * 1000)
            
            # 分解32位面積值為高低16位
            area_high = (min_area >> 16) & 0xFFFF
            area_low = min_area & 0xFFFF
            
            self.modbus_service.write_register('MIN_AREA_HIGH', area_high)
            self.modbus_service.write_register('MIN_AREA_LOW', area_low)
            self.modbus_service.write_register('MIN_ROUNDNESS', min_roundness)
            
            # 同步系統狀態
            self.modbus_service.write_register('SYSTEM_STATUS', 1)  # 已連接
            self.modbus_service.write_register('CAMERA_CONNECTED', 1)  # 相機已連接
            
            # 重置操作計數器（可選）
            # self.modbus_service.write_register('OPERATION_COUNT', 0)
            # self.modbus_service.write_register('ERROR_COUNT', 0)
            
            print(f"✅ 設定值已同步: 面積={min_area}, 圓度={self.detection_params.min_roundness}")
            
        except Exception as e:
            print(f"❌ 同步設定值失敗: {e}")
    
    def capture_image(self) -> Tuple[Optional[np.ndarray], float]:
        """捕獲圖像"""
        if not self.is_connected or not self.camera_manager:
            return None, 0.0
        
        capture_start = time.time()
        
        try:
            frame_data = self.camera_manager.get_image_data(self.camera_name, timeout=3000)
            
            if frame_data is None:
                return None, 0.0
            
            capture_time = time.time() - capture_start
            
            image_array = frame_data.data
            
            if len(image_array.shape) == 2:
                display_image = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
            else:
                display_image = image_array
            
            self.last_image = display_image
            return display_image, capture_time
            
        except Exception as e:
            self.logger.error(f"捕獲圖像失敗: {e}")
            return None, 0.0
    
    def capture_and_detect(self) -> VisionResult:
        """拍照並進行圓形檢測"""
        total_start = time.time()
        
        try:
            image, capture_time = self.capture_image()
            
            if image is None:
                result = VisionResult(
                    circle_count=0,
                    circles=[],
                    processing_time=0.0,
                    capture_time=capture_time,
                    total_time=time.time() - total_start,
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success=False,
                    error_message="圖像捕獲失敗"
                )
            else:
                process_start = time.time()
                circles, annotated_image = self.detector.detect_circles(image)
                processing_time = time.time() - process_start
                total_time = time.time() - total_start
                
                self.last_image = annotated_image
                
                result = VisionResult(
                    circle_count=len(circles),
                    circles=circles,
                    processing_time=processing_time,
                    capture_time=capture_time,
                    total_time=total_time,
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success=True
                )
            
            self.last_result = result
            
            # 更新Modbus結果
            self.modbus_service.update_detection_results(result)
            
            return result
            
        except Exception as e:
            error_msg = f"檢測失敗: {str(e)}"
            self.logger.error(error_msg)
            
            result = VisionResult(
                circle_count=0,
                circles=[],
                processing_time=0.0,
                capture_time=0.0,
                total_time=time.time() - total_start,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                success=False,
                error_message=error_msg
            )
            
            self.modbus_service.update_detection_results(result)
            return result
    
    def get_image_base64(self) -> Optional[str]:
        """獲取當前圖像的base64編碼"""
        if self.last_image is None:
            return None
        
        try:
            height, width = self.last_image.shape[:2]
            if width > 800:
                scale = 800 / width
                new_width = 800
                new_height = int(height * scale)
                display_image = cv2.resize(self.last_image, (new_width, new_height))
            else:
                display_image = self.last_image
            
            _, buffer = cv2.imencode('.jpg', display_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{image_base64}"
            
        except Exception as e:
            self.logger.error(f"圖像編碼失敗: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """獲取系統狀態 (包含詳細的Modbus狀態)"""
        status = {
            'connected': self.is_connected,
            'camera_name': self.camera_name,
            'camera_ip': self.camera_ip,
            'has_image': self.last_image is not None,
            'last_result': asdict(self.last_result) if self.last_result else None,
            'detection_params': asdict(self.detection_params),
            'modbus_enabled': MODBUS_AVAILABLE,
            'external_control': self.modbus_service.external_control_enabled
        }
        
        # 添加Modbus詳細狀態
        if MODBUS_AVAILABLE and self.modbus_service.context:
            modbus_status = {
                'context_available': True,
                'external_control_register': self.modbus_service.read_register('EXTERNAL_CONTROL_ENABLE'),
                'system_status_register': self.modbus_service.read_register('SYSTEM_STATUS'),
                'camera_connected_register': self.modbus_service.read_register('CAMERA_CONNECTED'),
                'operation_count': self.modbus_service.read_register('OPERATION_COUNT'),
                'error_count': self.modbus_service.read_register('ERROR_COUNT')
            }
            status['modbus_status'] = modbus_status
        else:
            status['modbus_status'] = {'context_available': False}
        
        if self.camera_manager and self.is_connected:
            try:
                stats = self.camera_manager.get_camera_statistics(self.camera_name)
                status['camera_stats'] = stats
            except:
                pass
        
        return status
    
    def disconnect(self):
        """斷開相機連接"""
        if self.camera_manager:
            self.camera_manager.shutdown()
            self.camera_manager = None
        
        self.is_connected = False
        self.modbus_service.update_system_status(False)
        self.last_image = None
        self.logger.info("相機已斷開連接")


# Flask應用設置
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ccd_vision_control_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# 創建控制器實例
vision_controller = CCD1VisionController()

# 設置日誌
logging.basicConfig(level=logging.INFO)


@app.route('/')
def index():
    """主頁面"""
    return render_template('ccd_vision.html')


@app.route('/api/status')
def get_status():
    """獲取系統狀態"""
    return jsonify(vision_controller.get_status())


@app.route('/api/initialize', methods=['POST'])
def initialize_camera():
    """初始化相機"""
    data = request.get_json()
    ip_address = data.get('ip_address') if data else None
    
    result = vision_controller.initialize_camera(ip_address)
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify(result)


@app.route('/api/update_params', methods=['POST'])
def update_detection_params():
    """更新檢測參數"""
    data = request.get_json()
    min_area = data.get('min_area', 50000.0)
    min_roundness = data.get('min_roundness', 0.8)
    
    vision_controller.update_detection_params(min_area, min_roundness)
    
    return jsonify({
        'success': True,
        'message': f'參數已更新: 面積>={min_area}, 圓度>={min_roundness}',
        'params': asdict(vision_controller.detection_params)
    })


@app.route('/api/capture', methods=['POST'])
def capture_image():
    """拍照"""
    image, capture_time = vision_controller.capture_image()
    
    if image is None:
        return jsonify({
            'success': False,
            'message': '圖像捕獲失敗',
            'capture_time_ms': 0
        })
    
    image_base64 = vision_controller.get_image_base64()
    capture_time_ms = capture_time * 1000
    
    result = {
        'success': True,
        'message': '圖像捕獲成功',
        'capture_time_ms': round(capture_time_ms, 2),
        'image': image_base64,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    socketio.emit('image_update', result)
    return jsonify(result)


@app.route('/api/capture_and_detect', methods=['POST'])
def capture_and_detect():
    """拍照並檢測"""
    result = vision_controller.capture_and_detect()
    
    response = {
        'success': result.success,
        'circle_count': result.circle_count,
        'circles': result.circles,
        'capture_time_ms': round(result.capture_time * 1000, 2),
        'processing_time_ms': round(result.processing_time * 1000, 2),
        'total_time_ms': round(result.total_time * 1000, 2),
        'timestamp': result.timestamp,
        'image': vision_controller.get_image_base64() if result.success else None,
        'error_message': result.error_message
    }
    
    socketio.emit('detection_result', response)
    return jsonify(response)


@app.route('/api/modbus/registers', methods=['GET'])
def get_modbus_registers():
    """獲取所有Modbus寄存器的即時數值"""
    modbus_service = vision_controller.modbus_service
    
    if not modbus_service or not modbus_service.context:
        return jsonify({
            'success': False,
            'message': 'Modbus服務不可用',
            'registers': {}
        })
    
    try:
        registers = {}
        
        # 控制寄存器 (200-209)
        control_registers = {
            '200_外部控制啟用': modbus_service.read_register('EXTERNAL_CONTROL_ENABLE'),
            '201_拍照觸發': modbus_service.read_register('CAPTURE_TRIGGER'),
            '202_拍照檢測觸發': modbus_service.read_register('DETECT_TRIGGER'),
            '203_系統狀態': modbus_service.read_register('SYSTEM_STATUS'),
            '204_相機連接狀態': modbus_service.read_register('CAMERA_CONNECTED'),
            '205_系統重置': modbus_service.read_register('RESET_SYSTEM'),
        }
        
        # 參數設定寄存器 (210-219)
        area_high = modbus_service.read_register('MIN_AREA_HIGH')
        area_low = modbus_service.read_register('MIN_AREA_LOW')
        combined_area = (area_high << 16) + area_low
        roundness_raw = modbus_service.read_register('MIN_ROUNDNESS')
        roundness_value = roundness_raw / 1000.0
        
        param_registers = {
            '210_最小面積_高16位': area_high,
            '211_最小面積_低16位': area_low,
            '211_合併面積值': combined_area,
            '212_最小圓度_x1000': roundness_raw,
            '212_圓度實際值': round(roundness_value, 3),
            '213_參數更新觸發': modbus_service.read_register('DETECTION_PARAMS_UPDATE'),
        }
        
        # 檢測結果寄存器 (220-249)
        result_registers = {
            '220_檢測圓形數量': modbus_service.read_register('CIRCLE_COUNT'),
        }
        
        # 圓形座標 (221-230)
        for i in range(1, 6):
            x_val = modbus_service.read_register(f'CIRCLE_{i}_X')
            y_val = modbus_service.read_register(f'CIRCLE_{i}_Y')
            result_registers[f'{220+i*2-1}_圓形{i}_X座標'] = x_val
            result_registers[f'{220+i*2}_圓形{i}_Y座標'] = y_val
        
        # 統計資訊寄存器 (250-269)
        stats_registers = {
            '250_最後拍照耗時ms': modbus_service.read_register('LAST_CAPTURE_TIME'),
            '251_最後處理耗時ms': modbus_service.read_register('LAST_PROCESS_TIME'),
            '252_最後總耗時ms': modbus_service.read_register('LAST_TOTAL_TIME'),
            '253_操作計數器': modbus_service.read_register('OPERATION_COUNT'),
            '254_錯誤計數器': modbus_service.read_register('ERROR_COUNT'),
            '260_軟體版本主號': modbus_service.read_register('VERSION_MAJOR'),
            '261_軟體版本次號': modbus_service.read_register('VERSION_MINOR'),
            '262_運行時間小時': modbus_service.read_register('UPTIME_HOURS'),
            '263_運行時間分鐘': modbus_service.read_register('UPTIME_MINUTES'),
        }
        
        # 組合所有寄存器
        registers.update(control_registers)
        registers.update(param_registers)
        registers.update(result_registers)
        registers.update(stats_registers)
        
        return jsonify({
            'success': True,
            'message': 'Modbus寄存器讀取成功',
            'registers': registers,
            'external_control_enabled': modbus_service.external_control_enabled,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_registers': len(registers)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'讀取寄存器失敗: {str(e)}',
            'registers': {},
            'error': str(e)
        })
    """Modbus安裝指南 (pymodbus 3.9.2)"""
    try:
        import pymodbus
        current_version = pymodbus.__version__
        version_info = f"當前版本: {current_version}"
    except:
        current_version = "未安裝"
        version_info = "pymodbus未安裝"
    
    return jsonify({
        'pymodbus_available': MODBUS_AVAILABLE,
        'current_version': current_version,
        'target_version': PYMODBUS_VERSION,
        'version_info': version_info,
        'install_commands': [
            'pip install pymodbus>=3.0.0',
            'pip install "pymodbus[serial]>=3.0.0"'
        ],
        'verify_command': 'python -c "import pymodbus; print(f\'pymodbus {pymodbus.__version__}\')"',
        'api_changes': [
            'pymodbus 3.x使用異步架構',
            '服務器啟動方式已更改',
            'API調用方式有所不同'
        ],
        'upgrade_notes': [
            'pymodbus 3.9.2是目前最新穩定版',
            '支援異步和同步操作',
            '向後兼容性有限，需要代碼適配'
        ],
        'restart_required': True,
        'compatibility': {
            'python_min': '3.7',
            'recommended_python': '3.8+',
            'async_support': True,
            'sync_support': True
        }
    })
    """斷開相機連接"""
    vision_controller.disconnect()
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify({'success': True, 'message': '相機已斷開連接'})


@app.route('/api/modbus/test', methods=['GET'])
def test_modbus():
    """測試Modbus連接狀態 (pymodbus 3.9.2)"""
    # 基本模組檢查
    if not MODBUS_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Modbus模組不可用',
            'available': False,
            'context': False,
            'pymodbus_version': PYMODBUS_VERSION,
            'install_command': 'pip install pymodbus>=3.0.0'
        })
    
    modbus_service = vision_controller.modbus_service
    
    # Context檢查
    if not modbus_service.context:
        return jsonify({
            'success': False,
            'message': 'Modbus服務未正確初始化 - Context為空',
            'available': True,
            'context': False,
            'pymodbus_version': PYMODBUS_VERSION,
            'suggestion': '重新啟動系統或檢查Modbus初始化過程'
        })
    
    try:
        # 檢查pymodbus版本
        import pymodbus
        actual_version = pymodbus.__version__
        
        # 測試寄存器讀寫
        test_address = modbus_service.REGISTERS['VERSION_MAJOR']
        test_value = 999
        
        # 測試寫入
        write_success = modbus_service.write_register('VERSION_MAJOR', test_value)
        
        # 測試讀取
        read_value = modbus_service.read_register('VERSION_MAJOR')
        
        # 恢復正確值
        modbus_service.write_register('VERSION_MAJOR', 2)
        
        # 檢查外部控制狀態
        external_control = modbus_service.read_register('EXTERNAL_CONTROL_ENABLE')
        
        # 全面測試結果
        test_passed = write_success and (read_value == test_value)
        
        return jsonify({
            'success': test_passed,
            'message': f'✅ Modbus服務正常 (pymodbus {actual_version})' if test_passed else '❌ Modbus讀寫測試失敗',
            'available': True,
            'context': True,
            'pymodbus_version': actual_version,
            'expected_version': PYMODBUS_VERSION,
            'write_success': write_success,
            'test_write_value': test_value,
            'test_read_value': read_value,
            'read_write_match': (read_value == test_value),
            'external_control_value': external_control,
            'external_control_enabled': modbus_service.external_control_enabled,
            'test_register_address': test_address,
            'register_count': len(modbus_service.REGISTERS),
            'server_running': modbus_service.running
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Modbus測試異常: {str(e)}',
            'available': True,
            'context': True,
            'pymodbus_version': PYMODBUS_VERSION,
            'error': str(e),
            'error_type': type(e).__name__
        })


@app.route('/api/modbus/toggle', methods=['POST'])
def toggle_external_control():
    """切換外部控制模式"""
    data = request.get_json()
    enable = data.get('enable', False)
    
    modbus_service = vision_controller.modbus_service
    
    # 檢查服務是否可用
    if not modbus_service or not modbus_service.context:
        return jsonify({
            'success': False,
            'message': 'Modbus服務不可用或未初始化'
        })
    
    try:
        value = 1 if enable else 0
        success = modbus_service.write_register('EXTERNAL_CONTROL_ENABLE', value)
        
        if success:
            # 直接同步狀態變數
            modbus_service.external_control_enabled = enable
            
            # 驗證寫入 (對模擬服務也有效)
            read_back = modbus_service.read_register('EXTERNAL_CONTROL_ENABLE')
            
            # 記錄日誌
            print(f"🔄 WebUI設定外部控制: {'啟用' if enable else '停用'}")
            
            service_type = "完整Modbus" if MODBUS_AVAILABLE else "模擬Modbus"
            
            return jsonify({
                'success': True,
                'external_control_enabled': enable,
                'message': f'外部控制已{"啟用" if enable else "禁用"} ({service_type})',
                'register_value': value,
                'read_back_value': read_back,
                'verified': (read_back == value),
                'service_type': service_type
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Modbus寄存器寫入失敗'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'操作失敗: {str(e)}'
        })


@socketio.on('connect')
def handle_connect():
    """客戶端連接"""
    emit('status_update', vision_controller.get_status())


@socketio.on('disconnect')
def handle_disconnect():
    """客戶端斷開"""
    pass


def main():
    """主函數"""
    print("🚀 CCD1 視覺控制系統啟動中...")
    
    if not CAMERA_MANAGER_AVAILABLE:
        print("❌ 相機管理器不可用，請檢查SDK導入")
        return
    
    try:
        # 初始化Modbus服務
        if MODBUS_AVAILABLE:
            if vision_controller.initialize_modbus():
                print(f"✅ Modbus TCP服務已啟動 (Port: 502, pymodbus {PYMODBUS_VERSION})")
                print("📊 CCD1 Modbus寄存器映射 (避免衝突，使用200-269):")
                print("   控制寄存器 (200-209):")
                print("   • 200: 外部控制啟用 (0=禁用, 1=啟用)")
                print("   • 201: 拍照觸發 (寫入1觸發)")
                print("   • 202: 拍照+檢測觸發 (寫入1觸發)")
                print("   • 203: 系統狀態 (0=斷線, 1=已連接, 2=處理中)")
                print("   • 204: 相機連接狀態 (0=斷線, 1=已連接)")
                print("   • 205: 系統重置 (寫入1重置)")
                print("   參數設定 (210-219):")
                print("   • 210-211: 最小面積設定 (32位分高低16位)")
                print("   • 212: 最小圓度設定 (乘以1000)")
                print("   • 213: 參數更新觸發 (寫入1更新)")
                print("   檢測結果 (220-249):")
                print("   • 220: 檢測到的圓形數量")
                print("   • 221-230: 圓形1-5的X,Y座標")
                print("   統計資訊 (250-269):")
                print("   • 250-252: 最後操作的時間統計")
                print("   • 253-254: 操作計數器/錯誤計數器")
                print("   • 260-263: 版本號與運行時間")
            else:
                print("⚠️ Modbus服務啟動失敗")
        else:
            print("⚠️ Modbus功能不可用")
        
        print("🌐 Web介面啟動中...")
        print("📱 訪問地址: http://localhost:5051")
        print("🎯 系統功能:")
        print("   • 相機連接管理")
        print("   • iOS風格參數調整")
        print("   • 圓形檢測與標註")
        print("   • Modbus TCP外部控制")
        print("=" * 50)
        
        socketio.run(app, host='0.0.0.0', port=5051, debug=False)
        
    except KeyboardInterrupt:
        print("\n🛑 用戶中斷，正在關閉系統...")
    except Exception as e:
        print(f"❌ 系統運行錯誤: {e}")
    finally:
        try:
            vision_controller.disconnect()
        except:
            pass
        print("✅ 系統已安全關閉")


if __name__ == "__main__":
    main()