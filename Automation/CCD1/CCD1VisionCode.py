# -*- coding: utf-8 -*-
"""
CCD1VisionCode.py - CCD[U+8996][U+89BA][U+63A7][U+5236][U+7CFB][U+7D71] (Modbus TCP Client[U+7248][U+672C])
[U+57FA][U+65BC][U+5DE5][U+696D][U+8A2D][U+5099][U+63A7][U+5236][U+67B6][U+69CB][U+7684][U+8996][U+89BA][U+8FA8][U+8B58]Web[U+63A7][U+5236][U+4ECB][U+9762]
[U+4F5C][U+70BA]Modbus TCP Client[U+9023][U+63A5][U+5916][U+90E8]PLC/HMI[U+8A2D][U+5099]
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

# [U+5C0E][U+5165]Modbus TCP Client[U+670D][U+52D9] ([U+9069][U+914D]pymodbus 3.9.2)
try:
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException, ConnectionException
    MODBUS_AVAILABLE = True
    PYMODBUS_VERSION = "3.9.2"
    print("[OK] Modbus Client[U+6A21][U+7D44][U+5C0E][U+5165][U+6210][U+529F] (pymodbus 3.9.2)")
except ImportError as e:
    print(f"[WARN][U+FE0F] Modbus Client[U+6A21][U+7D44][U+5C0E][U+5165][U+5931][U+6557]: {e}")
    print("[U+1F4A1] [U+8ACB][U+78BA][U+8A8D]pymodbus[U+7248][U+672C]: pip install pymodbus>=3.0.0")
    MODBUS_AVAILABLE = False
    PYMODBUS_VERSION = "unavailable"

# [U+5C0E][U+5165][U+76F8][U+6A5F][U+7BA1][U+7406][U+6A21][U+7D44]
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'API'))
try:
    from camera_manager import OptimizedCameraManager, CameraConfig, CameraMode, PixelFormat
    CAMERA_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"[FAIL] [U+7121][U+6CD5][U+5C0E][U+5165] camera_manager [U+6A21][U+7D44]: {e}")
    CAMERA_MANAGER_AVAILABLE = False


@dataclass
class DetectionParams:
    """[U+6AA2][U+6E2C][U+53C3][U+6578][U+914D][U+7F6E]"""
    min_area: float = 50000.0
    min_roundness: float = 0.8
    gaussian_kernel_size: int = 9
    gaussian_sigma: float = 2.0
    canny_low: int = 20
    canny_high: int = 60


@dataclass
class VisionResult:
    """[U+8996][U+89BA][U+8FA8][U+8B58][U+7D50][U+679C]"""
    circle_count: int
    circles: List[Dict[str, Any]]
    processing_time: float
    capture_time: float
    total_time: float
    timestamp: str
    success: bool
    error_message: Optional[str] = None


class ModbusTcpClientService:
    """Modbus TCP Client[U+670D][U+52D9] - [U+9023][U+63A5][U+5916][U+90E8]PLC/HMI[U+8A2D][U+5099]"""
    
    def __init__(self, server_ip="192.168.1.100", server_port=502):
        self.server_ip = server_ip
        self.server_port = server_port
        self.client: Optional[ModbusTcpClient] = None
        self.connected = False
        self.running = False
        self.vision_controller = None
        
        # [U+9023][U+63A5][U+53C3][U+6578]
        self.reconnect_delay = 5.0  # [U+91CD][U+9023][U+5EF6][U+9072]
        self.read_timeout = 3.0     # [U+8B80][U+53D6][U+8D85][U+6642]
        self.write_timeout = 3.0    # [U+5BEB][U+5165][U+8D85][U+6642]
        
        # [U+65B0][U+589E][U+FF1A][U+540C][U+6B65][U+63A7][U+5236]
        self.sync_enabled = False           # [U+540C][U+6B65][U+958B][U+95DC]
        self.sync_thread = None            # [U+540C][U+6B65][U+7DDA][U+7A0B]
        self.sync_running = False          # [U+540C][U+6B65][U+7DDA][U+7A0B][U+904B][U+884C][U+72C0][U+614B]
        self.sync_interval = 0.1           # [U+540C][U+6B65][U+9593][U+9694] (100ms)
        self.status_sync_counter = 0       # [U+72C0][U+614B][U+540C][U+6B65][U+8A08][U+6578][U+5668]
        self.status_sync_interval = 10     # [U+6BCF]10[U+6B21][U+5FAA][U+74B0][U+540C][U+6B65][U+4E00][U+6B21][U+72C0][U+614B] (1[U+79D2])
        
        # Modbus[U+5BC4][U+5B58][U+5668][U+6620][U+5C04] (CCD1[U+5C08][U+7528][U+5730][U+5740][U+6BB5]: 200-299)
        self.REGISTERS = {
            # [U+63A7][U+5236][U+5BC4][U+5B58][U+5668] (200-209) - [U+5F9E][U+5916][U+90E8]PLC[U+8B80][U+53D6][U+63A7][U+5236][U+6307][U+4EE4]
            'EXTERNAL_CONTROL_ENABLE': 200,    # [U+5916][U+90E8][U+63A7][U+5236][U+555F][U+7528] (0=[U+7981][U+7528], 1=[U+555F][U+7528])
            'CAPTURE_TRIGGER': 201,            # [U+62CD][U+7167][U+89F8][U+767C] ([U+8B80][U+53D6][U+5230]1[U+6642][U+89F8][U+767C])
            'DETECT_TRIGGER': 202,             # [U+62CD][U+7167]+[U+6AA2][U+6E2C][U+89F8][U+767C] ([U+8B80][U+53D6][U+5230]1[U+6642][U+89F8][U+767C])
            'SYSTEM_RESET': 203,               # [U+7CFB][U+7D71][U+91CD][U+7F6E] ([U+8B80][U+53D6][U+5230]1[U+6642][U+91CD][U+7F6E])
            'PARAM_UPDATE_TRIGGER': 204,       # [U+53C3][U+6578][U+66F4][U+65B0][U+89F8][U+767C]
            
            # [U+53C3][U+6578][U+8A2D][U+5B9A][U+5BC4][U+5B58][U+5668] (210-219) - [U+5F9E][U+5916][U+90E8]PLC[U+8B80][U+53D6][U+53C3][U+6578][U+8A2D][U+5B9A]
            'MIN_AREA_HIGH': 210,              # [U+6700][U+5C0F][U+9762][U+7A4D][U+8A2D][U+5B9A] ([U+9AD8]16[U+4F4D])
            'MIN_AREA_LOW': 211,               # [U+6700][U+5C0F][U+9762][U+7A4D][U+8A2D][U+5B9A] ([U+4F4E]16[U+4F4D])
            'MIN_ROUNDNESS': 212,              # [U+6700][U+5C0F][U+5713][U+5EA6][U+8A2D][U+5B9A] ([U+4E58][U+4EE5]1000)
            'GAUSSIAN_KERNEL': 213,            # [U+9AD8][U+65AF][U+6838][U+5927][U+5C0F]
            'CANNY_LOW': 214,                  # Canny[U+4F4E][U+95BE][U+503C]
            'CANNY_HIGH': 215,                 # Canny[U+9AD8][U+95BE][U+503C]
            
            # [U+72C0][U+614B][U+56DE][U+5831][U+5BC4][U+5B58][U+5668] (220-239) - [U+5BEB][U+5165][U+72C0][U+614B][U+5230][U+5916][U+90E8]PLC
            'SYSTEM_STATUS': 220,              # [U+7CFB][U+7D71][U+72C0][U+614B] (0=[U+65B7][U+7DDA], 1=[U+5DF2][U+9023][U+63A5], 2=[U+8655][U+7406][U+4E2D])
            'CAMERA_CONNECTED': 221,           # [U+76F8][U+6A5F][U+9023][U+63A5][U+72C0][U+614B] (0=[U+65B7][U+7DDA], 1=[U+5DF2][U+9023][U+63A5])
            'LAST_OPERATION_STATUS': 222,      # [U+6700][U+5F8C][U+64CD][U+4F5C][U+72C0][U+614B] (0=[U+5931][U+6557], 1=[U+6210][U+529F])
            'PROCESSING_PROGRESS': 223,        # [U+8655][U+7406][U+9032][U+5EA6] (0-100)
            
            # [U+7D50][U+679C][U+5BC4][U+5B58][U+5668] (240-279) - [U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230][U+5916][U+90E8]PLC
            'CIRCLE_COUNT': 240,               # [U+6AA2][U+6E2C][U+5230][U+7684][U+5713][U+5F62][U+6578][U+91CF]
            'CIRCLE_1_X': 241,                 # [U+5713][U+5F62]1 X[U+5EA7][U+6A19]
            'CIRCLE_1_Y': 242,                 # [U+5713][U+5F62]1 Y[U+5EA7][U+6A19]
            'CIRCLE_1_RADIUS': 243,            # [U+5713][U+5F62]1 [U+534A][U+5F91]
            'CIRCLE_2_X': 244,                 # [U+5713][U+5F62]2 X[U+5EA7][U+6A19]
            'CIRCLE_2_Y': 245,                 # [U+5713][U+5F62]2 Y[U+5EA7][U+6A19]
            'CIRCLE_2_RADIUS': 246,            # [U+5713][U+5F62]2 [U+534A][U+5F91]
            'CIRCLE_3_X': 247,                 # [U+5713][U+5F62]3 X[U+5EA7][U+6A19]
            'CIRCLE_3_Y': 248,                 # [U+5713][U+5F62]3 Y[U+5EA7][U+6A19]
            'CIRCLE_3_RADIUS': 249,            # [U+5713][U+5F62]3 [U+534A][U+5F91]
            'CIRCLE_4_X': 250,                 # [U+5713][U+5F62]4 X[U+5EA7][U+6A19]
            'CIRCLE_4_Y': 251,                 # [U+5713][U+5F62]4 Y[U+5EA7][U+6A19]
            'CIRCLE_4_RADIUS': 252,            # [U+5713][U+5F62]4 [U+534A][U+5F91]
            'CIRCLE_5_X': 253,                 # [U+5713][U+5F62]5 X[U+5EA7][U+6A19]
            'CIRCLE_5_Y': 254,                 # [U+5713][U+5F62]5 Y[U+5EA7][U+6A19]
            'CIRCLE_5_RADIUS': 255,            # [U+5713][U+5F62]5 [U+534A][U+5F91]
            
            # [U+7D71][U+8A08][U+8CC7][U+8A0A][U+5BC4][U+5B58][U+5668] (280-299) - [U+5BEB][U+5165][U+7D71][U+8A08][U+5230][U+5916][U+90E8]PLC
            'LAST_CAPTURE_TIME': 280,          # [U+6700][U+5F8C][U+62CD][U+7167][U+8017][U+6642] (ms)
            'LAST_PROCESS_TIME': 281,          # [U+6700][U+5F8C][U+8655][U+7406][U+8017][U+6642] (ms)
            'LAST_TOTAL_TIME': 282,            # [U+6700][U+5F8C][U+7E3D][U+8017][U+6642] (ms)
            'OPERATION_COUNT': 283,            # [U+64CD][U+4F5C][U+8A08][U+6578][U+5668]
            'ERROR_COUNT': 284,                # [U+932F][U+8AA4][U+8A08][U+6578][U+5668]
            'CONNECTION_COUNT': 285,           # [U+9023][U+63A5][U+8A08][U+6578][U+5668]
            'VERSION_MAJOR': 290,              # [U+8EDF][U+9AD4][U+7248][U+672C][U+4E3B][U+7248][U+865F]
            'VERSION_MINOR': 291,              # [U+8EDF][U+9AD4][U+7248][U+672C][U+6B21][U+7248][U+865F]
            'UPTIME_HOURS': 292,               # [U+7CFB][U+7D71][U+904B][U+884C][U+6642][U+9593] ([U+5C0F][U+6642])
            'UPTIME_MINUTES': 293,             # [U+7CFB][U+7D71][U+904B][U+884C][U+6642][U+9593] ([U+5206][U+9418])
        }
        
        # [U+72C0][U+614B][U+8FFD][U+8E64]
        self.last_trigger_states = {}
        self.operation_count = 0
        self.error_count = 0
        self.connection_count = 0
        self.start_time = time.time()
        
        # [U+5916][U+90E8][U+63A7][U+5236][U+72C0][U+614B]
        self.external_control_enabled = False
        self.last_params_hash = None
        
    def set_vision_controller(self, controller):
        """[U+8A2D][U+7F6E][U+8996][U+89BA][U+63A7][U+5236][U+5668][U+5F15][U+7528]"""
        self.vision_controller = controller
        
    def set_server_address(self, ip: str, port: int = 502):
        """[U+8A2D][U+7F6E]Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740]"""
        self.server_ip = ip
        self.server_port = port
        print(f"[U+1F527] Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740][U+8A2D][U+7F6E][U+70BA]: {ip}:{port}")
    
    def connect(self) -> bool:
        """[U+9023][U+63A5][U+5230]Modbus TCP[U+670D][U+52D9][U+5668]"""
        if not MODBUS_AVAILABLE:
            print("[FAIL] Modbus Client[U+4E0D][U+53EF][U+7528]")
            return False
        
        try:
            if self.client:
                self.client.close()
            
            print(f"[U+1F517] [U+6B63][U+5728][U+9023][U+63A5]Modbus TCP[U+670D][U+52D9][U+5668]: {self.server_ip}:{self.server_port}")
            
            self.client = ModbusTcpClient(
                host=self.server_ip,
                port=self.server_port,
                timeout=self.read_timeout
            )
            
            # [U+5617][U+8A66][U+9023][U+63A5]
            if self.client.connect():
                self.connected = True
                self.connection_count += 1
                
                # [U+5BEB][U+5165][U+521D][U+59CB][U+72C0][U+614B]
                self._write_initial_status()
                
                print(f"[OK] Modbus TCP Client[U+9023][U+63A5][U+6210][U+529F]: {self.server_ip}:{self.server_port}")
                return True
            else:
                print(f"[FAIL] Modbus TCP[U+9023][U+63A5][U+5931][U+6557]: {self.server_ip}:{self.server_port}")
                self.connected = False
                return False
                
        except Exception as e:
            print(f"[FAIL] Modbus TCP[U+9023][U+63A5][U+7570][U+5E38]: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """[U+65B7][U+958B]Modbus[U+9023][U+63A5]"""
        # [U+5148][U+505C][U+6B62][U+540C][U+6B65][U+7DDA][U+7A0B]
        self.stop_sync()
        
        if self.client and self.connected:
            try:
                # [U+5BEB][U+5165][U+65B7][U+7DDA][U+72C0][U+614B]
                self.write_register('SYSTEM_STATUS', 0)
                self.write_register('CAMERA_CONNECTED', 0)
                
                self.client.close()
                print("[U+1F50C] Modbus TCP Client[U+5DF2][U+65B7][U+958B][U+9023][U+63A5]")
            except:
                pass
        
        self.connected = False
        self.client = None
    
    def enable_external_control(self, enable: bool):
        """[U+555F][U+7528]/[U+7981][U+7528][U+5916][U+90E8][U+63A7][U+5236]"""
        self.external_control_enabled = enable
        
        if enable and self.connected:
            # [U+555F][U+7528][U+5916][U+90E8][U+63A7][U+5236][U+6642][U+958B][U+59CB][U+540C][U+6B65]
            self.start_sync()
            print("[U+1F504] [U+5916][U+90E8][U+63A7][U+5236][U+5DF2][U+555F][U+7528][U+FF0C][U+958B][U+59CB][U+540C][U+6B65][U+7DDA][U+7A0B]")
        else:
            # [U+7981][U+7528][U+5916][U+90E8][U+63A7][U+5236][U+6642][U+505C][U+6B62][U+540C][U+6B65]
            self.stop_sync()
            print("[U+23F9][U+FE0F] [U+5916][U+90E8][U+63A7][U+5236][U+5DF2][U+7981][U+7528][U+FF0C][U+505C][U+6B62][U+540C][U+6B65][U+7DDA][U+7A0B]")
    
    def start_sync(self):
        """[U+555F][U+52D5][U+540C][U+6B65][U+7DDA][U+7A0B]"""
        if self.sync_running:
            return  # [U+5DF2][U+7D93][U+5728][U+904B][U+884C]
        
        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        print("[OK] Modbus[U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+555F][U+52D5]")
    
    def stop_sync(self):
        """[U+505C][U+6B62][U+540C][U+6B65][U+7DDA][U+7A0B]"""
        if self.sync_running:
            self.sync_running = False
            if self.sync_thread and self.sync_thread.is_alive():
                self.sync_thread.join(timeout=2.0)  # [U+7B49][U+5F85][U+6700][U+591A]2[U+79D2]
            print("[U+1F6D1] Modbus[U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+505C][U+6B62]")
    
    def _sync_loop(self):
        """[U+540C][U+6B65][U+5FAA][U+74B0] - [U+5728][U+7368][U+7ACB][U+7DDA][U+7A0B][U+4E2D][U+904B][U+884C]"""
        print("[U+1F504] [U+540C][U+6B65][U+7DDA][U+7A0B][U+958B][U+59CB][U+904B][U+884C]...")
        
        while self.sync_running and self.connected:
            try:
                # 1. [U+6AA2][U+67E5][U+5916][U+90E8][U+63A7][U+5236][U+72C0][U+614B][U+8B8A][U+5316]
                self._check_external_control_changes()
                
                # 2. [U+5982][U+679C][U+5916][U+90E8][U+63A7][U+5236][U+555F][U+7528][U+FF0C][U+9032][U+884C][U+89F8][U+767C][U+6AA2][U+6E2C]
                if self.external_control_enabled:
                    self._check_all_triggers()
                    self._check_parameter_updates()
                else:
                    # [U+5982][U+679C][U+5916][U+90E8][U+63A7][U+5236][U+88AB][U+7981][U+7528][U+FF0C][U+505C][U+6B62][U+540C][U+6B65][U+7DDA][U+7A0B]
                    print("[WARN][U+FE0F] [U+5916][U+90E8][U+63A7][U+5236][U+5DF2][U+7981][U+7528][U+FF0C][U+540C][U+6B65][U+7DDA][U+7A0B][U+5C07][U+9000][U+51FA]")
                    break
                
                # 3. [U+5B9A][U+671F][U+540C][U+6B65][U+72C0][U+614B][U+FF08][U+6BCF]1[U+79D2][U+4E00][U+6B21][U+FF09]
                self.status_sync_counter += 1
                if self.status_sync_counter >= self.status_sync_interval:
                    self._sync_status_to_plc()
                    self._update_uptime()
                    self.status_sync_counter = 0
                
                # [U+77ED][U+66AB][U+4F11][U+7720]
                time.sleep(self.sync_interval)
                
            except ConnectionException:
                print("[FAIL] Modbus[U+9023][U+63A5][U+4E2D][U+65B7][U+FF0C][U+540C][U+6B65][U+7DDA][U+7A0B][U+9000][U+51FA]")
                self.connected = False
                break
                
            except Exception as e:
                print(f"[FAIL] [U+540C][U+6B65][U+7DDA][U+7A0B][U+932F][U+8AA4]: {e}")
                self.error_count += 1
                time.sleep(1.0)  # [U+932F][U+8AA4][U+6642][U+5EF6][U+9577][U+4F11][U+7720]
        
        self.sync_running = False
        print("[U+23F9][U+FE0F] [U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+9000][U+51FA]")
    
    def _check_all_triggers(self):
        """[U+6AA2][U+67E5][U+6240][U+6709][U+89F8][U+767C][U+4FE1][U+865F] ([U+589E][U+52A0][U+8A73][U+7D30][U+65E5][U+8A8C])"""
        try:
            # [U+6AA2][U+67E5][U+62CD][U+7167][U+89F8][U+767C]
            capture_trigger = self.read_register('CAPTURE_TRIGGER')
            if capture_trigger is not None:
                if (capture_trigger > 0 and 
                    capture_trigger != self.last_trigger_states.get('capture', 0)):
                    
                    print(f"[U+1F4F8] [U+6AA2][U+6E2C][U+5230][U+62CD][U+7167][U+89F8][U+767C]: {capture_trigger} ([U+4E0A][U+6B21]: {self.last_trigger_states.get('capture', 0)})")
                    self.last_trigger_states['capture'] = capture_trigger
                    self._handle_capture_trigger()
                    # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                    self.write_register('CAPTURE_TRIGGER', 0)
            
            # [U+6AA2][U+67E5][U+6AA2][U+6E2C][U+89F8][U+767C]
            detect_trigger = self.read_register('DETECT_TRIGGER')
            if detect_trigger is not None:
                if (detect_trigger > 0 and 
                    detect_trigger != self.last_trigger_states.get('detect', 0)):
                    
                    print(f"[U+1F50D] [U+6AA2][U+6E2C][U+5230][U+6AA2][U+6E2C][U+89F8][U+767C]: {detect_trigger} ([U+4E0A][U+6B21]: {self.last_trigger_states.get('detect', 0)})")
                    self.last_trigger_states['detect'] = detect_trigger
                    self._handle_detect_trigger()
                    # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                    self.write_register('DETECT_TRIGGER', 0)
            
            # [U+6AA2][U+67E5][U+91CD][U+7F6E][U+89F8][U+767C]
            reset_trigger = self.read_register('SYSTEM_RESET')
            if reset_trigger is not None:
                if (reset_trigger > 0 and 
                    reset_trigger != self.last_trigger_states.get('reset', 0)):
                    
                    print(f"[U+1F504] [U+6AA2][U+6E2C][U+5230][U+91CD][U+7F6E][U+89F8][U+767C]: {reset_trigger} ([U+4E0A][U+6B21]: {self.last_trigger_states.get('reset', 0)})")
                    self.last_trigger_states['reset'] = reset_trigger
                    self._handle_reset_trigger()
                    # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                    self.write_register('SYSTEM_RESET', 0)
                    
        except Exception as e:
            print(f"[FAIL] [U+6AA2][U+67E5][U+89F8][U+767C][U+4FE1][U+865F][U+5931][U+6557]: {e}")
    
    def get_debug_info(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+8ABF][U+8A66][U+4FE1][U+606F]"""
        return {
            'connected': self.connected,
            'external_control_enabled': self.external_control_enabled,
            'sync_running': self.sync_running,
            'sync_thread_alive': self.sync_thread.is_alive() if self.sync_thread else False,
            'last_trigger_states': self.last_trigger_states.copy(),
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'server_address': f"{self.server_ip}:{self.server_port}"
        }
    
    def _check_external_control_changes(self):
        """[U+6AA2][U+67E5][U+5916][U+90E8][U+63A7][U+5236][U+72C0][U+614B][U+8B8A][U+5316]"""
        try:
            control_value = self.read_register('EXTERNAL_CONTROL_ENABLE')
            if control_value is not None:
                new_state = bool(control_value)
                if new_state != self.external_control_enabled:
                    self.external_control_enabled = new_state
                    print(f"[U+1F504] [U+5916][U+90E8][U+63A7][U+5236][U+72C0][U+614B][U+540C][U+6B65]: {'[U+555F][U+7528]' if new_state else '[U+505C][U+7528]'}")
        except:
            pass
    
    def _check_all_triggers(self):
        """[U+6AA2][U+67E5][U+6240][U+6709][U+89F8][U+767C][U+4FE1][U+865F]"""
        try:
            # [U+6AA2][U+67E5][U+62CD][U+7167][U+89F8][U+767C]
            capture_trigger = self.read_register('CAPTURE_TRIGGER')
            if (capture_trigger is not None and capture_trigger > 0 and 
                capture_trigger != self.last_trigger_states.get('capture', 0)):
                
                self.last_trigger_states['capture'] = capture_trigger
                self._handle_capture_trigger()
                # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                self.write_register('CAPTURE_TRIGGER', 0)
            
            # [U+6AA2][U+67E5][U+6AA2][U+6E2C][U+89F8][U+767C]
            detect_trigger = self.read_register('DETECT_TRIGGER')
            if (detect_trigger is not None and detect_trigger > 0 and 
                detect_trigger != self.last_trigger_states.get('detect', 0)):
                
                self.last_trigger_states['detect'] = detect_trigger
                self._handle_detect_trigger()
                # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                self.write_register('DETECT_TRIGGER', 0)
            
            # [U+6AA2][U+67E5][U+91CD][U+7F6E][U+89F8][U+767C]
            reset_trigger = self.read_register('SYSTEM_RESET')
            if (reset_trigger is not None and reset_trigger > 0 and 
                reset_trigger != self.last_trigger_states.get('reset', 0)):
                
                self.last_trigger_states['reset'] = reset_trigger
                self._handle_reset_trigger()
                # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                self.write_register('SYSTEM_RESET', 0)
                
        except Exception as e:
            print(f"[FAIL] [U+6AA2][U+67E5][U+89F8][U+767C][U+4FE1][U+865F][U+5931][U+6557]: {e}")
    
    def _sync_status_to_plc(self):
        """[U+540C][U+6B65][U+72C0][U+614B][U+5230]PLC"""
        try:
            # [U+540C][U+6B65][U+7CFB][U+7D71][U+72C0][U+614B]
            if self.vision_controller and self.vision_controller.is_connected:
                self.write_register('SYSTEM_STATUS', 1)
                self.write_register('CAMERA_CONNECTED', 1)
            else:
                self.write_register('SYSTEM_STATUS', 0)
                self.write_register('CAMERA_CONNECTED', 0)
            
            # [U+540C][U+6B65][U+8A08][U+6578][U+5668]
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            self.write_register('CONNECTION_COUNT', self.connection_count)
            
        except Exception as e:
            print(f"[FAIL] [U+540C][U+6B65][U+72C0][U+614B][U+5230]PLC[U+5931][U+6557]: {e}")
    
    def _write_initial_status(self):
        """[U+5BEB][U+5165][U+521D][U+59CB][U+72C0][U+614B][U+5230]PLC"""
        try:
            # [U+7248][U+672C][U+8CC7][U+8A0A]
            self.write_register('VERSION_MAJOR', 2)
            self.write_register('VERSION_MINOR', 1)
            
            # [U+7CFB][U+7D71][U+72C0][U+614B]
            camera_status = 1 if (self.vision_controller and self.vision_controller.is_connected) else 0
            self.write_register('SYSTEM_STATUS', camera_status)
            self.write_register('CAMERA_CONNECTED', camera_status)
            self.write_register('LAST_OPERATION_STATUS', 1)
            
            # [U+8A08][U+6578][U+5668]
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            self.write_register('CONNECTION_COUNT', self.connection_count)
            
            print("[U+1F4CA] [U+521D][U+59CB][U+72C0][U+614B][U+5DF2][U+5BEB][U+5165]PLC")
            
        except Exception as e:
            print(f"[FAIL] [U+5BEB][U+5165][U+521D][U+59CB][U+72C0][U+614B][U+5931][U+6557]: {e}")
    
    def _handle_capture_trigger(self):
        """[U+8655][U+7406][U+62CD][U+7167][U+89F8][U+767C] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        if not self.vision_controller:
            return
        
        try:
            self.write_register('PROCESSING_PROGRESS', 50)
            print("[U+1F4F8] [U+5916][U+90E8][U+89F8][U+767C]: [U+57F7][U+884C][U+62CD][U+7167]")
            
            image, capture_time = self.vision_controller.capture_image()
            
            if image is not None:
                self.write_register('LAST_OPERATION_STATUS', 1)
                self.write_register('LAST_CAPTURE_TIME', int(capture_time * 1000))
                print(f"[OK] [U+62CD][U+7167][U+6210][U+529F][U+FF0C][U+8017][U+6642]: {capture_time*1000:.2f}ms")
            else:
                self.write_register('LAST_OPERATION_STATUS', 0)
                self.error_count += 1
                print("[FAIL] [U+62CD][U+7167][U+5931][U+6557]")
            
            self.operation_count += 1
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            self.write_register('PROCESSING_PROGRESS', 100)
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+62CD][U+7167][U+89F8][U+767C][U+5931][U+6557]: {e}")
            self.write_register('LAST_OPERATION_STATUS', 0)
            self.write_register('PROCESSING_PROGRESS', 0)
            self.error_count += 1
    
    def _handle_detect_trigger(self):
        """[U+8655][U+7406][U+6AA2][U+6E2C][U+89F8][U+767C] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        if not self.vision_controller:
            return
        
        try:
            self.write_register('PROCESSING_PROGRESS', 20)
            print("[U+1F50D] [U+5916][U+90E8][U+89F8][U+767C]: [U+57F7][U+884C][U+62CD][U+7167]+[U+6AA2][U+6E2C]")
            
            result = self.vision_controller.capture_and_detect()
            
            if result.success:
                # [U+66F4][U+65B0][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230]PLC
                self.update_detection_results(result)
                self.write_register('LAST_OPERATION_STATUS', 1)
                print(f"[OK] [U+6AA2][U+6E2C][U+6210][U+529F][U+FF0C][U+627E][U+5230] {result.circle_count} [U+500B][U+5713][U+5F62]")
            else:
                self.write_register('LAST_OPERATION_STATUS', 0)
                self.error_count += 1
                print(f"[FAIL] [U+6AA2][U+6E2C][U+5931][U+6557]: {result.error_message}")
            
            self.operation_count += 1
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            self.write_register('PROCESSING_PROGRESS', 100)
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+6AA2][U+6E2C][U+89F8][U+767C][U+5931][U+6557]: {e}")
            self.write_register('LAST_OPERATION_STATUS', 0)
            self.write_register('PROCESSING_PROGRESS', 0)
            self.error_count += 1
    
    def _handle_reset_trigger(self):
        """[U+8655][U+7406][U+91CD][U+7F6E][U+89F8][U+767C] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        try:
            print("[U+1F504] [U+5916][U+90E8][U+89F8][U+767C]: [U+7CFB][U+7D71][U+91CD][U+7F6E]")
            
            # [U+91CD][U+7F6E][U+8A08][U+6578][U+5668]
            self.operation_count = 0
            self.error_count = 0
            
            # [U+6E05][U+7A7A][U+6AA2][U+6E2C][U+7D50][U+679C]
            self.write_register('CIRCLE_COUNT', 0)
            for i in range(1, 6):
                self.write_register(f'CIRCLE_{i}_X', 0)
                self.write_register(f'CIRCLE_{i}_Y', 0)
                self.write_register(f'CIRCLE_{i}_RADIUS', 0)
            
            # [U+66F4][U+65B0][U+8A08][U+6578][U+5668]
            self.write_register('OPERATION_COUNT', 0)
            self.write_register('ERROR_COUNT', 0)
            
            print("[OK] [U+7CFB][U+7D71][U+91CD][U+7F6E][U+5B8C][U+6210]")
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+91CD][U+7F6E][U+89F8][U+767C][U+5931][U+6557]: {e}")
    
    def _handle_parameter_update(self):
        """[U+8655][U+7406][U+53C3][U+6578][U+66F4][U+65B0][U+89F8][U+767C] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        if not self.vision_controller:
            return
        
        try:
            print("[U+1F4CA] [U+5916][U+90E8][U+89F8][U+767C]: [U+53C3][U+6578][U+66F4][U+65B0]")
            
            # [U+8B80][U+53D6][U+65B0][U+53C3][U+6578]
            area_high = self.read_register('MIN_AREA_HIGH') or 0
            area_low = self.read_register('MIN_AREA_LOW') or 50000
            min_area = (area_high << 16) + area_low
            
            roundness_int = self.read_register('MIN_ROUNDNESS') or 800
            min_roundness = roundness_int / 1000.0
            
            gaussian_kernel = self.read_register('GAUSSIAN_KERNEL') or 9
            canny_low = self.read_register('CANNY_LOW') or 20
            canny_high = self.read_register('CANNY_HIGH') or 60
            
            # [U+66F4][U+65B0][U+8996][U+89BA][U+63A7][U+5236][U+5668][U+53C3][U+6578]
            self.vision_controller.update_detection_params(
                min_area=min_area,
                min_roundness=min_roundness,
                gaussian_kernel=gaussian_kernel,
                canny_low=canny_low,
                canny_high=canny_high
            )
            
            print(f"[OK] [U+53C3][U+6578][U+66F4][U+65B0][U+5B8C][U+6210]: [U+9762][U+7A4D]>={min_area}, [U+5713][U+5EA6]>={min_roundness}")
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+53C3][U+6578][U+66F4][U+65B0][U+5931][U+6557]: {e}")
    
    def _check_parameter_updates(self):
        """[U+6AA2][U+67E5][U+53C3][U+6578][U+66F4][U+65B0] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        try:
            param_trigger = self.read_register('PARAM_UPDATE_TRIGGER')
            if (param_trigger is not None and param_trigger > 0 and 
                param_trigger != self.last_trigger_states.get('param', 0)):
                
                self.last_trigger_states['param'] = param_trigger
                self._handle_parameter_update()
                # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                self.write_register('PARAM_UPDATE_TRIGGER', 0)
                
        except Exception as e:
            print(f"[FAIL] [U+6AA2][U+67E5][U+53C3][U+6578][U+66F4][U+65B0][U+5931][U+6557]: {e}")
    
    def _update_uptime(self):
        """[U+66F4][U+65B0][U+904B][U+884C][U+6642][U+9593] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        try:
            uptime_total_minutes = int((time.time() - self.start_time) / 60)
            uptime_hours = uptime_total_minutes // 60
            uptime_minutes = uptime_total_minutes % 60
            
            self.write_register('UPTIME_HOURS', uptime_hours)
            self.write_register('UPTIME_MINUTES', uptime_minutes)
        except:
            pass
    def start_monitoring(self):
        """[U+555F][U+52D5][U+57FA][U+790E][U+76E3][U+63A7] ([U+5DF2][U+68C4][U+7528][U+FF0C][U+6539][U+70BA][U+540C][U+6B65][U+7DDA][U+7A0B])"""
        print("[WARN][U+FE0F] start_monitoring[U+5DF2][U+68C4][U+7528][U+FF0C][U+8ACB][U+4F7F][U+7528]start_sync")
        return True
    
    def stop_monitoring(self):
        """[U+505C][U+6B62][U+57FA][U+790E][U+76E3][U+63A7] ([U+5DF2][U+68C4][U+7528][U+FF0C][U+6539][U+70BA][U+540C][U+6B65][U+7DDA][U+7A0B])"""
        print("[WARN][U+FE0F] stop_monitoring[U+5DF2][U+68C4][U+7528][U+FF0C][U+8ACB][U+4F7F][U+7528]stop_sync")
    
    def _monitor_loop(self):
        """[U+820A][U+76E3][U+63A7][U+5FAA][U+74B0] ([U+5DF2][U+68C4][U+7528])"""
        pass
    
    def _monitor_loop(self):
        """[U+820A][U+76E3][U+63A7][U+5FAA][U+74B0] ([U+5DF2][U+68C4][U+7528])"""
        pass
    
    def _update_uptime(self):
        """[U+66F4][U+65B0][U+904B][U+884C][U+6642][U+9593]"""
        try:
            uptime_total_minutes = int((time.time() - self.start_time) / 60)
            uptime_hours = uptime_total_minutes // 60
            uptime_minutes = uptime_total_minutes % 60
            
            self.write_register('UPTIME_HOURS', uptime_hours)
            self.write_register('UPTIME_MINUTES', uptime_minutes)
        except:
            pass
    
    def _check_external_control(self):
        """[U+6AA2][U+67E5][U+5916][U+90E8][U+63A7][U+5236][U+72C0][U+614B] ([U+5DF2][U+68C4][U+7528])"""
        pass
    
    def _check_triggers(self):
        """[U+6AA2][U+67E5][U+89F8][U+767C][U+4FE1][U+865F] ([U+5DF2][U+68C4][U+7528])"""
        pass
    
    def _check_parameter_updates(self):
        """[U+6AA2][U+67E5][U+53C3][U+6578][U+66F4][U+65B0]"""
        try:
            param_trigger = self.read_register('PARAM_UPDATE_TRIGGER')
            if (param_trigger is not None and param_trigger > 0 and 
                param_trigger != self.last_trigger_states.get('param', 0)):
                
                self.last_trigger_states['param'] = param_trigger
                self._handle_parameter_update()
                # [U+8655][U+7406][U+5B8C][U+6210][U+5F8C][U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F]
                self.write_register('PARAM_UPDATE_TRIGGER', 0)
                
        except Exception as e:
            print(f"[FAIL] [U+6AA2][U+67E5][U+53C3][U+6578][U+66F4][U+65B0][U+5931][U+6557]: {e}")
    
    def _handle_detect_trigger(self):
        """[U+8655][U+7406][U+6AA2][U+6E2C][U+89F8][U+767C] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        if not self.vision_controller:
            print("[FAIL] [U+6AA2][U+6E2C][U+89F8][U+767C][U+5931][U+6557]: vision_controller [U+4E0D][U+5B58][U+5728]")
            self.error_count += 1
            return
        
        try:
            print("[U+1F50D] [U+5916][U+90E8][U+89F8][U+767C]: [U+958B][U+59CB][U+57F7][U+884C][U+62CD][U+7167]+[U+6AA2][U+6E2C]")
            self.write_register('PROCESSING_PROGRESS', 20)
            
            # [U+6AA2][U+67E5][U+76F8][U+6A5F][U+9023][U+63A5][U+72C0][U+614B]
            if not self.vision_controller.is_connected:
                print("[FAIL] [U+6AA2][U+6E2C][U+89F8][U+767C][U+5931][U+6557]: [U+76F8][U+6A5F][U+672A][U+9023][U+63A5]")
                self.write_register('LAST_OPERATION_STATUS', 0)
                self.write_register('PROCESSING_PROGRESS', 0)
                self.error_count += 1
                return
            
            print("[U+1F4F8] [U+6B63][U+5728][U+57F7][U+884C][U+62CD][U+7167]+[U+6AA2][U+6E2C]...")
            result = self.vision_controller.capture_and_detect()
            
            if result and result.success:
                # [U+66F4][U+65B0][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230]PLC
                print(f"[OK] [U+6AA2][U+6E2C][U+6210][U+529F][U+FF0C][U+627E][U+5230] {result.circle_count} [U+500B][U+5713][U+5F62]")
                self.update_detection_results(result)
                self.write_register('LAST_OPERATION_STATUS', 1)
                self.write_register('PROCESSING_PROGRESS', 100)
            else:
                error_msg = result.error_message if result else "[U+6AA2][U+6E2C][U+7D50][U+679C][U+70BA][U+7A7A]"
                print(f"[FAIL] [U+6AA2][U+6E2C][U+5931][U+6557]: {error_msg}")
                self.write_register('LAST_OPERATION_STATUS', 0)
                self.write_register('PROCESSING_PROGRESS', 0)
                self.error_count += 1
            
            self.operation_count += 1
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+6AA2][U+6E2C][U+89F8][U+767C][U+7570][U+5E38]: {e}")
            print(f"[FAIL] [U+7570][U+5E38][U+985E][U+578B]: {type(e).__name__}")
            import traceback
            print(f"[FAIL] [U+8A73][U+7D30][U+5806][U+758A]: {traceback.format_exc()}")
            
            self.write_register('LAST_OPERATION_STATUS', 0)
            self.write_register('PROCESSING_PROGRESS', 0)
            self.error_count += 1
            self.write_register('ERROR_COUNT', self.error_count)
    
    def _handle_capture_trigger(self):
        """[U+8655][U+7406][U+62CD][U+7167][U+89F8][U+767C] ([U+5728][U+540C][U+6B65][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C])"""
        if not self.vision_controller:
            print("[FAIL] [U+62CD][U+7167][U+89F8][U+767C][U+5931][U+6557]: vision_controller [U+4E0D][U+5B58][U+5728]")
            self.error_count += 1
            return
        
        try:
            print("[U+1F4F8] [U+5916][U+90E8][U+89F8][U+767C]: [U+958B][U+59CB][U+57F7][U+884C][U+62CD][U+7167]")
            self.write_register('PROCESSING_PROGRESS', 50)
            
            # [U+6AA2][U+67E5][U+76F8][U+6A5F][U+9023][U+63A5][U+72C0][U+614B]
            if not self.vision_controller.is_connected:
                print("[FAIL] [U+62CD][U+7167][U+89F8][U+767C][U+5931][U+6557]: [U+76F8][U+6A5F][U+672A][U+9023][U+63A5]")
                self.write_register('LAST_OPERATION_STATUS', 0)
                self.write_register('PROCESSING_PROGRESS', 0)
                self.error_count += 1
                return
            
            print("[U+1F4F8] [U+6B63][U+5728][U+57F7][U+884C][U+62CD][U+7167]...")
            image, capture_time = self.vision_controller.capture_image()
            
            if image is not None:
                self.write_register('LAST_OPERATION_STATUS', 1)
                self.write_register('LAST_CAPTURE_TIME', int(capture_time * 1000))
                self.write_register('PROCESSING_PROGRESS', 100)
                print(f"[OK] [U+62CD][U+7167][U+6210][U+529F][U+FF0C][U+8017][U+6642]: {capture_time*1000:.2f}ms")
            else:
                self.write_register('LAST_OPERATION_STATUS', 0)
                self.write_register('PROCESSING_PROGRESS', 0)
                self.error_count += 1
                print("[FAIL] [U+62CD][U+7167][U+5931][U+6557]: [U+8FD4][U+56DE][U+5716][U+50CF][U+70BA][U+7A7A]")
            
            self.operation_count += 1
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+62CD][U+7167][U+89F8][U+767C][U+7570][U+5E38]: {e}")
            print(f"[FAIL] [U+7570][U+5E38][U+985E][U+578B]: {type(e).__name__}")
            import traceback
            print(f"[FAIL] [U+8A73][U+7D30][U+5806][U+758A]: {traceback.format_exc()}")
            
            self.write_register('LAST_OPERATION_STATUS', 0)
            self.write_register('PROCESSING_PROGRESS', 0)
            self.error_count += 1
            self.write_register('ERROR_COUNT', self.error_count)
    
    def _handle_reset_trigger(self):
        """[U+8655][U+7406][U+91CD][U+7F6E][U+89F8][U+767C]"""
        try:
            print("[U+1F504] [U+5916][U+90E8][U+89F8][U+767C]: [U+7CFB][U+7D71][U+91CD][U+7F6E]")
            
            # [U+91CD][U+7F6E][U+8A08][U+6578][U+5668]
            self.operation_count = 0
            self.error_count = 0
            
            # [U+6E05][U+7A7A][U+6AA2][U+6E2C][U+7D50][U+679C]
            self.write_register('CIRCLE_COUNT', 0)
            for i in range(1, 6):
                self.write_register(f'CIRCLE_{i}_X', 0)
                self.write_register(f'CIRCLE_{i}_Y', 0)
                self.write_register(f'CIRCLE_{i}_RADIUS', 0)
            
            # [U+66F4][U+65B0][U+8A08][U+6578][U+5668]
            self.write_register('OPERATION_COUNT', 0)
            self.write_register('ERROR_COUNT', 0)
            
            print("[OK] [U+7CFB][U+7D71][U+91CD][U+7F6E][U+5B8C][U+6210]")
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+91CD][U+7F6E][U+89F8][U+767C][U+5931][U+6557]: {e}")
    
    def _handle_parameter_update(self):
        """[U+8655][U+7406][U+53C3][U+6578][U+66F4][U+65B0][U+89F8][U+767C]"""
        if not self.vision_controller:
            return
        
        try:
            print("[U+1F4CA] [U+5916][U+90E8][U+89F8][U+767C]: [U+53C3][U+6578][U+66F4][U+65B0]")
            
            # [U+8B80][U+53D6][U+65B0][U+53C3][U+6578]
            area_high = self.read_register('MIN_AREA_HIGH') or 0
            area_low = self.read_register('MIN_AREA_LOW') or 50000
            min_area = (area_high << 16) + area_low
            
            roundness_int = self.read_register('MIN_ROUNDNESS') or 800
            min_roundness = roundness_int / 1000.0
            
            gaussian_kernel = self.read_register('GAUSSIAN_KERNEL') or 9
            canny_low = self.read_register('CANNY_LOW') or 20
            canny_high = self.read_register('CANNY_HIGH') or 60
            
            # [U+66F4][U+65B0][U+8996][U+89BA][U+63A7][U+5236][U+5668][U+53C3][U+6578]
            self.vision_controller.update_detection_params(
                min_area=min_area,
                min_roundness=min_roundness,
                gaussian_kernel=gaussian_kernel,
                canny_low=canny_low,
                canny_high=canny_high
            )
            
            print(f"[OK] [U+53C3][U+6578][U+66F4][U+65B0][U+5B8C][U+6210]: [U+9762][U+7A4D]>={min_area}, [U+5713][U+5EA6]>={min_roundness}")
            
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+53C3][U+6578][U+66F4][U+65B0][U+5931][U+6557]: {e}")
    
    def _update_system_status(self):
        """[U+66F4][U+65B0][U+7CFB][U+7D71][U+72C0][U+614B][U+5230]PLC ([U+5DF2][U+68C4][U+7528])"""
        pass
    
    def read_register(self, register_name: str) -> Optional[int]:
        """[U+8B80][U+53D6][U+5BC4][U+5B58][U+5668] (pymodbus 3.x [U+8A9E][U+6CD5][U+4FEE][U+6B63])"""
        if not self.connected or not self.client or register_name not in self.REGISTERS:
            return None
        
        try:
            address = self.REGISTERS[register_name]
            # pymodbus 3.x: [U+4F7F][U+7528][U+95DC][U+9375][U+5B57][U+53C3][U+6578]
            result = self.client.read_holding_registers(address, count=1, slave=1)
            
            if not result.isError():
                return result.registers[0]
            else:
                print(f"[FAIL] [U+8B80][U+53D6][U+5BC4][U+5B58][U+5668][U+5931][U+6557] {register_name}: {result}")
                return None
                
        except Exception as e:
            print(f"[FAIL] [U+8B80][U+53D6][U+5BC4][U+5B58][U+5668][U+7570][U+5E38] {register_name}: {e}")
            return None
    
    def write_register(self, register_name: str, value: int) -> bool:
        """[U+5BEB][U+5165][U+5BC4][U+5B58][U+5668] (pymodbus 3.x [U+8A9E][U+6CD5][U+4FEE][U+6B63])"""
        if not self.connected or not self.client or register_name not in self.REGISTERS:
            return False
        
        try:
            address = self.REGISTERS[register_name]
            # pymodbus 3.x: [U+4F7F][U+7528][U+95DC][U+9375][U+5B57][U+53C3][U+6578]
            result = self.client.write_register(address, value, slave=1)
            
            if not result.isError():
                return True
            else:
                print(f"[FAIL] [U+5BEB][U+5165][U+5BC4][U+5B58][U+5668][U+5931][U+6557] {register_name}: {result}")
                return False
                
        except Exception as e:
            print(f"[FAIL] [U+5BEB][U+5165][U+5BC4][U+5B58][U+5668][U+7570][U+5E38] {register_name}: {e}")
            return False
    
    def read_multiple_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        """[U+8B80][U+53D6][U+591A][U+500B][U+9023][U+7E8C][U+5BC4][U+5B58][U+5668] (pymodbus 3.x [U+8A9E][U+6CD5][U+4FEE][U+6B63])"""
        if not self.connected or not self.client:
            return None
        
        try:
            # pymodbus 3.x: [U+4F7F][U+7528][U+95DC][U+9375][U+5B57][U+53C3][U+6578]
            result = self.client.read_holding_registers(start_address, count=count, slave=1)
            
            if not result.isError():
                return result.registers
            else:
                print(f"[FAIL] [U+8B80][U+53D6][U+591A][U+500B][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {result}")
                return None
                
        except Exception as e:
            print(f"[FAIL] [U+8B80][U+53D6][U+591A][U+500B][U+5BC4][U+5B58][U+5668][U+7570][U+5E38]: {e}")
            return None
    
    def write_multiple_registers(self, start_address: int, values: List[int]) -> bool:
        """[U+5BEB][U+5165][U+591A][U+500B][U+9023][U+7E8C][U+5BC4][U+5B58][U+5668] (pymodbus 3.x [U+8A9E][U+6CD5][U+4FEE][U+6B63])"""
        if not self.connected or not self.client:
            return False
        
        try:
            # pymodbus 3.x: [U+4F7F][U+7528][U+95DC][U+9375][U+5B57][U+53C3][U+6578]
            result = self.client.write_registers(start_address, values, slave=1)
            
            if not result.isError():
                return True
            else:
                print(f"[FAIL] [U+5BEB][U+5165][U+591A][U+500B][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {result}")
                return False
                
        except Exception as e:
            print(f"[FAIL] [U+5BEB][U+5165][U+591A][U+500B][U+5BC4][U+5B58][U+5668][U+7570][U+5E38]: {e}")
            return False
    
    def update_detection_results(self, result: VisionResult):
        """[U+66F4][U+65B0][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230]PLC"""
        try:
            # [U+5BEB][U+5165][U+5713][U+5F62][U+6578][U+91CF]
            self.write_register('CIRCLE_COUNT', result.circle_count)
            
            # [U+5BEB][U+5165][U+5713][U+5F62][U+5EA7][U+6A19][U+548C][U+534A][U+5F91] ([U+6700][U+591A]5[U+500B])
            for i in range(5):
                if i < len(result.circles):
                    circle = result.circles[i]
                    self.write_register(f'CIRCLE_{i+1}_X', int(circle['center'][0]))
                    self.write_register(f'CIRCLE_{i+1}_Y', int(circle['center'][1]))
                    self.write_register(f'CIRCLE_{i+1}_RADIUS', int(circle['radius']))
                else:
                    # [U+6E05][U+7A7A][U+672A][U+4F7F][U+7528][U+7684][U+5BC4][U+5B58][U+5668]
                    self.write_register(f'CIRCLE_{i+1}_X', 0)
                    self.write_register(f'CIRCLE_{i+1}_Y', 0)
                    self.write_register(f'CIRCLE_{i+1}_RADIUS', 0)
            
            # [U+5BEB][U+5165][U+6642][U+9593][U+7D71][U+8A08]
            self.write_register('LAST_CAPTURE_TIME', int(result.capture_time * 1000))
            self.write_register('LAST_PROCESS_TIME', int(result.processing_time * 1000))
            self.write_register('LAST_TOTAL_TIME', int(result.total_time * 1000))
            
        except Exception as e:
            print(f"[FAIL] [U+66F4][U+65B0][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230]PLC[U+5931][U+6557]: {e}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+9023][U+63A5][U+72C0][U+614B]"""
        return {
            'connected': self.connected,
            'server_ip': self.server_ip,
            'server_port': self.server_port,
            'external_control_enabled': self.external_control_enabled,
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'connection_count': self.connection_count,
            'uptime_seconds': int(time.time() - self.start_time)
        }


