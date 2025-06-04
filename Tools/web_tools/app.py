# -*- coding: utf-8 -*-
"""
Flask Web UI 相機控制系統
基於 Camera_API.py 的 Web 界面實現
最終修復版本：直接訪問相機工作線程數據
"""

from flask import Flask, render_template, Response, request, jsonify, send_file
from Camera_API import create_camera_api, CameraMode, ImageFormat, CameraStatus, CameraParameters
import threading
import time
import cv2
import numpy as np
from ctypes import *
import base64
import io
import os
from datetime import datetime
import json

app = Flask(__name__)

# 全域變數
camera_api = create_camera_api()
camera_api.set_error_callback(lambda msg: print(f"[Camera Error] {msg}"))

# 串流相關變數
stream_thread = None
latest_frame = None
latest_raw_frame = None
stream_running = False
frame_lock = threading.Lock()

# FPS 計算相關變數
fps_calculator_thread = None
fps_running = False
current_fps = 0.0
frame_count = 0
fps_lock = threading.Lock()

# 保存相關變數
save_directory = "captured_images"
save_count = 0

# 設備列表快取
cached_devices = []

# 確保保存目錄存在
os.makedirs(save_directory, exist_ok=True)

# ========== 修復的影像獲取函數 ==========

def get_camera_frame_direct():
    """
    直接從相機工作線程獲取影像數據
    Returns:
        numpy array: BGR 格式的影像，失敗返回 None
    """
    if not camera_api.is_connected() or not camera_api.is_streaming():
        return None
    
    cam_op = camera_api._camera_operation
    if cam_op is None:
        return None
    
    try:
        # 直接使用相機操作對象的 SDK API 獲取圖像
        from MvCameraControl_class import MV_FRAME_OUT
        from CameraParams_header import memset
        
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))
        
        # 嘗試獲取一幀圖像（使用較短的超時）
        ret = cam_op.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 100)
        
        if ret == 0:  # 成功獲取
            try:
                width = stOutFrame.stFrameInfo.nWidth
                height = stOutFrame.stFrameInfo.nHeight
                pixel_type = stOutFrame.stFrameInfo.enPixelType
                frame_len = stOutFrame.stFrameInfo.nFrameLen
                
                print(f"直接獲取影像成功: {width}x{height}, 格式: 0x{pixel_type:08X}, 長度: {frame_len}")
                
                if width > 0 and height > 0 and frame_len > 0:
                    # 複製圖像數據
                    image_data = string_at(stOutFrame.pBufAddr, frame_len)
                    image_array = np.frombuffer(image_data, dtype=np.uint8)
                    
                    # 根據像素格式轉換
                    result_image = convert_pixel_format(image_array, width, height, pixel_type)
                    
                    # 釋放圖像緩衝區
                    cam_op.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                    
                    return result_image
                else:
                    print("影像尺寸無效")
                    cam_op.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                    return None
                    
            except Exception as e:
                print(f"處理影像數據錯誤: {str(e)}")
                cam_op.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                return None
        else:
            # 沒有可用的影像數據
            return None
            
    except Exception as e:
        print(f"直接獲取影像錯誤: {str(e)}")
        return None

