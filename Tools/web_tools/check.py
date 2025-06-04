# -*- coding: utf-8 -*-
"""
相機數據診斷腳本
用於檢查相機數據是否正常
"""

import time
import cv2
import numpy as np
from ctypes import *
from Camera_API import create_camera_api

def diagnose_camera_data():
    """診斷相機數據"""
    
    print("=== 相機數據診斷開始 ===")
    
    # 創建相機API
    api = create_camera_api()
    
    try:
        # 枚舉設備
        devices = api.enumerate_devices()
        if not devices:
            print("❌ 未找到設備")
            return
        
        print(f"✅ 找到 {len(devices)} 個設備")
        for i, device in enumerate(devices):
            print(f"  [{i}] {device}")
        
        # 連接第一個設備
        if not api.connect(0):
            print("❌ 連接設備失敗")
            return
        
        print("✅ 設備連接成功")
        
        # 開始串流
        if not api.start_streaming():
            print("❌ 啟動串流失敗")
            return
        
        print("✅ 串流啟動成功")
        
        # 等待數據穩定
        print("⏳ 等待數據穩定...")
        time.sleep(3.0)
        
        # 檢查相機操作對象
        cam_op = api._camera_operation
        if cam_op is None:
            print("❌ 相機操作對象為空")
            return
        
        print("✅ 相機操作對象正常")
        
        # 檢查屬性
        attrs_to_check = [
            'st_frame_info',
            'buf_save_image', 
            'buf_lock'
        ]
        
        for attr in attrs_to_check:
            if hasattr(cam_op, attr):
                value = getattr(cam_op, attr)
                if value is not None:
                    print(f"✅ {attr}: 存在")
                else:
                    print(f"❌ {attr}: 為空")
            else:
                print(f"❌ {attr}: 不存在")
        
        # 等待並檢查圖像信息
        print("\n⏳ 檢查圖像信息...")
        for i in range(10):
            if hasattr(cam_op, 'st_frame_info') and cam_op.st_frame_info:
                width = cam_op.st_frame_info.nWidth
                height = cam_op.st_frame_info.nHeight
                pixel_type = cam_op.st_frame_info.enPixelType
                frame_len = cam_op.st_frame_info.nFrameLen
                
                print(f"第 {i+1} 次檢查:")
                print(f"  寬度: {width}")
                print(f"  高度: {height}")
                print(f"  像素格式: 0x{pixel_type:08X}")
                print(f"  幀長度: {frame_len}")
                
                if width > 0 and height > 0:
                    print("✅ 圖像信息正常")
                    break
                else:
                    print("❌ 圖像信息異常")
            else:
                print(f"第 {i+1} 次檢查: 無圖像信息")
            
            time.sleep(1.0)
        
        # 嘗試獲取一幀圖像
        print("\n⏳ 嘗試獲取圖像...")
        
        if hasattr(cam_op, 'buf_lock'):
            if cam_op.buf_lock.acquire(timeout=2.0):
                try:
                    if (cam_op.st_frame_info and cam_op.buf_save_image and
                        cam_op.st_frame_info.nWidth > 0 and 
                        cam_op.st_frame_info.nHeight > 0):
                        
                        # 嘗試複製數據
                        width = cam_op.st_frame_info.nWidth
                        height = cam_op.st_frame_info.nHeight
                        frame_len = cam_op.st_frame_info.nFrameLen
                        
                        print(f"準備複製 {frame_len} 字節的圖像數據...")
                        
                        # 使用簡單的方法複製數據
                        buffer_size = min(frame_len, 1024*1024)  # 限制在1MB以內
                        
                        try:
                            # 方法1: 直接從ctypes數組讀取
                            test_data = bytes(cam_op.buf_save_image[:100])  # 只讀前100字節測試
                            print(f"✅ 成功讀取測試數據: {len(test_data)} 字節")
                            print(f"   前10字節: {test_data[:10].hex()}")
                            
                            # 方法2: 嘗試創建numpy數組
                            buffer_size = min(frame_len, sizeof(cam_op.buf_save_image))
                            image_data = (c_ubyte * buffer_size)()
                            cdll.msvcrt.memcpy(image_data, cam_op.buf_save_image, buffer_size)
                            
                            # 轉換為numpy
                            np_array = np.frombuffer(image_data, dtype=np.uint8)
                            print(f"✅ 成功創建numpy數組: {len(np_array)} 元素")
                            
                            # 嘗試重塑為圖像
                            if len(np_array) >= width * height:
                                # 嘗試作為Mono8
                                img = np_array[:width*height].reshape((height, width))
                                print(f"✅ 成功重塑為圖像: {img.shape}")
                                
                                # 嘗試保存測試圖像
                                cv2.imwrite("test_image.jpg", img)
                                print("✅ 測試圖像已保存為 test_image.jpg")
                                
                            else:
                                print(f"❌ 數據不足以構成完整圖像")
                                
                        except Exception as e:
                            print(f"❌ 數據處理錯誤: {str(e)}")
                        
                    else:
                        print("❌ 圖像數據無效")
                        
                finally:
                    cam_op.buf_lock.release()
            else:
                print("❌ 無法獲取緩衝區鎖")
        else:
            print("❌ 無緩衝區鎖")
        
    except Exception as e:
        print(f"❌ 診斷過程中出錯: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理
        try:
            api.stop_streaming()
            api.disconnect()
            print("\n✅ 清理完成")
        except:
            pass
    
    print("\n=== 相機數據診斷結束 ===")

if __name__ == "__main__":
    diagnose_camera_data()