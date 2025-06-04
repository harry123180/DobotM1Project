# -*- coding: utf-8 -*-
"""
Camera API - 抽象化相機控制API（修復版本）
基於Hikvision SDK的高級封裝，修復線程管理問題
"""

import threading
import time
import ctypes
from enum import Enum
from typing import List, Optional, Tuple, Callable
from ctypes import *

# 導入原始SDK模組
try:
    from MvCameraControl_class import *
    from MvErrorDefine_const import *
    from CameraParams_header import *
    from CamOperation_class import CameraOperation
    from PixelType_header import *
    
    # 嘗試導入改進的相機操作類
    try:
        from ImprovedCamOperation import ImprovedCameraOperation
        USE_IMPROVED_CAMERA = True
        print("使用改進的ImprovedCameraOperation類")
    except ImportError:
        USE_IMPROVED_CAMERA = False
        print("使用標準CameraOperation類")
        
except ImportError as e:
    print(f"導入SDK模組失敗: {e}")
    print("請確保所有SDK文件都在同一目錄下")
    raise


class CameraMode(Enum):
    """相機模式枚舉"""
    CONTINUOUS = "continuous"  # 連續模式
    TRIGGER = "trigger"       # 觸發模式


class ImageFormat(Enum):
    """圖像格式枚舉"""
    BMP = "bmp"
    JPEG = "jpeg"


class CameraStatus(Enum):
    """相機狀態枚舉"""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    STREAMING = "streaming"
    ERROR = "error"


class CameraInfo:
    """相機信息類"""
    def __init__(self, index: int, device_name: str, device_type: str, 
                 serial_number: str = "", ip_address: str = ""):
        self.index = index
        self.device_name = device_name
        self.device_type = device_type
        self.serial_number = serial_number
        self.ip_address = ip_address
    
    def __str__(self):
        return f"[{self.index}] {self.device_type}: {self.device_name}"


class CameraParameters:
    """相機參數類"""
    def __init__(self):
        self.frame_rate: float = 30.0
        self.exposure_time: float = 10000.0  # 微秒
        self.gain: float = 0.0
        self.packet_size: int = 1500
        
    def to_dict(self) -> dict:
        return {
            'frame_rate': self.frame_rate,
            'exposure_time': self.exposure_time,
            'gain': self.gain,
            'packet_size': self.packet_size
        }