def convert_pixel_format(image_array, width, height, pixel_type):
    """
    轉換像素格式為BGR格式
    """
    try:
        result_image = None
        
        if pixel_type == 0x01080001:  # Mono8
            expected_size = width * height
            if len(image_array) >= expected_size:
                mono_image = image_array[:expected_size].reshape((height, width))
                result_image = cv2.cvtColor(mono_image, cv2.COLOR_GRAY2BGR)
            
        elif pixel_type == 0x01100003:  # Mono10
            expected_size = width * height * 2
            if len(image_array) >= expected_size:
                mono10_data = image_array[:expected_size]
                mono10_image = np.frombuffer(mono10_data, dtype=np.uint16)[:width * height]
                mono10_image = mono10_image.reshape((height, width))
                mono8_image = (mono10_image >> 2).astype(np.uint8)
                result_image = cv2.cvtColor(mono8_image, cv2.COLOR_GRAY2BGR)
                
        elif pixel_type == 0x01100005:  # Mono12
            expected_size = width * height * 2
            if len(image_array) >= expected_size:
                mono12_data = image_array[:expected_size]
                mono12_image = np.frombuffer(mono12_data, dtype=np.uint16)[:width * height]
                mono12_image = mono12_image.reshape((height, width))
                mono8_image = (mono12_image >> 4).astype(np.uint8)
                result_image = cv2.cvtColor(mono8_image, cv2.COLOR_GRAY2BGR)
                
        elif pixel_type == 0x02180014:  # RGB8 Packed
            expected_size = width * height * 3
            if len(image_array) >= expected_size:
                rgb_image = image_array[:expected_size].reshape((height, width, 3))
                result_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
                
        elif pixel_type == 0x02180015:  # BGR8 Packed
            expected_size = width * height * 3
            if len(image_array) >= expected_size:
                result_image = image_array[:expected_size].reshape((height, width, 3))
                
        # Bayer格式處理
        elif pixel_type == 0x01080008:  # BayerRG8
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                result_image = cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_RG2BGR)
                
        elif pixel_type == 0x01080009:  # BayerGB8
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                result_image = cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_GB2BGR)
                
        elif pixel_type == 0x0108000A:  # BayerGR8
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                result_image = cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_GR2BGR)
                
        elif pixel_type == 0x0108000B:  # BayerBG8
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                result_image = cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_BG2BGR)
                
        else:
            # 未知格式，嘗試作為Mono8處理
            print(f"未知像素格式: 0x{pixel_type:08X}，嘗試作為Mono8處理")
            expected_size = width * height
            if len(image_array) >= expected_size:
                mono_image = image_array[:expected_size].reshape((height, width))
                result_image = cv2.cvtColor(mono_image, cv2.COLOR_GRAY2BGR)
        
        if result_image is not None and result_image.size > 0:
            print(f"像素格式轉換成功: {result_image.shape}")
            return result_image
        else:
            print("像素格式轉換失敗")
            return None
            
    except Exception as e:
        print(f"像素格式轉換錯誤: {str(e)}")
        return None

def fps_calculator():
    """FPS 計算線程"""
    global current_fps, frame_count, fps_running
    
    last_count = 0
    last_time = time.time()
    
    while fps_running:
        try:
            time.sleep(1.0)
            
            current_time = time.time()
            elapsed_time = current_time - last_time
            
            if elapsed_time >= 1.0:
                with fps_lock:
                    current_frame_count = frame_count
                    fps = (current_frame_count - last_count) / elapsed_time
                    current_fps = round(fps, 1)
                    last_count = current_frame_count
                
                last_time = current_time
                if current_fps > 0:
                    print(f"當前FPS: {current_fps}, 總幀數: {current_frame_count}")
                
        except Exception as e:
            print(f"FPS計算錯誤: {str(e)}")
            time.sleep(0.1)

def grab_frames():
    """持續擷取影像的線程函數 - 最終修復版"""
    global latest_frame, latest_raw_frame, stream_running, frame_count
    
    local_frame_count = 0
    success_count = 0
    
    print("開始影像擷取線程...")
    time.sleep(1.0)  # 給相機一些時間準備
    
    while stream_running:
        try:
            # 使用直接獲取方法
            raw = get_camera_frame_direct()
            
            if raw is not None:
                success_count += 1
                local_frame_count += 1
                
                # 更新幀計數
                with fps_lock:
                    frame_count = local_frame_count
                
                if raw.shape[0] > 0 and raw.shape[1] > 0:
                    # 保存原始影像用於存檔
                    with frame_lock:
                        latest_raw_frame = raw.copy()
                    
                    # 如果影像太大，縮小以加快處理速度
                    display_image = raw
                    if raw.shape[1] > 1920:
                        scale = 1920.0 / raw.shape[1]
                        new_width = int(raw.shape[1] * scale)
                        new_height = int(raw.shape[0] * scale)
                        display_image = cv2.resize(raw, (new_width, new_height))
                    
                    # 編碼為 JPEG
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                    ret, jpeg = cv2.imencode('.jpg', display_image, encode_param)
                    
                    if ret:
                        jpeg_bytes = jpeg.tobytes()
                        
                        # 存到全域變數
                        with frame_lock:
                            latest_frame = jpeg_bytes
                        
                        if success_count % 30 == 0:
                            print(f"已成功處理 {success_count} 幀，影像尺寸: {raw.shape}")
            
            # 控制處理速度
            time.sleep(0.01)
            
        except Exception as e:
            print(f"擷取影像異常: {str(e)}")
            time.sleep(0.1)
    
    print(f"影像擷取線程已結束，共處理了 {success_count} 幀")

