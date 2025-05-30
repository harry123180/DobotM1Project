# -- coding: utf-8 --

import sys
import copy
import msvcrt

from ctypes import *

sys.path.append("../MvImport")
from MvCameraControl_class import *

if __name__ == "__main__":

    # ch:初始化SDK | en: initialize SDK
    MvCamera.MV_CC_Initialize()

    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                  | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
    
    # ch:枚举设备 | en:Enum device
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0:
        print ("enum devices fail! ret[0x%x]" % ret)
        sys.exit()

    if deviceList.nDeviceNum == 0:
        print ("find no device!")
        sys.exit()

    print ("find %d devices!" % deviceList.nDeviceNum)

    for i in range(0, deviceList.nDeviceNum):
        mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE:
            print ("\ngige device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print ("device model name: %s" % strModeName)

            nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
            nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
            nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
            nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
            print ("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))
        elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
            print ("\nu3v device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print ("device model name: %s" % strModeName)

            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)
            print ("user serial number: %s" % strSerialNumber)
        elif mvcc_dev_info.nTLayerType == MV_GENTL_CAMERALINK_DEVICE:
            print ("\nCML device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stCMLInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print ("device model name: %s" % strModeName)

            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stCMLInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)
            print ("user serial number: %s" % strSerialNumber)
        elif mvcc_dev_info.nTLayerType == MV_GENTL_CXP_DEVICE:
            print ("\nCXP device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stCXPInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print ("device model name: %s" % strModeName)

            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stCXPInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)
            print ("user serial number: %s" % strSerialNumber)
        elif mvcc_dev_info.nTLayerType == MV_GENTL_XOF_DEVICE:
            print ("\nXoF device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stXoFInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print ("device model name: %s" % strModeName)

            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stXoFInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)
            print ("user serial number: %s" % strSerialNumber)

    nConnectionNum = input("please input the number of the device to connect:")

    if int(nConnectionNum) >= deviceList.nDeviceNum:
        print ("intput error!")
        sys.exit()

    # ch:创建相机实例 | en:Creat Camera Object
    cam = MvCamera()

    # ch:选择设备并创建句柄 | en:Select device and create handle
    stDeviceList = cast(deviceList.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)).contents

    ret = cam.MV_CC_CreateHandle(stDeviceList)
    if ret != 0:
        print ("create handle fail! ret[0x%x]" % ret)
        sys.exit()

    # ch:打开设备 | en:Open device
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print ("open device fail! ret[0x%x]" % ret)
        sys.exit()

    # ch:探测网络最佳包大小(只对GigE相机有效) | en:Detection network optimal package size(It only works for the GigE camera)
    if stDeviceList.nTLayerType == MV_GIGE_DEVICE or stDeviceList.nTLayerType == MV_GENTL_GIGE_DEVICE:
        nPacketSize = cam.MV_CC_GetOptimalPacketSize()
        if int(nPacketSize) > 0:
            ret = cam.MV_CC_SetIntValue("GevSCPSPacketSize",nPacketSize)
            if ret != 0:
                print ("Warning: Set Packet Size fail! ret[0x%x]" % ret)
        else:
            print ("Warning: Get Packet Size fail! ret[0x%x]" % nPacketSize)

    # ch:设置触发模式为off | en:Set trigger mode as off
    ret = cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
    if ret != 0:
        print ("set trigger mode fail! ret[0x%x]" % ret)
        sys.exit()
    # ch:开始取流 | en:Start grab image
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print ("start grabbing fail! ret[0x%x]" % ret)
        sys.exit()

    stOutFrame = MV_FRAME_OUT()  
    memset(byref(stOutFrame), 0, sizeof(stOutFrame))

    ret = cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
    if None != stOutFrame.pBufAddr and 0 == ret :
        print ("get one frame: Width[%d], Height[%d], nFrameNum[%d]"  % (stOutFrame.stFrameInfo.nWidth, stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nFrameNum))

        nRGBSize = stOutFrame.stFrameInfo.nWidth * stOutFrame.stFrameInfo.nHeight * 3
        stConvertParam = MV_CC_PIXEL_CONVERT_PARAM_EX()
        memset(byref(stConvertParam), 0, sizeof(stConvertParam))
        stConvertParam.nWidth = stOutFrame.stFrameInfo.nWidth
        stConvertParam.nHeight = stOutFrame.stFrameInfo.nHeight
        stConvertParam.pSrcData = stOutFrame.pBufAddr
        stConvertParam.nSrcDataLen = stOutFrame.stFrameInfo.nFrameLen
        stConvertParam.enSrcPixelType = stOutFrame.stFrameInfo.enPixelType  
        stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
        stConvertParam.pDstBuffer = (c_ubyte * nRGBSize)()
        stConvertParam.nDstBufferSize = nRGBSize

        ret = cam.MV_CC_ConvertPixelTypeEx(stConvertParam)
        if ret != 0:
            print ("convert pixel fail! ret[0x%x]" % ret)
            sys.exit()

        cam.MV_CC_FreeImageBuffer(stOutFrame)

        file_path = "AfterConvert_RGB.raw"   
        file_open = open(file_path.encode('ascii'), 'wb+')
        try:
            img_buff = (c_ubyte * stConvertParam.nDstLen)()
            cdll.msvcrt.memcpy(byref(img_buff), stConvertParam.pDstBuffer, stConvertParam.nDstLen)
            file_open.write(img_buff)
        except:
            raise Exception("save file executed failed:%s" % e.message)
        finally:
            file_open.close() 
    else:
        print ("get one frame fail, ret[0x%x]" % ret)
    
    print ("convert pixeltype succeed!")

    print ("press a key to continue.")
    msvcrt.getch()

    # ch:停止取流 | en:Stop grab image
    ret = cam.MV_CC_StopGrabbing()
    if ret != 0:
        print ("stop grabbing fail! ret[0x%x]" % ret)
        sys.exit()

    # ch:关闭设备 | Close device
    ret = cam.MV_CC_CloseDevice()
    if ret != 0:
        print ("close deivce fail! ret[0x%x]" % ret)
        sys.exit()

    # ch:销毁句柄 | Destroy handle
    ret = cam.MV_CC_DestroyHandle()
    if ret != 0:
        print ("destroy handle fail! ret[0x%x]" % ret)
        sys.exit()

    # ch:反初始化SDK | en: finalize SDK
    MvCamera.MV_CC_Finalize()