class CameraAPI:
    """相機API主類（修復版本）"""
    
    def __init__(self):
        # 初始化SDK
        MvCamera.MV_CC_Initialize()
        
        # 內部狀態
        self._device_list = None
        self._camera_operation = None
        self._current_camera_index = -1
        self._status = CameraStatus.DISCONNECTED
        self._mode = CameraMode.CONTINUOUS
        self._is_streaming = False
        self._parameters = CameraParameters()
        
        # 回調函數
        self._frame_callback: Optional[Callable] = None
        self._error_callback: Optional[Callable] = None
        
        # 線程鎖
        self._lock = threading.RLock()  # 使用遞歸鎖
        
        # 狀態追踪
        self._last_operation_time = 0
    
    def __del__(self):
        """析構函數"""
        try:
            self.disconnect()
            MvCamera.MV_CC_Finalize()
        except:
            pass
    
    # ========== 設備枚舉相關 ==========
    
    def enumerate_devices(self) -> List[CameraInfo]:
        """
        枚舉相機設備
        Returns:
            List[CameraInfo]: 設備信息列表
        """
        try:
            self._device_list = MV_CC_DEVICE_INFO_LIST()
            n_layer_type = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                          | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
            
            ret = MvCamera.MV_CC_EnumDevices(n_layer_type, self._device_list)
            if ret != MV_OK:
                raise Exception(f"枚舉設備失敗: 0x{ret:08x}")
            
            devices = []
            for i in range(self._device_list.nDeviceNum):
                device_info = self._parse_device_info(i)
                devices.append(device_info)
            
            return devices
            
        except Exception as e:
            self._call_error_callback(f"枚舉設備錯誤: {str(e)}")
            return []
    
    def _parse_device_info(self, index: int) -> CameraInfo:
        """解析設備信息"""
        mvcc_dev_info = cast(self._device_list.pDeviceInfo[index], 
                           POINTER(MV_CC_DEVICE_INFO)).contents
        
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
            # GigE設備
            gige_info = mvcc_dev_info.SpecialInfo.stGigEInfo
            device_name = self._decode_string(gige_info.chUserDefinedName)
            model_name = self._decode_string(gige_info.chModelName)
            serial_number = self._decode_string(gige_info.chSerialNumber)
            
            # 解析IP地址
            ip = gige_info.nCurrentIp
            ip_str = f"{(ip >> 24) & 0xFF}.{(ip >> 16) & 0xFF}.{(ip >> 8) & 0xFF}.{ip & 0xFF}"
            
            return CameraInfo(
                index=index,
                device_name=f"{device_name} {model_name}",
                device_type="GigE",
                serial_number=serial_number,
                ip_address=ip_str
            )
            
        elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
            # USB設備
            usb_info = mvcc_dev_info.SpecialInfo.stUsb3VInfo
            device_name = self._decode_string(usb_info.chUserDefinedName)
            model_name = self._decode_string(usb_info.chModelName)
            serial_number = self._decode_string(usb_info.chSerialNumber)
            
            return CameraInfo(
                index=index,
                device_name=f"{device_name} {model_name}",
                device_type="USB3",
                serial_number=serial_number
            )
        
        else:
            return CameraInfo(
                index=index,
                device_name="Unknown Device",
                device_type="Unknown"
            )
    
    def _decode_string(self, byte_array) -> str:
        """解碼字節數組為字符串"""
        try:
            # 轉換為c_char_p並解碼
            c_char_p_value = ctypes.cast(byte_array, ctypes.c_char_p)
            try:
                return c_char_p_value.value.decode('gbk')
            except UnicodeDecodeError:
                return str(c_char_p_value.value)
        except:
            return "Unknown"
    
    # ========== 設備連接相關 ==========
    
    def connect(self, device_index: int) -> bool:
        """
        連接到指定設備
        Args:
            device_index: 設備索引
        Returns:
            bool: 連接是否成功
        """
        with self._lock:
            try:
                # 確保之前的連接完全清理
                if self._status != CameraStatus.DISCONNECTED:
                    print("清理之前的連接...")
                    self._force_cleanup()
                    time.sleep(1.0)  # 等待清理完成
                
                if self._device_list is None:
                    raise Exception("請先枚舉設備")
                
                if device_index >= self._device_list.nDeviceNum:
                    raise Exception("設備索引超出範圍")
                
                # 創建相機操作對象
                cam = MvCamera()
                
                # 使用改進的相機操作類（如果可用）
                if USE_IMPROVED_CAMERA:
                    self._camera_operation = ImprovedCameraOperation(
                        cam, self._device_list, device_index
                    )
                else:
                    self._camera_operation = CameraOperation(
                        cam, self._device_list, device_index
                    )
                    # 修復語法錯誤
                    self._camera_operation.b_thread_closed = False
                
                # 打開設備
                ret = self._camera_operation.Open_device()
                if ret != MV_OK:
                    error_code = ret if ret is not None else 0xFFFFFFFF
                    raise Exception(f"打開設備失敗: 0x{error_code:08x}")
                
                self._current_camera_index = device_index
                self._status = CameraStatus.CONNECTED
                self._last_operation_time = time.time()
                
                # 設置默認參數
                self._apply_default_settings()
                
                return True
                
            except Exception as e:
                self._call_error_callback(f"連接設備錯誤: {str(e)}")
                self._status = CameraStatus.ERROR
                return False
    
    def disconnect(self) -> bool:
        """
        斷開設備連接
        Returns:
            bool: 斷開是否成功
        """
        with self._lock:
            return self._force_cleanup()
    
    def _force_cleanup(self) -> bool:
        """強制清理所有資源"""
        success = True
        
        try:
            print("開始強制清理資源...")
            
            # 1. 停止串流
            if self._is_streaming:
                print("停止串流...")
                try:
                    self._is_streaming = False
                    if self._camera_operation:
                        # 設置退出標誌
                        self._camera_operation.b_exit = True
                        
                        # 等待線程自然結束
                        if hasattr(self._camera_operation, 'thread_running'):
                            self._camera_operation.thread_running = False
                        if hasattr(self._camera_operation, 'thread_stop_event'):
                            self._camera_operation.thread_stop_event.set()
                        
                        # 等待一段時間
                        time.sleep(0.5)
                        
                        # 調用停止方法
                        ret = self._camera_operation.Stop_grabbing()
                        if ret != MV_OK and ret is not None:
                            print(f"停止串流警告: 0x{ret:08x}")
                except Exception as e:
                    print(f"停止串流異常: {str(e)}")
                    success = False
            
            # 2. 關閉設備
            if self._camera_operation:
                print("關閉設備...")
                try:
                    # 等待一下確保串流完全停止
                    time.sleep(0.5)
                    
                    ret = self._camera_operation.Close_device()
                    if ret != MV_OK and ret is not None:
                        print(f"關閉設備警告: 0x{ret:08x}")
                except Exception as e:
                    print(f"關閉設備異常: {str(e)}")
                    success = False
            
            # 3. 清理狀態
            self._camera_operation = None
            self._current_camera_index = -1
            self._status = CameraStatus.DISCONNECTED
            self._is_streaming = False
            
            print("資源清理完成")
            return success
            
        except Exception as e:
            self._call_error_callback(f"清理資源錯誤: {str(e)}")
            # 強制重置狀態
            self._camera_operation = None
            self._current_camera_index = -1
            self._status = CameraStatus.DISCONNECTED
            self._is_streaming = False
            return False
    
    def _apply_default_settings(self):
        """應用默認設置"""
        try:
            # 設置連續模式
            self.set_mode(CameraMode.CONTINUOUS)
            
            # 獲取當前參數
            self.get_parameters()
            
        except Exception as e:
            print(f"應用默認設置警告: {str(e)}")
    
    # ========== 串流控制相關 ==========
    
    def start_streaming(self, display_handle=None) -> bool:
        """
        開始串流
        Args:
            display_handle: 顯示窗口句柄（可選）
        Returns:
            bool: 啟動是否成功
        """
        with self._lock:
            if not self._check_connection():
                return False
            
            if self._is_streaming:
                return True
            
            try:
                # 檢查時間間隔，避免操作過於頻繁
                current_time = time.time()
                if current_time - self._last_operation_time < 1.0:
                    time.sleep(1.0 - (current_time - self._last_operation_time))
                
                # 確保設備處於正確狀態
                if not self._camera_operation.b_open_device:
                    self._call_error_callback("設備未打開")
                    return False
                
                # 如果檢測到之前的串流狀態，強制清理
                if (hasattr(self._camera_operation, 'b_start_grabbing') and 
                    self._camera_operation.b_start_grabbing):
                    print("檢測到之前的串流狀態，正在清理...")
                    self._camera_operation.b_start_grabbing = False
                    self._camera_operation.b_exit = True
                    time.sleep(1.0)
                    self._camera_operation.b_exit = False
                
                # 如果沒有提供display_handle，使用0作為默認值
                if display_handle is None:
                    display_handle = 0
                    
                ret = self._camera_operation.Start_grabbing(display_handle)
                if ret == MV_OK:
                    self._is_streaming = True
                    self._status = CameraStatus.STREAMING
                    self._last_operation_time = time.time()
                    return True
                else:
                    error_code = ret if ret is not None else 0xFFFFFFFF
                    raise Exception(f"開始串流失敗: 0x{error_code:08x}")
                    
            except Exception as e:
                self._call_error_callback(f"開始串流錯誤: {str(e)}")
                return False
    
    def stop_streaming(self) -> bool:
        """
        停止串流
        Returns:
            bool: 停止是否成功
        """
        with self._lock:
            if not self._is_streaming:
                return True
            
            try:
                print("正在停止串流...")
                
                # 標記停止狀態
                self._is_streaming = False
                self._status = CameraStatus.CONNECTED
                
                if self._camera_operation:
                    # 使用改進的停止方法
                    ret = self._camera_operation.Stop_grabbing()
                    if ret != MV_OK and ret is not None:
                        print(f"停止串流警告: 0x{ret:08x}")
                
                self._last_operation_time = time.time()
                print("串流已停止")
                return True
                
            except Exception as e:
                # 不要調用error callback，因為這可能導致無限遞歸
                print(f"停止串流錯誤: {str(e)}")
                # 即使出錯也要更新狀態
                self._is_streaming = False
                self._status = CameraStatus.CONNECTED
                return False
    
    def is_streaming(self) -> bool:
        """檢查是否正在串流"""
        return self._is_streaming
    
    # ========== 參數設置相關 ==========
    
    def set_packet_size(self, packet_size: int) -> bool:
        """
        設置網絡包大小（僅GigE設備有效）
        Args:
            packet_size: 包大小，0表示自動優化
        Returns:
            bool: 設置是否成功
        """
        if not self._check_connection():
            return False
        
        try:
            # 獲取最佳包大小
            optimal_size = self._camera_operation.obj_cam.MV_CC_GetOptimalPacketSize()
            if optimal_size > 0:
                ret = self._camera_operation.obj_cam.MV_CC_SetIntValue(
                    "GevSCPSPacketSize", optimal_size
                )
                if ret == MV_OK:
                    self._parameters.packet_size = optimal_size
                    return True
            
            return False
            
        except Exception as e:
            self._call_error_callback(f"設置包大小錯誤: {str(e)}")
            return False
    
    def get_parameters(self) -> Optional[CameraParameters]:
        """
        獲取當前參數
        Returns:
            CameraParameters: 參數對象
        """
        if not self._check_connection():
            return None
        
        try:
            ret = self._camera_operation.Get_parameter()
            if ret == MV_OK:
                self._parameters.frame_rate = self._camera_operation.frame_rate
                self._parameters.exposure_time = self._camera_operation.exposure_time
                self._parameters.gain = self._camera_operation.gain
                return self._parameters
            else:
                error_code = ret if ret is not None else 0xFFFFFFFF
                raise Exception(f"獲取參數失敗: 0x{error_code:08x}")
                
        except Exception as e:
            self._call_error_callback(f"獲取參數錯誤: {str(e)}")
            return None
    
    def set_parameters(self, params: CameraParameters) -> bool:
        """
        設置參數
        Args:
            params: 參數對象
        Returns:
            bool: 設置是否成功
        """
        if not self._check_connection():
            return False
        
        try:
            ret = self._camera_operation.Set_parameter(
                str(params.frame_rate),
                str(params.exposure_time), 
                str(params.gain)
            )
            if ret == MV_OK:
                self._parameters = params
                return True
            else:
                error_code = ret if ret is not None else 0xFFFFFFFF
                raise Exception(f"設置參數失敗: 0x{error_code:08x}")
                
        except Exception as e:
            self._call_error_callback(f"設置參數錯誤: {str(e)}")
            return False
    
    # ========== 模式設置相關 ==========
    
    def set_mode(self, mode: CameraMode) -> bool:
        """
        設置相機模式
        Args:
            mode: 相機模式
        Returns:
            bool: 設置是否成功
        """
        if not self._check_connection():
            return False
        
        try:
            # 如果正在串流，需要先停止
            was_streaming = self._is_streaming
            if was_streaming:
                self.stop_streaming()
                time.sleep(1.0)  # 增加等待時間
            
            is_trigger = (mode == CameraMode.TRIGGER)
            ret = self._camera_operation.Set_trigger_mode(is_trigger)
            
            if ret == MV_OK:
                self._mode = mode
                
                # 如果之前在串流，重新開始串流
                if was_streaming:
                    time.sleep(0.5)
                    self.start_streaming()
                
                return True
            else:
                error_code = ret if ret is not None else 0xFFFFFFFF
                raise Exception(f"設置模式失敗: 0x{error_code:08x}")
                
        except Exception as e:
            self._call_error_callback(f"設置模式錯誤: {str(e)}")
            return False
    
    def get_mode(self) -> CameraMode:
        """獲取當前模式"""
        return self._mode
    
    # ========== 觸發控制相關 ==========
    
    def software_trigger(self) -> bool:
        """
        軟觸發
        Returns:
            bool: 觸發是否成功
        """
        if not self._check_connection():
            return False
        
        if self._mode != CameraMode.TRIGGER:
            self._call_error_callback("軟觸發僅在觸發模式下可用")
            return False
        
        try:
            ret = self._camera_operation.Trigger_once()
            if ret is None:
                ret = MV_OK
            
            if ret == MV_OK:
                return True
            else:
                error_code = ret if ret is not None else 0xFFFFFFFF
                raise Exception(f"軟觸發失敗: 0x{error_code:08x}")
                
        except Exception as e:
            self._call_error_callback(f"軟觸發錯誤: {str(e)}")
            return False
    
    # ========== 圖像保存相關 ==========
    
    def save_image(self, format_type: ImageFormat = ImageFormat.BMP) -> bool:
        """
        保存圖像
        Args:
            format_type: 圖像格式
        Returns:
            bool: 保存是否成功
        """
        if not self._check_connection():
            return False
        
        if not self._is_streaming:
            self._call_error_callback("保存圖像需要在串流狀態下")
            return False
        
        try:
            # 檢查是否有圖像數據
            if (not hasattr(self._camera_operation, 'buf_save_image') or 
                self._camera_operation.buf_save_image is None):
                self._call_error_callback("圖像緩衝區為空，請稍候再試")
                return False
            
            if format_type == ImageFormat.BMP:
                ret = self._camera_operation.Save_Bmp()
            else:  # JPEG
                ret = self._camera_operation.Save_jpg()
            
            if ret is None:
                self._call_error_callback("保存失敗：圖像緩衝區為空")
                return False
            elif ret == MV_OK:
                return True
            else:
                error_code = ret if ret is not None else 0xFFFFFFFF
                raise Exception(f"保存圖像失敗: 0x{error_code:08x}")
                
        except Exception as e:
            self._call_error_callback(f"保存圖像錯誤: {str(e)}")
            return False
    
    # ========== 狀態查詢相關 ==========
    
    def get_status(self) -> CameraStatus:
        """獲取相機狀態"""
        return self._status
    
    def is_connected(self) -> bool:
        """檢查是否已連接"""
        return self._status in [CameraStatus.CONNECTED, CameraStatus.STREAMING]
    
    def get_current_device_index(self) -> int:
        """獲取當前設備索引"""
        return self._current_camera_index
    
    def get_device_info(self) -> Optional[CameraInfo]:
        """獲取當前設備信息"""
        if self._current_camera_index >= 0 and self._device_list:
            return self._parse_device_info(self._current_camera_index)
        return None
    
    # ========== 回調函數相關 ==========
    
    def set_frame_callback(self, callback: Callable):
        """設置幀回調函數"""
        self._frame_callback = callback
    
    def set_error_callback(self, callback: Callable):
        """設置錯誤回調函數"""
        self._error_callback = callback
    
    def _call_error_callback(self, error_msg: str):
        """調用錯誤回調"""
        if self._error_callback:
            try:
                self._error_callback(error_msg)
            except:
                pass
        else:
            print(f"Camera API Error: {error_msg}")
    
    # ========== 內部輔助方法 ==========
    
    def _check_connection(self) -> bool:
        """檢查連接狀態"""
        if not self.is_connected():
            self._call_error_callback("相機未連接")
            return False
        return True


# 便利函數
def create_camera_api() -> CameraAPI:
    """創建相機API實例"""
    return CameraAPI()


def get_available_cameras() -> List[CameraInfo]:
    """快速獲取可用相機列表"""
    api = create_camera_api()
    devices = api.enumerate_devices()
    del api
    return devices


# 測試用例
if __name__ == "__main__":
    # 基本測試
    api = create_camera_api()
    
    # 枚舉設備
    devices = api.enumerate_devices()
    print(f"找到 {len(devices)} 個設備:")
    for device in devices:
        print(f"  {device}")
    
    if devices:
        # 連接第一個設備
        if api.connect(0):
            print("設備連接成功")
            
            # 獲取參數
            params = api.get_parameters()
            if params:
                print(f"當前參數: {params.to_dict()}")
            
            # 設置模式
            api.set_mode(CameraMode.CONTINUOUS)
            print(f"當前模式: {api.get_mode()}")
            
            # 斷開連接
            api.disconnect()
            print("設備已斷開")
    
    print("測試完成")