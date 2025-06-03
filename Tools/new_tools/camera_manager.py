import time
import socket
import struct
import numpy as np
from ctypes import *
from MvCameraControl_class import MvCamera, MV_CC_DEVICE_INFO_LIST, MV_CC_DEVICE_INFO, MV_FRAME_OUT_INFO_EX
from CameraParams_const import *

class CameraManager:
    def __init__(self):
        self.device_list = MV_CC_DEVICE_INFO_LIST()
        self.cam = MvCamera()
        self.cam_handle_created = False
        self.connected = False

    def enum_devices(self):
        nTLayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE)
        ret = self.cam.MV_CC_EnumDevices(nTLayerType, self.device_list)
        if ret != 0:
            raise RuntimeError(f"Enum Devices Failed: {ret}")

        results = []
        for i in range(self.device_list.nDeviceNum):
            device_info = cast(self.device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if device_info.nTLayerType == MV_GIGE_DEVICE:
                ip_int = device_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip_str = socket.inet_ntoa(struct.pack('>I', ip_int))
                results.append((i, ip_str))
        return results

    def connect(self, index):
        if index >= self.device_list.nDeviceNum:
            raise ValueError("Device index out of range")

        device_info = cast(self.device_list.pDeviceInfo[index], POINTER(MV_CC_DEVICE_INFO))
        ret = self.cam.MV_CC_CreateHandle(device_info)
        if ret != 0:
            raise RuntimeError("Create Handle Failed")

        self.cam_handle_created = True
        ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            raise RuntimeError("Open Device Failed")

        # Set bandwidth to 200
        self.cam.MV_CC_SetIntValue("GevSCPSPacketSize", 200)

        # Set software trigger
        self.cam.MV_CC_SetEnumValueByString("TriggerMode", "On")
        self.cam.MV_CC_SetEnumValueByString("TriggerSource", "Software")

        self.connected = True

    def trigger_and_get_image(self):
        if not self.connected:
            raise RuntimeError("Camera not connected")

        self.cam.MV_CC_SetCommandValue("TriggerSoftware")
        time.sleep(0.1)

        frame_info = MV_FRAME_OUT_INFO_EX()
        buf_len = 2592 * 1944
        data_buf = create_string_buffer(buf_len)

        ret = self.cam.MV_CC_GetOneFrameTimeout(data_buf, buf_len, byref(frame_info), 1000)
        if ret != 0:
            raise RuntimeError("Get Image Failed")

        image = np.frombuffer(data_buf.raw[:frame_info.nFrameLen], dtype=np.uint8)
        image = image.reshape((frame_info.nHeight, frame_info.nWidth))
        return image

    def close(self):
        if self.connected:
            self.cam.MV_CC_CloseDevice()
            self.connected = False

        if self.cam_handle_created:
            self.cam.MV_CC_DestroyHandle()
            self.cam_handle_created = False
