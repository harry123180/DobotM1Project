# -*- coding: utf-8 -*-
"""
改進的相機操作類 - 修復線程管理問題
"""

import threading
import time
from ctypes import *
from CamOperation_class import CameraOperation, Is_mono_data, Is_color_data, To_hex_str
from CameraParams_header import *
from MvCameraControl_class import *

class ImprovedCameraOperation(CameraOperation):
    """改進的相機操作類，修復線程管理問題"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.work_thread = None
        self.thread_running = False
    
    def Start_grabbing(self, winHandle):
        """開始取圖 - 改進的線程管理"""
        if not self.b_start_grabbing and self.b_open_device:
            self.b_exit = False
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                return ret
            
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            
            # 使用新的線程管理方式
            self.thread_running = True
            self.work_thread = threading.Thread(
                target=self._work_thread_wrapper, 
                args=(winHandle,),
                daemon=True  # 設為守護線程
            )
            self.work_thread.start()
            self.b_thread_closed = True
            
            return MV_OK
        
        return MV_E_CALLORDER
    
    def Stop_grabbing(self):
        """停止取圖 - 改進的線程管理"""
        if self.b_start_grabbing and self.b_open_device:
            # 先設置退出標誌
            self.b_exit = True
            self.thread_running = False
            
            # 等待線程自然結束
            if self.work_thread and self.work_thread.is_alive():
                self.work_thread.join(timeout=2.0)
            
            # 停止相機取圖
            ret = self.obj_cam.MV_CC_StopGrabbing()
            if ret != 0:
                print(f"停止取圖返回碼: 0x{ret:08X}")
                # 即使返回錯誤，也要更新狀態
            
            print("stop grabbing successfully!")
            self.b_start_grabbing = False
            self.b_thread_closed = False
            
            # 清理緩衝區
            if self.buf_save_image is not None:
                del self.buf_save_image
                self.buf_save_image = None
            
            return MV_OK
        else:
            return MV_OK  # 如果沒有在取圖，直接返回成功
    
    def Close_device(self):
        """關閉設備 - 改進的清理邏輯"""
        if self.b_open_device:
            # 如果還在取圖，先停止
            if self.b_start_grabbing:
                self.Stop_grabbing()
            
            # 關閉設備
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                return ret
            
            # 銷毀句柄
            self.obj_cam.MV_CC_DestroyHandle()
            
            self.b_open_device = False
            self.b_start_grabbing = False
            self.b_exit = True
            self.thread_running = False
            
            print("close device successfully!")
            
            return MV_OK
        
        return MV_OK
    
    def _work_thread_wrapper(self, winHandle):
        """工作線程包裝函數"""
        try:
            self.Work_thread(winHandle)
        except Exception as e:
            print(f"工作線程異常: {str(e)}")
        finally:
            self.thread_running = False
            print("工作線程已結束")
    
    def Work_thread(self, winHandle):
        """取圖線程函數 - 改進版本"""
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))
        
        while self.thread_running and not self.b_exit:
            try:
                ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
                if 0 == ret:
                    # 拷貝圖像和圖像信息
                    if self.buf_save_image is None:
                        self.buf_save_image = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
                    
                    self.st_frame_info = stOutFrame.stFrameInfo
                    
                    # 獲取緩存鎖
                    self.buf_lock.acquire()
                    try:
                        cdll.msvcrt.memcpy(byref(self.buf_save_image), stOutFrame.pBufAddr, self.st_frame_info.nFrameLen)
                    finally:
                        self.buf_lock.release()
                    
                    print("get one frame: Width[%d], Height[%d], nFrameNum[%d]"
                          % (self.st_frame_info.nWidth, self.st_frame_info.nHeight, self.st_frame_info.nFrameNum))
                    
                    # 釋放緩存
                    self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                    
                    # 顯示圖像（如果提供了窗口句柄）
                    if winHandle and winHandle != 0:
                        stDisplayParam = MV_DISPLAY_FRAME_INFO()
                        memset(byref(stDisplayParam), 0, sizeof(stDisplayParam))
                        stDisplayParam.hWnd = int(winHandle)
                        stDisplayParam.nWidth = self.st_frame_info.nWidth
                        stDisplayParam.nHeight = self.st_frame_info.nHeight
                        stDisplayParam.enPixelType = self.st_frame_info.enPixelType
                        stDisplayParam.pData = self.buf_save_image
                        stDisplayParam.nDataLen = self.st_frame_info.nFrameLen
                        self.obj_cam.MV_CC_DisplayOneFrame(stDisplayParam)
                else:
                    if not self.b_exit:
                        print("no data, ret = " + To_hex_str(ret))
                    time.sleep(0.01)
                
                # 檢查退出條件
                if self.b_exit:
                    break
                    
            except Exception as e:
                print(f"取圖線程異常: {str(e)}")
                if self.b_exit:
                    break
                time.sleep(0.1)
        
        # 清理資源
        if self.buf_save_image is not None:
            del self.buf_save_image
            self.buf_save_image = None