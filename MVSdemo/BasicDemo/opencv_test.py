import os
import sys
import numpy as np
from os import getcwd
import cv2
import msvcrt
from ctypes import *

sys.path.append("../MvImport")
from MvCameraControl_class import *

# 設備資訊定義
DEVICE_INFO = {
    "設備型號": "MV-CE050-30UC",
    "設備序列號": "00DA1831623",
    "製造商名稱": "Hikrobot",
    "固件版本": "V1.6.3 201222 551351",
    "設備GUID": "2BDFA1831623",
    "設備家族名稱": "未知"
}

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
def open_device_and_display():
    def set_default_parameters(cam):
        """設置攝影機的默認參數，例如分辨率和像素格式"""
        ret = cam.MV_CC_SetEnumValue("PixelFormat", 17301512)  # 設置像素格式為 BayerGR8  # 設置像素格式，例如 BayerRG8
        if ret != 0:
            print("設置像素格式失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetIntValue("Width", 1280)  # 設置寬度
        if ret != 0:
            print("設置寬度失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetIntValue("Height", 720)  # 設置高度
        if ret != 0:
            print("設置高度失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetEnumValue("TriggerMode", 0)  # 設置為連續模式
        if ret != 0:
            print("設置觸發模式失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetImageNodeNum(10)  # 設置緩存節點數為 10
        if ret != 0:
            print("設置影像緩存節點數失敗，返回值 [0x%x]" % ret)
            sys.exit()
        ret = cam.MV_CC_SetFloatValue("AcquisitionFrameRate", 10.0)  # 設置幀率為 10 fps
        if ret != 0:
            print("設置幀率失敗，返回值 [0x%x]" % ret)
            sys.exit()
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

    # 設定取流
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print("開始取流失敗，返回值 [0x%x]" % ret)
        sys.exit()

    # 獲取圖像並顯示
    stOutFrame = MV_FRAME_OUT()
    memset(byref(stOutFrame), 0, sizeof(stOutFrame))
    i=0
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
                cv2.imshow("Camera Image", image)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            print("獲取圖像失敗，返回值 [0x%x]" % ret)
            i+=1
            if i >5:
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

# 主
if __name__ == "__main__":
    #print(f"OpenCV 使用的後端: {cv2.getBuildInformation()}"
    open_device_and_display()