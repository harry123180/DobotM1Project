# -*- coding: utf-8 -*-
"""
CCD1VisionCode_Enhanced.py v4.0 - CCD[U+8996][U+89BA][U+63A7][U+5236][U+7CFB][U+7D71] ([U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+7248][U+672C] + [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])
[U+5BE6][U+73FE][U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+3001][U+8F2A][U+8A62][U+5F0F][U+72C0][U+614B][U+76E3][U+63A7][U+3001][U+72C0][U+614B][U+6A5F][U+901A][U+4FE1][U+3001][U+6307][U+4EE4]/[U+72C0][U+614B][U+6A21][U+5F0F]
[U+65B0][U+589E]NPY[U+683C][U+5F0F][U+76F8][U+6A5F][U+5167][U+5916][U+53C3][U+8F09][U+5165][U+529F][U+80FD][U+3001][U+50CF][U+7D20][U+5EA7][U+6A19][U+5230][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB]
[U+9069][U+7528][U+65BC][U+81EA][U+52D5][U+5316][U+8A2D][U+5099][U+5C0D][U+63A5][U+6D41][U+7A0B]
"""

import sys
import os
import time
import threading
import json
import base64
import glob
from typing import Optional, Dict, Any, Tuple, List
import numpy as np
import cv2
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import IntEnum

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


# ==================== [U+63A7][U+5236][U+6307][U+4EE4][U+679A][U+8209] ====================
class ControlCommand(IntEnum):
    """[U+63A7][U+5236][U+6307][U+4EE4][U+679A][U+8209]"""
    CLEAR = 0          # [U+6E05][U+7A7A][U+63A7][U+5236]
    CAPTURE = 8        # [U+62CD][U+7167]
    DETECT = 16        # [U+62CD][U+7167]+[U+6AA2][U+6E2C]
    INITIALIZE = 32    # [U+91CD][U+65B0][U+521D][U+59CB][U+5316]


# ==================== [U+72C0][U+614B][U+4F4D][U+679A][U+8209] ====================
class StatusBits(IntEnum):
    """[U+72C0][U+614B][U+4F4D][U+679A][U+8209]"""
    READY = 0      # bit0: Ready[U+72C0][U+614B]
    RUNNING = 1    # bit1: Running[U+72C0][U+614B]  
    ALARM = 2      # bit2: Alarm[U+72C0][U+614B]
    INITIALIZED = 3 # bit3: [U+521D][U+59CB][U+5316][U+72C0][U+614B]


