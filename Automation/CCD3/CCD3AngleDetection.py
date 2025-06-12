# -*- coding: utf-8 -*-
import sys
import os
import time
import threading
import json
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import cv2
import numpy as np

# PyModbus imports
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Flask imports
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# Import camera manager and angle detection
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'API'))
from camera_manager import OptimizedCamera, CameraConfig

# Import angle detection algorithm
current_dir = os.path.dirname(os.path.abspath(__file__))
opencv_module_path = os.path.join(current_dir, '..', '..')
sys.path.append(opencv_module_path)
from opencv_detect_module import get_obj_angle, get_pre_treatment_image

# [U+8A2D][U+7F6E]logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StatusBits(Enum):
    READY = 0
    RUNNING = 1
    ALARM = 2
    INITIALIZED = 3

@dataclass
class AngleResult:
    success: bool
    center: Optional[Tuple[int, int]]
    angle: Optional[float]
    major_axis: Optional[float]
    minor_axis: Optional[float]
    rect_width: Optional[float]
    rect_height: Optional[float]
    contour_area: Optional[float]
    processing_time: float
    capture_time: float
    total_time: float
    error_message: Optional[str] = None

class SystemStateMachine:
    def __init__(self):
        self.status_register = 0b0001  # [U+521D][U+59CB][U+72C0][U+614B]: Ready=1
        self.lock = threading.Lock()
    
    def set_bit(self, bit_pos: StatusBits, value: bool):
        with self.lock:
            if value:
                self.status_register |= (1 << bit_pos.value)
            else:
                self.status_register &= ~(1 << bit_pos.value)
    
    def get_bit(self, bit_pos: StatusBits) -> bool:
        with self.lock:
            return bool(self.status_register & (1 << bit_pos.value))
    
    def is_ready(self) -> bool:
        return self.get_bit(StatusBits.READY)
    
    def is_running(self) -> bool:
        return self.get_bit(StatusBits.RUNNING)
    
    def is_alarm(self) -> bool:
        return self.get_bit(StatusBits.ALARM)
    
    def is_initialized(self) -> bool:
        return self.get_bit(StatusBits.INITIALIZED)
    
    def set_ready(self, ready: bool):
        self.set_bit(StatusBits.READY, ready)
    
    def set_running(self, running: bool):
        self.set_bit(StatusBits.RUNNING, running)
    
    def set_alarm(self, alarm: bool):
        self.set_bit(StatusBits.ALARM, alarm)
    
    def set_initialized(self, initialized: bool):
        self.set_bit(StatusBits.INITIALIZED, initialized)
    
    def reset_to_idle(self):
        with self.lock:
            self.status_register = 0b1001  # Ready=1, Initialized=1

