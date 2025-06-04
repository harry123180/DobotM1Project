# -*- coding: utf-8 -*-
"""
改進的相機操作類 - 修復線程管理問題（完全重寫版本）
"""

import threading
import time
import random
from ctypes import *
from CameraParams_header import *
from MvCameraControl_class import *
from MvErrorDefine_const import *

# 導入必要的工具函數
def To_hex_str(num):
    chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hexStr = ""
    if num < 0:
        num = num + 2 ** 32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr
    return hexStr

class ImprovedCameraOperation:
    """完全重寫的相機操作類，專注於線程安全"""
    
    def __init__(self, obj_cam, st_device_list, n_connect_num=0):
        self.obj_cam = obj_cam
        self.st_device_list = st_device_list
        self.n_connect_num = n_connect_num
        
        # 狀態變量
        self.b_open_device = False
        self.b_start_grabbing = False
        self.b_exit = False
        
        # 線程相關
        self.work_thread = None
        self.thread_running = False
        self.thread_stop_event = threading.Event()
        
        # 圖像緩衝相關
        self.buf_save_image = None
        self.st_frame_info = None
        self.buf_lock = threading.Lock()
        
        # 參數
        self.frame_rate = 0
        self.exposure_time = 0
        self.gain = 0

    def Open_device(self):
        """打開相機設備"""
        if self.b_open_device:
            return MV_OK
            
        if self.n_connect_num < 0:
            return MV_E_CALLORDER

        try:
            # 選擇設備並創建句柄
            nConnectionNum = int(self.n_connect_num)
            stDeviceList = cast(self.st_device_list.pDeviceInfo[int(nConnectionNum)],
                                POINTER(MV_CC_DEVICE_INFO)).contents
            
            ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
            if ret != 0:
                self.obj_cam.MV_CC_DestroyHandle()
                return ret

            ret = self.obj_cam.MV_CC_OpenDevice()
            if ret != 0:
                return ret
                
            print("open device successfully!")
            self.b_open_device = True

            # 網絡包大小優化（僅GigE設備）
            if stDeviceList.nTLayerType == MV_GIGE_DEVICE or stDeviceList.nTLayerType == MV_GENTL_GIGE_DEVICE:
                nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
                if int(nPacketSize) > 0:
                    ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                    if ret != 0:
                        print("warning: set packet size fail! ret[0x%x]" % ret)
                else:
                    print("warning: set packet size fail! ret[0x%x]" % nPacketSize)

            # 設置觸發模式為off
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            if ret != 0:
                print("set trigger mode fail! ret[0x%x]" % ret)
                
            return MV_OK
            
        except Exception as e:
            print(f"Open device exception: {str(e)}")
            return MV_E_UNKNOW

    def Start_grabbing(self, winHandle=0):
        """開始取圖"""
        if self.b_start_grabbing:
            print("Already grabbing")
            return MV_OK
            
        if not self.b_open_device:
            return MV_E_CALLORDER

        try:
            # 重置狀態
            self.b_exit = False
            self.thread_stop_event.clear()
            
            # 啟動相機取圖
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                return ret
            
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            
            # 啟動工作線程
            self.thread_running = True
            self.work_thread = threading.Thread(
                target=self._work_thread_safe,
                args=(winHandle,),
                daemon=True,
                name=f"CameraThread_{random.randint(1000, 9999)}"
            )
            self.work_thread.start()
            
            return MV_OK
            
        except Exception as e:
            print(f"Start grabbing exception: {str(e)}")
            self.b_start_grabbing = False
            return MV_E_UNKNOW

    def Stop_grabbing(self):
        """停止取圖"""
        if not self.b_start_grabbing:
            return MV_OK

        try:
            print("Stopping grabbing...")
            
            # 1. 設置停止標誌
            self.b_exit = True
            self.thread_running = False
            self.thread_stop_event.set()
            
            # 2. 等待線程結束
            if self.work_thread and self.work_thread.is_alive():
                print("Waiting for work thread to finish...")
                self.work_thread.join(timeout=3.0)
                
                if self.work_thread.is_alive():
                    print("Warning: Work thread did not finish in time")
                else:
                    print("Work thread finished successfully")
            
            # 3. 停止相機取圖
            if self.b_start_grabbing:
                ret = self.obj_cam.MV_CC_StopGrabbing()
                if ret != 0:
                    print(f"Warning: Stop grabbing returned error: 0x{ret:08X}")
            
            # 4. 清理狀態
            self.b_start_grabbing = False
            self.work_thread = None
            
            # 5. 清理緩衝區
            with self.buf_lock:
                if self.buf_save_image is not None:
                    try:
                        del self.buf_save_image
                    except:
                        pass
                    self.buf_save_image = None
                self.st_frame_info = None
            
            print("stop grabbing successfully!")
            return MV_OK
            
        except Exception as e:
            print(f"Stop grabbing exception: {str(e)}")
            # 強制清理狀態
            self.b_start_grabbing = False
            self.b_exit = True
            self.thread_running = False
            return MV_E_UNKNOW

    def Close_device(self):
        """關閉設備"""
        if not self.b_open_device:
            return MV_OK

        try:
            # 1. 先停止取圖
            if self.b_start_grabbing:
                self.Stop_grabbing()
                time.sleep(0.5)  # 等待完全停止
            
            # 2. 關閉設備
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                print(f"Warning: Close device returned error: 0x{ret:08X}")
            
            # 3. 銷毀句柄
            self.obj_cam.MV_CC_DestroyHandle()
            
            # 4. 重置狀態
            self.b_open_device = False
            self.b_start_grabbing = False
            self.b_exit = True
            
            print("close device successfully!")
            return MV_OK
            
        except Exception as e:
            print(f"Close device exception: {str(e)}")
            # 強制重置狀態
            self.b_open_device = False
            self.b_start_grabbing = False
            self.b_exit = True
            return MV_E_UNKNOW

    def _work_thread_safe(self, winHandle):
        """線程安全的工作線程"""
        stOutFrame = MV_FRAME_OUT()
        frame_count = 0
        
        try:
            print(f"Work thread started: {threading.current_thread().name}")
            
            while self.thread_running and not self.b_exit:
                try:
                    # 檢查停止事件
                    if self.thread_stop_event.is_set():
                        break
                    
                    # 獲取圖像
                    memset(byref(stOutFrame), 0, sizeof(stOutFrame))
                    ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 100)  # 減少超時時間
                    
                    if ret == 0:
                        frame_count += 1
                        
                        # 處理圖像數據
                        with self.buf_lock:
                            try:
                                # 分配或重用緩衝區
                                if (self.buf_save_image is None or 
                                    sizeof(self.buf_save_image) < stOutFrame.stFrameInfo.nFrameLen):
                                    self.buf_save_image = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
                                
                                # **關鍵修復：更新共享的frame info**
                                self.st_frame_info = stOutFrame.stFrameInfo
                                
                                # 複製圖像數據
                                cdll.msvcrt.memcpy(
                                    byref(self.buf_save_image), 
                                    stOutFrame.pBufAddr, 
                                    self.st_frame_info.nFrameLen
                                )
                                
                                # 每30幀輸出一次
                                if frame_count % 30 == 0:
                                    print(f"Processed {frame_count} frames: Width[{self.st_frame_info.nWidth}], Height[{self.st_frame_info.nHeight}]")
                                
                            except Exception as e:
                                print(f"Image processing error: {str(e)}")
                        
                        # 釋放緩存
                        self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                        
                        # 顯示圖像（如果有窗口句柄）
                        if winHandle and winHandle != 0:
                            try:
                                self._display_frame(winHandle)
                            except Exception as e:
                                print(f"Display error: {str(e)}")
                    
                    elif ret == MV_E_NODATA:
                        # 無數據是正常的，短暫等待
                        time.sleep(0.01)
                    else:
                        # 其他錯誤
                        if self.thread_running and not self.b_exit:
                            print(f"Get image buffer error: 0x{ret:08X}")
                        time.sleep(0.05)
                    
                    # 檢查退出條件
                    if self.b_exit or self.thread_stop_event.is_set():
                        break
                        
                except Exception as e:
                    print(f"Work thread inner exception: {str(e)}")
                    if self.b_exit:
                        break
                    time.sleep(0.1)
            
        except Exception as e:
            print(f"Work thread exception: {str(e)}")
        finally:
            self.thread_running = False
            print(f"Work thread finished: {threading.current_thread().name}, processed {frame_count} frames")

    def _display_frame(self, winHandle):
        """顯示圖像幀"""
        if not self.st_frame_info or not self.buf_save_image:
            return
            
        stDisplayParam = MV_DISPLAY_FRAME_INFO()
        memset(byref(stDisplayParam), 0, sizeof(stDisplayParam))
        stDisplayParam.hWnd = int(winHandle)
        stDisplayParam.nWidth = self.st_frame_info.nWidth
        stDisplayParam.nHeight = self.st_frame_info.nHeight
        stDisplayParam.enPixelType = self.st_frame_info.enPixelType
        stDisplayParam.pData = self.buf_save_image
        stDisplayParam.nDataLen = self.st_frame_info.nFrameLen
        self.obj_cam.MV_CC_DisplayOneFrame(stDisplayParam)

    def Set_trigger_mode(self, is_trigger_mode):
        """設置觸發模式"""
        if not self.b_open_device:
            return MV_E_CALLORDER

        try:
            if not is_trigger_mode:
                ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 0)
            else:
                ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 1)
                if ret == 0:
                    ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource", 7)
            return ret
        except Exception as e:
            print(f"Set trigger mode exception: {str(e)}")
            return MV_E_UNKNOW

    def Trigger_once(self):
        """軟觸發一次"""
        if self.b_open_device:
            try:
                return self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
            except Exception as e:
                print(f"Trigger once exception: {str(e)}")
                return MV_E_UNKNOW
        return MV_E_CALLORDER

    def Get_parameter(self):
        """獲取參數"""
        if not self.b_open_device:
            return MV_E_CALLORDER

        try:
            stFloatParam_FrameRate = MVCC_FLOATVALUE()
            stFloatParam_exposureTime = MVCC_FLOATVALUE()
            stFloatParam_gain = MVCC_FLOATVALUE()
            
            memset(byref(stFloatParam_FrameRate), 0, sizeof(MVCC_FLOATVALUE))
            memset(byref(stFloatParam_exposureTime), 0, sizeof(MVCC_FLOATVALUE))
            memset(byref(stFloatParam_gain), 0, sizeof(MVCC_FLOATVALUE))
            
            ret = self.obj_cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stFloatParam_FrameRate)
            if ret == 0:
                self.frame_rate = stFloatParam_FrameRate.fCurValue
            
            ret = self.obj_cam.MV_CC_GetFloatValue("ExposureTime", stFloatParam_exposureTime)
            if ret == 0:
                self.exposure_time = stFloatParam_exposureTime.fCurValue
            
            ret = self.obj_cam.MV_CC_GetFloatValue("Gain", stFloatParam_gain)
            if ret == 0:
                self.gain = stFloatParam_gain.fCurValue
            
            return MV_OK
        except Exception as e:
            print(f"Get parameter exception: {str(e)}")
            return MV_E_UNKNOW

    def Set_parameter(self, frameRate, exposureTime, gain):
        """設置參數"""
        if not frameRate or not exposureTime or not gain:
            print('Please provide all parameters!')
            return MV_E_PARAMETER
            
        if not self.b_open_device:
            return MV_E_CALLORDER

        try:
            # 設置自動曝光為關閉
            ret = self.obj_cam.MV_CC_SetEnumValue("ExposureAuto", 0)
            time.sleep(0.2)
            
            # 設置曝光時間
            ret = self.obj_cam.MV_CC_SetFloatValue("ExposureTime", float(exposureTime))
            if ret != 0:
                print(f'Set exposure time fail! ret = 0x{ret:08X}')
                return ret

            # 設置增益
            ret = self.obj_cam.MV_CC_SetFloatValue("Gain", float(gain))
            if ret != 0:
                print(f'Set gain fail! ret = 0x{ret:08X}')
                return ret

            # 設置幀率
            ret = self.obj_cam.MV_CC_SetFloatValue("AcquisitionFrameRate", float(frameRate))
            if ret != 0:
                print(f'Set frame rate fail! ret = 0x{ret:08X}')
                return ret

            print('Set parameter success!')
            return MV_OK
            
        except Exception as e:
            print(f"Set parameter exception: {str(e)}")
            return MV_E_UNKNOW

    def Save_jpg(self):
        """保存JPG圖像"""
        if self.buf_save_image is None or self.st_frame_info is None:
            return MV_E_NODATA

        try:
            with self.buf_lock:
                frame_num = getattr(self.st_frame_info, 'nFrameNum', int(time.time()))
                file_path = f"{frame_num}.jpg"
                c_file_path = file_path.encode('ascii')
                
                stSaveParam = MV_SAVE_IMAGE_TO_FILE_PARAM_EX()
                stSaveParam.enPixelType = self.st_frame_info.enPixelType
                stSaveParam.nWidth = self.st_frame_info.nWidth
                stSaveParam.nHeight = self.st_frame_info.nHeight
                stSaveParam.nDataLen = self.st_frame_info.nFrameLen
                stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
                stSaveParam.enImageType = MV_Image_Jpeg
                stSaveParam.nQuality = 80
                stSaveParam.pcImagePath = ctypes.create_string_buffer(c_file_path)
                stSaveParam.iMethodValue = 1
                
                ret = self.obj_cam.MV_CC_SaveImageToFileEx(stSaveParam)
                return ret
                
        except Exception as e:
            print(f"Save JPG exception: {str(e)}")
            return MV_E_UNKNOW

    def Save_Bmp(self):
        """保存BMP圖像"""
        if self.buf_save_image is None or self.st_frame_info is None:
            return MV_E_NODATA

        try:
            with self.buf_lock:
                frame_num = getattr(self.st_frame_info, 'nFrameNum', int(time.time()))
                file_path = f"{frame_num}.bmp"
                c_file_path = file_path.encode('ascii')
                
                stSaveParam = MV_SAVE_IMAGE_TO_FILE_PARAM_EX()
                stSaveParam.enPixelType = self.st_frame_info.enPixelType
                stSaveParam.nWidth = self.st_frame_info.nWidth
                stSaveParam.nHeight = self.st_frame_info.nHeight
                stSaveParam.nDataLen = self.st_frame_info.nFrameLen
                stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
                stSaveParam.enImageType = MV_Image_Bmp
                stSaveParam.pcImagePath = ctypes.create_string_buffer(c_file_path)
                stSaveParam.iMethodValue = 1
                
                ret = self.obj_cam.MV_CC_SaveImageToFileEx(stSaveParam)
                return ret
                
        except Exception as e:
            print(f"Save BMP exception: {str(e)}")
            return MV_E_UNKNOW

    def __del__(self):
        """析構函數"""
        try:
            if self.b_start_grabbing:
                self.Stop_grabbing()
            if self.b_open_device:
                self.Close_device()
        except:
            pass