import os
import sys
import numpy as np
from os import getcwd
import cv2
import msvcrt
from ctypes import *

sys.path.append("../MvImport")
from MvCameraControl_class import *
import numpy as np

# 相機內參矩陣
K = np.array([
    [7.35533899e+00, 0, 1.24451771e+00],
    [0.0, 7.35687528e+00, 1.02655760e+00],
    [0.0, 0.0, 1.0]
])

# 畸變係數
D = np.array([[-9.63028822e-02, 2.74658814e-01, 1.36385496e-03, 5.80934112e-04, 2.95541140e+00]])

R = np.array([
    [-9.99913875e-01,  -1.31241329e-02, -3.55145363e-06],
    [ -1.31241329e-02,  9.99913875e-01, -2.47572387e-06],
    [3.58363949e-06, -2.42890090e-06, -1.00000000e+00]
])

t = np.array([[352.96520021], [-109.49788733], [0.86068216]])
# 設備資訊定義
DEVICE_INFO = {
    "設備型號": "MV-CE050-30UC",
    "設備序列號": "00DA1831623",
    "製造商名稱": "Hikrobot",
    "固件版本": "V1.6.3 201222 551351",
    "設備GUID": "2BDFA1831623",
    "設備家族名稱": "未知"
}
def set_exposure_time(cam, exposure_time):
    """
    設置攝影機的曝光時間。
    :param cam: MvCamera 實例
    :param exposure_time: 曝光時間，單位微秒
    """
    # 關閉自動曝光模式
    ret = cam.MV_CC_SetEnumValue("ExposureAuto", 0)
    if ret != 0:
        print(f"無法設置自動曝光模式為手動，返回值: [0x{ret:x}]")
        return ret

    # 設置曝光時間
    ret = cam.MV_CC_SetFloatValue("ExposureTime", exposure_time)
    if ret != 0:
        print(f"無法設置曝光時間，返回值: [0x{ret:x}]")
        return ret

    print(f"曝光時間設置成功: {exposure_time} 微秒")
    return ret

# 枚舉設備
def enum_devices(device=0, device_way=False):
    """
    device = 0  枚舉網口、USB口、未知設備、cameralink 設備
    device = 1 枚舉GenTL設備
    """
    if device_way == False:
        if device == 0:
            tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE | MV_UNKNOW_DEVICE | MV_1394_DEVICE | MV_CAMERALINK_DEVICE
            deviceList = MV_CC_DEVICE_INFO_LIST()
            # 枚舉設備
            ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
            if ret != 0:
                print("枚舉設備失敗！返回值[0x%x]" % ret)
                sys.exit()
            if deviceList.nDeviceNum == 0:
                print("未發現設備！")
                sys.exit()
            print("發現 %d 台設備！" % deviceList.nDeviceNum)
            return deviceList
        else:
            pass
    elif device_way == True:
        pass
def pixel_to_world(u, v, depth, K, R, t):
    uv_homogeneous = np.array([u, v, 720])  # 齊次像素坐標 (u, v, 1)
    K_inv = np.linalg.inv(K)  # 計算內參矩陣的逆矩陣
    cam_coords = np.dot(K_inv, uv_homogeneous)  # 相機坐標 (X_c, Y_c, Z_c)

    # 將相機坐標轉換到世界坐標系
    #cam_coords = cam_coords.reshape(3, 1)  # 確保為列向量
    world_coords = np.dot(R.T, cam_coords - t.ravel())  # 世界坐標  # 世界坐標系 (X_w, Y_w, Z_w)

    return world_coords.flatten()