class MockModbusTcpClientService:
    """Modbus TCP Client[U+7684][U+6A21][U+64EC][U+5BE6][U+73FE] ([U+7576]pymodbus[U+4E0D][U+53EF][U+7528][U+6642][U+4F7F][U+7528])"""
    
    def __init__(self, server_ip="192.168.1.100", server_port=502):
        self.server_ip = server_ip
        self.server_port = server_port
        self.connected = False
        self.running = False
        self.vision_controller = None
        
        # [U+6A21][U+64EC][U+5BC4][U+5B58][U+5668][U+5B58][U+5132]
        self.registers = {}
        
        # [U+540C][U+6B65][U+63A7][U+5236] ([U+8207][U+771F][U+5BE6][U+7248][U+672C][U+76F8][U+540C])
        self.sync_enabled = False
        self.sync_thread = None
        self.sync_running = False
        self.sync_interval = 0.1
        self.status_sync_counter = 0
        self.status_sync_interval = 10
    
    def get_debug_info(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+8ABF][U+8A66][U+4FE1][U+606F] ([U+6A21][U+64EC][U+7248][U+672C])"""
        return {
            'connected': self.connected,
            'external_control_enabled': self.external_control_enabled,
            'sync_running': self.sync_running,
            'sync_thread_alive': self.sync_thread.is_alive() if self.sync_thread else False,
            'last_trigger_states': {},
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'server_address': f"{self.server_ip}:{self.server_port}",
            'mock_mode': True
        }
        
        # [U+5BC4][U+5B58][U+5668][U+6620][U+5C04] ([U+8207][U+771F][U+5BE6][U+7248][U+672C][U+76F8][U+540C])
        self.REGISTERS = {
            'EXTERNAL_CONTROL_ENABLE': 200,
            'CAPTURE_TRIGGER': 201,
            'DETECT_TRIGGER': 202,
            'SYSTEM_RESET': 203,
            'PARAM_UPDATE_TRIGGER': 204,
            'MIN_AREA_HIGH': 210,
            'MIN_AREA_LOW': 211,
            'MIN_ROUNDNESS': 212,
            'GAUSSIAN_KERNEL': 213,
            'CANNY_LOW': 214,
            'CANNY_HIGH': 215,
            'SYSTEM_STATUS': 220,
            'CAMERA_CONNECTED': 221,
            'LAST_OPERATION_STATUS': 222,
            'PROCESSING_PROGRESS': 223,
            'CIRCLE_COUNT': 240,
            'CIRCLE_1_X': 241,
            'CIRCLE_1_Y': 242,
            'CIRCLE_1_RADIUS': 243,
            'CIRCLE_2_X': 244,
            'CIRCLE_2_Y': 245,
            'CIRCLE_2_RADIUS': 246,
            'CIRCLE_3_X': 247,
            'CIRCLE_3_Y': 248,
            'CIRCLE_3_RADIUS': 249,
            'CIRCLE_4_X': 250,
            'CIRCLE_4_Y': 251,
            'CIRCLE_4_RADIUS': 252,
            'CIRCLE_5_X': 253,
            'CIRCLE_5_Y': 254,
            'CIRCLE_5_RADIUS': 255,
            'LAST_CAPTURE_TIME': 280,
            'LAST_PROCESS_TIME': 281,
            'LAST_TOTAL_TIME': 282,
            'OPERATION_COUNT': 283,
            'ERROR_COUNT': 284,
            'CONNECTION_COUNT': 285,
            'VERSION_MAJOR': 290,
            'VERSION_MINOR': 291,
            'UPTIME_HOURS': 292,
            'UPTIME_MINUTES': 293,
        }
        
        # [U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668]
        for name, address in self.REGISTERS.items():
            self.registers[address] = 0
        
        # [U+72C0][U+614B][U+8FFD][U+8E64]
        self.operation_count = 0
        self.error_count = 0
        self.connection_count = 0
        self.start_time = time.time()
        self.external_control_enabled = False
    
    def set_vision_controller(self, controller):
        self.vision_controller = controller
    
    def set_server_address(self, ip: str, port: int = 502):
        self.server_ip = ip
        self.server_port = port
        print(f"[WARN][U+FE0F] [U+6A21][U+64EC][U+6A21][U+5F0F]: Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740][U+8A2D][U+7F6E][U+70BA]: {ip}:{port}")
    
    def connect(self) -> bool:
        print(f"[WARN][U+FE0F] [U+6A21][U+64EC][U+9023][U+63A5][U+5230]Modbus TCP[U+670D][U+52D9][U+5668]: {self.server_ip}:{self.server_port}")
        self.connected = True
        self.connection_count += 1
        
        # [U+8A2D][U+7F6E][U+521D][U+59CB][U+503C]
        self.write_register('VERSION_MAJOR', 2)
        self.write_register('VERSION_MINOR', 1)
        self.write_register('MIN_AREA_LOW', 50000)
        self.write_register('MIN_ROUNDNESS', 800)
        
        return True
    
    def disconnect(self):
        print("[WARN][U+FE0F] [U+6A21][U+64EC]Modbus TCP Client[U+5DF2][U+65B7][U+958B][U+9023][U+63A5]")
        self.stop_sync()
        self.connected = False
    
    def enable_external_control(self, enable: bool):
        """[U+555F][U+7528]/[U+7981][U+7528][U+5916][U+90E8][U+63A7][U+5236] ([U+6A21][U+64EC][U+7248][U+672C])"""
        self.external_control_enabled = enable
        
        if enable and self.connected:
            self.start_sync()
            print("[WARN][U+FE0F] [U+6A21][U+64EC][U+5916][U+90E8][U+63A7][U+5236][U+5DF2][U+555F][U+7528][U+FF0C][U+958B][U+59CB][U+6A21][U+64EC][U+540C][U+6B65]")
        else:
            self.stop_sync()
            print("[WARN][U+FE0F] [U+6A21][U+64EC][U+5916][U+90E8][U+63A7][U+5236][U+5DF2][U+7981][U+7528][U+FF0C][U+505C][U+6B62][U+6A21][U+64EC][U+540C][U+6B65]")
    
    def start_sync(self):
        """[U+555F][U+52D5][U+6A21][U+64EC][U+540C][U+6B65][U+7DDA][U+7A0B]"""
        if self.sync_running:
            return
        
        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._mock_sync_loop, daemon=True)
        self.sync_thread.start()
        print("[WARN][U+FE0F] [U+6A21][U+64EC][U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+555F][U+52D5]")
    
    def stop_sync(self):
        """[U+505C][U+6B62][U+6A21][U+64EC][U+540C][U+6B65][U+7DDA][U+7A0B]"""
        if self.sync_running:
            self.sync_running = False
            if self.sync_thread and self.sync_thread.is_alive():
                self.sync_thread.join(timeout=1.0)
            print("[WARN][U+FE0F] [U+6A21][U+64EC][U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+505C][U+6B62]")
    
    def _mock_sync_loop(self):
        """[U+6A21][U+64EC][U+540C][U+6B65][U+5FAA][U+74B0]"""
        print("[WARN][U+FE0F] [U+6A21][U+64EC][U+540C][U+6B65][U+7DDA][U+7A0B][U+958B][U+59CB][U+904B][U+884C]...")
        
        while self.sync_running and self.connected:
            try:
                # [U+6A21][U+64EC][U+57FA][U+672C][U+7684][U+72C0][U+614B][U+66F4][U+65B0]
                if self.vision_controller and self.vision_controller.is_connected:
                    self.write_register('SYSTEM_STATUS', 1)
                    self.write_register('CAMERA_CONNECTED', 1)
                else:
                    self.write_register('SYSTEM_STATUS', 0)
                    self.write_register('CAMERA_CONNECTED', 0)
                
                # [U+66F4][U+65B0][U+8A08][U+6578][U+5668]
                self.write_register('OPERATION_COUNT', self.operation_count)
                self.write_register('ERROR_COUNT', self.error_count)
                
                time.sleep(self.sync_interval)
                
            except Exception as e:
                print(f"[WARN][U+FE0F] [U+6A21][U+64EC][U+540C][U+6B65][U+932F][U+8AA4]: {e}")
                time.sleep(1.0)
        
        print("[WARN][U+FE0F] [U+6A21][U+64EC][U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+9000][U+51FA]")
    
    def start_monitoring(self):
        print("[WARN][U+FE0F] [U+6A21][U+64EC]start_monitoring[U+FF0C][U+8ACB][U+4F7F][U+7528]start_sync")
        return True
    
    def stop_monitoring(self):
        print("[WARN][U+FE0F] [U+6A21][U+64EC]stop_monitoring[U+FF0C][U+8ACB][U+4F7F][U+7528]stop_sync")
    
    def read_register(self, register_name: str) -> Optional[int]:
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            return self.registers.get(address, 0)
        return None
    
    def write_register(self, register_name: str, value: int) -> bool:
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            self.registers[address] = value
            return True
        return False
    
    def read_multiple_registers(self, start_address: int, count: int) -> Optional[List[int]]:
        return [self.registers.get(start_address + i, 0) for i in range(count)]
    
    def write_multiple_registers(self, start_address: int, values: List[int]) -> bool:
        for i, value in enumerate(values):
            self.registers[start_address + i] = value
        return True
    
    def update_detection_results(self, result: VisionResult):
        self.write_register('CIRCLE_COUNT', result.circle_count)
        
        for i in range(5):
            if i < len(result.circles):
                circle = result.circles[i]
                self.write_register(f'CIRCLE_{i+1}_X', int(circle['center'][0]))
                self.write_register(f'CIRCLE_{i+1}_Y', int(circle['center'][1]))
                self.write_register(f'CIRCLE_{i+1}_RADIUS', int(circle['radius']))
            else:
                self.write_register(f'CIRCLE_{i+1}_X', 0)
                self.write_register(f'CIRCLE_{i+1}_Y', 0)
                self.write_register(f'CIRCLE_{i+1}_RADIUS', 0)
        
        self.write_register('LAST_CAPTURE_TIME', int(result.capture_time * 1000))
        self.write_register('LAST_PROCESS_TIME', int(result.processing_time * 1000))
        self.write_register('LAST_TOTAL_TIME', int(result.total_time * 1000))
    
    def get_connection_status(self) -> Dict[str, Any]:
        return {
            'connected': self.connected,
            'server_ip': self.server_ip,
            'server_port': self.server_port,
            'external_control_enabled': self.external_control_enabled,
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'connection_count': self.connection_count,
            'uptime_seconds': int(time.time() - self.start_time),
            'mock_mode': True
        }


class CircleDetector:
    """[U+5713][U+5F62][U+6AA2][U+6E2C][U+5668]"""
    
    def __init__(self, params: DetectionParams = None):
        self.params = params or DetectionParams()
    
    def update_params(self, params: DetectionParams):
        """[U+66F4][U+65B0][U+6AA2][U+6E2C][U+53C3][U+6578]"""
        self.params = params
    
    def is_circle(self, contour, tolerance=0.2):
        """[U+5224][U+65B7][U+8F2A][U+5ED3][U+662F][U+5426][U+70BA][U+5713][U+5F62]"""
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            return False
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        return 1 - tolerance < circularity < 1 + tolerance
    
    def detect_circles(self, image: np.ndarray) -> Tuple[List[Dict], np.ndarray]:
        """[U+6AA2][U+6E2C][U+5713][U+5F62][U+4E26][U+8FD4][U+56DE][U+7D50][U+679C][U+548C][U+6A19][U+8A3B][U+5716][U+50CF]"""
        if image is None:
            return [], None
        
        try:
            # [U+78BA][U+4FDD][U+662F][U+7070][U+5EA6][U+5716][U+50CF]
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # [U+5275][U+5EFA][U+5F69][U+8272][U+8F38][U+51FA][U+5716][U+50CF]
            if len(image.shape) == 3:
                result_image = image.copy()
            else:
                result_image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            
            # [U+4F7F][U+7528][U+53C3][U+6578][U+9032][U+884C][U+8655][U+7406]
            kernel_size = (self.params.gaussian_kernel_size, self.params.gaussian_kernel_size)
            blurred = cv2.GaussianBlur(gray, kernel_size, self.params.gaussian_sigma)
            
            # Canny [U+908A][U+7DE3][U+6AA2][U+6E2C]
            edges = cv2.Canny(blurred, self.params.canny_low, self.params.canny_high)
            
            # [U+8F2A][U+5ED3][U+6AA2][U+6E2C]
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            circles = []
            circle_id = 1
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # [U+4F7F][U+7528][U+8A2D][U+5B9A][U+7684][U+53C3][U+6578][U+9032][U+884C][U+7BE9][U+9078]
                if area < self.params.min_area:
                    continue
                
                # [U+8A08][U+7B97][U+5713][U+5EA6]
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                    
                roundness = (4 * np.pi * area) / (perimeter ** 2)
                
                # [U+6AA2][U+67E5][U+5713][U+5EA6][U+689D][U+4EF6]
                if roundness < self.params.min_roundness:
                    continue
                
                if self.is_circle(contour):
                    # [U+8A08][U+7B97][U+5713][U+5FC3][U+548C][U+534A][U+5F91]
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
                    
                    # [U+5728][U+5716][U+50CF][U+4E0A][U+7E6A][U+88FD][U+5713][U+5F62][U+548C][U+7DE8][U+865F]
                    cv2.circle(result_image, center, radius, (0, 255, 0), 3)  # [U+7DA0][U+8272][U+5713][U+5708]
                    cv2.circle(result_image, center, 5, (0, 0, 255), -1)      # [U+7D05][U+8272][U+5713][U+5FC3]
                    
                    # [U+7E6A][U+88FD][U+7DE8][U+865F]
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 2.0
                    thickness = 3
                    text = str(circle_id)
                    
                    # [U+8A08][U+7B97][U+6587][U+5B57][U+5927][U+5C0F][U+548C][U+4F4D][U+7F6E]
                    (text_width, text_height), _ = cv2.getTextSize(text, font, font_scale, thickness)
                    text_x = center[0] - text_width // 2
                    text_y = center[1] - radius - 10
                    
                    # [U+78BA][U+4FDD][U+6587][U+5B57][U+4E0D][U+6703][U+8D85][U+51FA][U+5716][U+50CF][U+908A][U+754C]
                    text_x = max(10, min(text_x, result_image.shape[1] - text_width - 10))
                    text_y = max(text_height + 10, min(text_y, result_image.shape[0] - 10))
                    
                    # [U+7E6A][U+88FD][U+6587][U+5B57][U+80CC][U+666F]
                    cv2.rectangle(result_image, 
                                (text_x - 5, text_y - text_height - 5),
                                (text_x + text_width + 5, text_y + 5),
                                (255, 255, 255), -1)
                    
                    # [U+7E6A][U+88FD][U+6587][U+5B57]
                    cv2.putText(result_image, text, (text_x, text_y), 
                              font, font_scale, (0, 0, 0), thickness)
                    
                    circle_id += 1
            
            return circles, result_image
            
        except Exception as e:
            print(f"[U+5713][U+5F62][U+6AA2][U+6E2C][U+5931][U+6557]: {e}")
            return [], image


class CCD1VisionController:
    """CCD1 [U+8996][U+89BA][U+63A7][U+5236][U+5668] (Modbus TCP Client[U+7248][U+672C])"""
    
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
        
        # [U+8A2D][U+7F6E][U+65E5][U+8A8C]
        self.logger = logging.getLogger("CCD1Vision")
        self.logger.setLevel(logging.INFO)
        
        # [U+9078][U+64C7][U+5408][U+9069][U+7684]Modbus Client[U+670D][U+52D9]
        if MODBUS_AVAILABLE:
            self.modbus_client = ModbusTcpClientService()
            print("[OK] [U+4F7F][U+7528][U+5B8C][U+6574]Modbus TCP Client[U+670D][U+52D9]")
        else:
            self.modbus_client = MockModbusTcpClientService()
            print("[WARN][U+FE0F] [U+4F7F][U+7528][U+6A21][U+64EC]Modbus TCP Client[U+670D][U+52D9] ([U+529F][U+80FD][U+53D7][U+9650])")
            
        self.modbus_client.set_vision_controller(self)
        
        # [U+521D][U+59CB][U+5316][U+76F8][U+6A5F][U+914D][U+7F6E]
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
    
    def set_modbus_server(self, ip: str, port: int = 502) -> Dict[str, Any]:
        """[U+8A2D][U+7F6E]Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740]"""
        try:
            # [U+5982][U+679C][U+5DF2][U+9023][U+63A5][U+FF0C][U+5148][U+65B7][U+958B]
            if self.modbus_client.connected:
                self.modbus_client.stop_monitoring()
                self.modbus_client.disconnect()
            
            # [U+8A2D][U+7F6E][U+65B0][U+5730][U+5740]
            self.modbus_client.set_server_address(ip, port)
            
            return {
                'success': True,
                'message': f'Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740][U+5DF2][U+8A2D][U+7F6E]: {ip}:{port}',
                'server_ip': ip,
                'server_port': port
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'[U+8A2D][U+7F6E]Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740][U+5931][U+6557]: {str(e)}'
            }
    
    def connect_modbus(self) -> Dict[str, Any]:
        """[U+9023][U+63A5]Modbus TCP[U+670D][U+52D9][U+5668]"""
        try:
            if self.modbus_client.connect():
                # [U+9023][U+63A5][U+6210][U+529F][U+5F8C][U+FF0C][U+6AA2][U+67E5][U+5916][U+90E8][U+63A7][U+5236][U+72C0][U+614B][U+4E26][U+555F][U+52D5][U+540C][U+6B65]
                # [U+8B80][U+53D6][U+7576][U+524D][U+5916][U+90E8][U+63A7][U+5236][U+72C0][U+614B]
                current_control = self.modbus_client.read_register('EXTERNAL_CONTROL_ENABLE')
                if current_control == 1:
                    # [U+5982][U+679C]PLC[U+7AEF][U+5DF2][U+7D93][U+555F][U+7528][U+5916][U+90E8][U+63A7][U+5236][U+FF0C][U+5247][U+81EA][U+52D5][U+555F][U+52D5][U+540C][U+6B65]
                    self.modbus_client.enable_external_control(True)
                    print("[U+1F504] [U+6AA2][U+6E2C][U+5230]PLC[U+7AEF][U+5916][U+90E8][U+63A7][U+5236][U+5DF2][U+555F][U+7528][U+FF0C][U+81EA][U+52D5][U+555F][U+52D5][U+540C][U+6B65][U+7DDA][U+7A0B]")
                
                return {
                    'success': True,
                    'message': f'Modbus TCP[U+9023][U+63A5][U+6210][U+529F]: {self.modbus_client.server_ip}:{self.modbus_client.server_port}',
                    'connection_status': self.modbus_client.get_connection_status(),
                    'auto_sync_started': current_control == 1
                }
            else:
                return {
                    'success': False,
                    'message': f'[U+7121][U+6CD5][U+9023][U+63A5][U+5230]Modbus[U+670D][U+52D9][U+5668]: {self.modbus_client.server_ip}:{self.modbus_client.server_port}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Modbus[U+9023][U+63A5][U+7570][U+5E38]: {str(e)}'
            }
    
    def disconnect_modbus(self) -> Dict[str, Any]:
        """[U+65B7][U+958B]Modbus[U+9023][U+63A5]"""
        try:
            self.modbus_client.disconnect()  # [U+9019][U+6703][U+81EA][U+52D5][U+505C][U+6B62][U+540C][U+6B65][U+7DDA][U+7A0B]
            
            return {
                'success': True,
                'message': 'Modbus[U+9023][U+63A5][U+5DF2][U+65B7][U+958B][U+FF0C][U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+505C][U+6B62]'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'[U+65B7][U+958B]Modbus[U+9023][U+63A5][U+5931][U+6557]: {str(e)}'
            }
    
    def update_detection_params(self, min_area: float = None, min_roundness: float = None, 
                              gaussian_kernel: int = None, canny_low: int = None, canny_high: int = None):
        """[U+66F4][U+65B0][U+6AA2][U+6E2C][U+53C3][U+6578]"""
        if min_area is not None:
            self.detection_params.min_area = min_area
        if min_roundness is not None:
            self.detection_params.min_roundness = min_roundness
        if gaussian_kernel is not None:
            self.detection_params.gaussian_kernel_size = gaussian_kernel
        if canny_low is not None:
            self.detection_params.canny_low = canny_low
        if canny_high is not None:
            self.detection_params.canny_high = canny_high
            
        self.detector.update_params(self.detection_params)
        
        self.logger.info(f"[U+6AA2][U+6E2C][U+53C3][U+6578][U+5DF2][U+66F4][U+65B0]: [U+9762][U+7A4D]>={self.detection_params.min_area}, [U+5713][U+5EA6]>={self.detection_params.min_roundness}")
    
    def initialize_camera(self, ip_address: str = None) -> Dict[str, Any]:
        """[U+521D][U+59CB][U+5316][U+76F8][U+6A5F][U+9023][U+63A5]"""
        try:
            if ip_address:
                self.camera_ip = ip_address
                self.camera_config.ip = ip_address
            
            self.logger.info(f"[U+6B63][U+5728][U+521D][U+59CB][U+5316][U+76F8][U+6A5F] {self.camera_name} (IP: {self.camera_ip})")
            
            if self.camera_manager:
                self.camera_manager.shutdown()
            
            self.camera_manager = OptimizedCameraManager()
            
            success = self.camera_manager.add_camera(self.camera_name, self.camera_config)
            if not success:
                raise Exception("[U+6DFB][U+52A0][U+76F8][U+6A5F][U+5931][U+6557]")
            
            connect_result = self.camera_manager.connect_camera(self.camera_name)
            if not connect_result:
                raise Exception("[U+76F8][U+6A5F][U+9023][U+63A5][U+5931][U+6557]")
            
            stream_result = self.camera_manager.start_streaming([self.camera_name])
            if not stream_result.get(self.camera_name, False):
                raise Exception("[U+958B][U+59CB][U+4E32][U+6D41][U+5931][U+6557]")
            
            # [U+8A2D][U+7F6E][U+589E][U+76CA][U+70BA]200
            camera = self.camera_manager.cameras[self.camera_name]
            camera.camera.MV_CC_SetFloatValue("Gain", 200.0)
            
            self.is_connected = True
            self.logger.info(f"[U+76F8][U+6A5F] {self.camera_name} [U+521D][U+59CB][U+5316][U+6210][U+529F]")
            
            return {
                'success': True,
                'message': f'[U+76F8][U+6A5F] {self.camera_name} [U+9023][U+63A5][U+6210][U+529F]',
                'camera_ip': self.camera_ip,
                'gain_set': 200.0
            }
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"[U+76F8][U+6A5F][U+521D][U+59CB][U+5316][U+5931][U+6557]: {str(e)}"
            self.logger.error(error_msg)
            
            return {
                'success': False,
                'message': error_msg,
                'camera_ip': self.camera_ip
            }
    
    def capture_image(self) -> Tuple[Optional[np.ndarray], float]:
        """[U+6355][U+7372][U+5716][U+50CF]"""
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
            self.logger.error(f"[U+6355][U+7372][U+5716][U+50CF][U+5931][U+6557]: {e}")
            return None, 0.0
    
    def capture_and_detect(self) -> VisionResult:
        """[U+62CD][U+7167][U+4E26][U+9032][U+884C][U+5713][U+5F62][U+6AA2][U+6E2C]"""
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
                    error_message="[U+5716][U+50CF][U+6355][U+7372][U+5931][U+6557]"
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
            
            # [U+66F4][U+65B0]Modbus[U+7D50][U+679C] ([U+5982][U+679C][U+9023][U+63A5])
            if self.modbus_client.connected:
                self.modbus_client.update_detection_results(result)
            
            return result
            
        except Exception as e:
            error_msg = f"[U+6AA2][U+6E2C][U+5931][U+6557]: {str(e)}"
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
            
            if self.modbus_client.connected:
                self.modbus_client.update_detection_results(result)
                
            return result
    
    def get_image_base64(self) -> Optional[str]:
        """[U+7372][U+53D6][U+7576][U+524D][U+5716][U+50CF][U+7684]base64[U+7DE8][U+78BC]"""
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
            self.logger.error(f"[U+5716][U+50CF][U+7DE8][U+78BC][U+5931][U+6557]: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+7CFB][U+7D71][U+72C0][U+614B]"""
        status = {
            'connected': self.is_connected,
            'camera_name': self.camera_name,
            'camera_ip': self.camera_ip,
            'has_image': self.last_image is not None,
            'last_result': asdict(self.last_result) if self.last_result else None,
            'detection_params': asdict(self.detection_params),
            'modbus_enabled': MODBUS_AVAILABLE,
            'modbus_connection': self.modbus_client.get_connection_status()
        }
        
        if self.camera_manager and self.is_connected:
            try:
                stats = self.camera_manager.get_camera_statistics(self.camera_name)
                status['camera_stats'] = stats
            except:
                pass
        
        return status
    
    def disconnect(self):
        """[U+65B7][U+958B][U+6240][U+6709][U+9023][U+63A5]"""
        # [U+65B7][U+958B][U+76F8][U+6A5F][U+9023][U+63A5]
        if self.camera_manager:
            self.camera_manager.shutdown()
            self.camera_manager = None
        
        self.is_connected = False
        self.last_image = None
        
        # [U+65B7][U+958B]Modbus[U+9023][U+63A5]
        try:
            self.modbus_client.stop_monitoring()
            self.modbus_client.disconnect()
        except:
            pass
        
        self.logger.info("[U+6240][U+6709][U+9023][U+63A5][U+5DF2][U+65B7][U+958B]")


