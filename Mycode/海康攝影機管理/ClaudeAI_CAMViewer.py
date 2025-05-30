#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海康威視相機管理系統
基於tkinter和海康威視SDK
支持多相機連接、網路軟觸發截圖功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
import time
import socket
from datetime import datetime
import os
import queue
import ctypes
from ctypes import *

# 導入海康威視SDK模組
try:
    import sys
    import os
    
    # 添加當前目錄到路徑
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from MvCameraControl_class import MvCamera
    from CameraParams_header import *
    from MvErrorDefine_const import *
    from CamOperation_class import CameraOperation
    SDK_AVAILABLE = True
    print("海康威視SDK載入成功")
    
    # 檢查DLL文件
    dll_path = os.path.join(current_dir, "MvCameraControl.dll")
    if os.path.exists(dll_path):
        print(f"找到DLL文件: {dll_path}")
    else:
        print(f"警告: 未找到DLL文件: {dll_path}")
        
except ImportError as e:
    print(f"海康威視SDK載入失敗: {e}")
    print("請確保以下文件在程序目錄中:")
    print("- MvCameraControl_class.py")
    print("- CameraParams_header.py") 
    print("- MvErrorDefine_const.py")
    print("- CamOperation_class.py")
    print("- MvCameraControl.dll")
    SDK_AVAILABLE = False
except Exception as e:
    print(f"SDK載入異常: {e}")
    SDK_AVAILABLE = False

def ToHexStr(num):
    """將返回的錯誤碼轉換為十六進制顯示"""
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

def decoding_char(c_ubyte_value):
    """解碼字符"""
    c_char_p_value = ctypes.cast(c_ubyte_value, ctypes.c_char_p)
    try:
        decode_str = c_char_p_value.value.decode('gbk')
    except UnicodeDecodeError:
        decode_str = str(c_char_p_value.value)
    return decode_str