# 判斷不同類型設備
def identify_different_devices(deviceList):
    # 判斷不同類型設備，並輸出相關資訊
    for i in range(0, deviceList.nDeviceNum):
        mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        # 判斷是否為網口攝影機
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
            print("\n網口設備序號: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                strModeName = strModeName + chr(per)
            print("當前設備型號名稱: %s" % strModeName)
            nip1_1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
            nip1_2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
            nip1_3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
            nip1_4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
            print("當前 IP 地址: %d.%d.%d.%d" % (nip1_1, nip1_2, nip1_3, nip1_4))
        elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
            print("\nU3V 設備序號: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print("當前設備型號名稱: %s" % strModeName)
            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)
            print("當前設備序列號: %s" % strSerialNumber)
            strmanufacturerName = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chVendorName:
                strmanufacturerName = strmanufacturerName + chr(per)
            print("製造商名稱: %s" % strmanufacturerName)
def resize_image(img, ratio):
    """
    等比例縮放圖像。
    
    :param img: 原始圖像 (NumPy 數組)
    :param ratio: 縮放比例 (float)，如 0.5 表示縮小一半
    :return: 縮放後的圖像 (NumPy 數組)
    """
    # 獲取原始圖像尺寸
    original_height, original_width = img.shape[:2]
    
    # 計算縮放後的尺寸
    new_width = int(original_width * ratio)
    new_height = int(original_height * ratio)
    
    # 使用 cv2.resize 進行縮放
    resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    
    return resized_img
# 設定 SDK 內部圖像緩存節點個數
def set_image_Node_num(cam, Num=50):
    ret = cam.MV_CC_SetImageNodeNum(nNum=50)
    if ret != 0:
        print("設定 SDK 內部圖像緩存節點個數失敗，返回值 [0x%x]" % ret)
    else:
        print("成功設定 SDK 內部圖像緩存節點個數為 %d" % Num)

# 設定取流策略
def set_grab_strategy(cam, grabstrategy=0, outputqueuesize=1):
    """
    設定取流策略:
    - OneByOne: 從舊到新逐幀獲取圖像
    - LatestImagesOnly: 只獲取最新幀，並清空緩存
    - LatestImages: 獲取最新 OutputQueueSize 幀圖像
    - UpcomingImage: 等待即將生成的圖像（僅支援網口攝影機）
    """
    ret = cam.MV_CC_SetGrabStrategy(enGrabStrategy=grabstrategy)
    if ret != 0:
        print("設定取流策略失敗，返回值 [0x%x]" % ret)
    else:
        print("成功設定取流策略為 %d" % grabstrategy)

# 開啟設備並顯示圖像
def process_and_detect_circles(image, circle_threshold=0.85):
    """
    對未校正與校正後的圖像進行灰階化、Canny 邊緣檢測，並檢測近似圓的輪廓。
    :param image: 原始 RGB 圖像
    :param circle_threshold: 圓形度的閾值，0.85 表示 85% 接近圓形
    """
    # 獲取圖像尺寸
    h, w = image.shape[:2]

    # 計算校正映射
    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(K, D, (w, h), 1, (w, h))
    map1, map2 = cv2.initUndistortRectifyMap(K, D, None, new_camera_matrix, (w, h), cv2.CV_16SC2)

    # 校正圖像
    corrected_image = cv2.remap(image, map1, map2, interpolation=cv2.INTER_LINEAR)

    # 原始與校正圖像分別處理
    images = {
        "Original": image.copy(),
        "Corrected": corrected_image.copy()
    }

    results = {}
    for key, img in images.items():
        # 轉為灰階
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Canny 邊緣檢測
        edges = cv2.Canny(gray, 50, 150)

        # 找到輪廓
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 檢測圓形輪廓
        circle_count = 0
        for contour in contours:
            # 計算輪廓的周長與面積
            perimeter = cv2.arcLength(contour, True)
            area = cv2.contourArea(contour)

            if perimeter == 0:
                continue

            # 計算圓形度
            circularity = (4 * np.pi * area) / (perimeter ** 2)

            # 若圓形度高於閾值且面積大於100，判斷為近似圓形
            if circularity >= circle_threshold and area > 100:
                circle_count += 1

                # 計算最小外接圓
                (x, y), radius = cv2.minEnclosingCircle(contour)
                center = (int(x), int(y))
                radius = int(radius)

                # 繪製輪廓與圓
                cv2.circle(img, center, radius, (255, 0, 0), 2)

                # 在圓心處標記
                cv2.circle(img, center, 3, (0, 0, 255), -1)

                # 在右下角標記編號、座標與面積
                text = f"#{circle_count} ({int(x)}, {int(y)}) area: {area:.2f} c: {circularity:.2f}"
                world_coords = pixel_to_world(x, y, 1000, K, R, t)
                print(world_coords,text)
                #print(text)
                text_position = (center[0] + 10, center[1] + 10)
                cv2.putText(img, text, text_position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        results[key] = img

    # 顯示結果
    #cv2.imshow("Original Image with Circles", results["Original"])
    #cv2.namedWindow('Corrected Image with Circles', cv2.WINDOW_NORMAL)
    #new_size = (800, 600)
    #resized_image = cv2.resize(results["Corrected"], new_size, interpolation=cv2.INTER_LINEAR)
    #resized_image = resize_image(results["Corrected"],0.5)
    #cv2.imshow("Corrected Image with Circles", results["Original"])

    return results["Original"]

def open_device_and_display():
    def set_default_parameters(cam):
        """設置攝影機的默認參數，例如分辨率和像素格式"""
        ret = cam.MV_CC_SetEnumValue("PixelFormat", 17301512)  # 設置像素格式為 BayerGR8
        if ret != 0:
            print("設置像素格式失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetIntValue("Width", 2592)  # 設置寬度
        if ret != 0:
            print("設置寬度失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetIntValue("Height", 1944)  # 設置高度
        if ret != 0:
            print("設置高度失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetEnumValue("TriggerMode", 0)  # 設置為連續模式
        if ret != 0:
            print("設置觸發模式失敗，返回值 [0x%x]" % ret)
            sys.exit()

    def set_exposure_time(cam, exposure_time):
        """
        設置攝影機的曝光時間。
        :param cam: MvCamera 實例
        :param exposure_time: 曝光時間，單位微秒
        """
        # 關閉自動曝光模式
        ret = cam.MV_CC_SetEnumValue("ExposureAuto", 0)
        if ret != 0:
            print(f"無法設置自動曝光模式為手動，返回值: [0x{ret:x}]")
            return ret

        # 設置曝光時間
        ret = cam.MV_CC_SetFloatValue("ExposureTime", exposure_time)
        if ret != 0:
            print(f"無法設置曝光時間，返回值: [0x{ret:x}]")
            return ret

        print(f"曝光時間設置成功: {exposure_time} 微秒")
        return ret

    deviceList = enum_devices(device=0, device_way=False)
    identify_different_devices(deviceList)
    cam = MvCamera()
    stDeviceList = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
    # 創建句柄
    ret = cam.MV_CC_CreateHandle(stDeviceList)
    if ret != 0:
        print("創建句柄失敗，返回值 [0x%x]" % ret)
        sys.exit()
    # 開啟設備
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print("開啟設備失敗，返回值 [0x%x]" % ret)
        sys.exit()
    print("成功開啟設備！")

    # 設置默認參數
    set_default_parameters(cam)

    # 設置曝光時間 (例如設置為 20000 微秒)
    exposure_time = 60000.0  # 曝光時間為 20 毫秒
    set_exposure_time(cam, exposure_time)

    # 設定取流
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print("開始取流失敗，返回值 [0x%x]" % ret)
        sys.exit()

    # 獲取圖像並顯示
    stOutFrame = MV_FRAME_OUT()
    memset(byref(stOutFrame), 0, sizeof(stOutFrame))
    i = 0
    while True:
        ret = cam.MV_CC_GetImageBuffer(stOutFrame, 3000)  # 增加超時時間
        if ret == 0:
            print("獲取圖像成功，寬度[%d], 高度[%d]" % (stOutFrame.stFrameInfo.nWidth, stOutFrame.stFrameInfo.nHeight))
            data = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
            cdll.msvcrt.memcpy(byref(data), stOutFrame.pBufAddr, stOutFrame.stFrameInfo.nFrameLen)

            if stOutFrame.stFrameInfo.enPixelType == 17301512:  # BayerGR8
                data = np.frombuffer(data, dtype=np.uint8).reshape(
                    stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth
                )
                image = cv2.cvtColor(data, cv2.COLOR_BAYER_GR2RGB)  # 將 BayerGR8 轉換為 RGB
                #new_size = (800, 600)
                #resized_image = cv2.resize(image, new_size, interpolation=cv2.INTER_LINEAR)
                #cv2.imshow("Camera Image", image)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            print("獲取圖像失敗，返回值 [0x%x]" % ret)
            i += 1
            if i > 5:
                break
            continue
        ret = cam.MV_CC_FreeImageBuffer(stOutFrame)
        if ret != 0:
            print("釋放影像緩存失敗，返回值 [0x%x]" % ret)
    cv2.destroyAllWindows()

    # 停止取流
    ret = cam.MV_CC_StopGrabbing()
    if ret != 0:
        print("停止取流失敗，返回值 [0x%x]" % ret)

    # 關閉設備
    ret = cam.MV_CC_CloseDevice()
    if ret != 0:
        print("關閉設備失敗，返回值 [0x%x]" % ret)

    # 銷毀句柄
    ret = cam.MV_CC_DestroyHandle()
    if ret != 0:
        print("銷毀句柄失敗，返回值 [0x%x]" % ret)






def open_device_and_display_with_circle_detection():
    def set_default_parameters(cam):
        """設置攝影機的默認參數，例如分辨率和像素格式"""
        ret = cam.MV_CC_SetEnumValue("PixelFormat", 17301512)  # 設置像素格式為 BayerGR8
        if ret != 0:
            print("設置像素格式失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetIntValue("Width", 2592)  # 設置寬度
        if ret != 0:
            print("設置寬度失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetIntValue("Height", 1944)  # 設置高度
        if ret != 0:
            print("設置高度失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetEnumValue("TriggerMode", 0)  # 設置為連續模式
        if ret != 0:
            print("設置觸發模式失敗，返回值 [0x%x]" % ret)
            sys.exit()

    def set_exposure_time(cam, exposure_time):
        """
        設置攝影機的曝光時間。
        :param cam: MvCamera 實例
        :param exposure_time: 曝光時間，單位微秒
        """
        # 關閉自動曝光模式
        ret = cam.MV_CC_SetEnumValue("ExposureAuto", 0)
        if ret != 0:
            print(f"無法設置自動曝光模式為手動，返回值: [0x{ret:x}]")
            return ret

        # 設置曝光時間
        ret = cam.MV_CC_SetFloatValue("ExposureTime", exposure_time)
        if ret != 0:
            print(f"無法設置曝光時間，返回值: [0x{ret:x}]")
            return ret

        print(f"曝光時間設置成功: {exposure_time} 微秒")
        return ret
    # 此函數基於原始的 `open_device_and_display`，加入輪廓檢測
    deviceList = enum_devices(device=0, device_way=False)
    identify_different_devices(deviceList)
    cam = MvCamera()
    stDeviceList = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents

    # 創建句柄
    ret = cam.MV_CC_CreateHandle(stDeviceList)
    if ret != 0:
        print("創建句柄失敗，返回值 [0x%x]" % ret)
        sys.exit()

    # 開啟設備
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print("開啟設備失敗，返回值 [0x%x]" % ret)
        sys.exit()

    # 設置默認參數
    set_default_parameters(cam)

    # 設置曝光時間
    exposure_time = 60000.0
    set_exposure_time(cam, exposure_time)

    # 開始取流
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print("開始取流失敗，返回值 [0x%x]" % ret)
        sys.exit()

    stOutFrame = MV_FRAME_OUT()
    memset(byref(stOutFrame), 0, sizeof(stOutFrame))
    

    # 獲取圖像並檢測圓
    while True:
        ret = cam.MV_CC_GetImageBuffer(stOutFrame, 3000)
        if ret == 0:
            data = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
            cdll.msvcrt.memcpy(byref(data), stOutFrame.pBufAddr, stOutFrame.stFrameInfo.nFrameLen)
            data = np.frombuffer(data, dtype=np.uint8).reshape(
                stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth
            )
            image = cv2.cvtColor(data, cv2.COLOR_BAYER_GR2RGB)
             # 校正畸變
            h, w = image.shape[:2]
            #new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(K, D, (w, h), 1, (w, h))
            #undistorted_img = cv2.undistort(image, K, D, None, new_camera_matrix)
            #new_size = (800, 600)
            #resized_image = cv2.resize(image, new_size, interpolation=cv2.INTER_LINEAR)

            # 呼叫處理函數
            processed_image = process_and_detect_circles(image) 
            cv2.namedWindow("Processed Image", cv2.WINDOW_NORMAL)  # 可調整大小
            cv2.resizeWindow("Processed Image", 800, 600)  # 設定視窗大小
            # 顯示處理後的影像
            cv2.imshow("Processed Image", processed_image)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            print("獲取圖像失敗，返回值 [0x%x]" % ret)
        ret = cam.MV_CC_FreeImageBuffer(stOutFrame)
        if ret != 0:
            print("釋放影像緩存失敗，返回值 [0x%x]" % ret)

    cv2.destroyAllWindows()
    cam.MV_CC_StopGrabbing()
    cam.MV_CC_CloseDevice()
    cam.MV_CC_DestroyHandle()


class Camera:
    def __init__(self, name="DefaultCamera", device_number=0, port=0, resolution=(1920, 1080), exposure_time=20000):
        """
        初始化相機物件
        :param name: 相機名稱
        :param device_number: 設備號
        :param port: 通訊埠號
        :param resolution: 解析度 (寬, 高)
        :param exposure_time: 曝光時間，單位微秒
        """
        
        self.name = name
        self.device_number = device_number
        self.port = port
        self.resolution = resolution
        self.exposure_time = exposure_time
        self.camera = None  # 用於保存 MvCamera 實例

        # 相機內參矩陣
        self.K = np.array([
            [7.35533899e+00, 0, 1.24451771e+00],
            [0.0, 7.35687528e+00, 1.02655760e+00],
            [0.0, 0.0, 1.0]
        ])

        # 畸變係數
        self.D = np.array([[-9.63028822e-02, 2.74658814e-01, 1.36385496e-03, 5.80934112e-04, 2.95541140e+00]])

        # 外參矩陣
        self.R = np.array([
            [-9.99913875e-01,  -1.31241329e-02, -3.55145363e-06],
            [-1.31241329e-02,  9.99913875e-01, -2.47572387e-06],
            [3.58363949e-06, -2.42890090e-06, -1.00000000e+00]
        ])

        self.t = np.array([[352.96520021+2], [-109.49788733+3], [0.86068216]])

    def initialize_camera(self):
        """初始化相機設備"""
        print(f"初始化相機: {self.name}, 設備號: {self.device_number}")
        device_list = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, device_list)
        if ret != 0 or device_list.nDeviceNum <= self.device_number:
            raise Exception("無法找到指定的設備或設備不存在！")

        self.camera = MvCamera()
        device_info = cast(device_list.pDeviceInfo[self.device_number], POINTER(MV_CC_DEVICE_INFO)).contents
        ret = self.camera.MV_CC_CreateHandle(device_info)
        if ret != 0:
            raise Exception(f"創建相機句柄失敗，返回值 [0x{ret:x}]")

        ret = self.camera.MV_CC_OpenDevice(MV_ACCESS_Exclusive, self.port)
        if ret != 0:
            raise Exception(f"開啟相機失敗，返回值 [0x{ret:x}]")

        #print("相機初始化成功！")
        self.set_resolution(*self.resolution)
        self.set_exposure_time(self.exposure_time)

    def set_resolution(self, width, height):
        """設置相機解析度"""
        print(f"設定解析度為 {width}x{height}")
        ret = self.camera.MV_CC_SetIntValue("Width", width)
        if ret != 0:
            raise Exception(f"無法設置寬度，返回值 [0x{ret:x}]")

        ret = self.camera.MV_CC_SetIntValue("Height", height)
        if ret != 0:
            raise Exception(f"無法設置高度，返回值 [0x{ret:x}]")

    def set_exposure_time(self, exposure_time):
        """設置曝光時間"""
        print(f"設置曝光時間為 {exposure_time} 微秒")
        ret = self.camera.MV_CC_SetEnumValue("ExposureAuto", 0)
        if ret != 0:
            raise Exception(f"無法設置自動曝光模式為手動，返回值 [0x{ret:x}]")

        ret = self.camera.MV_CC_SetFloatValue("ExposureTime", exposure_time)
        if ret != 0:
            raise Exception(f"無法設置曝光時間，返回值 [0x{ret:x}]")

    def capture_image(self):
        """捕獲影像並返回 NumPy 數組"""
        #print("捕獲影像...")
        ret = self.camera.MV_CC_StartGrabbing()
        if ret != 0:
            raise Exception(f"開始取流失敗，返回值 [0x{ret:x}]")

        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))

        ret = self.camera.MV_CC_GetImageBuffer(stOutFrame, 3000)
        if ret != 0:
            raise Exception(f"獲取圖像失敗，返回值 [0x{ret:x}]")

        data = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
        cdll.msvcrt.memcpy(byref(data), stOutFrame.pBufAddr, stOutFrame.stFrameInfo.nFrameLen)
        image = np.frombuffer(data, dtype=np.uint8).reshape(
            stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nWidth
        )

        self.camera.MV_CC_FreeImageBuffer(stOutFrame)
        self.camera.MV_CC_StopGrabbing()

        #print("影像捕獲成功！")
        return image

    def release_camera(self):
        """釋放相機資源"""
        print("釋放相機資源...")
        if self.camera:
            self.camera.MV_CC_CloseDevice()
            self.camera.MV_CC_DestroyHandle()
        print("相機已釋放")
    def pixel_to_world(self, u, v, depth=720):
        """
        將像素座標轉換為世界座標 (x, y)。
        :param u: 像素座標 x
        :param v: 像素座標 y
        :param depth: 深度值 (默認為 1.0，根據場景調整)
        :return: 世界座標 (x, y)
        """
        # 像素坐標轉換為齊次像素坐標
        uv_homogeneous = np.array([u, v, depth])

        # 計算相機坐標
        K_inv = np.linalg.inv(self.K)  # 內參矩陣的逆矩陣
        cam_coords = np.dot(K_inv, uv_homogeneous) 

        # 計算世界坐標
        world_coords = np.dot(self.R.T, cam_coords - self.t.ravel())

        # 返回世界座標中的 x 和 y
        return world_coords[0], world_coords[1]
    