# Flask[U+61C9][U+7528][U+8A2D][U+7F6E]
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ccd_vision_control_client_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# [U+5275][U+5EFA][U+63A7][U+5236][U+5668][U+5BE6][U+4F8B]
vision_controller = CCD1VisionController()

# [U+8A2D][U+7F6E][U+65E5][U+8A8C]
logging.basicConfig(level=logging.INFO)


@app.route('/')
def index():
    """[U+4E3B][U+9801][U+9762]"""
    return render_template('ccd_vision_client.html')


@app.route('/api/status')
def get_status():
    """[U+7372][U+53D6][U+7CFB][U+7D71][U+72C0][U+614B]"""
    return jsonify(vision_controller.get_status())


@app.route('/api/modbus/set_server', methods=['POST'])
def set_modbus_server():
    """[U+8A2D][U+7F6E]Modbus[U+670D][U+52D9][U+5668][U+5730][U+5740]"""
    data = request.get_json()
    ip = data.get('ip', '192.168.1.100')
    port = data.get('port', 502)
    
    result = vision_controller.set_modbus_server(ip, port)
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify(result)


@app.route('/api/modbus/connect', methods=['POST'])
def connect_modbus():
    """[U+9023][U+63A5]Modbus TCP[U+670D][U+52D9][U+5668]"""
    result = vision_controller.connect_modbus()
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify(result)