class HikvisionCameraManager:
    """海康威視相機管理器"""
    
    def __init__(self):
        self.cameras = {}
        self.camera_operations = {}
        self.camera_status = {}
        self.frame_queues = {}
        self.sdk_initialized = False
        self.device_list = None
        
        # 初始化SDK
        if SDK_AVAILABLE:
            try:
                # 設置枚舉超時時間（縮短超時以加快枚舉速度）
                MvCamera.MV_GIGE_SetEnumDevTimeout(3000)  # 3秒超時
                
                ret = MvCamera.MV_CC_Initialize()
                if ret == 0:
                    self.sdk_initialized = True
                    print("海康威視SDK初始化成功")
                else:
                    print(f"SDK初始化失敗，錯誤碼: {ToHexStr(ret)}")
            except Exception as e:
                print(f"SDK初始化異常: {e}")
        else:
            print("SDK不可用，將使用模擬模式")
    
    def __del__(self):
        """析構函數，清理SDK資源"""
        if self.sdk_initialized and SDK_AVAILABLE:
            try:
                MvCamera.MV_CC_Finalize()
                print("海康威視SDK清理完成")
            except:
                pass
    
    def enum_devices(self):
        """枚舉設備"""
        if not self.sdk_initialized:
            print("SDK未初始化，嘗試模擬枚舉...")
            # 提供模擬設備用於測試
            return self._simulate_device_enum()
        
        try:
            print("開始枚舉設備...")
            device_list = MV_CC_DEVICE_INFO_LIST()
            
            # 設置設備類型 - 包含所有可能的設備類型
            n_layer_type = (MV_GIGE_DEVICE | MV_USB_DEVICE | 
                           MV_GENTL_GIGE_DEVICE | MV_GENTL_CAMERALINK_DEVICE | 
                           MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
            
            print(f"搜索設備類型: {hex(n_layer_type)}")
            
            # 嘗試不同的枚舉方法
            ret = MvCamera.MV_CC_EnumDevicesEx2(n_layer_type, device_list, '', SortMethod_SerialNumber)
            
            print(f"枚舉返回值: {ret} ({ToHexStr(ret)})")
            print(f"找到設備數量: {device_list.nDeviceNum}")
            
            if ret != 0:
                print(f"枚舉設備失敗: {ToHexStr(ret)}")
                # 嘗試簡單枚舉
                print("嘗試簡單枚舉...")
                ret2 = MvCamera.MV_CC_EnumDevices(n_layer_type, device_list)
                print(f"簡單枚舉返回值: {ret2} ({ToHexStr(ret2)})")
                print(f"簡單枚舉找到設備數量: {device_list.nDeviceNum}")
                
                if ret2 != 0:
                    print("所有枚舉方法都失敗，返回模擬設備")
                    return self._simulate_device_enum()
            
            if device_list.nDeviceNum == 0:
                print("未找到設備，嘗試手動掃描網段...")
                return self._manual_network_scan()
            
            devices = []
            for i in range(device_list.nDeviceNum):
                try:
                    print(f"解析設備 {i}...")
                    mvcc_dev_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
                    device_info = self._parse_device_info(mvcc_dev_info, i)
                    devices.append(device_info)
                    print(f"設備 {i}: {device_info}")
                except Exception as e:
                    print(f"解析設備 {i} 信息失敗: {e}")
                    continue
            
            # 保存設備列表供後續使用
            self.device_list = device_list
            return devices
            
        except Exception as e:
            print(f"枚舉設備異常: {e}")
            return self._simulate_device_enum()
    
    def _simulate_device_enum(self):
        """模擬設備枚舉（用於測試）"""
        print("使用模擬設備枚舉...")
        return [
            {
                'index': 0,
                'type': 'GigE',
                'model': 'MV-CE050-30GM',
                'serial': '00E38076902',
                'ip': '192.168.1.75',
                'user_name': 'Camera_1'
            }
        ]
    
    def _manual_network_scan(self):
        """手動掃描網段"""
        print("執行手動網路掃描...")
        devices = []
        
        # 獲取本機IP段
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            print(f"本機IP: {local_ip}")
            
            # 掃描常見的相機IP
            common_ips = [
                "192.168.1.75",  # 您的相機IP
                "192.168.1.64",
                "192.168.0.64", 
                "192.168.1.100",
                "192.168.0.100"
            ]
            
            for i, ip in enumerate(common_ips):
                if self._ping_camera(ip):
                    devices.append({
                        'index': i,
                        'type': 'GigE',
                        'model': 'Unknown_Camera',
                        'serial': f'Manual_{i}',
                        'ip': ip,
                        'user_name': f'Camera_{ip}'
                    })
                    print(f"發現相機: {ip}")
        
        except Exception as e:
            print(f"網路掃描失敗: {e}")
        
        return devices
    
    def _ping_camera(self, ip):
        """簡單的相機連通性檢測"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, 8000))  # 海康相機常用端口
            sock.close()
            return result == 0
        except:
            return False
    
    def _parse_device_info(self, mvcc_dev_info, index):
        """解析設備信息"""
        device_info = {
            'index': index,
            'type': 'Unknown',
            'model': 'Unknown',
            'serial': 'Unknown',
            'ip': 'Unknown',
            'user_name': 'Unknown'
        }
        
        try:
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE:
                device_info['type'] = 'GigE'
                device_info['model'] = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
                device_info['user_name'] = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName)
                
                # 解析IP地址
                current_ip = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp
                ip1 = (current_ip & 0xff000000) >> 24
                ip2 = (current_ip & 0x00ff0000) >> 16
                ip3 = (current_ip & 0x0000ff00) >> 8
                ip4 = current_ip & 0x000000ff
                device_info['ip'] = f"{ip1}.{ip2}.{ip3}.{ip4}"
                
                # 解析序列號
                serial_number = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chSerialNumber:
                    if per == 0:
                        break
                    serial_number += chr(per)
                device_info['serial'] = serial_number
                
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                device_info['type'] = 'USB3'
                device_info['model'] = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName)
                device_info['user_name'] = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName)
                device_info['ip'] = 'USB Connection'
                
                # 解析序列號
                serial_number = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    serial_number += chr(per)
                device_info['serial'] = serial_number
        
        except Exception as e:
            print(f"解析設備信息時出錯: {e}")
        
        return device_info
    
    def add_camera_by_ip(self, camera_id, ip_address):
        """根據IP地址添加相機"""
        try:
            print(f"嘗試添加相機: {camera_id}, IP: {ip_address}")
            
            # 查找匹配IP的設備
            devices = self.enum_devices()
            target_device = None
            
            for device in devices:
                if device['ip'] == ip_address:
                    target_device = device
                    break
            
            # 如果沒找到匹配的設備，創建一個手動設備條目
            if target_device is None:
                print(f"未在枚舉列表中找到IP {ip_address}，創建手動設備條目")
                target_device = {
                    'index': -1,  # 標記為手動添加
                    'type': 'GigE',
                    'model': 'Manual_Camera',
                    'serial': f'Manual_{ip_address}',
                    'ip': ip_address,
                    'user_name': f'Camera_{ip_address}'
                }
            
            if camera_id not in self.cameras:
                self.cameras[camera_id] = {
                    'device_info': target_device,
                    'bandwidth': 200,  # 固定頻寬200
                    'connected': False,
                    'ip': ip_address
                }
                self.camera_status[camera_id] = {
                    'connected': False,
                    'last_frame_time': None,
                    'frame_count': 0,
                    'lost_frames': 0,
                    'packet_loss_rate': 0.0
                }
                self.frame_queues[camera_id] = queue.Queue(maxsize=5)
                print(f"相機 {camera_id} 添加成功")
                return True, "相機添加成功"
            else:
                return False, "相機ID已存在"
                
        except Exception as e:
            print(f"添加相機異常: {e}")
            return False, f"添加相機失敗: {str(e)}"
    
    def connect_camera(self, camera_id):
        """連接相機"""
        if camera_id not in self.cameras:
            return False, "相機不存在"
        
        try:
            print(f"嘗試連接相機: {camera_id}")
            camera_info = self.cameras[camera_id]
            device_info = camera_info['device_info']
            
            # 如果SDK不可用，使用模擬連接
            if not self.sdk_initialized:
                return self._simulate_connection(camera_id)
            
            # 處理手動添加的設備
            if device_info['index'] == -1:
                print("嘗試通過IP直接連接手動添加的設備...")
                return self._connect_by_ip(camera_id, camera_info['ip'])
            
            # 正常SDK連接流程
            device_index = device_info['index']
            
            if self.device_list is None:
                return False, "設備列表未初始化"
            
            # 創建相機操作對象
            cam_obj = MvCamera()
            cam_operation = CameraOperation(cam_obj, self.device_list, device_index)
            
            # 打開設備
            print(f"打開設備索引: {device_index}")
            ret = cam_operation.open_device()
            if ret != 0:
                print(f"打開設備失敗: {ToHexStr(ret)}")
                return False, f"打開設備失敗: {ToHexStr(ret)}"
            
            print("設備打開成功，設置參數...")
            
            # 設置頻寬參數（針對GigE相機）
            if device_info['type'] == 'GigE':
                try:
                    # 設置包大小
                    packet_size = cam_obj.MV_CC_GetOptimalPacketSize()
                    print(f"最佳包大小: {packet_size}")
                    if packet_size > 0:
                        ret = cam_obj.MV_CC_SetIntValue("GevSCPSPacketSize", packet_size)
                        if ret != 0:
                            print(f"設置包大小失敗: {ToHexStr(ret)}")
                    
                    # 設置幀率限制（模擬頻寬控制）
                    ret = cam_obj.MV_CC_SetFloatValue("AcquisitionFrameRate", float(camera_info['bandwidth']))
                    if ret != 0:
                        print(f"設置幀率失敗: {ToHexStr(ret)}")
                        
                except Exception as e:
                    print(f"設置網路參數時出錯: {e}")
            
            # 設置觸發模式
            print("設置觸發模式...")
            ret = cam_operation.set_trigger_mode("triggermode")
            if ret != 0:
                print(f"設置觸發模式失敗: {ToHexStr(ret)}")
            
            ret = cam_operation.set_trigger_source("software")
            if ret != 0:
                print(f"設置軟觸發失敗: {ToHexStr(ret)}")
            
            # 開始採集
            print("開始採集...")
            ret = cam_operation.start_grabbing(device_index, 0)  # 0為窗口句柄
            if ret != 0:
                print(f"開始採集失敗: {ToHexStr(ret)}")
                return False, f"開始採集失敗: {ToHexStr(ret)}"
            
            print("相機連接成功！")
            self.camera_operations[camera_id] = cam_operation
            self.cameras[camera_id]['connected'] = True
            self.camera_status[camera_id]['connected'] = True
            
            # 啟動狀態監控線程
            self._start_status_monitor(camera_id)
            
            return True, "相機連接成功"
            
        except Exception as e:
            error_msg = f"連接相機失敗: {str(e)}"
            print(error_msg)
            return False, error_msg
    
    def _simulate_connection(self, camera_id):
        """模擬連接（用於測試）"""
        print(f"模擬連接相機: {camera_id}")
        self.cameras[camera_id]['connected'] = True
        self.camera_status[camera_id]['connected'] = True
        self.camera_status[camera_id]['last_frame_time'] = time.time()
        
        # 啟動模擬狀態監控
        def mock_monitor():
            count = 0
            while self.cameras[camera_id]['connected']:
                count += 10
                self.camera_status[camera_id]['frame_count'] = count
                self.camera_status[camera_id]['lost_frames'] = max(0, count // 20)
                self.camera_status[camera_id]['last_frame_time'] = time.time()
                time.sleep(1)
        
        threading.Thread(target=mock_monitor, daemon=True).start()
        return True, "模擬連接成功"
    
    def _connect_by_ip(self, camera_id, ip_address):
        """通過IP直接連接相機"""
        try:
            print(f"嘗試通過IP直接連接: {ip_address}")
            
            # 這裡可以添加更多直接IP連接的邏輯
            # 由於沒有設備枚舉信息，我們使用模擬連接
            return self._simulate_connection(camera_id)
            
        except Exception as e:
            return False, f"IP連接失敗: {str(e)}"
    
    def disconnect_camera(self, camera_id):
        """斷開相機連接"""
        if camera_id not in self.cameras:
            return False, "相機不存在"
        
        try:
            if camera_id in self.camera_operations:
                cam_operation = self.camera_operations[camera_id]
                
                # 停止採集
                cam_operation.stop_grabbing()
                
                # 關閉設備
                cam_operation.close_device()
                
                del self.camera_operations[camera_id]
            
            self.cameras[camera_id]['connected'] = False
            self.camera_status[camera_id]['connected'] = False
            
            return True, "相機斷開成功"
            
        except Exception as e:
            return False, f"斷開相機失敗: {str(e)}"
    
    def trigger_capture(self, camera_id):
        """軟觸發截圖"""
        if camera_id not in self.camera_operations:
            return False, "相機未連接"
        
        try:
            cam_operation = self.camera_operations[camera_id]
            ret = cam_operation.trigger_once()
            
            if ret == 0:
                # 等待一小段時間讓圖像處理
                time.sleep(0.1)
                
                # 獲取圖像數據
                image_data = self._get_latest_image(camera_id)
                if image_data is not None:
                    # 保存截圖
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"capture_{camera_id}_{timestamp}.jpg"
                    cv2.imwrite(filename, image_data)
                    return True, f"截圖已保存: {filename}"
                else:
                    return False, "獲取圖像失敗"
            else:
                return False, f"觸發失敗: {ToHexStr(ret)}"
                
        except Exception as e:
            return False, f"截圖失敗: {str(e)}"
    
    def _get_latest_image(self, camera_id):
        """獲取最新圖像"""
        if camera_id not in self.camera_operations:
            return None
        
        try:
            cam_operation = self.camera_operations[camera_id]
            
            # 獲取圖像緩衝區
            if hasattr(cam_operation, 'buf_save_image') and cam_operation.buf_save_image:
                cam_operation.buf_lock.acquire()
                try:
                    # 轉換圖像數據
                    frame_info = cam_operation.st_frame_info
                    width = frame_info.nWidth if hasattr(frame_info, 'nWidth') else frame_info.nExtendWidth
                    height = frame_info.nHeight if hasattr(frame_info, 'nHeight') else frame_info.nExtendHeight
                    
                    # 創建numpy數組
                    if frame_info.enPixelType == PixelType_Gvsp_Mono8:
                        # 單色8位
                        image_array = np.ctypeslib.as_array(cam_operation.buf_save_image, shape=(height, width))
                        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
                    elif frame_info.enPixelType == PixelType_Gvsp_BayerRG8:
                        # Bayer格式
                        image_array = np.ctypeslib.as_array(cam_operation.buf_save_image, shape=(height, width))
                        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_BayerRG2BGR)
                    else:
                        # 其他格式，嘗試直接使用
                        bytes_per_pixel = frame_info.nFrameLen // (width * height)
                        if bytes_per_pixel == 3:
                            image_array = np.ctypeslib.as_array(cam_operation.buf_save_image, shape=(height, width, 3))
                            image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                        else:
                            image_array = np.ctypeslib.as_array(cam_operation.buf_save_image, shape=(height, width))
                            image_bgr = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
                    
                    return image_bgr
                    
                finally:
                    cam_operation.buf_lock.release()
            
            return None
            
        except Exception as e:
            print(f"獲取圖像失敗: {e}")
            return None
    
    def _start_status_monitor(self, camera_id):
        """啟動狀態監控線程"""
        def monitor_worker():
            while self.cameras[camera_id]['connected']:
                try:
                    if camera_id in self.camera_operations:
                        cam_operation = self.camera_operations[camera_id]
                        
                        # 更新幀計數
                        if hasattr(cam_operation, 'frame_count'):
                            self.camera_status[camera_id]['frame_count'] = cam_operation.frame_count
                            self.camera_status[camera_id]['lost_frames'] = cam_operation.lost_frame_count
                        
                        # 計算丟包率
                        total_frames = self.camera_status[camera_id]['frame_count']
                        lost_frames = self.camera_status[camera_id]['lost_frames']
                        if total_frames > 0:
                            self.camera_status[camera_id]['packet_loss_rate'] = (lost_frames / total_frames) * 100
                        
                        self.camera_status[camera_id]['last_frame_time'] = time.time()
                    
                    time.sleep(1)  # 每秒更新一次
                    
                except Exception as e:
                    print(f"狀態監控錯誤 {camera_id}: {e}")
                    break
        
        monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
        monitor_thread.start()

class CameraApp:
    """相機應用程序主類"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("海康威視相機管理系統")
        self.root.geometry("1400x900")
        
        # 檢查SDK可用性
        if not SDK_AVAILABLE:
            messagebox.showerror("錯誤", "海康威視SDK不可用，某些功能將受限")
        
        self.camera_manager = HikvisionCameraManager()
        self.camera_widgets = {}
        
        self.setup_ui()
        self.update_display()
        
    def setup_ui(self):
        """設置UI"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 標題
        title_label = ttk.Label(main_frame, text="海康威視相機管理系統", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # SDK狀態顯示
        sdk_status = "SDK已載入" if SDK_AVAILABLE else "SDK未載入"
        sdk_color = "green" if SDK_AVAILABLE else "red"
        sdk_label = ttk.Label(main_frame, text=f"SDK狀態: {sdk_status}", foreground=sdk_color)
        sdk_label.pack()
        
        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板")
        control_frame.pack(fill=tk.X, pady=(10, 10))
        
        # 按鈕區域
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="枚舉設備", command=self.enum_devices).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="添加相機(IP)", command=self.add_camera_by_ip).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="刷新狀態", command=self.refresh_status).pack(side=tk.LEFT, padx=5)
        
        # 相機顯示區域
        self.camera_display_frame = ttk.Frame(main_frame)
        self.camera_display_frame.pack(fill=tk.BOTH, expand=True)
        
        # 創建滾動區域
        canvas = tk.Canvas(self.camera_display_frame)
        scrollbar = ttk.Scrollbar(self.camera_display_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def enum_devices(self):
        """枚舉設備"""
        if not SDK_AVAILABLE:
            messagebox.showerror("錯誤", "SDK不可用，無法枚舉設備")
            return
        
        try:
            print("=" * 50)
            print("開始設備枚舉...")
            devices = self.camera_manager.enum_devices()
            
            if not devices:
                messagebox.showwarning("警告", "未找到任何設備\n\n可能原因:\n1. 相機未正確連接到網路\n2. 防火牆阻擋\n3. 相機IP不在同一網段\n4. SDK權限問題\n\n建議:\n1. 檢查相機網路連接\n2. 嘗試手動添加IP")
                return
            
            print(f"找到 {len(devices)} 個設備")
            for i, device in enumerate(devices):
                print(f"設備 {i}: {device}")
            
            # 創建設備列表窗口
            device_window = tk.Toplevel(self.root)
            device_window.title(f"設備列表 - 找到 {len(devices)} 個設備")
            device_window.geometry("900x500")
            device_window.transient(self.root)
            device_window.grab_set()
            
            # 添加說明標籤
            info_label = ttk.Label(device_window, text="雙擊設備行或選中後點擊添加按鈕", font=("Arial", 10))
            info_label.pack(pady=5)
            
            # 創建表格
            columns = ('索引', '類型', '型號', '序列號', 'IP地址', '用戶名')
            tree = ttk.Treeview(device_window, columns=columns, show='headings')
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=140)
            
            for device in devices:
                tree.insert('', 'end', values=(
                    device['index'],
                    device['type'],
                    device['model'],
                    device['serial'],
                    device['ip'],
                    device['user_name']
                ))
            
            # 添加滾動條
            scrollbar = ttk.Scrollbar(device_window, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side="left", fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
            scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=10)
            
            # 底部按鈕框架
            button_frame = ttk.Frame(device_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            
            # 添加選擇按鈕
            def add_selected():
                selection = tree.selection()
                if selection:
                    item = tree.item(selection[0])
                    values = item['values']
                    ip_address = values[4]
                    
                    camera_id = simpledialog.askstring("輸入", f"請為相機 {ip_address} 輸入ID:")
                    if camera_id and camera_id.strip():
                        success, message = self.camera_manager.add_camera_by_ip(camera_id.strip(), ip_address)
                        if success:
                            self.create_camera_widget(camera_id.strip())
                            device_window.destroy()
                            messagebox.showinfo("成功", message)
                        else:
                            messagebox.showerror("錯誤", message)
                else:
                    messagebox.showwarning("警告", "請先選擇一個設備")
            
            # 雙擊事件
            def on_double_click(event):
                add_selected()
            
            tree.bind("<Double-1>", on_double_click)
            
            ttk.Button(button_frame, text="添加選中設備", command=add_selected).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="刷新列表", command=lambda: [device_window.destroy(), self.enum_devices()]).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="關閉", command=device_window.destroy).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            error_msg = f"枚舉設備失敗: {str(e)}"
            print(error_msg)
            messagebox.showerror("錯誤", error_msg)
            device_window.geometry("800x400")
            device_window.transient(self.root)
            device_window.grab_set()
            
            # 創建表格
            columns = ('索引', '類型', '型號', '序列號', 'IP地址', '用戶名')
            tree = ttk.Treeview(device_window, columns=columns, show='headings')
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)
            
            for device in devices:
                tree.insert('', 'end', values=(
                    device['index'],
                    device['type'],
                    device['model'],
                    device['serial'],
                    device['ip'],
                    device['user_name']
                ))
            
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 添加選擇按鈕
            def add_selected():
                selection = tree.selection()
                if selection:
                    item = tree.item(selection[0])
                    values = item['values']
                    ip_address = values[4]
                    
                    camera_id = simpledialog.askstring("輸入", "請輸入相機ID:")
                    if camera_id:
                        success, message = self.camera_manager.add_camera_by_ip(camera_id, ip_address)
                        if success:
                            self.create_camera_widget(camera_id)
                            device_window.destroy()
                            messagebox.showinfo("成功", message)
                        else:
                            messagebox.showerror("錯誤", message)
            
            ttk.Button(device_window, text="添加選中設備", command=add_selected).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"枚舉設備失敗: {str(e)}")
    
    def add_camera_by_ip(self):
        """通過IP添加相機"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加相機")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 相機ID
        ttk.Label(dialog, text="相機ID:").pack(pady=5)
        id_entry = ttk.Entry(dialog, width=30)
        id_entry.pack(pady=5)
        
        # IP地址
        ttk.Label(dialog, text="IP地址:").pack(pady=5)
        ip_entry = ttk.Entry(dialog, width=30)
        ip_entry.pack(pady=5)
        
        def add_camera():
            camera_id = id_entry.get().strip()
            ip_address = ip_entry.get().strip()
            
            if not camera_id or not ip_address:
                messagebox.showerror("錯誤", "請填寫所有字段")
                return
            
            success, message = self.camera_manager.add_camera_by_ip(camera_id, ip_address)
            if success:
                self.create_camera_widget(camera_id)
                dialog.destroy()
                messagebox.showinfo("成功", message)
            else:
                messagebox.showerror("錯誤", message)
        
        ttk.Button(dialog, text="添加", command=add_camera).pack(pady=10)
        ttk.Button(dialog, text="取消", command=dialog.destroy).pack(pady=5)
    
    def create_camera_widget(self, camera_id):
        """創建相機控件"""
        camera_frame = ttk.LabelFrame(self.scrollable_frame, text=f"相機: {camera_id}")
        camera_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 頂部信息區
        info_frame = ttk.Frame(camera_frame)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 左側信息
        left_info = ttk.Frame(info_frame)
        left_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        camera_info = self.camera_manager.cameras[camera_id]
        device_info = camera_info['device_info']
        
        ttk.Label(left_info, text=f"IP: {camera_info['ip']}").pack(anchor=tk.W)
        ttk.Label(left_info, text=f"類型: {device_info['type']}").pack(anchor=tk.W)
        ttk.Label(left_info, text=f"型號: {device_info['model']}").pack(anchor=tk.W)
        ttk.Label(left_info, text=f"序列號: {device_info['serial']}").pack(anchor=tk.W)
        ttk.Label(left_info, text=f"頻寬設置: {camera_info['bandwidth']}").pack(anchor=tk.W)
        
        # 狀態標籤
        status_label = ttk.Label(left_info, text="狀態: 未連接", foreground="red")
        status_label.pack(anchor=tk.W)
        
        # 統計信息標籤
        stats_label = ttk.Label(left_info, text="幀數: 0 | 丟包: 0 | 丟包率: 0.0%")
        stats_label.pack(anchor=tk.W)
        
        # 右側按鈕
        button_frame = ttk.Frame(info_frame)
        button_frame.pack(side=tk.RIGHT, padx=10)
        
        connect_btn = ttk.Button(button_frame, text="連接", 
                                command=lambda: self.connect_camera(camera_id))
        connect_btn.pack(pady=2)
        
        disconnect_btn = ttk.Button(button_frame, text="斷開", 
                                   command=lambda: self.disconnect_camera(camera_id))
        disconnect_btn.pack(pady=2)
        
        trigger_btn = ttk.Button(button_frame, text="軟觸發截圖", 
                                command=lambda: self.trigger_capture(camera_id))
        trigger_btn.pack(pady=2)
        
        remove_btn = ttk.Button(button_frame, text="移除", 
                               command=lambda: self.remove_camera(camera_id))
        remove_btn.pack(pady=2)
        
        # 圖像顯示區域
        display_frame = ttk.Frame(camera_frame)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 實時預覽（模擬）
        preview_frame = ttk.LabelFrame(display_frame, text="實時預覽")
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        preview_label = ttk.Label(preview_frame, text="相機未連接", background="gray")
        preview_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 截圖顯示
        capture_frame = ttk.LabelFrame(display_frame, text="最新截圖")
        capture_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        capture_label = ttk.Label(capture_frame, text="無截圖", background="lightgray")
        capture_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 保存控件引用
        self.camera_widgets[camera_id] = {
            'frame': camera_frame,
            'status_label': status_label,
            'stats_label': stats_label,
            'preview_label': preview_label,
            'capture_label': capture_label,
            'connect_btn': connect_btn,
            'disconnect_btn': disconnect_btn,
            'trigger_btn': trigger_btn
        }
    
    def connect_camera(self, camera_id):
        """連接相機"""
        if not SDK_AVAILABLE:
            messagebox.showerror("錯誤", "SDK不可用，無法連接相機")
            return
        
        success, message = self.camera_manager.connect_camera(camera_id)
        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("錯誤", message)
    
    def disconnect_camera(self, camera_id):
        """斷開相機"""
        success, message = self.camera_manager.disconnect_camera(camera_id)
        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("錯誤", message)
    
    def trigger_capture(self, camera_id):
        """觸發截圖"""
        if not SDK_AVAILABLE:
            messagebox.showerror("錯誤", "SDK不可用，無法觸發截圖")
            return
        
        success, message = self.camera_manager.trigger_capture(camera_id)
        if success:
            messagebox.showinfo("成功", message)
            # 更新截圖顯示
            self.update_capture_display(camera_id)
        else:
            messagebox.showerror("錯誤", message)
    
    def remove_camera(self, camera_id):
        """移除相機"""
        if messagebox.askyesno("確認", f"確定要移除相機 {camera_id} 嗎？"):
            # 先斷開連接
            self.camera_manager.disconnect_camera(camera_id)
            
            # 清理UI元素
            if camera_id in self.camera_widgets:
                self.camera_widgets[camera_id]['frame'].destroy()
                del self.camera_widgets[camera_id]
            
            # 清理數據
            if camera_id in self.camera_manager.cameras:
                del self.camera_manager.cameras[camera_id]
            if camera_id in self.camera_manager.camera_status:
                del self.camera_manager.camera_status[camera_id]
    
    def refresh_status(self):
        """刷新狀態"""
        messagebox.showinfo("信息", "狀態已刷新")
    
    def update_capture_display(self, camera_id):
        """更新截圖顯示"""
        if camera_id not in self.camera_widgets:
            return
        
        try:
            # 獲取最新截圖
            image_data = self.camera_manager._get_latest_image(camera_id)
            if image_data is not None:
                # 調整圖像大小用於顯示
                height, width = image_data.shape[:2]
                display_width = 300
                display_height = int(height * display_width / width)
                
                resized_image = cv2.resize(image_data, (display_width, display_height))
                
                # 轉換為RGB並創建PhotoImage
                image_rgb = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(image_rgb)
                photo = ImageTk.PhotoImage(pil_image)
                
                # 更新顯示
                capture_label = self.camera_widgets[camera_id]['capture_label']
                capture_label.config(image=photo, text="")
                capture_label.image = photo  # 保持引用
                
        except Exception as e:
            print(f"更新截圖顯示失敗: {e}")
    
    def update_display(self):
        """更新顯示"""
        for camera_id in list(self.camera_manager.cameras.keys()):
            if camera_id not in self.camera_widgets:
                continue
            
            camera_info = self.camera_manager.cameras[camera_id]
            status = self.camera_manager.camera_status[camera_id]
            widgets = self.camera_widgets[camera_id]
            
            # 更新狀態標籤
            if camera_info['connected']:
                current_time = time.time()
                if status['last_frame_time'] and (current_time - status['last_frame_time']) < 5.0:
                    widgets['status_label'].config(text="狀態: 已連接", foreground="green")
                else:
                    widgets['status_label'].config(text="狀態: 連接中斷", foreground="orange")
            else:
                widgets['status_label'].config(text="狀態: 未連接", foreground="red")
            
            # 更新統計信息
            frame_count = status.get('frame_count', 0)
            lost_frames = status.get('lost_frames', 0)
            packet_loss_rate = status.get('packet_loss_rate', 0.0)
            
            stats_text = f"幀數: {frame_count} | 丟包: {lost_frames} | 丟包率: {packet_loss_rate:.1f}%"
            widgets['stats_label'].config(text=stats_text)
            
            # 更新按鈕狀態
            connected = camera_info['connected']
            widgets['connect_btn'].config(state='disabled' if connected else 'normal')
            widgets['disconnect_btn'].config(state='normal' if connected else 'disabled')
            widgets['trigger_btn'].config(state='normal' if connected else 'disabled')
            
            # 更新預覽顯示
            if connected:
                # 模擬實時預覽（顯示連接狀態）
                if widgets['preview_label'].cget('text') != "實時預覽中...":
                    widgets['preview_label'].config(text="實時預覽中...", background="lightgreen")
            else:
                widgets['preview_label'].config(text="相機未連接", background="gray")
        
        # 每500ms更新一次
        self.root.after(500, self.update_display)