def generate_mjpeg():
    """生成 MJPEG 串流"""
    global latest_frame, stream_running
    
    no_frame_count = 0
    
    while stream_running:
        with frame_lock:
            frame = latest_frame
        
        if frame:
            no_frame_count = 0
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        else:
            no_frame_count += 1
            if no_frame_count > 50:  # 減少等待時間
                # 發送一個提示影像
                placeholder_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder_frame, "Loading camera data...", 
                           (150, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.putText(placeholder_frame, f"Time: {datetime.now().strftime('%H:%M:%S')}", 
                           (200, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
                ret, jpeg = cv2.imencode('.jpg', placeholder_frame)
                if ret:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                no_frame_count = 0
            
            time.sleep(0.02)

def save_image_to_disk(image_data, format_type="bmp", custom_filename=None):
    """保存影像到磁碟"""
    global save_count
    
    try:
        if image_data is None or image_data.size == 0:
            return False, "", "無效的影像數據"
        
        print(f"準備保存影像: {image_data.shape}, 格式: {format_type}")
        
        # 生成文件名
        if custom_filename:
            custom_filename = "".join(c for c in custom_filename if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{custom_filename}.{format_type}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_count += 1
            filename = f"capture_{timestamp}_{save_count:04d}.{format_type}"
        
        filepath = os.path.join(save_directory, filename)
        os.makedirs(save_directory, exist_ok=True)
        
        # 保存影像
        if format_type.lower() in ["jpeg", "jpg"]:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
            success = cv2.imwrite(filepath, image_data, encode_param)
        elif format_type.lower() == "png":
            encode_param = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
            success = cv2.imwrite(filepath, image_data, encode_param)
        else:  # BMP
            success = cv2.imwrite(filepath, image_data)
        
        if success:
            file_size = os.path.getsize(filepath)
            print(f"影像已保存: {filepath}, 大小: {file_size} bytes")
            return True, filename, ""
        else:
            return False, "", "OpenCV 保存失敗"
            
    except Exception as e:
        print(f"保存影像異常: {str(e)}")
        return False, "", f"保存錯誤: {str(e)}"

# ========== Flask 路由 ==========

@app.route("/")
def index():
    """主頁面"""
    return render_template("index.html")

@app.route("/devices", methods=["GET"])
def list_devices():
    """列出所有設備"""
    try:
        devices = camera_api.enumerate_devices()
        dev_list = []
        for device in devices:
            dev_info = {
                "index": device.index,
                "name": device.device_name,
                "type": device.device_type,
                "serial": device.serial_number,
                "ip": device.ip_address if device.ip_address else "N/A"
            }
            dev_list.append(dev_info)
        
        return jsonify({
            "success": True,
            "devices": dev_list,
            "count": len(dev_list)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "devices": [],
            "count": 0
        })

@app.route("/connect", methods=["POST"])
def connect_camera():
    """連接相機"""
    try:
        data = request.get_json()
        idx = int(data.get("index", -1))
        
        if idx < 0:
            return jsonify({"success": False, "error": "無效的設備索引"})
        
        if camera_api.is_connected():
            camera_api.disconnect()
            time.sleep(0.5)
        
        ok = camera_api.connect(idx)
        
        if ok:
            device_info = camera_api.get_device_info()
            print(f"設備連接成功: {device_info.device_name if device_info else 'Unknown'}")
            return jsonify({
                "success": True,
                "device_info": {
                    "name": device_info.device_name if device_info else "Unknown",
                    "type": device_info.device_type if device_info else "Unknown"
                }
            })
        else:
            return jsonify({"success": False, "error": "連接失敗"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/disconnect", methods=["POST"])
def disconnect_camera():
    """斷開相機連接"""
    global stream_running, stream_thread, fps_running, fps_calculator_thread
    
    try:
        if stream_running or camera_api.is_streaming():
            print("正在停止串流...")
            
            fps_running = False
            if fps_calculator_thread and fps_calculator_thread.is_alive():
                fps_calculator_thread.join(timeout=1.0)
            
            stream_running = False
            if stream_thread and stream_thread.is_alive():
                stream_thread.join(timeout=2.0)
            
            try:
                camera_api.stop_streaming()
            except:
                pass
            
            time.sleep(0.5)
        
        ok = camera_api.disconnect()
        print("設備已斷開連接")
        return jsonify({"success": ok})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/status", methods=["GET"])
def get_status():
    """獲取相機狀態"""
    try:
        status = camera_api.get_status()
        is_connected = camera_api.is_connected()
        is_streaming = camera_api.is_streaming()
        current_mode = camera_api.get_mode()
        
        params = None
        if is_connected:
            params = camera_api.get_parameters()
        
        with fps_lock:
            fps = current_fps
        
        return jsonify({
            "success": True,
            "status": status.value,
            "is_connected": is_connected,
            "is_streaming": is_streaming,
            "mode": current_mode.value,
            "parameters": params.to_dict() if params else None,
            "fps": fps,
            "save_count": save_count
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/parameters", methods=["GET"])
def get_parameters():
    """獲取相機參數"""
    try:
        params = camera_api.get_parameters()
        if params:
            return jsonify({
                "success": True,
                "parameters": params.to_dict()
            })
        else:
            return jsonify({"success": False, "error": "無法獲取參數"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/parameters", methods=["POST"])
def set_parameters():
    """設置相機參數"""
    try:
        data = request.get_json()
        
        params = CameraParameters()
        params.frame_rate = float(data.get("frame_rate", 30.0))
        params.exposure_time = float(data.get("exposure_time", 10000.0))
        params.gain = float(data.get("gain", 0.0))
        
        ok = camera_api.set_parameters(params)
        if ok:
            print(f"參數設置成功: FPS={params.frame_rate}, 曝光={params.exposure_time}, 增益={params.gain}")
        return jsonify({"success": ok})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/mode", methods=["POST"])
def set_mode():
    """設置相機模式"""
    try:
        data = request.get_json()
        mode = data.get("mode", "continuous")
        
        cam_mode = CameraMode.CONTINUOUS if mode == "continuous" else CameraMode.TRIGGER
        ok = camera_api.set_mode(cam_mode)
        
        if ok:
            print(f"模式設置成功: {mode}")
        
        return jsonify({"success": ok})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/start_stream", methods=["POST"])
def start_stream():
    """開始串流"""
    global stream_thread, stream_running, latest_frame, latest_raw_frame, fps_calculator_thread, fps_running, frame_count
    
    try:
        if not camera_api.is_connected():
            return jsonify({"success": False, "error": "相機未連接"})
        
        if camera_api.is_streaming() or stream_running:
            return jsonify({"success": False, "error": "相機已經在串流中"})
        
        print("準備開始串流...")
        
        # 開始相機串流
        ok = camera_api.start_streaming()
        if not ok:
            return jsonify({"success": False, "error": "啟動串流失敗"})
        
        print("相機串流已啟動，等待準備就緒...")
        time.sleep(1.5)  # 給相機更多時間準備
        
        # 清空之前的數據
        with frame_lock:
            latest_frame = None
            latest_raw_frame = None
        
        with fps_lock:
            frame_count = 0
        
        # 啟動 FPS 計算線程
        fps_running = True
        fps_calculator_thread = threading.Thread(target=fps_calculator, daemon=True)
        fps_calculator_thread.start()
        print("FPS計算線程已啟動")
        
        # 啟動擷取線程
        stream_running = True
        stream_thread = threading.Thread(target=grab_frames, daemon=True)
        stream_thread.start()
        print("影像擷取線程已啟動")
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"啟動串流錯誤: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/stop_stream", methods=["POST"])
def stop_stream():
    """停止串流"""
    global stream_running, stream_thread, fps_running, fps_calculator_thread
    
    try:
        print("正在停止串流...")
        
        fps_running = False
        if fps_calculator_thread and fps_calculator_thread.is_alive():
            fps_calculator_thread.join(timeout=1.0)
        print("FPS計算線程已停止")
        
        stream_running = False
        if stream_thread and stream_thread.is_alive():
            stream_thread.join(timeout=2.0)
        print("影像擷取線程已停止")
        
        try:
            camera_api.stop_streaming()
            print("相機串流已停止")
        except Exception as e:
            error_msg = str(e).lower()
            if "thread" in error_msg or "invalid thread id" in error_msg:
                print("忽略線程錯誤，串流已停止")
            else:
                raise e
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"停止串流錯誤: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/trigger", methods=["POST"])
def software_trigger():
    """軟觸發"""
    try:
        print("執行軟觸發...")
        ok = camera_api.software_trigger()
        if ok:
            print("軟觸發成功")
        else:
            print("軟觸發失敗")
        return jsonify({"success": ok})
    except Exception as e:
        print(f"軟觸發錯誤: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/capture", methods=["POST"])
def capture_image():
    """拍照保存"""
    try:
        data = request.get_json()
        format_type = data.get("format", "bmp")
        custom_filename = data.get("filename", "")
        
        print(f"開始拍照保存，格式: {format_type}")
        
        if not camera_api.is_streaming():
            return jsonify({"success": False, "error": "需要在串流狀態下才能拍照"})
        
        # 優先使用保存的原始影像
        raw_image = None
        with frame_lock:
            if latest_raw_frame is not None:
                raw_image = latest_raw_frame.copy()
        
        # 如果沒有保存的影像，直接獲取
        if raw_image is None:
            print("嘗試直接獲取影像...")
            raw_image = get_camera_frame_direct()
        
        if raw_image is None:
            return jsonify({"success": False, "error": "無法獲取影像數據"})
        
        print(f"獲取到影像: {raw_image.shape}")
        
        # 保存影像
        success, filename, error_msg = save_image_to_disk(
            raw_image, 
            format_type, 
            custom_filename if custom_filename else None
        )
        
        if success:
            filepath = os.path.join(save_directory, filename)
            file_size = os.path.getsize(filepath)
            
            print(f"影像保存成功: {filename}, 大小: {file_size} bytes")
            
            return jsonify({
                "success": True,
                "filename": filename,
                "file_size": file_size,
                "save_path": save_directory,
                "save_count": save_count
            })
        else:
            print(f"影像保存失敗: {error_msg}")
            return jsonify({"success": False, "error": error_msg})
            
    except Exception as e:
        print(f"拍照保存異常: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/test_save", methods=["POST"])
def test_save_image():
    """測試保存功能"""
    try:
        # 創建測試圖像
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        test_image[:] = (64, 128, 192)  # 藍灰色背景
        
        cv2.putText(test_image, "Test Image", (200, 200), 
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        cv2.putText(test_image, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                   (150, 300), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        
        cv2.circle(test_image, (100, 100), 50, (0, 255, 0), -1)
        cv2.rectangle(test_image, (500, 50), (600, 150), (255, 0, 0), -1)
        
        print("創建測試圖像完成")
        
        success, filename, error_msg = save_image_to_disk(test_image, "bmp", "test_image")
        
        if success:
            filepath = os.path.join(save_directory, filename)
            file_size = os.path.getsize(filepath)
            print(f"測試圖像保存成功: {filename}")
            
            return jsonify({
                "success": True,
                "filename": filename,
                "file_size": file_size,
                "message": "測試圖像保存成功"
            })
        else:
            return jsonify({"success": False, "error": f"測試保存失敗: {error_msg}"})
            
    except Exception as e:
        print(f"測試保存異常: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/capture_settings", methods=["GET"])
def get_capture_settings():
    """獲取拍照設置資訊"""
    try:
        files = []
        if os.path.exists(save_directory):
            for filename in os.listdir(save_directory):
                filepath = os.path.join(save_directory, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    files.append({
                        "filename": filename,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        files.sort(key=lambda x: x["modified"], reverse=True)
        
        return jsonify({
            "success": True,
            "save_directory": save_directory,
            "save_count": save_count,
            "files": files[:20],
            "total_files": len(files)
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/download/<filename>")
def download_file(filename):
    """下載保存的檔案"""
    try:
        filepath = os.path.join(save_directory, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
        else:
            return jsonify({"error": "檔案不存在"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/video_feed")
def video_feed():
    """MJPEG 串流端點"""
    return Response(
        generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/snapshot")
def get_snapshot():
    """獲取當前影像快照"""
    try:
        with frame_lock:
            frame = latest_frame
        
        if frame:
            base64_image = base64.b64encode(frame).decode('utf-8')
            return jsonify({
                "success": True,
                "image": f"data:image/jpeg;base64,{base64_image}"
            })
        else:
            return jsonify({"success": False, "error": "無可用影像"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/fps", methods=["GET"])
def get_fps():
    """獲取當前FPS"""
    try:
        with fps_lock:
            fps = current_fps
            total_frames = frame_count
        
        return jsonify({
            "success": True,
            "fps": fps,
            "frame_count": total_frames
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/packet_size", methods=["POST"])
def optimize_packet_size():
    """優化網路包大小"""
    try:
        ok = camera_api.set_packet_size(0)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ========== 錯誤處理 ==========

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ========== 主程式 ==========

if __name__ == "__main__":
    print("啟動 Flask Web UI 相機控制系統...")
    print("請訪問 http://localhost:5000")
    print(f"影像保存目錄: {os.path.abspath(save_directory)}")
    
    app.config['JSON_AS_ASCII'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)