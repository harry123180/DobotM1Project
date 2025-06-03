# -*- coding: utf-8 -*-
import os
import time
from ctypes import *

from MvCameraControl_class import *
from MvErrorDefine_const import *
from CameraParams_header import *

# 相機操作類，負責相機的各種操作
class CameraOperation:

    def __init__(self, cam, device_list, camera_index):
        self.cam = cam
        self.device_list = device_list
        self.camera_index = camera_index
        
        # 相機參數
        self.exposure_time = 0.0
        self.gain = 0.0
        self.frame_rate = 0.0
        
        # 圖像參數
        self.image_buffer = None
        self.image_width = 0
        self.image_height = 0
        self.pixel_format = 0

    # 打開設備
    def Open_device(self):
        if not self.device_list:
            return MV_E_PARAMETER
            
        if self.camera_index >= self.device_list.nDeviceNum:
            return MV_E_PARAMETER

        # 選擇設備並創建句柄
        stDeviceInfo = cast(self.device_list.pDeviceInfo[self.camera_index], POINTER(MV_CC_DEVICE_INFO)).contents
        ret = self.cam.MV_CC_CreateHandle(stDeviceInfo)
        if ret != 0:
            return ret

        # 打開設備
        ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            return ret

        # 探測網路最佳包大小(只對GigE相機有效)
        if stDeviceInfo.nTLayerType == MV_GIGE_DEVICE:
            nPacketSize = self.cam.MV_CC_GetOptimalPacketSize()
            if int(nPacketSize) > 0:
                ret = self.cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                if ret != 0:
                    print("Warning: Set Packet Size failed! ret[0x%x]" % ret)
            else:
                print("Warning: Get Packet Size failed! ret[0x%x]" % nPacketSize)

        # 設置觸發模式為off
        ret = self.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        if ret != 0:
            print("Set trigger mode failed! ret[0x%x]" % ret)

        return MV_OK

    # 開始取流
    def Start_grabbing(self, win_handle=None):
        ret = self.cam.MV_CC_StartGrabbing()
        return ret

    # 停止取流
    def Stop_grabbing(self):
        ret = self.cam.MV_CC_StopGrabbing()
        return ret

    # 關閉設備
    def Close_device(self):
        # 停止取流
        ret = self.cam.MV_CC_StopGrabbing()
        if ret != 0:
            print("Stop grabbing failed! ret[0x%x]" % ret)

        # 關閉設備
        ret = self.cam.MV_CC_CloseDevice()
        if ret != 0:
            print("Close device failed! ret[0x%x]" % ret)

        # 銷毀句柄
        ret = self.cam.MV_CC_DestroyHandle()
        if ret != 0:
            print("Destroy handle failed! ret[0x%x]" % ret)

        return MV_OK

    # 設置觸發模式
    def Set_trigger_mode(self, is_trigger_mode):
        if is_trigger_mode:
            # 設置觸發模式為ON
            ret = self.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
            if ret != 0:
                return ret
            
            # 設置觸發源為軟觸發
            ret = self.cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
            if ret != 0:
                return ret
        else:
            # 設置觸發模式為OFF
            ret = self.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            if ret != 0:
                return ret

        return MV_OK

    # 軟觸發一次
    def Trigger_once(self):
        ret = self.cam.MV_CC_SetCommandValue("TriggerSoftware")
        return ret

    # 獲取參數
    def Get_parameter(self):
        # 獲取曝光時間
        stFloatValue = MVCC_FLOATVALUE()
        memset(byref(stFloatValue), 0, sizeof(MVCC_FLOATVALUE))
        ret = self.cam.MV_CC_GetFloatValue("ExposureTime", stFloatValue)
        if ret == 0:
            self.exposure_time = stFloatValue.fCurValue

        # 獲取增益
        stFloatValue = MVCC_FLOATVALUE()
        memset(byref(stFloatValue), 0, sizeof(MVCC_FLOATVALUE))
        ret = self.cam.MV_CC_GetFloatValue("Gain", stFloatValue)
        if ret == 0:
            self.gain = stFloatValue.fCurValue

        # 獲取幀率
        stFloatValue = MVCC_FLOATVALUE()
        memset(byref(stFloatValue), 0, sizeof(MVCC_FLOATVALUE))
        ret = self.cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stFloatValue)
        if ret == 0:
            self.frame_rate = stFloatValue.fCurValue

        return MV_OK

    # 設置參數
    def Set_parameter(self, frame_rate, exposure_time, gain):
        try:
            # 設置幀率
            if frame_rate is not None:
                ret = self.cam.MV_CC_SetFloatValue("AcquisitionFrameRate", float(frame_rate))
                if ret != 0:
                    return ret

            # 設置曝光時間
            if exposure_time is not None:
                ret = self.cam.MV_CC_SetFloatValue("ExposureTime", float(exposure_time))
                if ret != 0:
                    return ret

            # 設置增益
            if gain is not None:
                ret = self.cam.MV_CC_SetFloatValue("Gain", float(gain))
                if ret != 0:
                    return ret

            return MV_OK
        except ValueError:
            return MV_E_PARAMETER

    # 保存圖片
    def Save_Bmp(self):
        # 獲取圖像數據
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))
        ret = self.cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
        if ret != 0:
            return ret

        # 獲取圖像信息
        stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
        memset(byref(stConvertParam), 0, sizeof(stConvertParam))
        
        # 設置轉換參數
        stConvertParam.nWidth = stOutFrame.stFrameInfo.nWidth
        stConvertParam.nHeight = stOutFrame.stFrameInfo.nHeight
        stConvertParam.enSrcPixelType = stOutFrame.stFrameInfo.enPixelType
        stConvertParam.pSrcData = stOutFrame.pBufAddr
        stConvertParam.nSrcDataLen = stOutFrame.stFrameInfo.nFrameLen
        stConvertParam.enDstPixelType = PixelType_Gvsp_BGR8_Packed
        
        # 計算轉換後的圖像大小
        nConvertSize = stConvertParam.nWidth * stConvertParam.nHeight * 3
        stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
        stConvertParam.nDstBufferSize = nConvertSize
        
        # 執行像素格式轉換
        ret = self.cam.MV_CC_ConvertPixelType(stConvertParam)
        if ret != 0:
            self.cam.MV_CC_FreeImageBuffer(stOutFrame)
            return ret

        # 保存為BMP文件
        stSaveParam = MV_SAVE_IMAGE_PARAM_EX()
        stSaveParam.enImageType = MV_Image_Bmp
        stSaveParam.enPixelType = stConvertParam.enDstPixelType
        stSaveParam.nWidth = stConvertParam.nWidth
        stSaveParam.nHeight = stConvertParam.nHeight
        stSaveParam.pData = cast(stConvertParam.pDstBuffer, POINTER(c_ubyte))
        stSaveParam.nDataLen = stConvertParam.nDstLen
        stSaveParam.pImageBuffer = (c_ubyte * (stSaveParam.nWidth * stSaveParam.nHeight * 4))()
        stSaveParam.nBufferSize = stSaveParam.nWidth * stSaveParam.nHeight * 4

        # 保存圖片
        ret = self.cam.MV_CC_SaveImageEx2(stSaveParam)
        if ret != 0:
            self.cam.MV_CC_FreeImageBuffer(stOutFrame)
            return ret

        # 生成文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        file_name = f"Image_{timestamp}.bmp"
        
        # 確保保存目錄存在
        save_dir = "saved_images"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        file_path = os.path.join(save_dir, file_name)
        
        # 寫入文件
        try:
            with open(file_path, 'wb') as file:
                file.write(stSaveParam.pImageBuffer[:stSaveParam.nImageLen])
            print(f"Image saved as {file_path}")
        except Exception as e:
            print(f"Save image failed: {e}")
            self.cam.MV_CC_FreeImageBuffer(stOutFrame)
            return MV_E_OPENFILE

        # 釋放圖像緩存
        ret = self.cam.MV_CC_FreeImageBuffer(stOutFrame)
        return ret

    # 獲取圖像數據(用於實時預覽)
    def Get_image_data(self):
        """獲取圖像數據用於實時預覽"""
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))
        ret = self.cam.MV_CC_GetImageBuffer(stOutFrame, 100)
        if ret != 0:
            return None, ret

        try:
            # 獲取圖像信息
            image_data = {
                'width': stOutFrame.stFrameInfo.nWidth,
                'height': stOutFrame.stFrameInfo.nHeight,
                'pixel_format': stOutFrame.stFrameInfo.enPixelType,
                'data_len': stOutFrame.stFrameInfo.nFrameLen,
                'buffer_addr': stOutFrame.pBufAddr
            }
            
            return image_data, MV_OK
        finally:
            # 釋放圖像緩存
            self.cam.MV_CC_FreeImageBuffer(stOutFrame)