@app.route('/api/modbus/disconnect', methods=['POST'])
def disconnect_modbus():
    """[U+65B7][U+958B]Modbus[U+9023][U+63A5]"""
    result = vision_controller.disconnect_modbus()
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify(result)


@app.route('/api/modbus/registers', methods=['GET'])
def get_modbus_registers():
    """[U+7372][U+53D6][U+6240][U+6709]Modbus[U+5BC4][U+5B58][U+5668][U+7684][U+5373][U+6642][U+6578][U+503C]"""
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': 'Modbus Client[U+672A][U+9023][U+63A5]',
            'registers': {}
        })
    
    try:
        registers = {}
        
        # [U+63A7][U+5236][U+5BC4][U+5B58][U+5668] (200-209) - [U+5F9E]PLC[U+8B80][U+53D6]
        control_registers = {
            '200_[U+5916][U+90E8][U+63A7][U+5236][U+555F][U+7528]': modbus_client.read_register('EXTERNAL_CONTROL_ENABLE'),
            '201_[U+62CD][U+7167][U+89F8][U+767C]': modbus_client.read_register('CAPTURE_TRIGGER'),
            '202_[U+62CD][U+7167][U+6AA2][U+6E2C][U+89F8][U+767C]': modbus_client.read_register('DETECT_TRIGGER'),
            '203_[U+7CFB][U+7D71][U+91CD][U+7F6E]': modbus_client.read_register('SYSTEM_RESET'),
            '204_[U+53C3][U+6578][U+66F4][U+65B0][U+89F8][U+767C]': modbus_client.read_register('PARAM_UPDATE_TRIGGER'),
        }
        
        # [U+53C3][U+6578][U+8A2D][U+5B9A][U+5BC4][U+5B58][U+5668] (210-219) - [U+5F9E]PLC[U+8B80][U+53D6]
        area_high = modbus_client.read_register('MIN_AREA_HIGH') or 0
        area_low = modbus_client.read_register('MIN_AREA_LOW') or 0
        combined_area = (area_high << 16) + area_low
        roundness_raw = modbus_client.read_register('MIN_ROUNDNESS') or 0
        roundness_value = roundness_raw / 1000.0
        
        param_registers = {
            '210_[U+6700][U+5C0F][U+9762][U+7A4D]_[U+9AD8]16[U+4F4D]': area_high,
            '211_[U+6700][U+5C0F][U+9762][U+7A4D]_[U+4F4E]16[U+4F4D]': area_low,
            '211_[U+5408][U+4F75][U+9762][U+7A4D][U+503C]': combined_area,
            '212_[U+6700][U+5C0F][U+5713][U+5EA6]_x1000': roundness_raw,
            '212_[U+5713][U+5EA6][U+5BE6][U+969B][U+503C]': round(roundness_value, 3),
            '213_[U+9AD8][U+65AF][U+6838][U+5927][U+5C0F]': modbus_client.read_register('GAUSSIAN_KERNEL'),
            '214_Canny[U+4F4E][U+95BE][U+503C]': modbus_client.read_register('CANNY_LOW'),
            '215_Canny[U+9AD8][U+95BE][U+503C]': modbus_client.read_register('CANNY_HIGH'),
        }
        
        # [U+72C0][U+614B][U+56DE][U+5831][U+5BC4][U+5B58][U+5668] (220-239) - [U+5BEB][U+5165][U+5230]PLC
        status_registers = {
            '220_[U+7CFB][U+7D71][U+72C0][U+614B]': modbus_client.read_register('SYSTEM_STATUS'),
            '221_[U+76F8][U+6A5F][U+9023][U+63A5][U+72C0][U+614B]': modbus_client.read_register('CAMERA_CONNECTED'),
            '222_[U+6700][U+5F8C][U+64CD][U+4F5C][U+72C0][U+614B]': modbus_client.read_register('LAST_OPERATION_STATUS'),
            '223_[U+8655][U+7406][U+9032][U+5EA6]': modbus_client.read_register('PROCESSING_PROGRESS'),
        }
        
        # [U+6AA2][U+6E2C][U+7D50][U+679C][U+5BC4][U+5B58][U+5668] (240-279) - [U+5BEB][U+5165][U+5230]PLC
        result_registers = {
            '240_[U+6AA2][U+6E2C][U+5713][U+5F62][U+6578][U+91CF]': modbus_client.read_register('CIRCLE_COUNT'),
        }
        
        # [U+5713][U+5F62][U+8A73][U+7D30][U+8CC7][U+6599]
        for i in range(1, 6):
            x_val = modbus_client.read_register(f'CIRCLE_{i}_X')
            y_val = modbus_client.read_register(f'CIRCLE_{i}_Y')
            r_val = modbus_client.read_register(f'CIRCLE_{i}_RADIUS')
            result_registers[f'{240+i*3-2}_[U+5713][U+5F62]{i}_X[U+5EA7][U+6A19]'] = x_val
            result_registers[f'{240+i*3-1}_[U+5713][U+5F62]{i}_Y[U+5EA7][U+6A19]'] = y_val
            result_registers[f'{240+i*3}_[U+5713][U+5F62]{i}_[U+534A][U+5F91]'] = r_val
        
        # [U+7D71][U+8A08][U+8CC7][U+8A0A][U+5BC4][U+5B58][U+5668] (280-299) - [U+5BEB][U+5165][U+5230]PLC
        stats_registers = {
            '280_[U+6700][U+5F8C][U+62CD][U+7167][U+8017][U+6642]ms': modbus_client.read_register('LAST_CAPTURE_TIME'),
            '281_[U+6700][U+5F8C][U+8655][U+7406][U+8017][U+6642]ms': modbus_client.read_register('LAST_PROCESS_TIME'),
            '282_[U+6700][U+5F8C][U+7E3D][U+8017][U+6642]ms': modbus_client.read_register('LAST_TOTAL_TIME'),
            '283_[U+64CD][U+4F5C][U+8A08][U+6578][U+5668]': modbus_client.read_register('OPERATION_COUNT'),
            '284_[U+932F][U+8AA4][U+8A08][U+6578][U+5668]': modbus_client.read_register('ERROR_COUNT'),
            '285_[U+9023][U+63A5][U+8A08][U+6578][U+5668]': modbus_client.read_register('CONNECTION_COUNT'),
            '290_[U+8EDF][U+9AD4][U+7248][U+672C][U+4E3B][U+865F]': modbus_client.read_register('VERSION_MAJOR'),
            '291_[U+8EDF][U+9AD4][U+7248][U+672C][U+6B21][U+865F]': modbus_client.read_register('VERSION_MINOR'),
            '292_[U+904B][U+884C][U+6642][U+9593][U+5C0F][U+6642]': modbus_client.read_register('UPTIME_HOURS'),
            '293_[U+904B][U+884C][U+6642][U+9593][U+5206][U+9418]': modbus_client.read_register('UPTIME_MINUTES'),
        }
        
        # [U+7D44][U+5408][U+6240][U+6709][U+5BC4][U+5B58][U+5668]
        registers.update(control_registers)
        registers.update(param_registers)
        registers.update(status_registers)
        registers.update(result_registers)
        registers.update(stats_registers)
        
        return jsonify({
            'success': True,
            'message': 'Modbus[U+5BC4][U+5B58][U+5668][U+8B80][U+53D6][U+6210][U+529F]',
            'registers': registers,
            'external_control_enabled': modbus_client.external_control_enabled,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_registers': len(registers),
            'server_info': f"{modbus_client.server_ip}:{modbus_client.server_port}"
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+8B80][U+53D6][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {str(e)}',
            'registers': {},
            'error': str(e)
        })