# ==================== [U+6A19][U+5B9A][U+7BA1][U+7406][U+5668] ====================
class CalibrationManager:
    """[U+76F8][U+6A5F][U+6A19][U+5B9A][U+6578][U+64DA][U+7BA1][U+7406][U+5668]"""
    
    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvec = None
        self.tvec = None
        self.transformer = None
        self.intrinsic_file = None
        self.dist_coeffs_file = None
        self.extrinsic_file = None
        self.loaded_time = None
        
    def scan_calibration_files(self) -> Dict[str, Any]:
        """[U+6383][U+63CF][U+6A19][U+5B9A][U+6A94][U+6848]"""
        try:
            # [U+6383][U+63CF][U+5167][U+53C3][U+6A94][U+6848] ([U+56B4][U+683C][U+547D][U+540D])
            intrinsic_files = glob.glob(os.path.join(self.working_dir, "camera_matrix_*.npy"))
            dist_files = glob.glob(os.path.join(self.working_dir, "dist_coeffs_*.npy"))
            
            # [U+6383][U+63CF][U+5916][U+53C3][U+6A94][U+6848] ([U+5BEC][U+9B06][U+547D][U+540D])
            extrinsic_files = glob.glob(os.path.join(self.working_dir, "*extrinsic*.npy"))
            
            # [U+914D][U+5C0D][U+5167][U+53C3][U+6A94][U+6848]
            intrinsic_pairs = []
            for matrix_file in intrinsic_files:
                basename = os.path.basename(matrix_file)
                if basename.startswith("camera_matrix_"):
                    timestamp = basename.replace("camera_matrix_", "").replace(".npy", "")
                    corresponding_dist = os.path.join(self.working_dir, f"dist_coeffs_{timestamp}.npy")
                    if corresponding_dist in dist_files:
                        intrinsic_pairs.append({
                            'camera_matrix': matrix_file,
                            'dist_coeffs': corresponding_dist,
                            'timestamp': timestamp
                        })
            
            return {
                'success': True,
                'working_dir': self.working_dir,
                'intrinsic_pairs': intrinsic_pairs,
                'extrinsic_files': extrinsic_files,
                'total_intrinsic_pairs': len(intrinsic_pairs),
                'total_extrinsic_files': len(extrinsic_files),
                'scan_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'working_dir': self.working_dir,
                'intrinsic_pairs': [],
                'extrinsic_files': [],
                'total_intrinsic_pairs': 0,
                'total_extrinsic_files': 0
            }
    
    def load_calibration_data(self, intrinsic_file: str = None, extrinsic_file: str = None) -> Dict[str, Any]:
        """[U+8F09][U+5165][U+6A19][U+5B9A][U+6578][U+64DA]"""
        try:
            scan_result = self.scan_calibration_files()
            if not scan_result['success']:
                return {
                    'success': False,
                    'error': '[U+6383][U+63CF][U+6A94][U+6848][U+5931][U+6557]',
                    'loaded': False
                }
            
            # [U+81EA][U+52D5][U+9078][U+64C7][U+6700][U+65B0][U+7684][U+5167][U+53C3][U+6A94][U+6848]
            if intrinsic_file is None and scan_result['intrinsic_pairs']:
                latest_pair = max(scan_result['intrinsic_pairs'], key=lambda x: x['timestamp'])
                intrinsic_file = latest_pair['camera_matrix']
                dist_file = latest_pair['dist_coeffs']
            else:
                # [U+627E][U+5230][U+5C0D][U+61C9][U+7684][U+7578][U+8B8A][U+4FC2][U+6578][U+6A94][U+6848]
                if intrinsic_file:
                    basename = os.path.basename(intrinsic_file)
                    if basename.startswith("camera_matrix_"):
                        timestamp = basename.replace("camera_matrix_", "").replace(".npy", "")
                        dist_file = os.path.join(self.working_dir, f"dist_coeffs_{timestamp}.npy")
                    else:
                        return {
                            'success': False,
                            'error': '[U+5167][U+53C3][U+6A94][U+6848][U+547D][U+540D][U+683C][U+5F0F][U+4E0D][U+6B63][U+78BA]',
                            'loaded': False
                        }
            
            # [U+81EA][U+52D5][U+9078][U+64C7][U+7B2C][U+4E00][U+500B][U+5916][U+53C3][U+6A94][U+6848]
            if extrinsic_file is None and scan_result['extrinsic_files']:
                extrinsic_file = scan_result['extrinsic_files'][0]
            
            if not intrinsic_file or not dist_file or not extrinsic_file:
                return {
                    'success': False,
                    'error': '[U+7F3A][U+5C11][U+5FC5][U+8981][U+7684][U+6A19][U+5B9A][U+6A94][U+6848]',
                    'loaded': False,
                    'missing': {
                        'intrinsic': not intrinsic_file,
                        'dist_coeffs': not dist_file,
                        'extrinsic': not extrinsic_file
                    }
                }
            
            # [U+8F09][U+5165][U+5167][U+53C3][U+6578][U+64DA]
            self.camera_matrix = np.load(intrinsic_file)
            self.dist_coeffs = np.load(dist_file)
            
            # [U+8F09][U+5165][U+5916][U+53C3][U+6578][U+64DA]
            extrinsic_data = np.load(extrinsic_file, allow_pickle=True)
            if isinstance(extrinsic_data, np.ndarray) and extrinsic_data.shape == ():
                extrinsic_data = extrinsic_data.item()
            
            self.rvec = extrinsic_data['rvec']
            self.tvec = extrinsic_data['tvec']
            
            # [U+9A57][U+8B49][U+6578][U+64DA][U+683C][U+5F0F]
            if self.camera_matrix.shape != (3, 3):
                raise ValueError(f"[U+5167][U+53C3][U+77E9][U+9663][U+683C][U+5F0F][U+932F][U+8AA4]: {self.camera_matrix.shape}, [U+61C9][U+70BA] (3,3)")
            
            if len(self.dist_coeffs.shape) == 2:
                self.dist_coeffs = self.dist_coeffs.flatten()
            
            if len(self.dist_coeffs) < 4:
                raise ValueError(f"[U+7578][U+8B8A][U+4FC2][U+6578][U+4E0D][U+8DB3]: {len(self.dist_coeffs)}, [U+81F3][U+5C11][U+9700][U+8981]4[U+500B]")
            
            # [U+78BA][U+4FDD][U+65CB][U+8F49][U+5411][U+91CF][U+548C][U+5E73][U+79FB][U+5411][U+91CF][U+683C][U+5F0F][U+6B63][U+78BA]
            self.rvec = np.array(self.rvec).reshape(3, 1)
            self.tvec = np.array(self.tvec).reshape(3, 1)
            
            # [U+5275][U+5EFA][U+5EA7][U+6A19][U+8F49][U+63DB][U+5668]
            self.transformer = CameraCoordinateTransformer(
                self.camera_matrix, self.dist_coeffs, self.rvec, self.tvec
            )
            
            # [U+8A18][U+9304][U+8F09][U+5165][U+4FE1][U+606F]
            self.intrinsic_file = intrinsic_file
            self.dist_coeffs_file = dist_file
            self.extrinsic_file = extrinsic_file
            self.loaded_time = datetime.now()
            
            return {
                'success': True,
                'loaded': True,
                'files': {
                    'camera_matrix': os.path.basename(intrinsic_file),
                    'dist_coeffs': os.path.basename(dist_file),
                    'extrinsic': os.path.basename(extrinsic_file)
                },
                'camera_matrix_shape': self.camera_matrix.shape,
                'dist_coeffs_count': len(self.dist_coeffs),
                'transformer_ready': self.transformer.is_valid(),
                'loaded_time': self.loaded_time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            # [U+6E05][U+7A7A][U+5DF2][U+8F09][U+5165][U+7684][U+6578][U+64DA]
            self.camera_matrix = None
            self.dist_coeffs = None
            self.rvec = None
            self.tvec = None
            self.transformer = None
            
            return {
                'success': False,
                'error': str(e),
                'loaded': False
            }
    
    def get_status(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+6A19][U+5B9A][U+72C0][U+614B]"""
        return {
            'calibration_loaded': self.is_calibration_loaded(),
            'transformer_ready': self.transformer.is_valid() if self.transformer else False,
            'working_dir': self.working_dir,
            'files': {
                'camera_matrix': os.path.basename(self.intrinsic_file) if self.intrinsic_file else None,
                'dist_coeffs': os.path.basename(self.dist_coeffs_file) if self.dist_coeffs_file else None,
                'extrinsic': os.path.basename(self.extrinsic_file) if self.extrinsic_file else None
            },
            'loaded_time': self.loaded_time.strftime("%Y-%m-%d %H:%M:%S") if self.loaded_time else None,
            'camera_matrix_shape': self.camera_matrix.shape if self.camera_matrix is not None else None,
            'dist_coeffs_count': len(self.dist_coeffs) if self.dist_coeffs is not None else None
        }
    
    def is_calibration_loaded(self) -> bool:
        """[U+6AA2][U+67E5][U+6A19][U+5B9A][U+6578][U+64DA][U+662F][U+5426][U+5DF2][U+8F09][U+5165]"""
        return (self.camera_matrix is not None and 
                self.dist_coeffs is not None and 
                self.rvec is not None and 
                self.tvec is not None)


# ==================== [U+5EA7][U+6A19][U+8F49][U+63DB][U+5668] ====================
class CameraCoordinateTransformer:
    """[U+76F8][U+6A5F][U+5EA7][U+6A19][U+8F49][U+63DB][U+5668]"""
    
    def __init__(self, camera_matrix, dist_coeffs, rvec, tvec):
        self.K = camera_matrix
        self.D = dist_coeffs
        self.rvec = rvec.reshape(3, 1)
        self.tvec = tvec.reshape(3, 1)
        
        # [U+8A08][U+7B97][U+65CB][U+8F49][U+77E9][U+9663]
        self.R, _ = cv2.Rodrigues(self.rvec)
        self.R_inv = np.linalg.inv(self.R)
        self.K_inv = np.linalg.inv(self.K)
        
    def pixel_to_world(self, pixel_coords_list) -> Optional[List[Tuple[float, float]]]:
        """[U+5C07][U+50CF][U+7D20][U+5EA7][U+6A19][U+8F49][U+63DB][U+70BA][U+4E16][U+754C][U+5EA7][U+6A19] (Z=0[U+5E73][U+9762][U+6295][U+5F71])"""
        try:
            if not self.is_valid():
                return None
            
            world_coords_list = []
            
            for pixel_coords in pixel_coords_list:
                # [U+78BA][U+4FDD][U+8F38][U+5165][U+683C][U+5F0F][U+6B63][U+78BA]
                if len(pixel_coords) != 2:
                    world_coords_list.append((0.0, 0.0))
                    continue
                
                # [U+8F49][U+63DB][U+70BA]numpy[U+9663][U+5217][U+683C][U+5F0F][U+FF0C][U+9069][U+914D]cv2.undistortPoints
                pixel_point = np.array([[pixel_coords]], dtype=np.float32)
                
                # [U+53BB][U+7578][U+8B8A][U+8655][U+7406]
                undistorted_point = cv2.undistortPoints(pixel_point, self.K, self.D, P=self.K)
                u, v = undistorted_point[0, 0]
                
                # [U+6B78][U+4E00][U+5316][U+5EA7][U+6A19]
                normalized_coords = self.K_inv @ np.array([u, v, 1.0])
                
                # [U+8A08][U+7B97][U+6DF1][U+5EA6][U+4FC2][U+6578] s (Z=0[U+5E73][U+9762][U+6295][U+5F71])
                denominator = self.R[2] @ normalized_coords
                if abs(denominator) < 1e-6:
                    # [U+907F][U+514D][U+9664][U+4EE5][U+96F6]
                    world_coords_list.append((0.0, 0.0))
                    continue
                
                s = (0 - self.tvec[2, 0]) / denominator
                
                # [U+8A08][U+7B97][U+76F8][U+6A5F][U+5EA7][U+6A19][U+7CFB][U+4E2D][U+7684]3D[U+9EDE]
                camera_point = s * normalized_coords
                
                # [U+8F49][U+63DB][U+5230][U+4E16][U+754C][U+5EA7][U+6A19][U+7CFB]
                world_point = self.R_inv @ (camera_point - self.tvec.ravel())
                
                # [U+8FD4][U+56DE]X, Y[U+5EA7][U+6A19] ([U+4FDD][U+7559]2[U+4F4D][U+5C0F][U+6578])
                world_x = round(world_point[0], 2)
                world_y = round(world_point[1], 2)
                
                world_coords_list.append((world_x, world_y))
            
            return world_coords_list
            
        except Exception as e:
            print(f"[FAIL] [U+5EA7][U+6A19][U+8F49][U+63DB][U+5931][U+6557]: {e}")
            return None
    
    def is_valid(self) -> bool:
        """[U+6AA2][U+67E5][U+8F49][U+63DB][U+5668][U+662F][U+5426][U+6709][U+6548]"""
        return (self.K is not None and 
                self.D is not None and 
                self.rvec is not None and 
                self.tvec is not None)


# ==================== [U+7CFB][U+7D71][U+72C0][U+614B][U+7BA1][U+7406] ====================
class SystemStateMachine:
    """[U+7CFB][U+7D71][U+72C0][U+614B][U+6A5F][U+7BA1][U+7406]"""
    
    def __init__(self):
        self.status_register = 0b0000  # 4[U+4F4D][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
        self.lock = threading.Lock()
        
    def get_bit(self, bit_pos: StatusBits) -> bool:
        """[U+7372][U+53D6][U+6307][U+5B9A][U+4F4D][U+7684][U+72C0][U+614B]"""
        with self.lock:
            return bool(self.status_register & (1 << bit_pos))
    
    def set_bit(self, bit_pos: StatusBits, value: bool):
        """[U+8A2D][U+7F6E][U+6307][U+5B9A][U+4F4D][U+7684][U+72C0][U+614B]"""
        with self.lock:
            if value:
                self.status_register |= (1 << bit_pos)
            else:
                self.status_register &= ~(1 << bit_pos)
    
    def get_status_register(self) -> int:
        """[U+7372][U+53D6][U+5B8C][U+6574][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+503C]"""
        with self.lock:
            return self.status_register
    
    def is_ready(self) -> bool:
        """[U+6AA2][U+67E5][U+662F][U+5426]Ready[U+72C0][U+614B]"""
        return self.get_bit(StatusBits.READY)
    
    def is_running(self) -> bool:
        """[U+6AA2][U+67E5][U+662F][U+5426]Running[U+72C0][U+614B]"""
        return self.get_bit(StatusBits.RUNNING)
    
    def is_alarm(self) -> bool:
        """[U+6AA2][U+67E5][U+662F][U+5426]Alarm[U+72C0][U+614B]"""
        return self.get_bit(StatusBits.ALARM)
    
    def is_initialized(self) -> bool:
        """[U+6AA2][U+67E5][U+662F][U+5426][U+5DF2][U+521D][U+59CB][U+5316]"""
        return self.get_bit(StatusBits.INITIALIZED)
    
    def set_ready(self, ready: bool = True):
        """[U+8A2D][U+7F6E]Ready[U+72C0][U+614B]"""
        self.set_bit(StatusBits.READY, ready)
    
    def set_running(self, running: bool = True):
        """[U+8A2D][U+7F6E]Running[U+72C0][U+614B]"""
        self.set_bit(StatusBits.RUNNING, running)
    
    def set_alarm(self, alarm: bool = True):
        """[U+8A2D][U+7F6E]Alarm[U+72C0][U+614B]"""
        self.set_bit(StatusBits.ALARM, alarm)
        if alarm:
            # Alarm[U+6642][U+FF0C][U+521D][U+59CB][U+5316][U+72C0][U+614B][U+8A2D][U+70BA]0
            self.set_bit(StatusBits.INITIALIZED, False)
    
    def set_initialized(self, initialized: bool = True):
        """[U+8A2D][U+7F6E][U+521D][U+59CB][U+5316][U+72C0][U+614B]"""
        self.set_bit(StatusBits.INITIALIZED, initialized)
    
    def reset_to_idle(self):
        """[U+91CD][U+7F6E][U+5230][U+7A7A][U+9592][U+72C0][U+614B]"""
        with self.lock:
            self.status_register = 0b0001  # [U+53EA][U+4FDD][U+7559]Ready=1[U+FF0C][U+5176][U+4ED6][U+4F4D][U+6E05][U+96F6]
    
    def get_status_description(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+72C0][U+614B][U+63CF][U+8FF0]"""
        return {
            'ready': self.is_ready(),
            'running': self.is_running(),
            'alarm': self.is_alarm(),
            'initialized': self.is_initialized(),
            'status_register': self.get_status_register(),
            'binary_representation': f"{self.get_status_register():04b}"
        }


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
    """[U+8996][U+89BA][U+8FA8][U+8B58][U+7D50][U+679C] (v4.0[U+64F4][U+5C55])"""
    circle_count: int
    circles: List[Dict[str, Any]]
    processing_time: float
    capture_time: float
    total_time: float
    timestamp: str
    success: bool
    has_world_coords: bool = False  # [U+65B0][U+589E]: [U+4E16][U+754C][U+5EA7][U+6A19][U+6709][U+6548][U+6027]
    error_message: Optional[str] = None


class EnhancedModbusTcpClientService:
    """[U+589E][U+5F37][U+578B]Modbus TCP Client[U+670D][U+52D9] - [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+7248][U+672C] (v4.0)"""
    
    def __init__(self, server_ip="192.168.1.100", server_port=502):
        self.server_ip = server_ip
        self.server_port = server_port
        self.client: Optional[ModbusTcpClient] = None
        self.connected = False
        self.vision_controller = None
        
        # [U+72C0][U+614B][U+6A5F][U+7BA1][U+7406]
        self.state_machine = SystemStateMachine()
        
        # [U+9023][U+63A5][U+53C3][U+6578]
        self.reconnect_delay = 5.0
        self.read_timeout = 3.0
        self.write_timeout = 3.0
        
        # [U+540C][U+6B65][U+63A7][U+5236]
        self.sync_enabled = False
        self.sync_thread = None
        self.sync_running = False
        self.sync_interval = 0.05  # 50ms[U+8F2A][U+8A62][U+9593][U+9694][U+FF0C][U+66F4][U+5FEB][U+97FF][U+61C9]
        
        # [U+63E1][U+624B][U+63A7][U+5236]
        self.last_control_command = 0
        self.command_processing = False
        
        # [U+65B0][U+7684][U+5BC4][U+5B58][U+5668][U+6620][U+5C04] ([U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F] v4.0)
        self.REGISTERS = {
            # ===== [U+6838][U+5FC3][U+63A7][U+5236][U+63E1][U+624B][U+5BC4][U+5B58][U+5668] =====
            'CONTROL_COMMAND': 200,        # [U+63A7][U+5236][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668] (0=[U+6E05][U+7A7A], 8=[U+62CD][U+7167], 16=[U+62CD][U+7167]+[U+6AA2][U+6E2C], 32=[U+91CD][U+65B0][U+521D][U+59CB][U+5316])
            'STATUS_REGISTER': 201,        # [U+72C0][U+614B][U+5BC4][U+5B58][U+5668] (bit0=Ready, bit1=Running, bit2=Alarm, bit3=Initialized)
            
            # ===== [U+6AA2][U+6E2C][U+53C3][U+6578][U+5BC4][U+5B58][U+5668] (210-219) =====
            'MIN_AREA_HIGH': 210,          # [U+6700][U+5C0F][U+9762][U+7A4D][U+8A2D][U+5B9A] ([U+9AD8]16[U+4F4D])
            'MIN_AREA_LOW': 211,           # [U+6700][U+5C0F][U+9762][U+7A4D][U+8A2D][U+5B9A] ([U+4F4E]16[U+4F4D])
            'MIN_ROUNDNESS': 212,          # [U+6700][U+5C0F][U+5713][U+5EA6][U+8A2D][U+5B9A] ([U+4E58][U+4EE5]1000)
            'GAUSSIAN_KERNEL': 213,        # [U+9AD8][U+65AF][U+6838][U+5927][U+5C0F]
            'CANNY_LOW': 214,              # Canny[U+4F4E][U+95BE][U+503C]
            'CANNY_HIGH': 215,             # Canny[U+9AD8][U+95BE][U+503C]
            
            # ===== [U+50CF][U+7D20][U+5EA7][U+6A19][U+6AA2][U+6E2C][U+7D50][U+679C][U+5BC4][U+5B58][U+5668] (240-255) =====
            'CIRCLE_COUNT': 240,           # [U+6AA2][U+6E2C][U+5230][U+7684][U+5713][U+5F62][U+6578][U+91CF]
            'CIRCLE_1_X': 241,             # [U+5713][U+5F62]1 X[U+5EA7][U+6A19]
            'CIRCLE_1_Y': 242,             # [U+5713][U+5F62]1 Y[U+5EA7][U+6A19]
            'CIRCLE_1_RADIUS': 243,        # [U+5713][U+5F62]1 [U+534A][U+5F91]
            'CIRCLE_2_X': 244,             # [U+5713][U+5F62]2 X[U+5EA7][U+6A19]
            'CIRCLE_2_Y': 245,             # [U+5713][U+5F62]2 Y[U+5EA7][U+6A19]
            'CIRCLE_2_RADIUS': 246,        # [U+5713][U+5F62]2 [U+534A][U+5F91]
            'CIRCLE_3_X': 247,             # [U+5713][U+5F62]3 X[U+5EA7][U+6A19]
            'CIRCLE_3_Y': 248,             # [U+5713][U+5F62]3 Y[U+5EA7][U+6A19]
            'CIRCLE_3_RADIUS': 249,        # [U+5713][U+5F62]3 [U+534A][U+5F91]
            'CIRCLE_4_X': 250,             # [U+5713][U+5F62]4 X[U+5EA7][U+6A19]
            'CIRCLE_4_Y': 251,             # [U+5713][U+5F62]4 Y[U+5EA7][U+6A19]
            'CIRCLE_4_RADIUS': 252,        # [U+5713][U+5F62]4 [U+534A][U+5F91]
            'CIRCLE_5_X': 253,             # [U+5713][U+5F62]5 X[U+5EA7][U+6A19]
            'CIRCLE_5_Y': 254,             # [U+5713][U+5F62]5 Y[U+5EA7][U+6A19]
            'CIRCLE_5_RADIUS': 255,        # [U+5713][U+5F62]5 [U+534A][U+5F91]
            
            # ===== [U+4E16][U+754C][U+5EA7][U+6A19][U+6AA2][U+6E2C][U+7D50][U+679C][U+5BC4][U+5B58][U+5668] (256-275) v4.0[U+65B0][U+589E] =====
            'WORLD_COORD_VALID': 256,      # [U+4E16][U+754C][U+5EA7][U+6A19][U+6709][U+6548][U+6A19][U+8A8C] (0=[U+7121][U+6548], 1=[U+6709][U+6548])
            'CIRCLE_1_WORLD_X_HIGH': 257,  # [U+5713][U+5F62]1[U+4E16][U+754C]X[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_1_WORLD_X_LOW': 258,   # [U+5713][U+5F62]1[U+4E16][U+754C]X[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_1_WORLD_Y_HIGH': 259,  # [U+5713][U+5F62]1[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_1_WORLD_Y_LOW': 260,   # [U+5713][U+5F62]1[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_2_WORLD_X_HIGH': 261,  # [U+5713][U+5F62]2[U+4E16][U+754C]X[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_2_WORLD_X_LOW': 262,   # [U+5713][U+5F62]2[U+4E16][U+754C]X[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_2_WORLD_Y_HIGH': 263,  # [U+5713][U+5F62]2[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_2_WORLD_Y_LOW': 264,   # [U+5713][U+5F62]2[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_3_WORLD_X_HIGH': 265,  # [U+5713][U+5F62]3[U+4E16][U+754C]X[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_3_WORLD_X_LOW': 266,   # [U+5713][U+5F62]3[U+4E16][U+754C]X[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_3_WORLD_Y_HIGH': 267,  # [U+5713][U+5F62]3[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_3_WORLD_Y_LOW': 268,   # [U+5713][U+5F62]3[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_4_WORLD_X_HIGH': 269,  # [U+5713][U+5F62]4[U+4E16][U+754C]X[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_4_WORLD_X_LOW': 270,   # [U+5713][U+5F62]4[U+4E16][U+754C]X[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_4_WORLD_Y_HIGH': 271,  # [U+5713][U+5F62]4[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_4_WORLD_Y_LOW': 272,   # [U+5713][U+5F62]4[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_5_WORLD_X_HIGH': 273,  # [U+5713][U+5F62]5[U+4E16][U+754C]X[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_5_WORLD_X_LOW': 274,   # [U+5713][U+5F62]5[U+4E16][U+754C]X[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            'CIRCLE_5_WORLD_Y_HIGH': 275,  # [U+5713][U+5F62]5[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+9AD8][U+4F4D]
            'CIRCLE_5_WORLD_Y_LOW': 276,   # [U+5713][U+5F62]5[U+4E16][U+754C]Y[U+5EA7][U+6A19][U+4F4E][U+4F4D]
            
            # ===== [U+7D71][U+8A08][U+8CC7][U+8A0A][U+5BC4][U+5B58][U+5668] (280-299) =====
            'LAST_CAPTURE_TIME': 280,      # [U+6700][U+5F8C][U+62CD][U+7167][U+8017][U+6642] (ms)
            'LAST_PROCESS_TIME': 281,      # [U+6700][U+5F8C][U+8655][U+7406][U+8017][U+6642] (ms)
            'LAST_TOTAL_TIME': 282,        # [U+6700][U+5F8C][U+7E3D][U+8017][U+6642] (ms)
            'OPERATION_COUNT': 283,        # [U+64CD][U+4F5C][U+8A08][U+6578][U+5668]
            'ERROR_COUNT': 284,            # [U+932F][U+8AA4][U+8A08][U+6578][U+5668]
            'CONNECTION_COUNT': 285,       # [U+9023][U+63A5][U+8A08][U+6578][U+5668]
            'VERSION_MAJOR': 290,          # [U+8EDF][U+9AD4][U+7248][U+672C][U+4E3B][U+7248][U+865F] (v4.0)
            'VERSION_MINOR': 291,          # [U+8EDF][U+9AD4][U+7248][U+672C][U+6B21][U+7248][U+865F]
            'UPTIME_HOURS': 292,           # [U+7CFB][U+7D71][U+904B][U+884C][U+6642][U+9593] ([U+5C0F][U+6642])
            'UPTIME_MINUTES': 293,         # [U+7CFB][U+7D71][U+904B][U+884C][U+6642][U+9593] ([U+5206][U+9418])
        }
        
        # [U+7D71][U+8A08][U+8A08][U+6578]
        self.operation_count = 0
        self.error_count = 0
        self.connection_count = 0
        self.start_time = time.time()
    
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
            self.state_machine.set_alarm(True)
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
            
            if self.client.connect():
                self.connected = True
                self.connection_count += 1
                
                # [U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
                self._initialize_status_registers()
                
                # [U+6AA2][U+67E5][U+76F8][U+6A5F][U+72C0][U+614B][U+4E26][U+8A2D][U+7F6E][U+521D][U+59CB][U+5316][U+4F4D]
                self._update_initialization_status()
                
                print(f"[OK] Modbus TCP Client[U+9023][U+63A5][U+6210][U+529F]: {self.server_ip}:{self.server_port}")
                return True
            else:
                print(f"[FAIL] Modbus TCP[U+9023][U+63A5][U+5931][U+6557]: {self.server_ip}:{self.server_port}")
                self.connected = False
                self.state_machine.set_alarm(True)
                return False
                
        except Exception as e:
            print(f"[FAIL] Modbus TCP[U+9023][U+63A5][U+7570][U+5E38]: {e}")
            self.connected = False
            self.state_machine.set_alarm(True)
            return False
    
    def disconnect(self):
        """[U+65B7][U+958B]Modbus[U+9023][U+63A5]"""
        self.stop_handshake_sync()
        
        if self.client and self.connected:
            try:
                # [U+8A2D][U+7F6E][U+65B7][U+7DDA][U+72C0][U+614B]
                self.state_machine.set_alarm(True)
                self.write_register('STATUS_REGISTER', self.state_machine.get_status_register())
                
                self.client.close()
                print("[U+1F50C] Modbus TCP Client[U+5DF2][U+65B7][U+958B][U+9023][U+63A5]")
            except:
                pass
        
        self.connected = False
        self.client = None
    
    def start_handshake_sync(self):
        """[U+555F][U+52D5][U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B]"""
        if self.sync_running:
            return
        
        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._handshake_sync_loop, daemon=True)
        self.sync_thread.start()
        print("[OK] [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+555F][U+52D5]")
    
    def stop_handshake_sync(self):
        """[U+505C][U+6B62][U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B]"""
        if self.sync_running:
            self.sync_running = False
            if self.sync_thread and self.sync_thread.is_alive():
                self.sync_thread.join(timeout=2.0)
            print("[U+1F6D1] [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+505C][U+6B62]")
    
    def _handshake_sync_loop(self):
        """[U+63E1][U+624B][U+540C][U+6B65][U+5FAA][U+74B0] - [U+9AD8][U+983B][U+8F2A][U+8A62][U+5F0F][U+72C0][U+614B][U+76E3][U+63A7]"""
        print("[U+1F504] [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B][U+958B][U+59CB][U+904B][U+884C]...")
        
        while self.sync_running and self.connected:
            try:
                # 1. [U+66F4][U+65B0][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+5230]PLC
                self._update_status_to_plc()
                
                # 2. [U+8B80][U+53D6][U+63A7][U+5236][U+6307][U+4EE4][U+4E26][U+8655][U+7406][U+63E1][U+624B][U+908F][U+8F2F]
                self._process_handshake_control()
                
                # 3. [U+5B9A][U+671F][U+66F4][U+65B0][U+7D71][U+8A08][U+8CC7][U+8A0A][U+548C][U+7CFB][U+7D71][U+72C0][U+614B]
                self._update_system_statistics()
                
                # 4. [U+66F4][U+65B0][U+4E16][U+754C][U+5EA7][U+6A19][U+6709][U+6548][U+6027][U+6A19][U+8A8C] (v4.0[U+65B0][U+589E])
                self._update_world_coord_status()
                
                # [U+77ED][U+66AB][U+4F11][U+7720] (50ms[U+8F2A][U+8A62][U+9593][U+9694])
                time.sleep(self.sync_interval)
                
            except ConnectionException:
                print("[FAIL] Modbus[U+9023][U+63A5][U+4E2D][U+65B7][U+FF0C][U+540C][U+6B65][U+7DDA][U+7A0B][U+9000][U+51FA]")
                self.connected = False
                self.state_machine.set_alarm(True)
                break
                
            except Exception as e:
                print(f"[FAIL] [U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B][U+932F][U+8AA4]: {e}")
                self.error_count += 1
                time.sleep(0.5)  # [U+932F][U+8AA4][U+6642][U+7A0D][U+9577][U+4F11][U+7720]
        
        self.sync_running = False
        print("[U+23F9][U+FE0F] [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B][U+5DF2][U+9000][U+51FA]")
    
    def _process_handshake_control(self):
        """[U+8655][U+7406][U+63E1][U+624B][U+63A7][U+5236][U+908F][U+8F2F]"""
        try:
            # [U+8B80][U+53D6][U+63A7][U+5236][U+6307][U+4EE4]
            control_command = self.read_register('CONTROL_COMMAND')
            if control_command is None:
                return
            
            # [U+6AA2][U+67E5][U+662F][U+5426][U+6709][U+65B0][U+7684][U+63A7][U+5236][U+6307][U+4EE4]
            if control_command != self.last_control_command:
                print(f"[U+1F3AF] [U+6536][U+5230][U+65B0][U+63A7][U+5236][U+6307][U+4EE4]: {control_command} ([U+4E0A][U+6B21]: {self.last_control_command})")
                
                # [U+6839][U+64DA][U+63A7][U+5236][U+6307][U+4EE4][U+8655][U+7406]
                if control_command == ControlCommand.CLEAR:
                    self._handle_clear_command()
                elif control_command in [ControlCommand.CAPTURE, ControlCommand.DETECT, ControlCommand.INITIALIZE]:
                    self._handle_action_command(control_command)
                
                self.last_control_command = control_command
            
            # [U+6AA2][U+67E5]Running[U+72C0][U+614B][U+5B8C][U+6210][U+5F8C][U+7684]Ready[U+6062][U+5FA9][U+908F][U+8F2F]
            if (not self.state_machine.is_running() and 
                control_command == ControlCommand.CLEAR and
                not self.command_processing):
                
                if not self.state_machine.is_ready() and not self.state_machine.is_alarm():
                    print("[U+1F7E2] [U+6062][U+5FA9]Ready[U+72C0][U+614B]")
                    self.state_machine.set_ready(True)
                    
        except Exception as e:
            print(f"[FAIL] [U+8655][U+7406][U+63E1][U+624B][U+63A7][U+5236][U+5931][U+6557]: {e}")
            self.error_count += 1
    
    def _handle_clear_command(self):
        """[U+8655][U+7406][U+6E05][U+7A7A][U+63A7][U+5236][U+6307][U+4EE4]"""
        if self.command_processing:
            return  # [U+6B63][U+5728][U+8655][U+7406][U+6307][U+4EE4][U+FF0C][U+4E0D][U+8655][U+7406][U+6E05][U+7A7A]
            
        # [U+6E05][U+7A7A][U+63A7][U+5236][U+6307][U+4EE4][U+4E0D][U+9700][U+8981]Ready[U+6AA2][U+67E5][U+FF0C][U+76F4][U+63A5][U+6E05][U+7A7A][U+76F8][U+95DC][U+72C0][U+614B]
        print("[U+1F5D1][U+FE0F] [U+8655][U+7406][U+6E05][U+7A7A][U+63A7][U+5236][U+6307][U+4EE4]")
        # [U+9019][U+88E1][U+4E0D][U+8A2D][U+7F6E][U+4EFB][U+4F55][U+72C0][U+614B][U+FF0C][U+7B49][U+5F85][U+63E1][U+624B][U+908F][U+8F2F][U+81EA][U+7136][U+6062][U+5FA9]Ready
    
    def _handle_action_command(self, command: ControlCommand):
        """[U+8655][U+7406][U+52D5][U+4F5C][U+6307][U+4EE4] ([U+62CD][U+7167][U+3001][U+6AA2][U+6E2C][U+3001][U+521D][U+59CB][U+5316])"""
        # [U+6AA2][U+67E5]Ready[U+72C0][U+614B]
        if not self.state_machine.is_ready():
            print(f"[WARN][U+FE0F] [U+7CFB][U+7D71][U+672A]Ready[U+FF0C][U+5FFD][U+7565][U+63A7][U+5236][U+6307][U+4EE4] {command}")
            return
        
        if self.command_processing:
            print(f"[WARN][U+FE0F] [U+6B63][U+5728][U+8655][U+7406][U+6307][U+4EE4][U+FF0C][U+5FFD][U+7565][U+65B0][U+6307][U+4EE4] {command}")
            return
        
        # [U+8A2D][U+7F6E]Running[U+72C0][U+614B][U+FF0C][U+6E05][U+9664]Ready[U+72C0][U+614B]
        print(f"[U+1F680] [U+958B][U+59CB][U+8655][U+7406][U+63A7][U+5236][U+6307][U+4EE4]: {command}")
        self.state_machine.set_ready(False)
        self.state_machine.set_running(True)
        self.command_processing = True
        
        # [U+5728][U+7368][U+7ACB][U+7DDA][U+7A0B][U+4E2D][U+57F7][U+884C][U+547D][U+4EE4][U+FF0C][U+907F][U+514D][U+963B][U+585E][U+540C][U+6B65][U+5FAA][U+74B0]
        command_thread = threading.Thread(
            target=self._execute_command_async,
            args=(command,),
            daemon=True
        )
        command_thread.start()
    
    def _execute_command_async(self, command: ControlCommand):
        """[U+7570][U+6B65][U+57F7][U+884C][U+63A7][U+5236][U+6307][U+4EE4]"""
        try:
            if command == ControlCommand.CAPTURE:
                self._execute_capture()
            elif command == ControlCommand.DETECT:
                self._execute_detect()
            elif command == ControlCommand.INITIALIZE:
                self._execute_initialize()
            
        except Exception as e:
            print(f"[FAIL] [U+57F7][U+884C][U+63A7][U+5236][U+6307][U+4EE4][U+5931][U+6557]: {e}")
            self.error_count += 1
            self.state_machine.set_alarm(True)
        
        finally:
            # [U+7121][U+8AD6][U+6210][U+529F][U+5931][U+6557][U+FF0C][U+90FD][U+8981][U+6E05][U+9664]Running[U+72C0][U+614B]
            print(f"[OK] [U+63A7][U+5236][U+6307][U+4EE4] {command} [U+57F7][U+884C][U+5B8C][U+6210]")
            self.state_machine.set_running(False)
            self.command_processing = False
            self.operation_count += 1
    
    def _execute_capture(self):
        """[U+57F7][U+884C][U+62CD][U+7167][U+6307][U+4EE4]"""
        if not self.vision_controller:
            raise Exception("[U+8996][U+89BA][U+63A7][U+5236][U+5668][U+672A][U+8A2D][U+7F6E]")
        
        print("[U+1F4F8] [U+57F7][U+884C][U+62CD][U+7167][U+6307][U+4EE4]")
        image, capture_time = self.vision_controller.capture_image()
        
        if image is not None:
            self.write_register('LAST_CAPTURE_TIME', int(capture_time * 1000))
            print(f"[OK] [U+62CD][U+7167][U+6210][U+529F][U+FF0C][U+8017][U+6642]: {capture_time*1000:.2f}ms")
        else:
            raise Exception("[U+62CD][U+7167][U+5931][U+6557]")
    
    def _execute_detect(self):
        """[U+57F7][U+884C][U+62CD][U+7167]+[U+6AA2][U+6E2C][U+6307][U+4EE4] ([U+542B][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])"""
        if not self.vision_controller:
            raise Exception("[U+8996][U+89BA][U+63A7][U+5236][U+5668][U+672A][U+8A2D][U+7F6E]")
        
        print("[U+1F50D] [U+57F7][U+884C][U+62CD][U+7167]+[U+6AA2][U+6E2C][U+6307][U+4EE4] ([U+542B][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])")
        result = self.vision_controller.capture_and_detect()
        
        if result.success:
            self.update_detection_results(result)
            coord_info = "[U+542B][U+4E16][U+754C][U+5EA7][U+6A19]" if result.has_world_coords else "[U+50C5][U+50CF][U+7D20][U+5EA7][U+6A19]"
            print(f"[OK] [U+6AA2][U+6E2C][U+6210][U+529F][U+FF0C][U+627E][U+5230] {result.circle_count} [U+500B][U+5713][U+5F62] ({coord_info})")
        else:
            raise Exception(f"[U+6AA2][U+6E2C][U+5931][U+6557]: {result.error_message}")
    
    def _execute_initialize(self):
        """[U+57F7][U+884C][U+91CD][U+65B0][U+521D][U+59CB][U+5316][U+6307][U+4EE4]"""
        print("[U+1F504] [U+57F7][U+884C][U+91CD][U+65B0][U+521D][U+59CB][U+5316][U+6307][U+4EE4]")
        
        # [U+6E05][U+9664]Alarm[U+72C0][U+614B]
        self.state_machine.set_alarm(False)
        
        # [U+91CD][U+65B0][U+521D][U+59CB][U+5316][U+76F8][U+6A5F]
        if self.vision_controller:
            init_result = self.vision_controller.initialize_camera()
            if not init_result.get('success', False):
                raise Exception("[U+76F8][U+6A5F][U+521D][U+59CB][U+5316][U+5931][U+6557]")
        
        # [U+66F4][U+65B0][U+521D][U+59CB][U+5316][U+72C0][U+614B]
        self._update_initialization_status()
        
        print("[OK] [U+91CD][U+65B0][U+521D][U+59CB][U+5316][U+5B8C][U+6210]")
    
    def _initialize_status_registers(self):
        """[U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]"""
        try:
            # [U+5BEB][U+5165][U+7248][U+672C][U+8CC7][U+8A0A] (v4.0)
            self.write_register('VERSION_MAJOR', 4)  # [U+7248][U+672C][U+5347][U+7D1A][U+5230]4.0
            self.write_register('VERSION_MINOR', 0)
            
            # [U+5F37][U+5236][U+91CD][U+7F6E][U+72C0][U+614B][U+6A5F][U+5230][U+521D][U+59CB][U+72C0][U+614B]
            self.state_machine.reset_to_idle()
            
            # [U+78BA][U+4FDD][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+56FA][U+5B9A][U+70BA][U+521D][U+59CB][U+503C]
            initial_status = 0b0001  # Ready=1, [U+5176][U+4ED6][U+4F4D]=0[U+FF0C][U+78BA][U+4FDD][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+503C][U+70BA]1
            self.state_machine.status_register = initial_status
            
            # [U+5BEB][U+5165][U+56FA][U+5B9A][U+7684][U+521D][U+59CB][U+72C0][U+614B][U+5230]PLC
            self.write_register('STATUS_REGISTER', initial_status)
            self.write_register('CONTROL_COMMAND', 0)  # [U+6E05][U+7A7A][U+63A7][U+5236][U+6307][U+4EE4]
            
            # [U+521D][U+59CB][U+5316][U+8A08][U+6578][U+5668]
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            self.write_register('CONNECTION_COUNT', self.connection_count)
            
            # [U+521D][U+59CB][U+5316][U+4E16][U+754C][U+5EA7][U+6A19][U+76F8][U+95DC][U+5BC4][U+5B58][U+5668] (v4.0[U+65B0][U+589E])
            self.write_register('WORLD_COORD_VALID', 0)  # [U+521D][U+59CB][U+70BA][U+7121][U+6548]
            
            print(f"[U+1F4CA] [U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+521D][U+59CB][U+5316][U+5B8C][U+6210][U+FF0C][U+56FA][U+5B9A][U+521D][U+59CB][U+503C]: {initial_status} (Ready=1)")
            
        except Exception as e:
            print(f"[FAIL] [U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {e}")
    
    def _update_status_to_plc(self):
        """[U+66F4][U+65B0][U+72C0][U+614B][U+5230]PLC"""
        try:
            # [U+66F4][U+65B0][U+72C0][U+614B][U+5BC4][U+5B58][U+5668]
            status_value = self.state_machine.get_status_register()
            self.write_register('STATUS_REGISTER', status_value)
            
            # [U+66F4][U+65B0][U+8A08][U+6578][U+5668]
            self.write_register('OPERATION_COUNT', self.operation_count)
            self.write_register('ERROR_COUNT', self.error_count)
            
        except Exception as e:
            print(f"[FAIL] [U+66F4][U+65B0][U+72C0][U+614B][U+5230]PLC[U+5931][U+6557]: {e}")
    
    def _update_system_statistics(self):
        """[U+66F4][U+65B0][U+7CFB][U+7D71][U+7D71][U+8A08][U+8CC7][U+8A0A]"""
        try:
            # [U+66F4][U+65B0][U+904B][U+884C][U+6642][U+9593]
            uptime_total_minutes = int((time.time() - self.start_time) / 60)
            uptime_hours = uptime_total_minutes // 60
            uptime_minutes = uptime_total_minutes % 60
            
            self.write_register('UPTIME_HOURS', uptime_hours)
            self.write_register('UPTIME_MINUTES', uptime_minutes)
            
        except Exception as e:
            pass  # [U+7D71][U+8A08][U+66F4][U+65B0][U+5931][U+6557][U+4E0D][U+5F71][U+97FF][U+4E3B][U+6D41][U+7A0B]
    
    def _update_world_coord_status(self):
        """[U+66F4][U+65B0][U+4E16][U+754C][U+5EA7][U+6A19][U+6709][U+6548][U+6027][U+6A19][U+8A8C] (v4.0[U+65B0][U+589E])"""
        try:
            if (self.vision_controller and 
                self.vision_controller.calibration_manager and
                self.vision_controller.calibration_manager.is_calibration_loaded() and
                self.vision_controller.calibration_manager.transformer and
                self.vision_controller.calibration_manager.transformer.is_valid()):
                self.write_register('WORLD_COORD_VALID', 1)
            else:
                self.write_register('WORLD_COORD_VALID', 0)
        except:
            pass  # [U+72C0][U+614B][U+66F4][U+65B0][U+5931][U+6557][U+4E0D][U+5F71][U+97FF][U+4E3B][U+6D41][U+7A0B]
    
    def _update_initialization_status(self):
        """[U+66F4][U+65B0][U+521D][U+59CB][U+5316][U+72C0][U+614B]"""
        try:
            # [U+6AA2][U+67E5][U+7CFB][U+7D71][U+521D][U+59CB][U+5316][U+72C0][U+614B]
            modbus_ok = self.connected
            camera_ok = (self.vision_controller and 
                        self.vision_controller.is_connected)
            
            if modbus_ok and camera_ok:
                # [U+7CFB][U+7D71][U+5B8C][U+5168][U+521D][U+59CB][U+5316][U+FF1A]Ready=1, Initialized=1, Alarm=0, Running=0
                self.state_machine.set_initialized(True)
                self.state_machine.set_alarm(False)
                self.state_machine.set_ready(True)
                self.state_machine.set_running(False)
                print("[OK] [U+7CFB][U+7D71][U+5B8C][U+5168][U+521D][U+59CB][U+5316][U+FF0C][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+56FA][U+5B9A][U+70BA]: Ready=1, Initialized=1")
            else:
                # [U+7CFB][U+7D71][U+672A][U+5B8C][U+5168][U+521D][U+59CB][U+5316][U+FF1A][U+8A2D][U+7F6E]Alarm=1, Initialized=0
                self.state_machine.set_initialized(False)
                self.state_machine.set_alarm(True)
                self.state_machine.set_ready(False)
                print(f"[WARN][U+FE0F] [U+7CFB][U+7D71][U+672A][U+5B8C][U+5168][U+521D][U+59CB][U+5316] - Modbus: {modbus_ok}, Camera: {camera_ok}")
                
        except Exception as e:
            print(f"[FAIL] [U+66F4][U+65B0][U+521D][U+59CB][U+5316][U+72C0][U+614B][U+5931][U+6557]: {e}")
    
    def read_register(self, register_name: str) -> Optional[int]:
        """[U+8B80][U+53D6][U+5BC4][U+5B58][U+5668]"""
        if not self.connected or not self.client or register_name not in self.REGISTERS:
            return None
        
        try:
            address = self.REGISTERS[register_name]
            result = self.client.read_holding_registers(address, count=1, slave=1)
            
            if not result.isError():
                return result.registers[0]
            else:
                return None
                
        except Exception as e:
            return None
    
    def write_register(self, register_name: str, value: int) -> bool:
        """[U+5BEB][U+5165][U+5BC4][U+5B58][U+5668]"""
        if not self.connected or not self.client or register_name not in self.REGISTERS:
            return False
        
        try:
            address = self.REGISTERS[register_name]
            result = self.client.write_register(address, value, slave=1)
            
            return not result.isError()
                
        except Exception as e:
            return False
    
    def _world_coord_to_registers(self, world_x: float, world_y: float) -> Tuple[int, int, int, int]:
        """[U+5C07][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+70BA][U+5BC4][U+5B58][U+5668][U+503C] ([U+4FDD][U+7559]2[U+4F4D][U+5C0F][U+6578][U+7CBE][U+5EA6])"""
        try:
            # [U+5EA7][U+6A19][U+00D7]100[U+8F49][U+63DB][U+70BA]32[U+4F4D][U+6709][U+7B26][U+865F][U+6574][U+6578]
            world_x_int = int(world_x * 100)
            world_y_int = int(world_y * 100)
            
            # [U+9650][U+5236][U+7BC4][U+570D]: [U+00B1]21474.83mm
            max_value = 2147483
            min_value = -2147483
            
            world_x_int = max(min_value, min(max_value, world_x_int))
            world_y_int = max(min_value, min(max_value, world_y_int))
            
            # [U+62C6][U+5206][U+70BA][U+9AD8][U+4F4D][U+548C][U+4F4E][U+4F4D]
            world_x_high = (world_x_int >> 16) & 0xFFFF
            world_x_low = world_x_int & 0xFFFF
            world_y_high = (world_y_int >> 16) & 0xFFFF
            world_y_low = world_y_int & 0xFFFF
            
            return world_x_high, world_x_low, world_y_high, world_y_low
            
        except Exception as e:
            print(f"[FAIL] [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+5931][U+6557]: {e}")
            return 0, 0, 0, 0
    
    def update_detection_results(self, result: VisionResult):
        """[U+66F4][U+65B0][U+6AA2][U+6E2C][U+7D50][U+679C][U+5230]PLC (v4.0[U+64F4][U+5C55])"""
        try:
            # [U+5BEB][U+5165][U+5713][U+5F62][U+6578][U+91CF]
            self.write_register('CIRCLE_COUNT', result.circle_count)
            
            # [U+5BEB][U+5165][U+50CF][U+7D20][U+5EA7][U+6A19][U+6AA2][U+6E2C][U+7D50][U+679C][U+548C][U+4E16][U+754C][U+5EA7][U+6A19][U+6AA2][U+6E2C][U+7D50][U+679C] ([U+6700][U+591A]5[U+500B])
            for i in range(5):
                if i < len(result.circles):
                    circle = result.circles[i]
                    
                    # [U+50CF][U+7D20][U+5EA7][U+6A19] ([U+539F][U+6709][U+529F][U+80FD])
                    self.write_register(f'CIRCLE_{i+1}_X', int(circle['center'][0]))
                    self.write_register(f'CIRCLE_{i+1}_Y', int(circle['center'][1]))
                    self.write_register(f'CIRCLE_{i+1}_RADIUS', int(circle['radius']))
                    
                    # [U+4E16][U+754C][U+5EA7][U+6A19] (v4.0[U+65B0][U+589E])
                    if result.has_world_coords and 'world_coords' in circle:
                        world_x, world_y = circle['world_coords']
                        world_x_high, world_x_low, world_y_high, world_y_low = self._world_coord_to_registers(world_x, world_y)
                        
                        self.write_register(f'CIRCLE_{i+1}_WORLD_X_HIGH', world_x_high)
                        self.write_register(f'CIRCLE_{i+1}_WORLD_X_LOW', world_x_low)
                        self.write_register(f'CIRCLE_{i+1}_WORLD_Y_HIGH', world_y_high)
                        self.write_register(f'CIRCLE_{i+1}_WORLD_Y_LOW', world_y_low)
                    else:
                        # [U+6E05][U+7A7A][U+4E16][U+754C][U+5EA7][U+6A19][U+5BC4][U+5B58][U+5668]
                        self.write_register(f'CIRCLE_{i+1}_WORLD_X_HIGH', 0)
                        self.write_register(f'CIRCLE_{i+1}_WORLD_X_LOW', 0)
                        self.write_register(f'CIRCLE_{i+1}_WORLD_Y_HIGH', 0)
                        self.write_register(f'CIRCLE_{i+1}_WORLD_Y_LOW', 0)
                else:
                    # [U+6E05][U+7A7A][U+672A][U+4F7F][U+7528][U+7684][U+5BC4][U+5B58][U+5668] ([U+50CF][U+7D20][U+5EA7][U+6A19])
                    self.write_register(f'CIRCLE_{i+1}_X', 0)
                    self.write_register(f'CIRCLE_{i+1}_Y', 0)
                    self.write_register(f'CIRCLE_{i+1}_RADIUS', 0)
                    
                    # [U+6E05][U+7A7A][U+672A][U+4F7F][U+7528][U+7684][U+5BC4][U+5B58][U+5668] ([U+4E16][U+754C][U+5EA7][U+6A19])
                    self.write_register(f'CIRCLE_{i+1}_WORLD_X_HIGH', 0)
                    self.write_register(f'CIRCLE_{i+1}_WORLD_X_LOW', 0)
                    self.write_register(f'CIRCLE_{i+1}_WORLD_Y_HIGH', 0)
                    self.write_register(f'CIRCLE_{i+1}_WORLD_Y_LOW', 0)
            
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
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'connection_count': self.connection_count,
            'uptime_seconds': int(time.time() - self.start_time),
            'state_machine': self.state_machine.get_status_description(),
            'last_control_command': self.last_control_command,
            'command_processing': self.command_processing,
            'handshake_mode': True,
            'version': '4.0',  # v4.0[U+7248][U+672C][U+6A19][U+8B58]
            'world_coord_support': True  # [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+652F][U+63F4]
        }
    
    def get_debug_info(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+8ABF][U+8A66][U+4FE1][U+606F]"""
        return {
            'connected': self.connected,
            'sync_running': self.sync_running,
            'sync_thread_alive': self.sync_thread.is_alive() if self.sync_thread else False,
            'last_control_command': self.last_control_command,
            'command_processing': self.command_processing,
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'server_address': f"{self.server_ip}:{self.server_port}",
            'state_machine': self.state_machine.get_status_description(),
            'handshake_mode': True,
            'sync_interval_ms': self.sync_interval * 1000,
            'version': '4.0',
            'world_coord_support': True,
            'register_count': len(self.REGISTERS)
        }


# ==================== [U+6A21][U+64EC][U+7248][U+672C] ([U+7576]pymodbus[U+4E0D][U+53EF][U+7528][U+6642]) ====================
class MockEnhancedModbusTcpClientService(EnhancedModbusTcpClientService):
    """[U+6A21][U+64EC][U+589E][U+5F37][U+578B]Modbus TCP Client[U+670D][U+52D9] (v4.0)"""
    
    def __init__(self, server_ip="192.168.1.100", server_port=502):
        # [U+8ABF][U+7528][U+7236][U+985E][U+521D][U+59CB][U+5316][U+FF0C][U+4F46][U+8DF3][U+904E]Modbus[U+76F8][U+95DC][U+90E8][U+5206]
        self.server_ip = server_ip
        self.server_port = server_port
        self.client = None
        self.connected = False
        self.vision_controller = None
        
        # [U+72C0][U+614B][U+6A5F][U+7BA1][U+7406]
        self.state_machine = SystemStateMachine()
        
        # [U+6A21][U+64EC][U+5BC4][U+5B58][U+5668][U+5B58][U+5132]
        self.registers = {}
        
        # [U+5176][U+4ED6][U+5C6C][U+6027][U+8207][U+7236][U+985E][U+76F8][U+540C]
        self.reconnect_delay = 5.0
        self.read_timeout = 3.0
        self.write_timeout = 3.0
        self.sync_enabled = False
        self.sync_thread = None
        self.sync_running = False
        self.sync_interval = 0.05
        self.last_control_command = 0
        self.command_processing = False
        
        # [U+521D][U+59CB][U+5316][U+5BC4][U+5B58][U+5668][U+6620][U+5C04] (v4.0[U+64F4][U+5C55])
        self.REGISTERS = {
            'CONTROL_COMMAND': 200,
            'STATUS_REGISTER': 201,
            'MIN_AREA_HIGH': 210,
            'MIN_AREA_LOW': 211,
            'MIN_ROUNDNESS': 212,
            'GAUSSIAN_KERNEL': 213,
            'CANNY_LOW': 214,
            'CANNY_HIGH': 215,
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
            # [U+4E16][U+754C][U+5EA7][U+6A19][U+5BC4][U+5B58][U+5668] (v4.0[U+65B0][U+589E])
            'WORLD_COORD_VALID': 256,
            'CIRCLE_1_WORLD_X_HIGH': 257,
            'CIRCLE_1_WORLD_X_LOW': 258,
            'CIRCLE_1_WORLD_Y_HIGH': 259,
            'CIRCLE_1_WORLD_Y_LOW': 260,
            'CIRCLE_2_WORLD_X_HIGH': 261,
            'CIRCLE_2_WORLD_X_LOW': 262,
            'CIRCLE_2_WORLD_Y_HIGH': 263,
            'CIRCLE_2_WORLD_Y_LOW': 264,
            'CIRCLE_3_WORLD_X_HIGH': 265,
            'CIRCLE_3_WORLD_X_LOW': 266,
            'CIRCLE_3_WORLD_Y_HIGH': 267,
            'CIRCLE_3_WORLD_Y_LOW': 268,
            'CIRCLE_4_WORLD_X_HIGH': 269,
            'CIRCLE_4_WORLD_X_LOW': 270,
            'CIRCLE_4_WORLD_Y_HIGH': 271,
            'CIRCLE_4_WORLD_Y_LOW': 272,
            'CIRCLE_5_WORLD_X_HIGH': 273,
            'CIRCLE_5_WORLD_X_LOW': 274,
            'CIRCLE_5_WORLD_Y_HIGH': 275,
            'CIRCLE_5_WORLD_Y_LOW': 276,
            # [U+7D71][U+8A08][U+8CC7][U+8A0A]
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
        
        # [U+7D71][U+8A08][U+8A08][U+6578]
        self.operation_count = 0
        self.error_count = 0
        self.connection_count = 0
        self.start_time = time.time()
    
    def connect(self) -> bool:
        """[U+6A21][U+64EC][U+9023][U+63A5]"""
        print(f"[WARN][U+FE0F] [U+6A21][U+64EC][U+9023][U+63A5][U+5230]Modbus TCP[U+670D][U+52D9][U+5668]: {self.server_ip}:{self.server_port}")
        self.connected = True
        self.connection_count += 1
        
        # [U+521D][U+59CB][U+5316][U+6A21][U+64EC][U+5BC4][U+5B58][U+5668][U+FF0C][U+78BA][U+4FDD][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+56FA][U+5B9A][U+503C]
        self._initialize_status_registers()
        self._update_initialization_status()
        
        # [U+5F37][U+5236][U+8A2D][U+7F6E][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+70BA][U+56FA][U+5B9A][U+503C] 1 (Ready=1)
        self.state_machine.reset_to_idle()
        self.registers[self.REGISTERS['STATUS_REGISTER']] = 1
        print(f"[U+1F4CA] [U+6A21][U+64EC][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+56FA][U+5B9A][U+70BA]: 1 (Ready=1)")
        
        return True
    
    def read_register(self, register_name: str) -> Optional[int]:
        """[U+6A21][U+64EC][U+8B80][U+53D6][U+5BC4][U+5B58][U+5668]"""
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            return self.registers.get(address, 0)
        return None
    
    def write_register(self, register_name: str, value: int) -> bool:
        """[U+6A21][U+64EC][U+5BEB][U+5165][U+5BC4][U+5B58][U+5668]"""
        if register_name in self.REGISTERS:
            address = self.REGISTERS[register_name]
            self.registers[address] = value
            return True
        return False


# ==================== [U+5713][U+5F62][U+6AA2][U+6E2C][U+5668] ====================
class CircleDetector:
    """[U+5713][U+5F62][U+6AA2][U+6E2C][U+5668] ([U+4FDD][U+6301][U+539F][U+6709][U+908F][U+8F2F])"""
    
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
                    cv2.circle(result_image, center, radius, (0, 255, 0), 3)
                    cv2.circle(result_image, center, 5, (0, 0, 255), -1)
                    
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
    """CCD1 [U+8996][U+89BA][U+63A7][U+5236][U+5668] (v4.0[U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+7248][U+672C])"""
    
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
        
        # v4.0[U+65B0][U+589E]: [U+6A19][U+5B9A][U+7BA1][U+7406][U+5668]
        working_dir = os.path.dirname(os.path.abspath(__file__))
        self.calibration_manager = CalibrationManager(working_dir)
        
        # [U+8A2D][U+7F6E][U+65E5][U+8A8C]
        self.logger = logging.getLogger("CCD1Vision")
        self.logger.setLevel(logging.INFO)
        
        # [U+9078][U+64C7][U+5408][U+9069][U+7684]Modbus Client[U+670D][U+52D9]
        if MODBUS_AVAILABLE:
            self.modbus_client = EnhancedModbusTcpClientService()
            print("[OK] [U+4F7F][U+7528][U+589E][U+5F37][U+578B]Modbus TCP Client[U+670D][U+52D9] ([U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F] v4.0)")
        else:
            self.modbus_client = MockEnhancedModbusTcpClientService()
            print("[WARN][U+FE0F] [U+4F7F][U+7528][U+6A21][U+64EC][U+589E][U+5F37][U+578B]Modbus TCP Client[U+670D][U+52D9] ([U+529F][U+80FD][U+53D7][U+9650])")
            
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
                self.modbus_client.stop_handshake_sync()
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
                # [U+9023][U+63A5][U+6210][U+529F][U+5F8C][U+81EA][U+52D5][U+555F][U+52D5][U+63E1][U+624B][U+540C][U+6B65]
                self.modbus_client.start_handshake_sync()
                
                return {
                    'success': True,
                    'message': f'Modbus TCP[U+9023][U+63A5][U+6210][U+529F][U+FF0C][U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F][U+5DF2][U+555F][U+52D5]: {self.modbus_client.server_ip}:{self.modbus_client.server_port}',
                    'connection_status': self.modbus_client.get_connection_status(),
                    'handshake_mode': True,
                    'version': '4.0'
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
            self.modbus_client.disconnect()  # [U+9019][U+6703][U+81EA][U+52D5][U+505C][U+6B62][U+63E1][U+624B][U+540C][U+6B65][U+7DDA][U+7A0B]
            
            return {
                'success': True,
                'message': 'Modbus[U+9023][U+63A5][U+5DF2][U+65B7][U+958B][U+FF0C][U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+540C][U+6B65][U+5DF2][U+505C][U+6B62]'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'[U+65B7][U+958B]Modbus[U+9023][U+63A5][U+5931][U+6557]: {str(e)}'
            }
    
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
            
            # [U+66F4][U+65B0]Modbus[U+7684][U+521D][U+59CB][U+5316][U+72C0][U+614B]
            if self.modbus_client.connected:
                self.modbus_client._update_initialization_status()
            
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
            
            # [U+66F4][U+65B0]Modbus[U+7684]Alarm[U+72C0][U+614B]
            if self.modbus_client.connected:
                self.modbus_client.state_machine.set_alarm(True)
                self.modbus_client._update_initialization_status()
            
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
            # [U+8A2D][U+7F6E]Alarm[U+72C0][U+614B]
            if self.modbus_client.connected:
                self.modbus_client.state_machine.set_alarm(True)
            return None, 0.0
    
    def capture_and_detect(self) -> VisionResult:
        """[U+62CD][U+7167][U+4E26][U+9032][U+884C][U+5713][U+5F62][U+6AA2][U+6E2C] (v4.0[U+542B][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])"""
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
                    has_world_coords=False,
                    error_message="[U+5716][U+50CF][U+6355][U+7372][U+5931][U+6557]"
                )
            else:
                process_start = time.time()
                circles, annotated_image = self.detector.detect_circles(image)
                
                # v4.0[U+65B0][U+589E]: [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB]
                has_world_coords = False
                if (self.calibration_manager.is_calibration_loaded() and 
                    self.calibration_manager.transformer and 
                    self.calibration_manager.transformer.is_valid() and 
                    len(circles) > 0):
                    
                    try:
                        # [U+63D0][U+53D6][U+50CF][U+7D20][U+5EA7][U+6A19]
                        pixel_coords_list = [circle['center'] for circle in circles]
                        
                        # [U+8F49][U+63DB][U+70BA][U+4E16][U+754C][U+5EA7][U+6A19]
                        world_coords_list = self.calibration_manager.transformer.pixel_to_world(pixel_coords_list)
                        
                        if world_coords_list:
                            # [U+5C07][U+4E16][U+754C][U+5EA7][U+6A19][U+52A0][U+5165][U+7D50][U+679C]
                            for i, (circle, world_coords) in enumerate(zip(circles, world_coords_list)):
                                circle['world_coords'] = world_coords
                            
                            has_world_coords = True
                            print(f"[U+1F30D] [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+6210][U+529F][U+FF0C]{len(circles)}[U+500B][U+5713][U+5F62]")
                        else:
                            print("[WARN][U+FE0F] [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+5931][U+6557]")
                    except Exception as e:
                        print(f"[FAIL] [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+7570][U+5E38]: {e}")
                
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
                    success=True,
                    has_world_coords=has_world_coords
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
                has_world_coords=False,
                error_message=error_msg
            )
            
            # [U+8A2D][U+7F6E]Alarm[U+72C0][U+614B]
            if self.modbus_client.connected:
                self.modbus_client.state_machine.set_alarm(True)
                self.modbus_client.update_detection_results(result)
            
            return result
    
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
    
    # v4.0[U+65B0][U+589E]: [U+6A19][U+5B9A][U+76F8][U+95DC][U+65B9][U+6CD5]
    def scan_calibration_files(self) -> Dict[str, Any]:
        """[U+6383][U+63CF][U+6A19][U+5B9A][U+6A94][U+6848]"""
        return self.calibration_manager.scan_calibration_files()
    
    def load_calibration_data(self, intrinsic_file: str = None, extrinsic_file: str = None) -> Dict[str, Any]:
        """[U+8F09][U+5165][U+6A19][U+5B9A][U+6578][U+64DA]"""
        return self.calibration_manager.load_calibration_data(intrinsic_file, extrinsic_file)
    
    def get_calibration_status(self) -> Dict[str, Any]:
        """[U+7372][U+53D6][U+6A19][U+5B9A][U+72C0][U+614B]"""
        return self.calibration_manager.get_status()
    
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
        """[U+7372][U+53D6][U+7CFB][U+7D71][U+72C0][U+614B] (v4.0[U+64F4][U+5C55])"""
        status = {
            'connected': self.is_connected,
            'camera_name': self.camera_name,
            'camera_ip': self.camera_ip,
            'has_image': self.last_image is not None,
            'last_result': asdict(self.last_result) if self.last_result else None,
            'detection_params': asdict(self.detection_params),
            'modbus_enabled': MODBUS_AVAILABLE,
            'modbus_connection': self.modbus_client.get_connection_status(),
            'handshake_mode': True,
            'version': '4.0',
            # v4.0[U+65B0][U+589E]: [U+6A19][U+5B9A][U+72C0][U+614B]
            'calibration_status': self.get_calibration_status(),
            'world_coord_support': True
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
        
        # [U+66F4][U+65B0]Modbus[U+72C0][U+614B]
        if self.modbus_client.connected:
            self.modbus_client.state_machine.set_alarm(True)
            self.modbus_client._update_initialization_status()
        
        # [U+65B7][U+958B]Modbus[U+9023][U+63A5]
        try:
            self.modbus_client.stop_handshake_sync()
            self.modbus_client.disconnect()
        except:
            pass
        
        self.logger.info("[U+6240][U+6709][U+9023][U+63A5][U+5DF2][U+65B7][U+958B]")


# ==================== Flask[U+61C9][U+7528][U+8A2D][U+7F6E] ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ccd_vision_enhanced_handshake_world_coord_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# [U+5275][U+5EFA][U+63A7][U+5236][U+5668][U+5BE6][U+4F8B]
vision_controller = CCD1VisionController()

# [U+8A2D][U+7F6E][U+65E5][U+8A8C]
logging.basicConfig(level=logging.INFO)


# ==================== [U+8DEF][U+7531][U+5B9A][U+7FA9] ====================
@app.route('/')
def index():
    """[U+4E3B][U+9801][U+9762]"""
    return render_template('ccd_vision_enhanced_world_coord.html')


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


@app.route('/api/modbus/status', methods=['GET'])
def get_modbus_status():
    """[U+7372][U+53D6]Modbus[U+72C0][U+614B][U+6A5F][U+8CC7][U+8A0A]"""
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': 'Modbus Client[U+672A][U+9023][U+63A5]',
            'status': {}
        })
    
    try:
        # [U+8B80][U+53D6][U+7576][U+524D][U+5BC4][U+5B58][U+5668][U+72C0][U+614B]
        control_command = modbus_client.read_register('CONTROL_COMMAND')
        status_register = modbus_client.read_register('STATUS_REGISTER')
        world_coord_valid = modbus_client.read_register('WORLD_COORD_VALID')
        
        status_info = {
            'control_command': control_command,
            'status_register': status_register,
            'world_coord_valid': world_coord_valid,  # v4.0[U+65B0][U+589E]
            'state_machine': modbus_client.state_machine.get_status_description(),
            'last_control_command': modbus_client.last_control_command,
            'command_processing': modbus_client.command_processing,
            'sync_running': modbus_client.sync_running,
            'operation_count': modbus_client.operation_count,
            'error_count': modbus_client.error_count,
            'version': '4.0'
        }
        
        return jsonify({
            'success': True,
            'message': '[U+6210][U+529F][U+7372][U+53D6]Modbus[U+72C0][U+614B] (v4.0[U+4E16][U+754C][U+5EA7][U+6A19][U+7248][U+672C])',
            'status': status_info,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+7372][U+53D6]Modbus[U+72C0][U+614B][U+5931][U+6557]: {str(e)}',
            'status': {}
        })


@app.route('/api/modbus/registers', methods=['GET'])
def get_modbus_registers():
    """[U+7372][U+53D6][U+6240][U+6709]Modbus[U+5BC4][U+5B58][U+5668][U+7684][U+5373][U+6642][U+6578][U+503C] (v4.0[U+542B][U+4E16][U+754C][U+5EA7][U+6A19])"""
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': 'Modbus Client[U+672A][U+9023][U+63A5]',
            'registers': {}
        })
    
    try:
        registers = {}
        
        # [U+6838][U+5FC3][U+63A7][U+5236][U+63E1][U+624B][U+5BC4][U+5B58][U+5668]
        control_registers = {
            '200_[U+63A7][U+5236][U+6307][U+4EE4]': modbus_client.read_register('CONTROL_COMMAND'),
            '201_[U+72C0][U+614B][U+5BC4][U+5B58][U+5668]': modbus_client.read_register('STATUS_REGISTER'),
        }
        
        # [U+89E3][U+6790][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+7684][U+5404][U+500B][U+4F4D]
        status_value = control_registers['201_[U+72C0][U+614B][U+5BC4][U+5B58][U+5668]'] or 0
        status_bits = {
            '201_Ready[U+72C0][U+614B]_bit0': (status_value >> 0) & 1,
            '201_Running[U+72C0][U+614B]_bit1': (status_value >> 1) & 1,
            '201_Alarm[U+72C0][U+614B]_bit2': (status_value >> 2) & 1,
            '201_[U+521D][U+59CB][U+5316][U+72C0][U+614B]_bit3': (status_value >> 3) & 1,
        }
        
        # [U+50CF][U+7D20][U+5EA7][U+6A19][U+6AA2][U+6E2C][U+7D50][U+679C][U+5BC4][U+5B58][U+5668]
        result_registers = {
            '240_[U+6AA2][U+6E2C][U+5713][U+5F62][U+6578][U+91CF]': modbus_client.read_register('CIRCLE_COUNT'),
        }
        
        # [U+5713][U+5F62][U+50CF][U+7D20][U+5EA7][U+6A19][U+8A73][U+7D30][U+8CC7][U+6599]
        for i in range(1, 6):
            x_val = modbus_client.read_register(f'CIRCLE_{i}_X')
            y_val = modbus_client.read_register(f'CIRCLE_{i}_Y')
            r_val = modbus_client.read_register(f'CIRCLE_{i}_RADIUS')
            result_registers[f'{240+i*3-2}_[U+5713][U+5F62]{i}_[U+50CF][U+7D20]X[U+5EA7][U+6A19]'] = x_val
            result_registers[f'{240+i*3-1}_[U+5713][U+5F62]{i}_[U+50CF][U+7D20]Y[U+5EA7][U+6A19]'] = y_val
            result_registers[f'{240+i*3}_[U+5713][U+5F62]{i}_[U+534A][U+5F91]'] = r_val
        
        # v4.0[U+65B0][U+589E]: [U+4E16][U+754C][U+5EA7][U+6A19][U+6AA2][U+6E2C][U+7D50][U+679C][U+5BC4][U+5B58][U+5668] (256-276)
        world_coord_registers = {
            '256_[U+4E16][U+754C][U+5EA7][U+6A19][U+6709][U+6548][U+6A19][U+8A8C]': modbus_client.read_register('WORLD_COORD_VALID'),
        }
        
        # [U+5713][U+5F62][U+4E16][U+754C][U+5EA7][U+6A19][U+8A73][U+7D30][U+8CC7][U+6599]
        for i in range(1, 6):
            x_high = modbus_client.read_register(f'CIRCLE_{i}_WORLD_X_HIGH')
            x_low = modbus_client.read_register(f'CIRCLE_{i}_WORLD_X_LOW')
            y_high = modbus_client.read_register(f'CIRCLE_{i}_WORLD_Y_HIGH')
            y_low = modbus_client.read_register(f'CIRCLE_{i}_WORLD_Y_LOW')
            
            # [U+8A08][U+7B97][U+5BE6][U+969B][U+4E16][U+754C][U+5EA7][U+6A19][U+503C] ([U+6062][U+5FA9][U+7CBE][U+5EA6])
            if x_high is not None and x_low is not None:
                world_x_int = (x_high << 16) | x_low
                if world_x_int >= 2147483648:  # [U+8655][U+7406][U+8CA0][U+6578]
                    world_x_int -= 4294967296
                world_x_mm = world_x_int / 100.0
            else:
                world_x_mm = 0.0
            
            if y_high is not None and y_low is not None:
                world_y_int = (y_high << 16) | y_low
                if world_y_int >= 2147483648:  # [U+8655][U+7406][U+8CA0][U+6578]
                    world_y_int -= 4294967296
                world_y_mm = world_y_int / 100.0
            else:
                world_y_mm = 0.0
            
            base_addr = 257 + (i-1) * 4
            world_coord_registers[f'{base_addr}_[U+5713][U+5F62]{i}_[U+4E16][U+754C]X[U+9AD8][U+4F4D]'] = x_high
            world_coord_registers[f'{base_addr+1}_[U+5713][U+5F62]{i}_[U+4E16][U+754C]X[U+4F4E][U+4F4D]'] = x_low
            world_coord_registers[f'{base_addr+2}_[U+5713][U+5F62]{i}_[U+4E16][U+754C]Y[U+9AD8][U+4F4D]'] = y_high
            world_coord_registers[f'{base_addr+3}_[U+5713][U+5F62]{i}_[U+4E16][U+754C]Y[U+4F4E][U+4F4D]'] = y_low
            world_coord_registers[f'[U+5713][U+5F62]{i}_[U+4E16][U+754C]X[U+5EA7][U+6A19]_[U+8A08][U+7B97][U+503C]_mm'] = world_x_mm
            world_coord_registers[f'[U+5713][U+5F62]{i}_[U+4E16][U+754C]Y[U+5EA7][U+6A19]_[U+8A08][U+7B97][U+503C]_mm'] = world_y_mm
        
        # [U+7D71][U+8A08][U+8CC7][U+8A0A][U+5BC4][U+5B58][U+5668]
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
        registers.update(status_bits)
        registers.update(result_registers)
        registers.update(world_coord_registers)
        registers.update(stats_registers)
        
        return jsonify({
            'success': True,
            'message': 'Modbus[U+5BC4][U+5B58][U+5668][U+8B80][U+53D6][U+6210][U+529F] (v4.0[U+4E16][U+754C][U+5EA7][U+6A19][U+7248][U+672C])',
            'registers': registers,
            'handshake_mode': True,
            'world_coord_support': True,
            'state_machine': modbus_client.state_machine.get_status_description(),
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_registers': len(registers),
            'server_info': f"{modbus_client.server_ip}:{modbus_client.server_port}",
            'version': '4.0'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+8B80][U+53D6][U+5BC4][U+5B58][U+5668][U+5931][U+6557]: {str(e)}',
            'registers': {},
            'error': str(e)
        })


# v4.0[U+65B0][U+589E]: [U+6A19][U+5B9A][U+76F8][U+95DC]API
@app.route('/api/calibration/scan', methods=['GET'])
def scan_calibration_files():
    """[U+6383][U+63CF][U+6A19][U+5B9A][U+6A94][U+6848]"""
    result = vision_controller.scan_calibration_files()
    return jsonify(result)


@app.route('/api/calibration/load', methods=['POST'])
def load_calibration_data():
    """[U+8F09][U+5165][U+6A19][U+5B9A][U+6578][U+64DA]"""
    data = request.get_json()
    intrinsic_file = data.get('intrinsic_file') if data else None
    extrinsic_file = data.get('extrinsic_file') if data else None
    
    result = vision_controller.load_calibration_data(intrinsic_file, extrinsic_file)
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify(result)


@app.route('/api/calibration/status', methods=['GET'])
def get_calibration_status():
    """[U+7372][U+53D6][U+6A19][U+5B9A][U+72C0][U+614B]"""
    result = vision_controller.get_calibration_status()
    return jsonify(result)


@app.route('/api/modbus/test', methods=['GET'])
def test_modbus():
    """[U+6E2C][U+8A66]Modbus Client[U+9023][U+63A5][U+72C0][U+614B] (v4.0)"""
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
        
        # [U+6E2C][U+8A66][U+8B80][U+5BEB][U+64CD][U+4F5C] ([U+4F7F][U+7528][U+65B0][U+7684][U+63E1][U+624B][U+5BC4][U+5B58][U+5668])
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
                modbus_client.write_register('VERSION_MAJOR', 4)  # v4.0
            else:
                error_message = f"[U+8B80][U+53D6][U+503C][U+4E0D][U+5339][U+914D]: [U+671F][U+671B]99, [U+5BE6][U+969B]{read_value}"
        else:
            error_message = "[U+5BEB][U+5165][U+64CD][U+4F5C][U+5931][U+6557]"
        
        # [U+7372][U+53D6][U+63E1][U+624B][U+72C0][U+614B]
        connection_status = modbus_client.get_connection_status()
        
        return jsonify({
            'success': test_success,
            'message': f'[OK] [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F][U+6B63][U+5E38] (v4.0, pymodbus {actual_version})' if test_success else f'[FAIL] Modbus[U+6E2C][U+8A66][U+5931][U+6557]: {error_message}',
            'available': True,
            'connected': True,
            'pymodbus_version': actual_version,
            'expected_version': PYMODBUS_VERSION,
            'write_success': write_success,
            'test_passed': test_success,
            'error_message': error_message,
            'connection_status': connection_status,
            'register_count': len(modbus_client.REGISTERS),
            'handshake_mode': True,
            'world_coord_support': True,
            'version': '4.0',
            'state_machine': modbus_client.state_machine.get_status_description()
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


@app.route('/api/modbus/manual_command', methods=['POST'])
def manual_command():
    """[U+624B][U+52D5][U+767C][U+9001][U+63A7][U+5236][U+6307][U+4EE4] ([U+6A21][U+64EC]PLC[U+64CD][U+4F5C])"""
    data = request.get_json()
    command = data.get('command', 0)
    
    modbus_client = vision_controller.modbus_client
    
    if not modbus_client.connected:
        return jsonify({
            'success': False,
            'message': 'Modbus[U+672A][U+9023][U+63A5]'
        })
    
    try:
        # [U+9A57][U+8B49][U+63A7][U+5236][U+6307][U+4EE4]
        valid_commands = [0, 8, 16, 32]
        if command not in valid_commands:
            return jsonify({
                'success': False,
                'message': f'[U+7121][U+6548][U+7684][U+63A7][U+5236][U+6307][U+4EE4]: {command}[U+FF0C][U+6709][U+6548][U+503C]: {valid_commands}'
            })
        
        # [U+5BEB][U+5165][U+63A7][U+5236][U+6307][U+4EE4]
        success = modbus_client.write_register('CONTROL_COMMAND', command)
        
        if success:
            command_names = {
                0: "[U+6E05][U+7A7A][U+63A7][U+5236]",
                8: "[U+62CD][U+7167]", 
                16: "[U+62CD][U+7167]+[U+6AA2][U+6E2C] ([U+542B][U+4E16][U+754C][U+5EA7][U+6A19])",
                32: "[U+91CD][U+65B0][U+521D][U+59CB][U+5316]"
            }
            
            return jsonify({
                'success': True,
                'message': f'[U+624B][U+52D5][U+63A7][U+5236][U+6307][U+4EE4][U+5DF2][U+767C][U+9001]: {command} ({command_names.get(command, "[U+672A][U+77E5]")})',
                'command': command,
                'command_name': command_names.get(command, "[U+672A][U+77E5]"),
                'state_machine': modbus_client.state_machine.get_status_description(),
                'version': '4.0'
            })
        else:
            return jsonify({
                'success': False,
                'message': '[U+5BEB][U+5165][U+63A7][U+5236][U+6307][U+4EE4][U+5931][U+6557]'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+767C][U+9001][U+624B][U+52D5][U+6307][U+4EE4][U+5931][U+6557]: {str(e)}'
        })


@app.route('/api/modbus/debug', methods=['GET'])
def get_modbus_debug():
    """[U+7372][U+53D6]Modbus[U+8ABF][U+8A66][U+4FE1][U+606F] (v4.0)"""
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
                'CONTROL_COMMAND': modbus_client.read_register('CONTROL_COMMAND'),
                'STATUS_REGISTER': modbus_client.read_register('STATUS_REGISTER'),
                'CIRCLE_COUNT': modbus_client.read_register('CIRCLE_COUNT'),
                'WORLD_COORD_VALID': modbus_client.read_register('WORLD_COORD_VALID'),  # v4.0[U+65B0][U+589E]
                'OPERATION_COUNT': modbus_client.read_register('OPERATION_COUNT'),
                'ERROR_COUNT': modbus_client.read_register('ERROR_COUNT'),
                'VERSION_MAJOR': modbus_client.read_register('VERSION_MAJOR'),
                'VERSION_MINOR': modbus_client.read_register('VERSION_MINOR')
            }
            debug_info['current_registers'] = current_registers
        
        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'mode': '[U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F] v4.0 ([U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])',
            'version': '4.0',
            'world_coord_support': True
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'[U+7372][U+53D6][U+8ABF][U+8A66][U+4FE1][U+606F][U+5931][U+6557]: {str(e)}',
            'error': str(e)
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
    """[U+62CD][U+7167][U+4E26][U+6AA2][U+6E2C] (v4.0[U+542B][U+4E16][U+754C][U+5EA7][U+6A19])"""
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
        'error_message': result.error_message,
        'has_world_coords': result.has_world_coords,  # v4.0[U+65B0][U+589E]
        'version': '4.0'
    }
    
    socketio.emit('detection_result', response)
    return jsonify(response)


@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    """[U+65B7][U+958B][U+6240][U+6709][U+9023][U+63A5]"""
    vision_controller.disconnect()
    socketio.emit('status_update', vision_controller.get_status())
    
    return jsonify({'success': True, 'message': '[U+6240][U+6709][U+9023][U+63A5][U+5DF2][U+65B7][U+958B]'})


@app.route('/api/modbus/info', methods=['GET'])
def get_modbus_info():
    """[U+7372][U+53D6]Modbus Client[U+8CC7][U+8A0A] (v4.0)"""
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
        'handshake_mode': True,
        'world_coord_support': True,  # v4.0[U+65B0][U+589E]
        'system_version': '4.0',
        'install_commands': [
            'pip install pymodbus>=3.0.0',
            'pip install "pymodbus[serial]>=3.0.0"'
        ],
        'verify_command': 'python -c "import pymodbus; print(f\'pymodbus {pymodbus.__version__}\')"',
        'architecture': 'Modbus TCP Client - [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F] v4.0 ([U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])',
        'register_mapping': {
            '[U+63A7][U+5236][U+6307][U+4EE4] (200)': '0=[U+6E05][U+7A7A], 8=[U+62CD][U+7167], 16=[U+62CD][U+7167]+[U+6AA2][U+6E2C], 32=[U+91CD][U+65B0][U+521D][U+59CB][U+5316]',
            '[U+72C0][U+614B][U+5BC4][U+5B58][U+5668] (201)': 'bit0=Ready, bit1=Running, bit2=Alarm, bit3=Initialized',
            '[U+6AA2][U+6E2C][U+53C3][U+6578] (210-219)': '[U+6AA2][U+6E2C][U+53C3][U+6578][U+8A2D][U+5B9A]',
            '[U+50CF][U+7D20][U+5EA7][U+6A19][U+7D50][U+679C] (240-255)': '[U+5713][U+5F62][U+6AA2][U+6E2C][U+7D50][U+679C][U+548C][U+50CF][U+7D20][U+5EA7][U+6A19]',
            '[U+4E16][U+754C][U+5EA7][U+6A19][U+7D50][U+679C] (256-276)': 'v4.0[U+65B0][U+589E]: [U+5713][U+5F62][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+7D50][U+679C]',
            '[U+7D71][U+8A08][U+8CC7][U+8A0A] (280-299)': '[U+6642][U+9593][U+7D71][U+8A08][U+548C][U+7CFB][U+7D71][U+8A08][U+6578][U+5668]'
        },
        'control_commands': {
            '0': '[U+6E05][U+7A7A][U+63A7][U+5236]',
            '8': '[U+62CD][U+7167]',
            '16': '[U+62CD][U+7167]+[U+6AA2][U+6E2C] ([U+542B][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])', 
            '32': '[U+91CD][U+65B0][U+521D][U+59CB][U+5316]'
        },
        'status_bits': {
            'bit0': 'Ready[U+72C0][U+614B] - [U+7CFB][U+7D71][U+6E96][U+5099][U+63A5][U+53D7][U+65B0][U+6307][U+4EE4]',
            'bit1': 'Running[U+72C0][U+614B] - [U+7CFB][U+7D71][U+6B63][U+5728][U+57F7][U+884C][U+64CD][U+4F5C]',
            'bit2': 'Alarm[U+72C0][U+614B] - [U+7CFB][U+7D71][U+7570][U+5E38][U+6216][U+932F][U+8AA4]',
            'bit3': 'Initialized[U+72C0][U+614B] - [U+7CFB][U+7D71][U+5DF2][U+5B8C][U+5168][U+521D][U+59CB][U+5316]'
        },
        'world_coord_features': {
            'coordinate_system': 'Z=0[U+5E73][U+9762][U+6295][U+5F71]',
            'precision': '2[U+4F4D][U+5C0F][U+6578] ([U+00D7]100[U+5B58][U+5132])',
            'range': '[U+00B1]21474.83mm',
            'storage_format': '32[U+4F4D][U+6709][U+7B26][U+865F][U+6574][U+6578][U+FF0C][U+62C6][U+5206][U+70BA][U+9AD8][U+4F4D][U+4F4E][U+4F4D]',
            'file_support': 'NPY[U+683C][U+5F0F][U+5167][U+5916][U+53C3][U+6A94][U+6848]',
            'calibration_files': {
                'intrinsic': 'camera_matrix_YYYYMMDD_HHMMSS.npy, dist_coeffs_YYYYMMDD_HHMMSS.npy',
                'extrinsic': '*extrinsic*.npy ([U+5305][U+542B]rvec[U+548C]tvec)'
            }
        },
        'handshake_logic': [
            '1. [U+53EA][U+6709]Ready=1[U+6642][U+624D][U+63A5][U+53D7][U+63A7][U+5236][U+6307][U+4EE4]',
            '2. [U+6536][U+5230][U+6307][U+4EE4][U+5F8C]Ready[U+2192]0, Running[U+2192]1',
            '3. [U+57F7][U+884C][U+5B8C][U+6210][U+5F8C]Running[U+2192]0',
            '4. [U+63A7][U+5236][U+6307][U+4EE4][U+6E05][U+96F6][U+4E14]Running=0[U+6642]Ready[U+2192]1',
            '5. [U+7570][U+5E38][U+6642][U+8A2D][U+7F6E]Alarm=1, Initialized[U+2192]0',
            '6. v4.0: [U+81EA][U+52D5][U+6AA2][U+6E2C][U+6A19][U+5B9A][U+6578][U+64DA][U+6709][U+6548][U+6027]'
        ],
        'features': [
            '[U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+5354][U+8B70]',
            '50ms[U+9AD8][U+983B][U+8F2A][U+8A62]',
            '[U+72C0][U+614B][U+6A5F][U+7BA1][U+7406]',
            '[U+6307][U+4EE4]/[U+72C0][U+614B][U+6A21][U+5F0F]',
            '[U+81EA][U+52D5][U+7570][U+5E38][U+6AA2][U+6E2C]',
            '[U+5B8C][U+6574][U+63E1][U+624B][U+908F][U+8F2F]',
            'v4.0: NPY[U+5167][U+5916][U+53C3][U+7BA1][U+7406]',
            'v4.0: [U+50CF][U+7D20][U+5EA7][U+6A19][U+5230][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB]',
            'v4.0: [U+5411][U+4E0B][U+517C][U+5BB9][U+7121][U+6A19][U+5B9A][U+6A21][U+5F0F]'
        ],
        'restart_required': True,
        'compatibility': {
            'python_min': '3.7',
            'recommended_python': '3.8+',
            'opencv_required': True,
            'numpy_required': True,
            'async_support': True,
            'sync_support': True,
            'automation_ready': True
        }
    })


# ==================== Socket.IO [U+4E8B][U+4EF6][U+8655][U+7406] ====================
@socketio.on('connect')
def handle_connect():
    """[U+5BA2][U+6236][U+7AEF][U+9023][U+63A5]"""
    emit('status_update', vision_controller.get_status())


@socketio.on('disconnect')
def handle_disconnect():
    """[U+5BA2][U+6236][U+7AEF][U+65B7][U+958B]"""
    pass


# ==================== [U+4E3B][U+51FD][U+6578] ====================
def main():
    """[U+4E3B][U+51FD][U+6578]"""
    print("[U+1F680] CCD1 [U+8996][U+89BA][U+63A7][U+5236][U+7CFB][U+7D71][U+555F][U+52D5][U+4E2D] ([U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+7248][U+672C] v4.0 + [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB])...")
    
    if not CAMERA_MANAGER_AVAILABLE:
        print("[FAIL] [U+76F8][U+6A5F][U+7BA1][U+7406][U+5668][U+4E0D][U+53EF][U+7528][U+FF0C][U+8ACB][U+6AA2][U+67E5]SDK[U+5C0E][U+5165]")
        return
    
    try:
        print("[U+1F527] [U+7CFB][U+7D71][U+67B6][U+69CB]: Modbus TCP Client - [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+6A21][U+5F0F] v4.0")
        print("[U+1F4E1] [U+9023][U+63A5][U+6A21][U+5F0F]: [U+4E3B][U+52D5][U+9023][U+63A5][U+5916][U+90E8]PLC/HMI[U+8A2D][U+5099]")
        print("[U+1F91D] [U+63E1][U+624B][U+5354][U+8B70]: [U+6307][U+4EE4]/[U+72C0][U+614B][U+6A21][U+5F0F][U+FF0C]50ms[U+9AD8][U+983B][U+8F2A][U+8A62]")
        print("[U+1F30D] [U+65B0][U+529F][U+80FD]: NPY[U+5167][U+5916][U+53C3][U+7BA1][U+7406] + [U+50CF][U+7D20][U+5EA7][U+6A19][U+5230][U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB]")
        
        if MODBUS_AVAILABLE:
            print(f"[OK] Modbus TCP Client[U+6A21][U+7D44][U+53EF][U+7528] (pymodbus {PYMODBUS_VERSION})")
            print("[U+1F4CA] CCD1 [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+5BC4][U+5B58][U+5668][U+6620][U+5C04] v4.0:")
            print("   [U+250C][U+2500] [U+63A7][U+5236][U+6307][U+4EE4][U+5BC4][U+5B58][U+5668] (200)")
            print("   [U+2502]  [U+2022] 0: [U+6E05][U+7A7A][U+63A7][U+5236]")
            print("   [U+2502]  [U+2022] 8: [U+62CD][U+7167]")
            print("   [U+2502]  [U+2022] 16: [U+62CD][U+7167]+[U+6AA2][U+6E2C] ([U+542B][U+4E16][U+754C][U+5EA7][U+6A19])")
            print("   [U+2502]  [U+2022] 32: [U+91CD][U+65B0][U+521D][U+59CB][U+5316]")
            print("   [U+251C][U+2500] [U+72C0][U+614B][U+5BC4][U+5B58][U+5668] (201) - [U+56FA][U+5B9A][U+521D][U+59CB][U+503C]")
            print("   [U+2502]  [U+2022] bit0: Ready[U+72C0][U+614B]")
            print("   [U+2502]  [U+2022] bit1: Running[U+72C0][U+614B]")
            print("   [U+2502]  [U+2022] bit2: Alarm[U+72C0][U+614B]")
            print("   [U+2502]  [U+2022] bit3: Initialized[U+72C0][U+614B]")
            print("   [U+2502]  [U+2022] [U+521D][U+59CB][U+503C]: 1 (Ready=1, [U+5176][U+4ED6]=0)")
            print("   [U+2502]  [U+2022] [U+5B8C][U+5168][U+521D][U+59CB][U+5316][U+5F8C]: 9 (Ready=1, Initialized=1)")
            print("   [U+251C][U+2500] [U+6AA2][U+6E2C][U+53C3][U+6578] (210-219)")
            print("   [U+2502]  [U+2022] [U+9762][U+7A4D][U+3001][U+5713][U+5EA6][U+3001][U+5716][U+50CF][U+8655][U+7406][U+53C3][U+6578]")
            print("   [U+251C][U+2500] [U+50CF][U+7D20][U+5EA7][U+6A19][U+7D50][U+679C] (240-255)")
            print("   [U+2502]  [U+2022] [U+5713][U+5F62][U+6578][U+91CF][U+3001][U+50CF][U+7D20][U+5EA7][U+6A19][U+3001][U+534A][U+5F91]")
            print("   [U+251C][U+2500] [U+4E16][U+754C][U+5EA7][U+6A19][U+7D50][U+679C] (256-276) [U+2B50]v4.0[U+65B0][U+589E][U+2B50]")
            print("   [U+2502]  [U+2022] 256: [U+4E16][U+754C][U+5EA7][U+6A19][U+6709][U+6548][U+6A19][U+8A8C]")
            print("   [U+2502]  [U+2022] 257-276: [U+5713][U+5F62][U+4E16][U+754C][U+5EA7][U+6A19] (X[U+9AD8][U+4F4D]/[U+4F4E][U+4F4D], Y[U+9AD8][U+4F4D]/[U+4F4E][U+4F4D])")
            print("   [U+2502]  [U+2022] [U+7CBE][U+5EA6]: [U+00D7]100[U+5B58][U+5132][U+FF0C][U+4FDD][U+7559]2[U+4F4D][U+5C0F][U+6578]")
            print("   [U+2502]  [U+2022] [U+7BC4][U+570D]: [U+00B1]21474.83mm")
            print("   [U+2514][U+2500] [U+7D71][U+8A08][U+8CC7][U+8A0A] (280-299)")
            print("      [U+2022] [U+6642][U+9593][U+7D71][U+8A08][U+3001][U+8A08][U+6578][U+5668][U+3001][U+7248][U+672C][U+4FE1][U+606F]")
            print("")
            print("[U+1F30D] [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB][U+529F][U+80FD] v4.0:")
            print("   [U+2022] [U+5167][U+53C3][U+6A94][U+6848]: camera_matrix_YYYYMMDD_HHMMSS.npy")
            print("   [U+2022] [U+7578][U+8B8A][U+4FC2][U+6578]: dist_coeffs_YYYYMMDD_HHMMSS.npy") 
            print("   [U+2022] [U+5916][U+53C3][U+6A94][U+6848]: *extrinsic*.npy ([U+5305][U+542B]rvec/tvec)")
            print("   [U+2022] [U+6295][U+5F71][U+5E73][U+9762]: Z=0[U+5E73][U+9762]")
            print("   [U+2022] [U+81EA][U+52D5][U+6383][U+63CF]: [U+7A0B][U+5F0F][U+540C][U+5C64][U+76EE][U+9304]")
            print("   [U+2022] [U+5411][U+4E0B][U+517C][U+5BB9]: [U+7121][U+6A19][U+5B9A][U+6642][U+50C5][U+63D0][U+4F9B][U+50CF][U+7D20][U+5EA7][U+6A19]")
            print("")
            print("[U+1F91D] [U+63E1][U+624B][U+908F][U+8F2F]:")
            print("   1. [U+7CFB][U+7D71][U+521D][U+59CB][U+5316][U+5B8C][U+6210] [U+2192] Ready=1")
            print("   2. PLC[U+4E0B][U+63A7][U+5236][U+6307][U+4EE4] [U+2192] [U+6AA2][U+67E5]Ready=1")
            print("   3. [U+958B][U+59CB][U+57F7][U+884C] [U+2192] Ready=0, Running=1")
            print("   4. [U+57F7][U+884C][U+5B8C][U+6210] [U+2192] Running=0")
            print("   5. PLC[U+6E05][U+96F6][U+6307][U+4EE4] [U+2192] Ready=1 ([U+6E96][U+5099][U+4E0B][U+6B21])")
            print("   6. [U+7570][U+5E38][U+767C][U+751F] [U+2192] Alarm=1, Initialized=0")
            print("   7. v4.0: [U+81EA][U+52D5][U+66F4][U+65B0][U+4E16][U+754C][U+5EA7][U+6A19][U+6709][U+6548][U+6027][U+6A19][U+8A8C]")
        else:
            print("[WARN][U+FE0F] Modbus Client[U+529F][U+80FD][U+4E0D][U+53EF][U+7528] ([U+4F7F][U+7528][U+6A21][U+64EC][U+6A21][U+5F0F])")
        
        print("[U+1F310] Web[U+4ECB][U+9762][U+555F][U+52D5][U+4E2D]...")
        print("[U+1F4F1] [U+8A2A][U+554F][U+5730][U+5740]: http://localhost:5051")
        print("[U+1F3AF] [U+7CFB][U+7D71][U+529F][U+80FD]:")
        print("   [U+2022] [U+76F8][U+6A5F][U+9023][U+63A5][U+7BA1][U+7406]")
        print("   [U+2022] [U+53C3][U+6578][U+8ABF][U+6574][U+4ECB][U+9762]")
        print("   [U+2022] [U+5713][U+5F62][U+6AA2][U+6E2C][U+8207][U+6A19][U+8A3B]")
        print("   [U+2022] [U+904B][U+52D5][U+63A7][U+5236][U+63E1][U+624B][U+5354][U+8B70]")
        print("   [U+2022] [U+5373][U+6642][U+72C0][U+614B][U+76E3][U+63A7]")
        print("   [U+2022] [U+72C0][U+614B][U+6A5F][U+7BA1][U+7406]")
        print("   [U+2022] [U+2B50] v4.0: [U+6A19][U+5B9A][U+6A94][U+6848][U+7BA1][U+7406]")
        print("   [U+2022] [U+2B50] v4.0: [U+4E16][U+754C][U+5EA7][U+6A19][U+8F49][U+63DB]")
        print("   [U+2022] [U+2B50] v4.0: [U+96D9][U+5EA7][U+6A19][U+7CFB][U+7D50][U+679C][U+986F][U+793A]")
        print("[U+1F517] [U+4F7F][U+7528][U+8AAA][U+660E]:")
        print("   1. [U+6E96][U+5099][U+5167][U+5916][U+53C3]NPY[U+6A94][U+6848] ([U+653E][U+5165][U+7A0B][U+5F0F][U+540C][U+5C64][U+76EE][U+9304])")
        print("   2. [U+8A2D][U+7F6E]Modbus[U+670D][U+52D9][U+5668]IP[U+5730][U+5740]")
        print("   3. [U+9023][U+63A5][U+5230][U+5916][U+90E8]PLC/HMI[U+8A2D][U+5099]")
        print("   4. [U+521D][U+59CB][U+5316][U+76F8][U+6A5F][U+9023][U+63A5]")
        print("   5. [U+6383][U+63CF][U+4E26][U+8F09][U+5165][U+6A19][U+5B9A][U+6A94][U+6848] ([U+53EF][U+9078])")
        print("   6. [U+7CFB][U+7D71][U+81EA][U+52D5][U+9032][U+5165][U+63E1][U+624B][U+6A21][U+5F0F]")
        print("   7. PLC[U+901A][U+904E][U+63A7][U+5236][U+6307][U+4EE4][U+64CD][U+4F5C][U+7CFB][U+7D71]")
        print("   8. [U+76E3][U+63A7][U+72C0][U+614B][U+5BC4][U+5B58][U+5668][U+78BA][U+8A8D][U+57F7][U+884C][U+72C0][U+614B]")
        print("   9. [U+8B80][U+53D6][U+50CF][U+7D20][U+5EA7][U+6A19]+[U+4E16][U+754C][U+5EA7][U+6A19][U+6AA2][U+6E2C][U+7D50][U+679C]")
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