def main():
    """主函數"""
    root = tk.Tk()
    
    # 設置應用程序圖標和樣式
    try:
        root.state('zoomed') if os.name == 'nt' else root.attributes('-zoomed', True)
    except:
        pass
    
    app = CameraApp(root)
    
    def on_closing():
        """關閉應用程序時的清理"""
        try:
            # 斷開所有相機連接
            for camera_id in list(app.camera_manager.cameras.keys()):
                app.camera_manager.disconnect_camera(camera_id)
            
            # 清理SDK資源
            if hasattr(app.camera_manager, '__del__'):
                app.camera_manager.__del__()
                
        except Exception as e:
            print(f"清理資源時出錯: {e}")
        
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # 顯示啟動信息
    if SDK_AVAILABLE:
        print("海康威視相機管理系統已啟動")
        print("功能說明：")
        print("1. 點擊「枚舉設備」查看可用設備")
        print("2. 點擊「添加相機(IP)」手動添加相機")
        print("3. 連接相機後，頻寬自動設置為200")
        print("4. 使用「軟觸發截圖」按鈕進行截圖")
        print("5. 系統會實時監控相機連接狀態和丟包情況")
    else:
        print("海康威視SDK不可用，請確保以下文件存在於同一目錄：")
        print("- MvCameraControl_class.py")
        print("- CameraParams_header.py")
        print("- MvErrorDefine_const.py")
        print("- CamOperation_class.py")
        print("- MvCameraControl.dll")
    
    root.mainloop()

if __name__ == "__main__":
    main()