@app.route('/api/modbus/test', methods=['GET'])
def test_modbus():
    """[U+6E2C][U+8A66]Modbus Client[U+9023][U+63A5][U+72C0][U+614B]"""
    if not MODBUS_AVAILABLE:
        return jsonify({
            'success': False,
            'message': 'Modbus Client[U+6A21][U+7D44][U+4E0D][U+53EF][U+7528]',
            'available': False,
            'connected': False,
            'pymodbus_version': PYMODBUS_VERSION,
            'install_command': 'pip install pymodbus>=3.0.0'
        })
    
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': f'[U+672A][U+9023][U+63A5][U+5230]Modbus[U+670D][U+52D9][U+5668]: {modbus_client.server_ip}:{modbus_client.server_port}',
            'available': True,
            'connected': False,
            'pymodbus_version': PYMODBUS_VERSION,
            'suggestion': '[U+8ACB][U+5148][U+9023][U+63A5][U+5230]Modbus TCP[U+670D][U+52D9][U+5668]'
        })
    
    try:
        # [U+6AA2][U+67E5]pymodbus[U+7248][U+672C]
        import pymodbus
        actual_version = pymodbus.__version__
        
        # [U+6E2C][U+8A66][U+8B80][U+5BEB][U+64CD][U+4F5C]
        test_success = False
        error_message = ""
        
        # [U+6E2C][U+8A66][U+5BEB][U+5165][U+7248][U+672C][U+865F]
        write_success = modbus_client.write_register('VERSION_MAJOR', 99)
        if write_success:
            # [U+6E2C][U+8A66][U+8B80][U+53D6]
            read_value = modbus_client.read_register('VERSION_MAJOR')
            if read_value == 99:
                test_success = True
                # [U+6062][U+5FA9][U+6B63][U+78BA][U+503C]
                modbus_client.write_register('VERSION_MAJOR', 2)
            else:
                error_message = f"[U+8B80][U+53D6][U+503C][U+4E0D][U+5339][U+914D]: [U+671F][U+671B]99, [U+5BE6][U+969B]{read_value}"
        else:
            error_message = "[U+5BEB][U+5165][U+64CD][U+4F5C][U+5931][U+6557]"
        
        # [U+7372][U+53D6][U+9023][U+63A5][U+72C0][U+614B]
        connection_status = modbus_client.get_connection_status()
        
        return jsonify({
            'success': test_success,
            'message': f'[OK] Modbus Client[U+6B63][U+5E38] (pymodbus {actual_version})' if test_success else f'[FAIL] Modbus[U+6E2C][U+8A66][U+5931][U+6557]: {error_message}',
            'available': True,
            'connected': True,
            'pymodbus_version': actual_version,
            'expected_version': PYMODBUS_VERSION,
            'write_success': write_success,
            'test_passed': test_success,
            'error_message': error_message,
            'connection_status': connection_status,
            'register_count': len(modbus_client.REGISTERS)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Modbus[U+6E2C][U+8A66][U+7570][U+5E38]: {str(e)}',
            'available': True,
            'connected': modbus_client.connected,
            'pymodbus_version': PYMODBUS_VERSION,
            'error': str(e),
            'error_type': type(e).__name__
        })


