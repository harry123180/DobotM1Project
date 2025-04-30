# camera_manager.py
import threading
import time
import logging
from MvCameraControl_class import MvCamera
from CameraParams_header import *
from CameraParams_const import *
from MvErrorDefine_const import *
from ctypes import *

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# 1. 相機設定：名稱 -> IP or Serial
CAMERA_CONFIG = {
    "cam_3": "192.168.1.8",
    "cam_5": "192.168.1.75",
    "cam_4": "192.168.1.7",
    
}

# 2. 全域狀態表
camera_pool = {}

class CameraHandler:
    def __init__(self, name, ip):
        self.name = name
        self.ip = ip
        self.camera = MvCamera()
        self.connected = False
        self.last_error = None
        self.running = True
        self.lock = threading.Lock()
        self.reconnect_thread = threading.Thread(target=self.auto_reconnect, daemon=True)
        self.reconnect_thread.start()
    def shutdown(self):
        """關閉取流與設備"""
        self.running = False
        if self.connected:
            self.camera.MV_CC_StopGrabbing()
            self.camera.MV_CC_CloseDevice()
            self.connected = False
            logging.info(f"[{self.name}] Shutdown completed.")

    def get_status(self):
        """回傳目前狀態"""
        return {
            "connected": self.connected,
            "ip": self.ip,
            "last_error": self.last_error
        }

    def connect(self):
        try:
            logging.info(f"[{self.name}] Enumerating devices...")
            device_list = MV_CC_DEVICE_INFO_LIST()
            ret = self.camera.MV_CC_EnumDevices(MV_GIGE_DEVICE, device_list)
            if ret != MV_OK or device_list.nDeviceNum == 0:
                raise Exception("No camera found.")

            for i in range(device_list.nDeviceNum):
                device = device_list.pDeviceInfo[i].contents
                if device.nTLayerType == MV_GIGE_DEVICE:
                    ip = device.SpecialInfo.stGigEInfo.nCurrentIp
                    ip_addr = "{}.{}.{}.{}".format(
                        (ip >> 24) & 0xFF,
                        (ip >> 16) & 0xFF,
                        (ip >> 8) & 0xFF,
                        ip & 0xFF)
                    if ip_addr == self.ip:
                        self.device_info = device_list.pDeviceInfo[i]
                        break
            else:
                raise Exception(f"Camera with IP {self.ip} not found.")

            # Create and open device
            self.camera.MV_CC_CreateHandle(self.device_info.contents)
            ret = self.camera.MV_CC_OpenDevice()
            if ret != MV_OK:
                raise Exception(f"OpenDevice failed: {ret}")

            # 開啟取流
            self.camera.MV_CC_StartGrabbing()

            self.connected = True
            self.last_error = None
            logging.info(f"[{self.name}] Connected successfully.")
        except Exception as e:
            self.connected = False
            self.last_error = str(e)
            logging.error(f"[{self.name}] Connect failed: {e}")
    def auto_reconnect(self):
        while self.running:
            if not self.connected:
                logging.warning(f"[{self.name}] Not connected, trying to reconnect...")
                self.connect()
            time.sleep(5)

    def capture_image(self):
        if not self.connected:
            raise RuntimeError(f"Camera {self.name} not connected.")

        with self.lock:
            try:
                # 建立 buffer 與資訊結構
                width, height = 2592, 1944  # 根據你的設定調整
                img_size = width * height
                pData = (c_ubyte * img_size)()
                frame_info = MV_FRAME_OUT_INFO_EX()

                ret = self.camera.MV_CC_GetOneFrameTimeout(pData, img_size, frame_info, 1000)
                if ret != MV_OK:
                    raise RuntimeError(f"Get image failed: {ret}")

                # 回傳 raw bytes
                return bytes(pData[:frame_info.nWidth * frame_info.nHeight])
            except Exception as e:
                self.last_error = str(e)
                raise


def initialize_all_cameras():
    for name, ip in CAMERA_CONFIG.items():
        handler = CameraHandler(name, ip)
        camera_pool[name] = handler
    logging.info("All cameras initialized.")

# 提供簡單 API 給主程式呼叫
def get_all_status():
    return {name: handler.get_status() for name, handler in camera_pool.items()}

def get_image(camera_name):
    if camera_name not in camera_pool:
        raise ValueError(f"Camera {camera_name} not found.")
    return camera_pool[camera_name].capture_image()

def shutdown_all():
    for handler in camera_pool.values():
        handler.shutdown()
