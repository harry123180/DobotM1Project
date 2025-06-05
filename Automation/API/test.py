import sys
import time
import random
import cv2
import numpy as np
from ctypes import *
import statistics

# 添加海康威視SDK路徑
sys.path.append("../MvImport")
from MvCameraControl_class import *
from CameraParams_header import *
from MvErrorDefine_const import *

class VisionTimingTest:
    def __init__(self, camera_ip="192.168.1.8"):
        self.camera_ip = camera_ip
        self.camera = None
        self.device_info = None
        
        # 時間記錄
        self.timing_records = []
        
    def find_camera_by_ip(self):
        """根據IP地址找到對應的相機"""
        print(f"正在搜尋IP為 {self.camera_ip} 的相機...")
        
        # 枚舉設備
        device_list = MV_CC_DEVICE_INFO_LIST()
        tlayer_type = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
        
        if ret != 0:
            print(f"❌ 枚舉設備失敗，錯誤碼: [0x{ret:x}]")
            return None
            
        if device_list.nDeviceNum == 0:
            print("❌ 未發現任何設備")
            return None
            
        print(f"發現 {device_list.nDeviceNum} 台設備")
        
        # 搜尋指定IP的設備
        for i in range(device_list.nDeviceNum):
            device_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            
            if device_info.nTLayerType == MV_GIGE_DEVICE:
                # 解析IP地址
                current_ip = device_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip_str = f"{(current_ip & 0xff000000) >> 24}.{(current_ip & 0x00ff0000) >> 16}.{(current_ip & 0x0000ff00) >> 8}.{current_ip & 0x000000ff}"
                
                print(f"發現網路相機 [{i}]: IP = {ip_str}")
                
                if ip_str == self.camera_ip:
                    print(f"✅ 找到目標相機: {ip_str}")
                    return device_info
                    
        print(f"❌ 未找到IP為 {self.camera_ip} 的相機")
        return None
    
    def initialize_camera(self):
        """初始化相機"""
        start_time = time.time()
        
        # 找到指定IP的相機
        self.device_info = self.find_camera_by_ip()
        if self.device_info is None:
            return False
            
        # 創建相機實例
        self.camera = MvCamera()
        
        # 創建句柄
        ret = self.camera.MV_CC_CreateHandle(self.device_info)
        if ret != 0:
            print(f"❌ 創建句柄失敗，錯誤碼: [0x{ret:x}]")
            return False
            
        # 開啟設備
        ret = self.camera.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            print(f"❌ 開啟設備失敗，錯誤碼: [0x{ret:x}]")
            return False
            
        # 設置相機參數
        self.setup_camera_parameters()
        
        init_time = time.time() - start_time
        print(f"✅ 相機初始化完成，耗時: {init_time:.3f}秒")
        return True
    
    def setup_camera_parameters(self):
        """設置相機參數"""
        # 設置像素格式為BayerGR8
        ret = self.camera.MV_CC_SetEnumValue("PixelFormat", 17301512)
        if ret != 0:
            print(f"⚠️ 設置像素格式失敗，錯誤碼: [0x{ret:x}]")
            
        # 設置解析度
        ret = self.camera.MV_CC_SetIntValue("Width", 2592)
        if ret != 0:
            print(f"⚠️ 設置寬度失敗，錯誤碼: [0x{ret:x}]")
            
        ret = self.camera.MV_CC_SetIntValue("Height", 1944)
        if ret != 0:
            print(f"⚠️ 設置高度失敗，錯誤碼: [0x{ret:x}]")
            
        # 設置為連續模式
        ret = self.camera.MV_CC_SetEnumValue("TriggerMode", 0)
        if ret != 0:
            print(f"⚠️ 設置觸發模式失敗，錯誤碼: [0x{ret:x}]")
            
        # 設置曝光時間
        ret = self.camera.MV_CC_SetEnumValue("ExposureAuto", 0)  # 關閉自動曝光
        if ret == 0:
            ret = self.camera.MV_CC_SetFloatValue("ExposureTime", 60000.0)
            if ret != 0:
                print(f"⚠️ 設置曝光時間失敗，錯誤碼: [0x{ret:x}]")
    
    def capture_image(self):
        """捕獲圖像並轉換為OpenCV格式"""
        capture_start = time.time()
        
        # 開始取流
        ret = self.camera.MV_CC_StartGrabbing()
        if ret != 0:
            print(f"❌ 開始取流失敗，錯誤碼: [0x{ret:x}]")
            return None, 0
            
        # 獲取圖像
        frame_out = MV_FRAME_OUT()
        memset(byref(frame_out), 0, sizeof(frame_out))
        
        ret = self.camera.MV_CC_GetImageBuffer(frame_out, 3000)
        if ret != 0:
            print(f"❌ 獲取圖像失敗，錯誤碼: [0x{ret:x}]")
            self.camera.MV_CC_StopGrabbing()
            return None, 0
            
        try:
            # 複製圖像數據
            data = (c_ubyte * frame_out.stFrameInfo.nFrameLen)()
            cdll.msvcrt.memcpy(byref(data), frame_out.pBufAddr, frame_out.stFrameInfo.nFrameLen)
            
            # 轉換為numpy陣列
            if frame_out.stFrameInfo.enPixelType == 17301512:  # BayerGR8
                data_array = np.frombuffer(data, dtype=np.uint8).reshape(
                    frame_out.stFrameInfo.nHeight, frame_out.stFrameInfo.nWidth
                )
                # 轉換為RGB
                image = cv2.cvtColor(data_array, cv2.COLOR_BAYER_GR2RGB)
            else:
                print(f"⚠️ 未支援的像素格式: {frame_out.stFrameInfo.enPixelType}")
                image = None
                
        finally:
            # 釋放緩存
            self.camera.MV_CC_FreeImageBuffer(frame_out)
            self.camera.MV_CC_StopGrabbing()
            
        capture_time = time.time() - capture_start
        return image, capture_time
    
    def detect_circles(self, image):
        """檢測圓形"""
        if image is None:
            return 0, 0
            
        detect_start = time.time()
        
        # 轉為灰階
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # 直方圖均衡與模糊
        equalized = cv2.equalizeHist(gray)
        blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
        
        # 門檻二值化
        _, binary_thresh = cv2.threshold(blurred, 170, 255, cv2.THRESH_BINARY)
        
        # 初始邊緣偵測
        edges_initial = cv2.Canny(binary_thresh, 10, 350)
        
        # 建立形態學kernel
        kernel_dilate = np.ones((13, 13), np.uint8)
        kernel_erode = np.ones((11, 11), np.uint8)
        
        # 輪廓填滿處理
        contours_initial, _ = cv2.findContours(edges_initial, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled_mask = np.zeros_like(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
        cv2.drawContours(filled_mask, contours_initial, -1, (255, 255, 255), thickness=cv2.FILLED)
        
        # 反轉並進行形態學處理
        inverted_mask = cv2.bitwise_not(filled_mask)
        morphed_mask = cv2.dilate(inverted_mask, kernel_dilate, iterations=1)
        morphed_mask = cv2.erode(morphed_mask, kernel_erode, iterations=1)
        
        # 再次邊緣偵測
        edges_final = cv2.Canny(morphed_mask, 10, 350)
        contours_final, _ = cv2.findContours(edges_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 圓形檢測
        circle_count = 0
        threshold_roundness = 0.85
        
        for cnt in contours_final:
            area = cv2.contourArea(cnt)
            perimeter = cv2.arcLength(cnt, True)
            
            if perimeter == 0 or area < 30:
                continue
                
            roundness = (4 * np.pi * area) / (perimeter ** 2)
            
            if roundness > threshold_roundness:
                circle_count += 1
                
        detect_time = time.time() - detect_start
        return circle_count, detect_time
    
    def cleanup_camera(self):
        """清理相機資源"""
        cleanup_start = time.time()
        
        if self.camera:
            self.camera.MV_CC_CloseDevice()
            self.camera.MV_CC_DestroyHandle()
            
        cleanup_time = time.time() - cleanup_start
        return cleanup_time
    
    def run_single_test(self, test_index):
        """執行單次測試"""
        print(f"\n--- 第 {test_index + 1} 次測試 ---")
        
        # 隨機延遲模擬真實觸發
        delay = random.uniform(0.1, 1.0)
        time.sleep(delay)
        
        total_start = time.time()
        
        # 初始化相機
        init_success = self.initialize_camera()
        if not init_success:
            print(f"❌ 第 {test_index + 1} 次測試初始化失敗")
            return None
            
        # 捕獲圖像
        image, capture_time = self.capture_image()
        if image is None:
            print(f"❌ 第 {test_index + 1} 次測試捕獲圖像失敗")
            self.cleanup_camera()
            return None
            
        # 檢測圓形
        circle_count, detect_time = self.detect_circles(image)
        
        # 清理資源
        cleanup_time = self.cleanup_camera()
        
        total_time = time.time() - total_start
        
        # 記錄結果
        result = {
            'test_index': test_index + 1,
            'circle_count': circle_count,
            'capture_time': capture_time,
            'detect_time': detect_time,
            'cleanup_time': cleanup_time,
            'total_time': total_time
        }
        
        print(f"✅ 檢測到圓形數量: {circle_count}")
        print(f"📊 拍照耗時: {capture_time:.3f}秒")
        print(f"📊 檢測耗時: {detect_time:.3f}秒")
        print(f"📊 清理耗時: {cleanup_time:.3f}秒")
        print(f"📊 總耗時: {total_time:.3f}秒")
        
        return result
    
    def run_timing_test(self, num_tests=10):
        """執行完整的耗時測試"""
        print(f"🚀 開始進行 {num_tests} 次視覺辨識流程耗時測試")
        print("=" * 50)
        
        # 初始化SDK
        MvCamera.MV_CC_Initialize()
        
        try:
            for i in range(num_tests):
                result = self.run_single_test(i)
                if result:
                    self.timing_records.append(result)
                else:
                    print(f"⚠️ 第 {i + 1} 次測試失敗，跳過")
                    
        finally:
            # 反初始化SDK
            MvCamera.MV_CC_Finalize()
            
        # 生成統計報告
        self.generate_report()
    
    def generate_report(self):
        """生成統計報告"""
        if not self.timing_records:
            print("❌ 沒有有效的測試記錄")
            return
            
        print("\n" + "=" * 50)
        print("📈 測試統計報告")
        print("=" * 50)
        
        # 基本統計
        total_tests = len(self.timing_records)
        circle_counts = [r['circle_count'] for r in self.timing_records]
        capture_times = [r['capture_time'] for r in self.timing_records]
        detect_times = [r['detect_time'] for r in self.timing_records]
        cleanup_times = [r['cleanup_time'] for r in self.timing_records]
        total_times = [r['total_time'] for r in self.timing_records]
        
        print(f"📊 總測試次數: {total_tests}")
        print(f"📊 成功率: {total_tests}/10 ({total_tests/10*100:.1f}%)")
        
        print(f"\n🎯 圓形檢測結果:")
        print(f"   • 平均檢測到: {statistics.mean(circle_counts):.1f} 個圓形")
        print(f"   • 最多檢測到: {max(circle_counts)} 個圓形")
        print(f"   • 最少檢測到: {min(circle_counts)} 個圓形")
        
        print(f"\n⏱️ 拍照耗時統計:")
        print(f"   • 平均耗時: {statistics.mean(capture_times):.3f} 秒")
        print(f"   • 最長耗時: {max(capture_times):.3f} 秒")
        print(f"   • 最短耗時: {min(capture_times):.3f} 秒")
        print(f"   • 標準差: {statistics.stdev(capture_times):.3f} 秒")
        
        print(f"\n🔍 檢測耗時統計:")
        print(f"   • 平均耗時: {statistics.mean(detect_times):.3f} 秒")
        print(f"   • 最長耗時: {max(detect_times):.3f} 秒")
        print(f"   • 最短耗時: {min(detect_times):.3f} 秒")
        print(f"   • 標準差: {statistics.stdev(detect_times):.3f} 秒")
        
        print(f"\n🧹 清理耗時統計:")
        print(f"   • 平均耗時: {statistics.mean(cleanup_times):.3f} 秒")
        print(f"   • 最長耗時: {max(cleanup_times):.3f} 秒")
        print(f"   • 最短耗時: {min(cleanup_times):.3f} 秒")
        print(f"   • 標準差: {statistics.stdev(cleanup_times):.3f} 秒")
        
        print(f"\n⚡ 總流程耗時統計:")
        print(f"   • 平均耗時: {statistics.mean(total_times):.3f} 秒")
        print(f"   • 最長耗時: {max(total_times):.3f} 秒")
        print(f"   • 最短耗時: {min(total_times):.3f} 秒")
        print(f"   • 標準差: {statistics.stdev(total_times):.3f} 秒")
        
        # 詳細結果表格
        print(f"\n📋 詳細測試結果:")
        print("次數 | 圓形數 | 拍照(s) | 檢測(s) | 清理(s) | 總計(s)")
        print("-" * 55)
        for r in self.timing_records:
            print(f"{r['test_index']:2d}   |   {r['circle_count']:2d}   | {r['capture_time']:6.3f} | {r['detect_time']:6.3f} | {r['cleanup_time']:6.3f} | {r['total_time']:6.3f}")

def main():
    """主函數"""
    # 設置目標相機IP
    camera_ip = "192.168.1.8"  # 您可以修改這個IP地址
    
    # 創建測試實例
    tester = VisionTimingTest(camera_ip)
    
    # 執行10次測試
    tester.run_timing_test(10)

if __name__ == "__main__":
    main()