@app.route('/api/initialize', methods=['POST'])
def initialize_camera():
    """[U+521D][U+59CB][U+5316][U+76F8][U+6A5F]"""
    data = request.get_json()
    ip_address = data.get('ip_address') if data else None
    
    result = vision_controller.initialize_camera(ip_address)
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify(result)


@app.route('/api/update_params', methods=['POST'])
def update_detection_params():
    """[U+66F4][U+65B0][U+6AA2][U+6E2C][U+53C3][U+6578]"""
    data = request.get_json()
    min_area = data.get('min_area')
    min_roundness = data.get('min_roundness')
    gaussian_kernel = data.get('gaussian_kernel')
    canny_low = data.get('canny_low')
    canny_high = data.get('canny_high')
    
    vision_controller.update_detection_params(
        min_area=min_area,
        min_roundness=min_roundness,
        gaussian_kernel=gaussian_kernel,
        canny_low=canny_low,
        canny_high=canny_high
    )
    
    return jsonify({
        'success': True,
        'message': '[U+53C3][U+6578][U+5DF2][U+66F4][U+65B0]',
        'params': asdict(vision_controller.detection_params)
    })


@app.route('/api/capture', methods=['POST'])
def capture_image():
    """[U+62CD][U+7167]"""
    image, capture_time = vision_controller.capture_image()
    
    if image is None:
        return jsonify({
            'success': False,
            'message': '[U+5716][U+50CF][U+6355][U+7372][U+5931][U+6557]',
            'capture_time_ms': 0
        })
    
    image_base64 = vision_controller.get_image_base64()
    capture_time_ms = capture_time * 1000
    
    result = {
        'success': True,
        'message': '[U+5716][U+50CF][U+6355][U+7372][U+6210][U+529F]',
        'capture_time_ms': round(capture_time_ms, 2),
        'image': image_base64,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    socketio.emit('image_update', result)
    return jsonify(result)


@app.route('/api/capture_and_detect', methods=['POST'])
def capture_and_detect():
    """[U+62CD][U+7167][U+4E26][U+6AA2][U+6E2C]"""
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


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """[U+65B7][U+958B][U+6240][U+6709][U+9023][U+63A5]"""
    vision_controller.disconnect()
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify({'success': True, 'message': '[U+6240][U+6709][U+9023][U+63A5][U+5DF2][U+65B7][U+958B]'})


@app.route('/api/modbus/toggle_external_control', methods=['POST'])
def toggle_external_control():
    """[U+5207][U+63DB][U+5916][U+90E8][U+63A7][U+5236][U+6A21][U+5F0F]"""
    data = request.get_json()
    enable = data.get('enable', False)
    
    modbus_client = vision_controller.modbus_client
    
    # [U+6AA2][U+67E5][U+670D][U+52D9][U+662F][U+5426][U+53EF][U+7528]
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': 'Modbus Client[U+672A][U+9023][U+63A5][U+5230][U+670D][U+52D9][U+5668]'
        })
    
    try:
        # [U+5BEB][U+5165][U+5916][U+90E8][U+63A7][U+5236][U+555F][U+7528][U+5BC4][U+5B58][U+5668][U+5230]PLC
        value = 1 if enable else 0
        success = modbus_client.write_register('EXTERNAL_CONTROL_ENABLE', value)
        
        if success:
            # [U+555F][U+7528]/[U+7981][U+7528][U+540C][U+6B65][U+7DDA][U+7A0B]
            modbus_client.enable_external_control(enable)
            
            # [U+9A57][U+8B49][U+5BEB][U+5165] ([U+5F9E]PLC[U+8B80][U+56DE][U+78BA][U+8A8D])
            read_back = modbus_client.read_register('EXTERNAL_CONTROL_ENABLE')
            
            # [U+8A18][U+9304][U+65E5][U+8A8C]
            action = '[U+555F][U+7528]' if enable else '[U+505C][U+7528]'
            sync_status = '[U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+555F][U+52D5]' if enable else '[U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+505C][U+6B62]'
            print(f"[U+1F504] WebUI[U+8A2D][U+5B9A][U+5916][U+90E8][U+63A7][U+5236]: {action}, {sync_status}")
            
            service_type = "Modbus TCP Client" if MODBUS_AVAILABLE else "[U+6A21][U+64EC]Client"
            
            return jsonify({
                'success': True,
                'external_control_enabled': enable,
                'message': f'[U+5916][U+90E8][U+63A7][U+5236][U+5DF2]{action} ({service_type}), {sync_status}',
                'register_value': value,
                'read_back_value': read_back,
                'verified': (read_back == value),
                'service_type': service_type,
                'sync_thread_status': '[U+904B][U+884C][U+4E2D]' if enable else '[U+5DF2][U+505C][U+6B62]'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Modbus[U+5BC4][U+5B58][U+5668][U+5BEB][U+5165][U+5931][U+6557]'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+64CD][U+4F5C][U+5931][U+6557]: {str(e)}'
        })


