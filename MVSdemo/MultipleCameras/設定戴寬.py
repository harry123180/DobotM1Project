from MvCameraControl_class import MvCamera
from ctypes import *
from MvErrorDefine_const import *

def ip_to_str(ip_uint32):
    return ".".join([str((ip_uint32 >> i) & 0xFF) for i in (24, 16, 8, 0)])

def set_scpd_to_all_devices(scpd_val=8000):
    device_list = MV_CC_DEVICE_INFO_LIST()
    ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE, device_list)
    if ret != 0 or device_list.nDeviceNum == 0:
        print("無法找到相機或枚舉失敗")
        return

    for i in range(device_list.nDeviceNum):
        dev_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        if dev_info.nTLayerType != MV_GIGE_DEVICE:
            continue

        cam = MvCamera()
        cam.MV_CC_CreateHandle(dev_info)
        cam.MV_CC_OpenDevice()

        ip_str = ip_to_str(dev_info.SpecialInfo.stGigEInfo.nCurrentIp)
        print(f"設定相機 {i}，IP: {ip_str}")

        ret = cam.MV_CC_SetIntValue("GevSCPD", scpd_val)
        if ret == 0:
            print(f"  SCPD 設為 {scpd_val} 成功")
        else:
            print(f"  設定 SCPD 失敗: 0x{ret:X}")
            continue

        cam.MV_CC_SetEnumValueByString("UserSetSelector", "UserSet1")
        cam.MV_CC_SetCommandValue("UserSetSave")
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()

if __name__ == "__main__":
    set_scpd_to_all_devices()