class AngleDetector:
    def __init__(self):
        self.min_area_rate = 0.05
        self.sequence_mode = False
        self.gaussian_kernel = 3
        self.threshold_mode = 0  # 0=OTSU, 1=Manual
        self.manual_threshold = 127
    
    def update_params(self, **kwargs):
        """[U+66F4][U+65B0][U+6AA2][U+6E2C][U+53C3][U+6578]"""
        if 'min_area_rate' in kwargs:
            self.min_area_rate = kwargs['min_area_rate'] / 1000.0
        if 'sequence_mode' in kwargs:
            self.sequence_mode = bool(kwargs['sequence_mode'])
        if 'gaussian_kernel' in kwargs:
            self.gaussian_kernel = kwargs['gaussian_kernel']
        if 'threshold_mode' in kwargs:
            self.threshold_mode = kwargs['threshold_mode']
        if 'manual_threshold' in kwargs:
            self.manual_threshold = kwargs['manual_threshold']
    
    def get_pre_treatment_image_enhanced(self, image):
        """[U+589E][U+5F37][U+7248][U+5F71][U+50CF][U+524D][U+8655][U+7406]"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (self.gaussian_kernel, self.gaussian_kernel), 0)
        
        if self.threshold_mode == 0:
            # OTSU[U+81EA][U+52D5][U+95BE][U+503C]
            _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            # [U+624B][U+52D5][U+95BE][U+503C]
            _, thresh = cv2.threshold(blur, self.manual_threshold, 255, cv2.THRESH_BINARY)
        
        return thresh
    
    def detect_angle(self, image, mode=0) -> AngleResult:
        """
        [U+89D2][U+5EA6][U+6AA2][U+6E2C][U+4E3B][U+51FD][U+6578]
        mode: 0=[U+6A62][U+5713][U+64EC][U+5408][U+6A21][U+5F0F], 1=[U+6700][U+5C0F][U+5916][U+63A5][U+77E9][U+5F62][U+6A21][U+5F0F]
        """
        start_time = time.time()
        
        try:
            print(f"[U+958B][U+59CB][U+89D2][U+5EA6][U+6AA2][U+6E2C][U+FF0C][U+6A21][U+5F0F]: {mode}, [U+5716][U+50CF][U+5C3A][U+5BF8]: {image.shape}")
            
            # [U+6AA2][U+67E5][U+5716][U+50CF][U+683C][U+5F0F][U+4E26][U+8F49][U+63DB][U+70BA]OpenCV[U+7B97][U+6CD5][U+6240][U+9700][U+7684]BGR[U+683C][U+5F0F]
            if len(image.shape) == 2:
                # [U+7070][U+5EA6][U+5716][U+50CF][U+FF0C][U+8F49][U+63DB][U+70BA]BGR
                print("[U+6AA2][U+6E2C][U+5230][U+7070][U+5EA6][U+5716][U+50CF][U+FF0C][U+8F49][U+63DB][U+70BA]BGR[U+683C][U+5F0F]")
                bgr_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            elif len(image.shape) == 3 and image.shape[2] == 1:
                # [U+55AE][U+901A][U+9053][U+5716][U+50CF][U+FF0C][U+8F49][U+63DB][U+70BA]BGR
                print("[U+6AA2][U+6E2C][U+5230][U+55AE][U+901A][U+9053][U+5716][U+50CF][U+FF0C][U+8F49][U+63DB][U+70BA]BGR[U+683C][U+5F0F]")
                gray_image = image.squeeze()
                bgr_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
            elif len(image.shape) == 3 and image.shape[2] == 3:
                # [U+5DF2][U+7D93][U+662F]3[U+901A][U+9053][U+5716][U+50CF]
                print("[U+6AA2][U+6E2C][U+5230]3[U+901A][U+9053][U+5716][U+50CF][U+FF0C][U+76F4][U+63A5][U+4F7F][U+7528]")
                bgr_image = image
            else:
                raise Exception(f"[U+4E0D][U+652F][U+63F4][U+7684][U+5716][U+50CF][U+683C][U+5F0F]: {image.shape}")
            
            print(f"[U+8F49][U+63DB][U+5F8C][U+5716][U+50CF][U+5C3A][U+5BF8]: {bgr_image.shape}")
            
            # [U+8ABF][U+7528][U+6838][U+5FC3][U+7B97][U+6CD5] - [U+50B3][U+5165]BGR[U+683C][U+5F0F][U+5716][U+50CF]
            result = get_obj_angle(bgr_image.copy(), mode=mode)
            
            if result is None:
                print("[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+5931][U+6557]: [U+672A][U+6AA2][U+6E2C][U+5230][U+6709][U+6548][U+7269][U+9AD4]")
                return AngleResult(
                    success=False,
                    center=None,
                    angle=None,
                    major_axis=None,
                    minor_axis=None,
                    rect_width=None,
                    rect_height=None,
                    contour_area=None,
                    processing_time=0,
                    capture_time=0,
                    total_time=time.time() - start_time,
                    error_message="[U+672A][U+6AA2][U+6E2C][U+5230][U+6709][U+6548][U+7269][U+9AD4]"
                )
            
            center, angle = result
            processing_time = (time.time() - start_time) * 1000
            
            print(f"[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+6210][U+529F]: [U+4E2D][U+5FC3][U+5EA7][U+6A19]({center[0]}, {center[1]}), [U+89D2][U+5EA6]{angle:.2f}[U+5EA6], [U+8655][U+7406][U+6642][U+9593]{processing_time:.2f}ms")
            
            # [U+5F9E]opencv_detect_module.py[U+7372][U+53D6][U+984D][U+5916][U+8CC7][U+8A0A][U+9700][U+8981][U+589E][U+5F37][U+7B97][U+6CD5]
            # [U+76EE][U+524D][U+5148][U+8FD4][U+56DE][U+57FA][U+672C][U+7D50][U+679C][U+FF0C][U+5F8C][U+7E8C][U+6574][U+5408][U+5167][U+5916][U+5F91][U+7B97][U+6CD5][U+6642][U+64F4][U+5C55]
            
            return AngleResult(
                success=True,
                center=center,
                angle=angle,
                major_axis=None,  # [U+5F85][U+6574][U+5408]
                minor_axis=None,  # [U+5F85][U+6574][U+5408]
                rect_width=None,  # [U+5F85][U+6574][U+5408]
                rect_height=None, # [U+5F85][U+6574][U+5408]
                contour_area=None, # [U+5F85][U+6574][U+5408]
                processing_time=processing_time,
                capture_time=0,
                total_time=processing_time
            )
            
        except Exception as e:
            print(f"[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+7570][U+5E38]: {str(e)}")
            return AngleResult(
                success=False,
                center=None,
                angle=None,
                major_axis=None,
                minor_axis=None,
                rect_width=None,
                rect_height=None,
                contour_area=None,
                processing_time=0,
                capture_time=0,
                total_time=time.time() - start_time,
                error_message=str(e)
            )

class CCD3AngleDetectionService:
    def __init__(self):
        self.base_address = 800
        self.modbus_client = None
        self.server_ip = "127.0.0.1"
        self.server_port = 502
        
        # [U+7D44][U+4EF6][U+521D][U+59CB][U+5316]
        self.state_machine = SystemStateMachine()
        self.angle_detector = AngleDetector()
        self.camera = None
        
        # [U+63A7][U+5236][U+8B8A][U+91CF]
        self.last_control_command = 0
        self.command_processing = False
        self.handshake_thread = None
        self.stop_handshake = False
        
        # [U+7D71][U+8A08][U+8CC7][U+8A0A]
        self.operation_count = 0
        self.error_count = 0
        self.connection_count = 0
        self.start_time = time.time()
        
        # [U+914D][U+7F6E][U+6A94][U+6848]
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ccd3_config.json')
        self.load_config()
    
    def load_config(self):
        """[U+8F09][U+5165][U+914D][U+7F6E][U+6A94][U+6848]"""
        default_config = {
            "module_id": "CCD3_Angle_Detection",
            "camera_config": {
                "name": "ccd3_camera",
                "ip": "192.168.1.10",
                "exposure_time": 20000.0,
                "gain": 200.0,
                "frame_rate": 30.0,
                "width": 2592,
                "height": 1944
            },
            "tcp_server": {
                "host": "127.0.0.1",
                "port": 502,
                "unit_id": 1
            },
            "modbus_mapping": {
                "base_address": 800
            },
            "detection_params": {
                "min_area_rate": 50,
                "sequence_mode": 0,
                "gaussian_kernel": 3,
                "threshold_mode": 0,
                "manual_threshold": 127
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = default_config
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            
            # [U+61C9][U+7528][U+914D][U+7F6E]
            self.server_ip = config['tcp_server']['host']
            self.server_port = config['tcp_server']['port']
            self.base_address = config['modbus_mapping']['base_address']
            
        except Exception as e:
            print(f"[U+914D][U+7F6E][U+6A94][U+6848][U+8F09][U+5165][U+932F][U+8AA4]: {e}")
    
    def connect_modbus(self) -> bool:
        """[U+9023][U+63A5]Modbus TCP[U+670D][U+52D9][U+5668]"""
        try:
            print("[U+6B63][U+5728][U+9023][U+63A5]Modbus TCP[U+670D][U+52D9][U+5668]...")
            
            if self.modbus_client:
                self.modbus_client.close()
            
            self.modbus_client = ModbusTcpClient(
                host=self.server_ip,
                port=self.server_port,
                timeout=3
            )
            
            if self.modbus_client.connect():
                self.connection_count += 1
                print(f"CCD3[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+6A21][U+7D44][U+5DF2][U+9023][U+63A5][U+5230]Modbus[U+670D][U+52D9][U+5668]: {self.server_ip}:{self.server_port}")
                return True
            else:
                print(f"Modbus[U+9023][U+63A5][U+5931][U+6557]: [U+7121][U+6CD5][U+9023][U+63A5][U+5230] {self.server_ip}:{self.server_port}")
                self.state_machine.set_alarm(True)
                return False
                
        except Exception as e:
            print(f"Modbus[U+9023][U+63A5][U+932F][U+8AA4]: {e}")
            self.state_machine.set_alarm(True)
            return False
    
    def initialize_camera(self, ip_address: str = "192.168.1.10") -> bool:
        """[U+521D][U+59CB][U+5316][U+76F8][U+6A5F]"""
        try:
            print(f"[U+6B63][U+5728][U+521D][U+59CB][U+5316][U+76F8][U+6A5F][U+FF0C]IP[U+5730][U+5740]: {ip_address}")
            
            if self.camera:
                print("[U+95DC][U+9589][U+73FE][U+6709][U+76F8][U+6A5F][U+9023][U+63A5]...")
                self.camera.disconnect()
                self.camera = None
            
            # [U+4F7F][U+7528]camera_manager.py[U+FF0C][U+9700][U+8981][U+63D0][U+4F9B]logger[U+53C3][U+6578]
            config = CameraConfig(
                name="ccd3_camera",
                ip=ip_address,
                exposure_time=20000.0,
                gain=200.0,
                frame_rate=30.0,
                width=2592,
                height=1944
            )
            
            print(f"[U+76F8][U+6A5F][U+914D][U+7F6E]: [U+66DD][U+5149][U+6642][U+9593]={config.exposure_time}, [U+589E][U+76CA]={config.gain}, [U+5206][U+8FA8][U+7387]={config.width}x{config.height}")
            
            self.camera = OptimizedCamera(config, logger)
            
            print("[U+6B63][U+5728][U+9023][U+63A5][U+76F8][U+6A5F]...")
            if self.camera.connect():
                print(f"CCD3[U+76F8][U+6A5F][U+5DF2][U+6210][U+529F][U+9023][U+63A5]: {ip_address}")
                
                # [U+5148][U+555F][U+52D5][U+4E32][U+6D41]
                print("[U+555F][U+52D5][U+76F8][U+6A5F][U+4E32][U+6D41]...")
                if self.camera.start_streaming():
                    print("[U+76F8][U+6A5F][U+4E32][U+6D41][U+555F][U+52D5][U+6210][U+529F]")
                    
                    # [U+6E2C][U+8A66][U+5716][U+50CF][U+6355][U+7372][U+80FD][U+529B][U+4F86][U+9A57][U+8B49][U+76F8][U+6A5F][U+662F][U+5426][U+771F][U+6B63][U+53EF][U+7528]
                    print("[U+6E2C][U+8A66][U+76F8][U+6A5F][U+5716][U+50CF][U+6355][U+7372][U+80FD][U+529B]...")
                    try:
                        test_image = self.camera.capture_frame()
                        if test_image is not None:
                            print(f"[U+76F8][U+6A5F][U+6E2C][U+8A66][U+6210][U+529F][U+FF0C][U+53EF][U+4EE5][U+6355][U+7372][U+5716][U+50CF][U+FF0C][U+6E2C][U+8A66][U+5716][U+50CF][U+5C3A][U+5BF8]: {test_image.data.shape}")
                            self.state_machine.set_initialized(True)
                            self.state_machine.set_alarm(False)
                            return True
                        else:
                            print("[U+76F8][U+6A5F][U+6E2C][U+8A66][U+5931][U+6557]: [U+7121][U+6CD5][U+6355][U+7372][U+5716][U+50CF]")
                            self.state_machine.set_alarm(True)
                            self.state_machine.set_initialized(False)
                            return False
                    except Exception as e:
                        print(f"[U+76F8][U+6A5F][U+6E2C][U+8A66][U+7570][U+5E38]: {e}")
                        self.state_machine.set_alarm(True)
                        self.state_machine.set_initialized(False)
                        return False
                else:
                    print("[U+76F8][U+6A5F][U+4E32][U+6D41][U+555F][U+52D5][U+5931][U+6557]")
                    self.state_machine.set_alarm(True)
                    self.state_machine.set_initialized(False)
                    return False
            else:
                print(f"[U+76F8][U+6A5F][U+9023][U+63A5][U+5931][U+6557]: {ip_address}")
                self.state_machine.set_alarm(True)
                self.state_machine.set_initialized(False)
                return False
                
        except Exception as e:
            print(f"[U+76F8][U+6A5F][U+521D][U+59CB][U+5316][U+932F][U+8AA4]: {e}")
            self.state_machine.set_alarm(True)
            self.state_machine.set_initialized(False)
            return False
    
    def capture_and_detect_angle(self, mode: int = 0) -> AngleResult:
        """[U+62CD][U+7167][U+4E26][U+6AA2][U+6E2C][U+89D2][U+5EA6]"""
        print(f"[U+958B][U+59CB][U+62CD][U+7167]+[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+FF0C][U+6AA2][U+6E2C][U+6A21][U+5F0F]: {mode}")
        
        if not self.camera:
            print("[U+932F][U+8AA4]: [U+76F8][U+6A5F][U+672A][U+521D][U+59CB][U+5316]")
            return AngleResult(
                success=False, center=None, angle=None,
                major_axis=None, minor_axis=None, rect_width=None, rect_height=None,
                contour_area=None, processing_time=0, capture_time=0, total_time=0,
                error_message="[U+76F8][U+6A5F][U+672A][U+521D][U+59CB][U+5316]"
            )
        
        # [U+6AA2][U+67E5][U+76F8][U+6A5F][U+72C0][U+614B] - [U+4F7F][U+7528][U+5BE6][U+969B][U+6355][U+7372][U+6E2C][U+8A66][U+800C][U+4E0D][U+662F]device[U+5C6C][U+6027]
        if not self.camera:
            print("[U+932F][U+8AA4]: [U+76F8][U+6A5F][U+672A][U+521D][U+59CB][U+5316]")
            return AngleResult(
                success=False, center=None, angle=None,
                major_axis=None, minor_axis=None, rect_width=None, rect_height=None,
                contour_area=None, processing_time=0, capture_time=0, total_time=0,
                error_message="[U+76F8][U+6A5F][U+672A][U+521D][U+59CB][U+5316]"
            )
        
        capture_start = time.time()
        
        try:
            # [U+62CD][U+7167]
            print("[U+6B63][U+5728][U+6355][U+7372][U+5716][U+50CF]...")
            frame_data = self.camera.capture_frame()
            
            if frame_data is None:
                print("[U+932F][U+8AA4]: [U+5716][U+50CF][U+6355][U+7372][U+5931][U+6557][U+FF0C][U+8FD4][U+56DE]None")
                raise Exception("[U+5716][U+50CF][U+6355][U+7372][U+5931][U+6557]")
            
            image = frame_data.data
            capture_time = (time.time() - capture_start) * 1000
            print(f"[U+5716][U+50CF][U+6355][U+7372][U+6210][U+529F][U+FF0C][U+8017][U+6642]: {capture_time:.2f}ms, [U+5716][U+50CF][U+5C3A][U+5BF8]: {image.shape}")
            
            # [U+66F4][U+65B0][U+6AA2][U+6E2C][U+53C3][U+6578]
            detection_params = self.read_detection_parameters()
            if detection_params:
                print(f"[U+6AA2][U+6E2C][U+53C3][U+6578]: {detection_params}")
                self.angle_detector.update_params(**detection_params)
            else:
                print("[U+4F7F][U+7528][U+9810][U+8A2D][U+6AA2][U+6E2C][U+53C3][U+6578]")
            
            # [U+89D2][U+5EA6][U+6AA2][U+6E2C]
            detect_start = time.time()
            print("[U+958B][U+59CB][U+89D2][U+5EA6][U+6AA2][U+6E2C]...")
            result = self.angle_detector.detect_angle(image, mode)
            result.capture_time = capture_time
            result.total_time = (time.time() - capture_start) * 1000
            
            if result.success:
                self.operation_count += 1
                print(f"[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+5B8C][U+6210] - [U+7E3D][U+8017][U+6642]: {result.total_time:.2f}ms")
            else:
                self.error_count += 1
                print(f"[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+5931][U+6557]: {result.error_message}")
            
            return result
            
        except Exception as e:
            self.error_count += 1
            error_msg = str(e)
            print(f"[U+6355][U+7372][U+6216][U+6AA2][U+6E2C][U+904E][U+7A0B][U+7570][U+5E38]: {error_msg}")
            return AngleResult(
                success=False, center=None, angle=None,
                major_axis=None, minor_axis=None, rect_width=None, rect_height=None,
                contour_area=None, processing_time=0,
                capture_time=(time.time() - capture_start) * 1000,
                total_time=(time.time() - capture_start) * 1000,
                error_message=error_msg
            )
    
    def read_detection_parameters(self) -> Dict[str, Any]:
        """[U+8B80][U+53D6][U+6AA2][U+6E2C][U+53C3][U+6578][U+5BC4][U+5B58][U+5668]"""
        params = {}
        try:
            if self.modbus_client and self.modbus_client.connected:
                result = self.modbus_client.read_holding_registers(
                    address=self.base_address + 10, count=10, slave=1
                )
                if not result.isError():
                    registers = result.registers
                    params['detection_mode'] = registers[0]
                    params['min_area_rate'] = registers[1]
                    params['sequence_mode'] = registers[2]
                    params['gaussian_kernel'] = registers[3]
                    params['threshold_mode'] = registers[4]
                    params['manual_threshold'] = registers[5]
        except Exception as e:
            print(f"[U+8B80][U+53D6][U+6AA2][U+6E2C][U+53C3][U+6578][U+932F][U+8AA4]: {e}")
        
        return params
    
    def write_detection_result(self, result: AngleResult):
        """[U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230][U+5BC4][U+5B58][U+5668]"""
        try:
            if not self.modbus_client or not self.modbus_client.connected:
                print("[U+8B66][U+544A]: Modbus[U+672A][U+9023][U+63A5][U+FF0C][U+7121][U+6CD5][U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C]")
                return
            
            # [U+6AA2][U+6E2C][U+7D50][U+679C][U+5BC4][U+5B58][U+5668] (840-859)
            result_registers = [0] * 20
            
            if result.success and result.center and result.angle is not None:
                result_registers[0] = 1  # [U+6AA2][U+6E2C][U+6210][U+529F][U+6A19][U+8A8C]
                result_registers[1] = int(result.center[0])  # [U+4E2D][U+5FC3]X[U+5EA7][U+6A19]
                result_registers[2] = int(result.center[1])  # [U+4E2D][U+5FC3]Y[U+5EA7][U+6A19]
                
                # [U+89D2][U+5EA6]32[U+4F4D][U+5B58][U+5132] ([U+9AD8][U+4F4E][U+4F4D])
                angle_int = int(result.angle * 100)  # [U+4FDD][U+7559]2[U+4F4D][U+5C0F][U+6578]
                result_registers[3] = (angle_int >> 16) & 0xFFFF  # [U+89D2][U+5EA6][U+9AD8][U+4F4D]
                result_registers[4] = angle_int & 0xFFFF          # [U+89D2][U+5EA6][U+4F4E][U+4F4D]
                
                print(f"[U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C]: [U+6210][U+529F][U+6A19][U+8A8C]=1, [U+4E2D][U+5FC3]=({result_registers[1]}, {result_registers[2]}), [U+89D2][U+5EA6]={result.angle:.2f}[U+5EA6]")
                
                # [U+5176][U+4ED6][U+53C3][U+6578] ([U+5F85][U+6574][U+5408][U+5167][U+5916][U+5F91][U+7B97][U+6CD5][U+6642][U+5BE6][U+73FE])
                if result.major_axis:
                    result_registers[5] = int(result.major_axis)
                if result.minor_axis:
                    result_registers[6] = int(result.minor_axis)
                if result.rect_width:
                    result_registers[7] = int(result.rect_width)
                if result.rect_height:
                    result_registers[8] = int(result.rect_height)
                if result.contour_area:
                    result_registers[9] = int(result.contour_area)
            else:
                print("[U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C]: [U+6AA2][U+6E2C][U+5931][U+6557]")
            
            # [U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C] (840-859)
            self.modbus_client.write_registers(
                address=self.base_address + 40, values=result_registers, slave=1
            )
            
            # [U+5BEB][U+5165][U+7D71][U+8A08][U+8CC7][U+8A0A] (880-899)
            stats_registers = [
                int(result.capture_time),      # 880: [U+62CD][U+7167][U+8017][U+6642]
                int(result.processing_time),   # 881: [U+8655][U+7406][U+8017][U+6642]
                int(result.total_time),        # 882: [U+7E3D][U+8017][U+6642]
                self.operation_count,          # 883: [U+64CD][U+4F5C][U+8A08][U+6578]
                self.error_count,              # 884: [U+932F][U+8AA4][U+8A08][U+6578]
                self.connection_count,         # 885: [U+9023][U+63A5][U+8A08][U+6578]
                0, 0, 0, 0,                   # 886-889: [U+4FDD][U+7559]
                3,                            # 890: [U+8EDF][U+9AD4][U+7248][U+672C][U+4E3B][U+865F]
                0,                            # 891: [U+8EDF][U+9AD4][U+7248][U+672C][U+6B21][U+865F]
                int((time.time() - self.start_time) // 3600),  # 892: [U+904B][U+884C][U+5C0F][U+6642]
                int((time.time() - self.start_time) % 3600 // 60), # 893: [U+904B][U+884C][U+5206][U+9418]
                0, 0, 0, 0, 0, 0             # 894-899: [U+4FDD][U+7559]
            ]
            
            self.modbus_client.write_registers(
                address=self.base_address + 80, values=stats_registers, slave=1
            )
            
            print(f"[U+7D71][U+8A08][U+8CC7][U+8A0A][U+5DF2][U+66F4][U+65B0]: [U+6210][U+529F][U+6B21][U+6578]={self.operation_count}, [U+932F][U+8AA4][U+6B21][U+6578]={self.error_count}")
            
        except Exception as e:
            print(f"[U+5BEB][U+5165][U+6AA2][U+6E2C][U+7D50][U+679C][U+932F][U+8AA4]: {e}")
    
    def _handshake_sync_loop(self):
        """[U+63E1][U+624B][U+540C][U+6B65][U+5FAA][U+74B0]"""
        print("CCD3[U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B][U+555F][U+52D5]")
        
        while not self.stop_handshake:
            try:
                if self.modbus_client and self.modbus_client.connected:
                    # [U+66F4][U+65B0][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
                    self._update_status_register()
                    
                    # [U+8655][U+7406][U+63A7][U+5236][U+6307][U+4EE4]
                    self._process_control_commands()
                
                time.sleep(0.05)  # 50ms[U+5FAA][U+74B0]
                
            except Exception as e:
                print(f"[U+63E1][U+624B][U+540C][U+6B65][U+932F][U+8AA4]: {e}")
                time.sleep(1)
        
        print("CCD3[U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B][U+505C][U+6B62]")
    
    def _update_status_register(self):
        """[U+66F4][U+65B0][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]"""
        try:
            # [U+66F4][U+65B0][U+521D][U+59CB][U+5316][U+72C0][U+614B] - [U+6AA2][U+67E5][U+76F8][U+6A5F][U+4E32][U+6D41][U+72C0][U+614B]
            camera_ok = self.camera is not None and getattr(self.camera, 'is_streaming', False)
            modbus_ok = self.modbus_client is not None and self.modbus_client.connected
            
            self.state_machine.set_initialized(camera_ok)
            if not (camera_ok and modbus_ok):
                if not camera_ok:
                    self.state_machine.set_alarm(True)
                    # print("[U+72C0][U+614B][U+66F4][U+65B0]: [U+76F8][U+6A5F][U+672A][U+6B63][U+78BA][U+521D][U+59CB][U+5316]")  # [U+907F][U+514D][U+904E][U+591A][U+8F38][U+51FA]
            
            # [U+5BEB][U+5165][U+72C0][U+614B][U+5BC4][U+5B58][U+5668] (801)
            self.modbus_client.write_register(
                address=self.base_address + 1,
                value=self.state_machine.status_register,
                slave=1
            )
            
        except Exception as e:
            print(f"[U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+66F4][U+65B0][U+932F][U+8AA4]: {e}")
    
    def _process_control_commands(self):
        """[U+8655][U+7406][U+63A7][U+5236][U+6307][U+4EE4]"""
        try:
            # [U+8B80][U+53D6][U+63A7][U+5236][U+6307][U+4EE4] (800)
            result = self.modbus_client.read_holding_registers(
                address=self.base_address, count=1, slave=1
            )
            
            if result.isError():
                return
            
            control_command = result.registers[0]
            
            # [U+6AA2][U+67E5][U+65B0][U+6307][U+4EE4]
            if control_command != self.last_control_command and control_command != 0:
                if not self.command_processing:
                    print(f"[U+6536][U+5230][U+65B0][U+63A7][U+5236][U+6307][U+4EE4]: {control_command} ([U+4E0A][U+6B21]: {self.last_control_command})")
                    self._handle_control_command(control_command)
                    self.last_control_command = control_command
            
            # PLC[U+6E05][U+96F6][U+6307][U+4EE4][U+5F8C][U+6062][U+5FA9]Ready
            elif control_command == 0 and self.last_control_command != 0:
                print("PLC[U+5DF2][U+6E05][U+96F6][U+6307][U+4EE4][U+FF0C][U+6062][U+5FA9]Ready[U+72C0][U+614B]")
                self.state_machine.set_ready(True)
                self.last_control_command = 0
                
        except Exception as e:
            print(f"[U+63A7][U+5236][U+6307][U+4EE4][U+8655][U+7406][U+932F][U+8AA4]: {e}")
    
    def _handle_control_command(self, command: int):
        """[U+8655][U+7406][U+63A7][U+5236][U+6307][U+4EE4]"""
        if not self.state_machine.is_ready():
            print(f"[U+7CFB][U+7D71][U+672A]Ready[U+FF0C][U+7121][U+6CD5][U+57F7][U+884C][U+6307][U+4EE4] {command}")
            return
        
        print(f"[U+958B][U+59CB][U+8655][U+7406][U+63A7][U+5236][U+6307][U+4EE4]: {command}")
        self.command_processing = True
        self.state_machine.set_ready(False)
        self.state_machine.set_running(True)
        
        # [U+7570][U+6B65][U+57F7][U+884C][U+6307][U+4EE4]
        threading.Thread(target=self._execute_command_async, args=(command,), daemon=True).start()
    
    def _execute_command_async(self, command: int):
        """[U+7570][U+6B65][U+57F7][U+884C][U+6307][U+4EE4]"""
        try:
            if command == 8:
                # [U+55AE][U+7D14][U+62CD][U+7167]
                print("[U+57F7][U+884C][U+62CD][U+7167][U+6307][U+4EE4]")
                if self.camera and getattr(self.camera, 'is_streaming', False):
                    frame_data = self.camera.capture_frame()
                    if frame_data is not None:
                        print(f"[U+62CD][U+7167][U+5B8C][U+6210][U+FF0C][U+5716][U+50CF][U+5C3A][U+5BF8]: {frame_data.data.shape}")
                    else:
                        print("[U+62CD][U+7167][U+5931][U+6557]: [U+7121][U+6CD5][U+6355][U+7372][U+5716][U+50CF]")
                        self.error_count += 1
                else:
                    print("[U+62CD][U+7167][U+5931][U+6557]: [U+76F8][U+6A5F][U+672A][U+521D][U+59CB][U+5316][U+6216][U+4E32][U+6D41][U+672A][U+555F][U+52D5]")
                    self.error_count += 1
                        
            elif command == 16:
                # [U+62CD][U+7167]+[U+89D2][U+5EA6][U+6AA2][U+6E2C]
                print("[U+57F7][U+884C][U+62CD][U+7167]+[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+6307][U+4EE4]")
                
                # [U+8B80][U+53D6][U+6AA2][U+6E2C][U+6A21][U+5F0F] (810)
                mode_result = self.modbus_client.read_holding_registers(
                    address=self.base_address + 10, count=1, slave=1
                )
                detection_mode = 0
                if not mode_result.isError():
                    detection_mode = mode_result.registers[0]
                
                print(f"[U+6AA2][U+6E2C][U+6A21][U+5F0F]: {detection_mode}")
                
                result = self.capture_and_detect_angle(detection_mode)
                self.write_detection_result(result)
                
                if result.success:
                    print(f"[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+5B8C][U+6210]: [U+4E2D][U+5FC3]{result.center}, [U+89D2][U+5EA6]{result.angle:.2f}[U+5EA6]")
                else:
                    print(f"[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+5931][U+6557]: {result.error_message}")
                    
            elif command == 32:
                # [U+91CD][U+65B0][U+521D][U+59CB][U+5316]
                print("[U+57F7][U+884C][U+91CD][U+65B0][U+521D][U+59CB][U+5316][U+6307][U+4EE4]")
                success = self.initialize_camera()
                if success:
                    print("[U+91CD][U+65B0][U+521D][U+59CB][U+5316][U+6210][U+529F]")
                else:
                    print("[U+91CD][U+65B0][U+521D][U+59CB][U+5316][U+5931][U+6557]")
            
            else:
                print(f"[U+672A][U+77E5][U+6307][U+4EE4]: {command}")
                
        except Exception as e:
            print(f"[U+6307][U+4EE4][U+57F7][U+884C][U+932F][U+8AA4]: {e}")
            self.error_count += 1
            self.state_machine.set_alarm(True)
        
        finally:
            print(f"[U+63A7][U+5236][U+6307][U+4EE4] {command} [U+57F7][U+884C][U+5B8C][U+6210]")
            self.command_processing = False
            self.state_machine.set_running(False)
    
    def start_handshake_service(self):
        """[U+555F][U+52D5][U+63E1][U+624B][U+670D][U+52D9]"""
        if not self.handshake_thread or not self.handshake_thread.is_alive():
            self.stop_handshake = False
            self.handshake_thread = threading.Thread(target=self._handshake_sync_loop, daemon=True)
            self.handshake_thread.start()
            print("[U+63E1][U+624B][U+670D][U+52D9][U+5DF2][U+555F][U+52D5]")
    
    def stop_handshake_service(self):
        """[U+505C][U+6B62][U+63E1][U+624B][U+670D][U+52D9]"""
        print("[U+6B63][U+5728][U+505C][U+6B62][U+63E1][U+624B][U+670D][U+52D9]...")
        self.stop_handshake = True
        if self.handshake_thread:
            self.handshake_thread.join(timeout=2)
    
    def disconnect(self):
        """[U+65B7][U+958B][U+9023][U+63A5]"""
        print("[U+6B63][U+5728][U+65B7][U+958B][U+6240][U+6709][U+9023][U+63A5]...")
        self.stop_handshake_service()
        
        if self.camera:
            print("[U+6B63][U+5728][U+95DC][U+9589][U+76F8][U+6A5F][U+9023][U+63A5]...")
            # [U+5148][U+505C][U+6B62][U+4E32][U+6D41]
            if getattr(self.camera, 'is_streaming', False):
                print("[U+505C][U+6B62][U+76F8][U+6A5F][U+4E32][U+6D41]...")
                self.camera.stop_streaming()
            # [U+7136][U+5F8C][U+65B7][U+958B][U+9023][U+63A5]
            self.camera.disconnect()
            self.camera = None
        
        if self.modbus_client:
            print("[U+6B63][U+5728][U+95DC][U+9589]Modbus[U+9023][U+63A5]...")
            self.modbus_client.close()
            self.modbus_client = None
        
        print("CCD3[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+6A21][U+7D44][U+5DF2][U+65B7][U+958B][U+9023][U+63A5]")

# Flask Web[U+61C9][U+7528]
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'ccd3_angle_detection_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# [U+5168][U+5C40][U+670D][U+52D9][U+5BE6][U+4F8B]
ccd3_service = CCD3AngleDetectionService()

@app.route('/')
def index():
    return render_template('ccd3_angle_detection.html')

@app.route('/api/modbus/set_server', methods=['POST'])
def set_modbus_server():
    data = request.json
    ip = data.get('ip', '127.0.0.1')
    port = data.get('port', 502)
    
    ccd3_service.server_ip = ip
    ccd3_service.server_port = port
    
    return jsonify({'success': True, 'message': f'Modbus[U+670D][U+52D9][U+5668][U+8A2D][U+7F6E][U+70BA] {ip}:{port}'})

@app.route('/api/modbus/connect', methods=['POST'])
def connect_modbus():
    success = ccd3_service.connect_modbus()
    if success:
        ccd3_service.start_handshake_service()
        return jsonify({'success': True, 'message': 'Modbus[U+9023][U+63A5][U+6210][U+529F][U+FF0C][U+63E1][U+624B][U+670D][U+52D9][U+5DF2][U+555F][U+52D5]'})
    else:
        return jsonify({'success': False, 'message': 'Modbus[U+9023][U+63A5][U+5931][U+6557]'})

@app.route('/api/initialize', methods=['POST'])
def initialize_camera():
    data = request.json
    ip = data.get('ip', '192.168.1.10')
    
    success = ccd3_service.initialize_camera(ip)
    message = f'[U+76F8][U+6A5F][U+521D][U+59CB][U+5316]{"[U+6210][U+529F]" if success else "[U+5931][U+6557]"}'
    
    return jsonify({'success': success, 'message': message})

@app.route('/api/capture_and_detect', methods=['POST'])
def capture_and_detect():
    data = request.json
    mode = data.get('mode', 0)
    
    result = ccd3_service.capture_and_detect_angle(mode)
    
    # [U+5C07]numpy[U+985E][U+578B][U+8F49][U+63DB][U+70BA]Python[U+539F][U+751F][U+985E][U+578B][U+4EE5][U+652F][U+63F4]JSON[U+5E8F][U+5217][U+5316]
    response_data = {
        'success': result.success,
        'center': [int(result.center[0]), int(result.center[1])] if result.center else None,
        'angle': float(result.angle) if result.angle is not None else None,
        'processing_time': float(result.processing_time),
        'capture_time': float(result.capture_time),
        'total_time': float(result.total_time)
    }
    
    if not result.success:
        response_data['error'] = result.error_message
    
    return jsonify(response_data)

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        'modbus_connected': ccd3_service.modbus_client and ccd3_service.modbus_client.connected,
        'camera_initialized': ccd3_service.state_machine.is_initialized(),
        'ready': ccd3_service.state_machine.is_ready(),
        'running': ccd3_service.state_machine.is_running(),
        'alarm': ccd3_service.state_machine.is_alarm(),
        'operation_count': ccd3_service.operation_count,
        'error_count': ccd3_service.error_count,
        'connection_count': ccd3_service.connection_count
    })

@app.route('/api/modbus/registers', methods=['GET'])
def get_registers():
    """[U+8B80][U+53D6][U+6240][U+6709][U+5BC4][U+5B58][U+5668][U+6578][U+503C]"""
    registers = {}
    
    try:
        if ccd3_service.modbus_client and ccd3_service.modbus_client.connected:
            # [U+8B80][U+53D6][U+63E1][U+624B][U+5BC4][U+5B58][U+5668] (800-801)
            result = ccd3_service.modbus_client.read_holding_registers(
                address=ccd3_service.base_address, count=2, slave=1
            )
            if not result.isError():
                registers['control_command'] = result.registers[0]
                registers['status_register'] = result.registers[1]
            
            # [U+8B80][U+53D6][U+6AA2][U+6E2C][U+53C3][U+6578] (810-819)
            result = ccd3_service.modbus_client.read_holding_registers(
                address=ccd3_service.base_address + 10, count=10, slave=1
            )
            if not result.isError():
                registers['detection_params'] = result.registers
            
            # [U+8B80][U+53D6][U+6AA2][U+6E2C][U+7D50][U+679C] (840-859)
            result = ccd3_service.modbus_client.read_holding_registers(
                address=ccd3_service.base_address + 40, count=20, slave=1
            )
            if not result.isError():
                registers['detection_results'] = result.registers
            
            # [U+8B80][U+53D6][U+7D71][U+8A08][U+8CC7][U+8A0A] (880-899)
            result = ccd3_service.modbus_client.read_holding_registers(
                address=ccd3_service.base_address + 80, count=20, slave=1
            )
            if not result.isError():
                registers['statistics'] = result.registers
                
    except Exception as e:
        print(f"[U+5BC4][U+5B58][U+5668][U+8B80][U+53D6][U+932F][U+8AA4]: {e}")
    
    return jsonify(registers)

@socketio.on('connect')
def handle_connect():
    emit('status_update', {'message': 'CCD3[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+7CFB][U+7D71][U+5DF2][U+9023][U+63A5]'})

@socketio.on('get_status')
def handle_get_status():
    status = get_status().data
    emit('status_update', status)

if __name__ == '__main__':
    print("CCD3[U+89D2][U+5EA6][U+8FA8][U+8B58][U+7CFB][U+7D71][U+555F][U+52D5][U+4E2D]...")
    print(f"[U+7CFB][U+7D71][U+67B6][U+69CB]: Modbus TCP Client - [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F]")
    print(f"[U+57FA][U+5730][U+5740]: {ccd3_service.base_address}")
    print(f"[U+76F8][U+6A5F]IP: 192.168.1.10")
    print(f"Web[U+4ECB][U+9762][U+555F][U+52D5][U+4E2D]... http://localhost:5052")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5052, debug=False)
    except KeyboardInterrupt:
        print("\n[U+6B63][U+5728][U+95DC][U+9589]CCD3[U+89D2][U+5EA6][U+6AA2][U+6E2C][U+7CFB][U+7D71]...")
        ccd3_service.disconnect()
    except Exception as e:
        print(f"[U+7CFB][U+7D71][U+932F][U+8AA4]: {e}")
        ccd3_service.disconnect()