@app.route('/api/modbus/debug', methods=['GET'])
def get_modbus_debug():
    """[U+7372][U+53D6]Modbus[U+8ABF][U+8A66][U+4FE1][U+606F]"""
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client:
        return jsonify({
            'success': False,
            'message': 'Modbus Client[U+4E0D][U+5B58][U+5728]'
        })
    
    try:
        debug_info = modbus_client.get_debug_info()
        
        # [U+984D][U+5916][U+6AA2][U+67E5][U+7576][U+524D][U+5BC4][U+5B58][U+5668][U+72C0][U+614B]
        if modbus_client.connected:
            current_registers = {
                'EXTERNAL_CONTROL_ENABLE': modbus_client.read_register('EXTERNAL_CONTROL_ENABLE'),
                'CAPTURE_TRIGGER': modbus_client.read_register('CAPTURE_TRIGGER'),
                'DETECT_TRIGGER': modbus_client.read_register('DETECT_TRIGGER'),
                'SYSTEM_RESET': modbus_client.read_register('SYSTEM_RESET'),
                'CIRCLE_COUNT': modbus_client.read_register('CIRCLE_COUNT'),
                'SYSTEM_STATUS': modbus_client.read_register('SYSTEM_STATUS'),
                'CAMERA_CONNECTED': modbus_client.read_register('CAMERA_CONNECTED')
            }
            debug_info['current_registers'] = current_registers
        
        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+7372][U+53D6][U+8ABF][U+8A66][U+4FE1][U+606F][U+5931][U+6557]: {str(e)}',
            'error': str(e)
        })


@app.route('/api/modbus/reset_trigger_states', methods=['POST'])
def reset_trigger_states():
    """[U+91CD][U+7F6E][U+89F8][U+767C][U+72C0][U+614B][U+8A18][U+9304]"""
    modbus_client = vision_controller.modbus_client
    
    try:
        # [U+6E05][U+9664][U+89F8][U+767C][U+72C0][U+614B][U+8A18][U+9304]
        old_states = modbus_client.last_trigger_states.copy()
        modbus_client.last_trigger_states.clear()
        
        # [U+91CD][U+7F6E][U+932F][U+8AA4][U+8A08][U+6578][U+FF08][U+53EF][U+9078][U+FF09]
        reset_errors = request.get_json().get('reset_errors', False) if request.get_json() else False
        if reset_errors:
            modbus_client.error_count = 0
            modbus_client.write_register('ERROR_COUNT', 0)
        
        return jsonify({
            'success': True,
            'message': '[U+89F8][U+767C][U+72C0][U+614B][U+5DF2][U+91CD][U+7F6E]',
            'old_states': old_states,
            'error_count_reset': reset_errors,
            'current_error_count': modbus_client.error_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+91CD][U+7F6E][U+89F8][U+767C][U+72C0][U+614B][U+5931][U+6557]: {str(e)}'
        })


@app.route('/api/modbus/clear_triggers', methods=['POST'])
def clear_triggers():
    """[U+6E05][U+9664][U+6240][U+6709][U+89F8][U+767C][U+4FE1][U+865F]"""
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': 'Modbus[U+672A][U+9023][U+63A5]'
        })
    
    try:
        # [U+6E05][U+9664][U+6240][U+6709][U+89F8][U+767C][U+4FE1][U+865F]
        triggers_cleared = {}
        triggers_cleared['CAPTURE_TRIGGER'] = modbus_client.write_register('CAPTURE_TRIGGER', 0)
        triggers_cleared['DETECT_TRIGGER'] = modbus_client.write_register('DETECT_TRIGGER', 0)
        triggers_cleared['SYSTEM_RESET'] = modbus_client.write_register('SYSTEM_RESET', 0)
        triggers_cleared['PARAM_UPDATE_TRIGGER'] = modbus_client.write_register('PARAM_UPDATE_TRIGGER', 0)
        
        # [U+91CD][U+7F6E][U+8655][U+7406][U+9032][U+5EA6]
        modbus_client.write_register('PROCESSING_PROGRESS', 0)
        
        success_count = sum(triggers_cleared.values())
        
        return jsonify({
            'success': True,
            'message': f'[U+5DF2][U+6E05][U+9664] {success_count}/4 [U+500B][U+89F8][U+767C][U+4FE1][U+865F]',
            'triggers_cleared': triggers_cleared
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+6E05][U+9664][U+89F8][U+767C][U+4FE1][U+865F][U+5931][U+6557]: {str(e)}'
        })


@app.route('/api/modbus/manual_trigger', methods=['POST'])
def manual_trigger():
    """[U+624B][U+52D5][U+89F8][U+767C][U+6AA2][U+6E2C] ([U+7E5E][U+904E]Modbus[U+FF0C][U+76F4][U+63A5][U+8ABF][U+7528])"""
    data = request.get_json()
    action = data.get('action', 'detect')  # 'capture' [U+6216] 'detect'
    
    modbus_client = vision_controller.modbus_client
    
    try:
        if action == 'capture':
            print("[U+1F527] [U+624B][U+52D5][U+89F8][U+767C]: [U+62CD][U+7167]")
            modbus_client._handle_capture_trigger()
        elif action == 'detect':
            print("[U+1F527] [U+624B][U+52D5][U+89F8][U+767C]: [U+62CD][U+7167]+[U+6AA2][U+6E2C]")
            modbus_client._handle_detect_trigger()
        else:
            return jsonify({
                'success': False,
                'message': '[U+7121][U+6548][U+7684][U+64CD][U+4F5C][U+985E][U+578B]'
            })
        
        return jsonify({
            'success': True,
            'message': f'[U+624B][U+52D5][U+89F8][U+767C] {action} [U+5B8C][U+6210]',
            'operation_count': modbus_client.operation_count,
            'error_count': modbus_client.error_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+624B][U+52D5][U+89F8][U+767C][U+5931][U+6557]: {str(e)}'
        })


@app.route('/api/modbus/force_sync', methods=['POST'])
def force_start_sync():
    """[U+5F37][U+5236][U+555F][U+52D5][U+540C][U+6B65][U+7DDA][U+7A0B] ([U+8ABF][U+8A66][U+7528])"""
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': 'Modbus[U+672A][U+9023][U+63A5]'
        })
    
    try:
        # [U+5F37][U+5236][U+555F][U+52D5][U+540C][U+6B65]
        modbus_client.external_control_enabled = True
        modbus_client.start_sync()
        
        return jsonify({
            'success': True,
            'message': '[U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+5F37][U+5236][U+555F][U+52D5]',
            'sync_running': modbus_client.sync_running,
            'external_control': modbus_client.external_control_enabled
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+5F37][U+5236][U+555F][U+52D5][U+540C][U+6B65][U+5931][U+6557]: {str(e)}'
        })


@app.route('/api/modbus/info', methods=['GET'])
def get_modbus_info():
    """[U+7372][U+53D6]Modbus Client[U+8CC7][U+8A0A]"""
    try:
        import pymodbus
        current_version = pymodbus.__version__
        version_info = f"[U+7576][U+524D][U+7248][U+672C]: {current_version}"
    except:
        current_version = "[U+672A][U+5B89][U+88DD]"
        version_info = "pymodbus[U+672A][U+5B89][U+88DD]"
    
    return jsonify({
        'pymodbus_available': MODBUS_AVAILABLE,
        'current_version': current_version,
        'target_version': PYMODBUS_VERSION,
        'version_info': version_info,
        'client_mode': True,
        'server_mode': False,
        'install_commands': [
            'pip install pymodbus>=3.0.0',
            'pip install "pymodbus[serial]>=3.0.0"'
        ],
        'verify_command': 'python -c "import pymodbus; print(f\'pymodbus {pymodbus.__version__}\')"',
        'architecture': 'Modbus TCP Client ([U+9023][U+63A5][U+5916][U+90E8]PLC/HMI)',
        'register_mapping': {
            '[U+63A7][U+5236][U+5BC4][U+5B58][U+5668] (200-209)': '[U+5F9E]PLC[U+8B80][U+53D6][U+63A7][U+5236][U+6307][U+4EE4]',
            '[U+53C3][U+6578][U+8A2D][U+5B9A] (210-219)': '[U+5F9E]PLC[U+8B80][U+53D6][U+6AA2][U+6E2C][U+53C3][U+6578]',
            '[U+72C0][U+614B][U+56DE][U+5831] (220-239)': '[U+5BEB][U+5165][U+7CFB][U+7D71][U+72C0][U+614B][U+5230]PLC',
            '[U+6AA2][U+6E2C][U+7D50][U+679C] (240-279)': '[U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230]PLC',
            '[U+7D71][U+8A08][U+8CC7][U+8A0A] (280-299)': '[U+5BEB][U+5165][U+7D71][U+8A08][U+8CC7][U+6599][U+5230]PLC'
        },
        'features': [
            '[U+81EA][U+52D5][U+91CD][U+9023][U+6A5F][U+5236]',
            '[U+5916][U+90E8][U+89F8][U+767C][U+63A7][U+5236]',
            '[U+53C3][U+6578][U+52D5][U+614B][U+66F4][U+65B0]',
            '[U+72C0][U+614B][U+5373][U+6642][U+56DE][U+5831]',
            '[U+932F][U+8AA4][U+8A08][U+6578][U+8FFD][U+8E64]'
        ],
        'restart_required': True,
        'compatibility': {
            'python_min': '3.7',
            'recommended_python': '3.8+',
            'async_support': True,
            'sync_support': True
        }
    })


@socketio.on('connect')
def handle_connect():
    """[U+5BA2][U+6236][U+7AEF][U+9023][U+63A5]"""
    emit('status_update', vision_controller.get_status())


@socketio.on('disconnect')
def handle_disconnect():
    """[U+5BA2][U+6236][U+7AEF][U+65B7][U+958B]"""
    pass


def main():
    """[U+4E3B][U+51FD][U+6578]"""
    print("[U+1F680] CCD1 [U+8996][U+89BA][U+63A7][U+5236][U+7CFB][U+7D71][U+555F][U+52D5][U+4E2D] (Modbus TCP Client[U+7248][U+672C])...")
    
    if not CAMERA_MANAGER_AVAILABLE:
        print("[FAIL] [U+76F8][U+6A5F][U+7BA1][U+7406][U+5668][U+4E0D][U+53EF][U+7528][U+FF0C][U+8ACB][U+6AA2][U+67E5]SDK[U+5C0E][U+5165]")
        return
    
    try:
        print("[U+1F527] [U+7CFB][U+7D71][U+67B6][U+69CB]: Modbus TCP Client")
        print("[U+1F4E1] [U+9023][U+63A5][U+6A21][U+5F0F]: [U+4E3B][U+52D5][U+9023][U+63A5][U+5916][U+90E8]PLC/HMI[U+8A2D][U+5099]")
        
        if MODBUS_AVAILABLE:
            print(f"[OK] Modbus TCP Client[U+6A21][U+7D44][U+53EF][U+7528] (pymodbus {PYMODBUS_VERSION})")
            print("[U+1F4CA] CCD1 Modbus[U+5BC4][U+5B58][U+5668][U+6620][U+5C04] (Client[U+6A21][U+5F0F]):")
            print("   [U+250C][U+2500] [U+63A7][U+5236][U+5BC4][U+5B58][U+5668] (200-209) [U+2190] [U+5F9E]PLC[U+8B80][U+53D6]")
            print("   [U+2502]  [U+2022] 200: [U+5916][U+90E8][U+63A7][U+5236][U+555F][U+7528]")
            print("   [U+2502]  [U+2022] 201: [U+62CD][U+7167][U+89F8][U+767C]")
            print("   [U+2502]  [U+2022] 202: [U+62CD][U+7167]+[U+6AA2][U+6E2C][U+89F8][U+767C]")
            print("   [U+2502]  [U+2022] 203: [U+7CFB][U+7D71][U+91CD][U+7F6E]")
            print("   [U+2502]  [U+2022] 204: [U+53C3][U+6578][U+66F4][U+65B0][U+89F8][U+767C]")
            print("   [U+251C][U+2500] [U+53C3][U+6578][U+8A2D][U+5B9A] (210-219) [U+2190] [U+5F9E]PLC[U+8B80][U+53D6]")
            print("   [U+2502]  [U+2022] 210-211: [U+6700][U+5C0F][U+9762][U+7A4D][U+8A2D][U+5B9A]")
            print("   [U+2502]  [U+2022] 212: [U+6700][U+5C0F][U+5713][U+5EA6][U+8A2D][U+5B9A]")
            print("   [U+2502]  [U+2022] 213-215: [U+5716][U+50CF][U+8655][U+7406][U+53C3][U+6578]")
            print("   [U+251C][U+2500] [U+72C0][U+614B][U+56DE][U+5831] (220-239) [U+2192] [U+5BEB][U+5165][U+5230]PLC")
            print("   [U+2502]  [U+2022] 220: [U+7CFB][U+7D71][U+72C0][U+614B]")
            print("   [U+2502]  [U+2022] 221: [U+76F8][U+6A5F][U+9023][U+63A5][U+72C0][U+614B]")
            print("   [U+2502]  [U+2022] 222: [U+6700][U+5F8C][U+64CD][U+4F5C][U+72C0][U+614B]")
            print("   [U+2502]  [U+2022] 223: [U+8655][U+7406][U+9032][U+5EA6]")
            print("   [U+251C][U+2500] [U+6AA2][U+6E2C][U+7D50][U+679C] (240-279) [U+2192] [U+5BEB][U+5165][U+5230]PLC")
            print("   [U+2502]  [U+2022] 240: [U+6AA2][U+6E2C][U+5713][U+5F62][U+6578][U+91CF]")
            print("   [U+2502]  [U+2022] 241-255: [U+5713][U+5F62]1-5[U+7684][U+5EA7][U+6A19][U+548C][U+534A][U+5F91]")
            print("   [U+2514][U+2500] [U+7D71][U+8A08][U+8CC7][U+8A0A] (280-299) [U+2192] [U+5BEB][U+5165][U+5230]PLC")
            print("      [U+2022] 280-282: [U+6642][U+9593][U+7D71][U+8A08]")
            print("      [U+2022] 283-285: [U+8A08][U+6578][U+5668]")
            print("      [U+2022] 290-293: [U+7248][U+672C][U+8207][U+904B][U+884C][U+6642][U+9593]")
        else:
            print("[WARN][U+FE0F] Modbus Client[U+529F][U+80FD][U+4E0D][U+53EF][U+7528] ([U+4F7F][U+7528][U+6A21][U+64EC][U+6A21][U+5F0F])")
        
        print("[U+1F310] Web[U+4ECB][U+9762][U+555F][U+52D5][U+4E2D]...")
        print("[U+1F4F1] [U+8A2A][U+554F][U+5730][U+5740]: http://localhost:5051")
        print("[U+1F3AF] [U+7CFB][U+7D71][U+529F][U+80FD]:")
        print("   [U+2022] [U+76F8][U+6A5F][U+9023][U+63A5][U+7BA1][U+7406]")
        print("   [U+2022] [U+53C3][U+6578][U+8ABF][U+6574][U+4ECB][U+9762]")
        print("   [U+2022] [U+5713][U+5F62][U+6AA2][U+6E2C][U+8207][U+6A19][U+8A3B]")
        print("   [U+2022] Modbus TCP Client[U+5916][U+90E8][U+63A7][U+5236]")
        print("   [U+2022] [U+5373][U+6642][U+72C0][U+614B][U+76E3][U+63A7]")
        print("[U+1F517] [U+4F7F][U+7528][U+8AAA][U+660E]:")
        print("   1. [U+5148][U+8A2D][U+7F6E]Modbus[U+670D][U+52D9][U+5668]IP[U+5730][U+5740]")
        print("   2. [U+9023][U+63A5][U+5230][U+5916][U+90E8]PLC/HMI[U+8A2D][U+5099]")
        print("   3. [U+521D][U+59CB][U+5316][U+76F8][U+6A5F][U+9023][U+63A5]")
        print("   4. [U+555F][U+7528][U+5916][U+90E8][U+63A7][U+5236][U+6A21][U+5F0F]")
        print("   5. [U+901A][U+904E]PLC[U+63A7][U+5236][U+62CD][U+7167][U+548C][U+6AA2][U+6E2C]")
        print("=" * 60)
        
        socketio.run(app, host='0.0.0.0', port=5051, debug=False)
        
    except KeyboardInterrupt:
        print("\n[U+1F6D1] [U+7528][U+6236][U+4E2D][U+65B7][U+FF0C][U+6B63][U+5728][U+95DC][U+9589][U+7CFB][U+7D71]...")
    except Exception as e:
        print(f"[FAIL] [U+7CFB][U+7D71][U+904B][U+884C][U+932F][U+8AA4]: {e}")
    finally:
        try:
            vision_controller.disconnect()
        except:
            pass
        print("[OK] [U+7CFB][U+7D71][U+5DF2][U+5B89][U+5168][U+95DC][U+9589]")


if __name__ == "__main__":
    main()