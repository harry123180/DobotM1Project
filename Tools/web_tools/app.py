# -*- coding: utf-8 -*-
"""
直接SDK解決方案 - 完全繞過ImprovedCameraOperation的數據同步問題
直接使用SDK API獲取圖像
"""

from flask import Flask, render_template, Response, request, jsonify
from Camera_API import create_camera_api, CameraMode, ImageFormat, CameraStatus, CameraParameters
import threading
import time
import cv2
import numpy as np
from ctypes import *
import base64
from datetime import datetime

# 直接導入SDK
from MvCameraControl_class import *
from CameraParams_header import *

app = Flask(__name__)

# 全域變數
camera_api = create_camera_api()
camera_api.set_error_callback(lambda msg: print(f"[Camera Error] {msg}"))

# 串流相關變數
stream_thread = None
latest_frame = None
stream_running = False
frame_lock = threading.Lock()

def get_image_direct():
    """
    完全繞過ImprovedCameraOperation，直接使用SDK獲取圖像
    """
    if not camera_api.is_connected() or not camera_api.is_streaming():
        return None
    
    cam_op = camera_api._camera_operation
    if cam_op is None or not hasattr(cam_op, 'obj_cam'):
        return None
    
    try:
        # 直接使用SDK的MV_CC_GetImageBuffer
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))
        
        # 獲取圖像，超時100ms
        ret = cam_op.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 100)
        
        if ret == 0:
            try:
                # 從SDK直接獲取圖像信息
                width = stOutFrame.stFrameInfo.nWidth
                height = stOutFrame.stFrameInfo.nHeight
                pixel_type = stOutFrame.stFrameInfo.enPixelType
                frame_len = stOutFrame.stFrameInfo.nFrameLen
                
                if width <= 0 or height <= 0 or frame_len <= 0:
                    cam_op.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                    return None
                
                # 直接從SDK緩衝區複製數據
                image_buffer = (c_ubyte * frame_len)()
                cdll.msvcrt.memcpy(image_buffer, stOutFrame.pBufAddr, frame_len)
                
                # 立即釋放SDK緩衝區
                cam_op.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                
                # 轉換為numpy數組
                np_array = np.frombuffer(image_buffer, dtype=np.uint8)
                
                # 轉換為BGR格式
                bgr_image = convert_to_bgr_simple(np_array, width, height, pixel_type)
                
                return bgr_image
                
            except Exception as e:
                # 確保釋放緩衝區
                try:
                    cam_op.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
                except:
                    pass
                print(f"圖像處理錯誤: {str(e)}")
                return None
        else:
            # 沒有數據可用
            return None
            
    except Exception as e:
        print(f"直接SDK獲取錯誤: {str(e)}")
        return None

def convert_to_bgr_simple(image_array, width, height, pixel_type):
    """
    簡化的像素格式轉換
    """
    try:
        # Mono8 - 最常見的格式
        if pixel_type == 0x01080001:
            expected_size = width * height
            if len(image_array) >= expected_size:
                mono_image = image_array[:expected_size].reshape((height, width))
                return cv2.cvtColor(mono_image, cv2.COLOR_GRAY2BGR)
        
        # BGR8 Packed
        elif pixel_type == 0x02180015:
            expected_size = width * height * 3
            if len(image_array) >= expected_size:
                return image_array[:expected_size].reshape((height, width, 3))
        
        # RGB8 Packed
        elif pixel_type == 0x02180014:
            expected_size = width * height * 3
            if len(image_array) >= expected_size:
                rgb_image = image_array[:expected_size].reshape((height, width, 3))
                return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
        
        # Bayer RG8
        elif pixel_type == 0x01080008:
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                return cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_RG2BGR)
        
        # Bayer GB8
        elif pixel_type == 0x01080009:
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                return cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_GB2BGR)
        
        # Bayer GR8
        elif pixel_type == 0x0108000A:
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                return cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_GR2BGR)
        
        # Bayer BG8
        elif pixel_type == 0x0108000B:
            expected_size = width * height
            if len(image_array) >= expected_size:
                bayer_image = image_array[:expected_size].reshape((height, width))
                return cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_BG2BGR)
        
        # 未知格式 - 嘗試作為Mono8處理
        else:
            print(f"未知像素格式 0x{pixel_type:08X}，嘗試作為Mono8處理")
            expected_size = width * height
            if len(image_array) >= expected_size:
                mono_image = image_array[:expected_size].reshape((height, width))
                return cv2.cvtColor(mono_image, cv2.COLOR_GRAY2BGR)
        
        print(f"無法處理像素格式 0x{pixel_type:08X}")
        return None
        
    except Exception as e:
        print(f"像素轉換錯誤: {str(e)}")
        return None

def direct_grab_thread():
    """
    直接使用SDK的擷取線程
    """
    global latest_frame, stream_running
    
    frame_count = 0
    success_count = 0
    error_count = 0
    
    print("直接SDK擷取線程啟動")
    
    while stream_running:
        try:
            # 直接獲取圖像
            bgr_image = get_image_direct()
            
            if bgr_image is not None:
                error_count = 0
                success_count += 1
                
                # 調整圖像大小以提高性能
                if bgr_image.shape[1] > 1920:
                    scale = 1920.0 / bgr_image.shape[1]
                    new_width = int(bgr_image.shape[1] * scale)
                    new_height = int(bgr_image.shape[0] * scale)
                    bgr_image = cv2.resize(bgr_image, (new_width, new_height))
                
                # 編碼為JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                ret, jpeg = cv2.imencode('.jpg', bgr_image, encode_param)
                
                if ret:
                    jpeg_bytes = jpeg.tobytes()
                    
                    # 更新全域變數
                    with frame_lock:
                        latest_frame = jpeg_bytes
                    
                    frame_count += 1
                    
                    # 每50幀輸出一次統計
                    if frame_count % 50 == 0:
                        success_rate = success_count / (success_count + error_count) * 100
                        print(f"直接SDK統計: 幀數={frame_count}, 成功率={success_rate:.1f}%")
                        success_count = 0
                        error_count = 0
            else:
                error_count += 1
                
                # 控制錯誤輸出頻率
                if error_count > 0 and error_count % 100 == 0:
                    print(f"直接SDK獲取失敗計數: {error_count}")
            
            # 控制幀率
            time.sleep(0.033)  # 約30fps
            
        except Exception as e:
            print(f"直接SDK擷取異常: {str(e)}")
            error_count += 1
            time.sleep(0.1)
    
    print("直接SDK擷取線程結束")

def generate_mjpeg():
    """生成MJPEG串流"""
    global latest_frame, stream_running
    
    no_frame_count = 0
    
    while stream_running:
        try:
            with frame_lock:
                frame = latest_frame
            
            if frame:
                no_frame_count = 0
                # 輸出MJPEG幀
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + 
                       frame + b"\r\n")
            else:
                no_frame_count += 1
                if no_frame_count > 50:  # 5秒沒圖像顯示等待
                    # 創建等待圖像
                    waiting_img = create_waiting_image()
                    if waiting_img:
                        yield (b"--frame\r\n"
                               b"Content-Type: image/jpeg\r\n"
                               b"Content-Length: " + str(len(waiting_img)).encode() + b"\r\n\r\n" + 
                               waiting_img + b"\r\n")
                    no_frame_count = 0
                
                time.sleep(0.1)
                
        except GeneratorExit:
            break
        except Exception as e:
            print(f"MJPEG生成錯誤: {str(e)}")
            time.sleep(0.1)

def create_waiting_image():
    """創建等待圖像"""
    try:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "Direct SDK Loading...", (180, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        ret, jpeg = cv2.imencode('.jpg', img)
        if ret:
            return jpeg.tobytes()
    except:
        pass
    return None

# ========== Flask路由 ==========

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/devices", methods=["GET"])
def list_devices():
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
        
        return jsonify({"success": True, "devices": dev_list, "count": len(dev_list)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "devices": [], "count": 0})

@app.route("/connect", methods=["POST"])
def connect_camera():
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
    global stream_running, stream_thread
    
    try:
        if stream_running:
            stream_running = False
            if stream_thread and stream_thread.is_alive():
                stream_thread.join(timeout=3.0)
        
        if camera_api.is_streaming():
            camera_api.stop_streaming()
        
        camera_api.disconnect()
        return jsonify({"success": True})
        
    except Exception as e:
        if "thread" in str(e).lower():
            return jsonify({"success": True})
        return jsonify({"success": False, "error": str(e)})

@app.route("/status", methods=["GET"])
def get_status():
    try:
        status = camera_api.get_status()
        is_connected = camera_api.is_connected()
        is_streaming = camera_api.is_streaming()
        current_mode = camera_api.get_mode()
        
        params = None
        if is_connected:
            params = camera_api.get_parameters()
        
        return jsonify({
            "success": True,
            "status": status.value,
            "is_connected": is_connected,
            "is_streaming": is_streaming,
            "mode": current_mode.value,
            "parameters": params.to_dict() if params else None
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/start_stream", methods=["POST"])
def start_stream():
    global stream_thread, stream_running, latest_frame
    
    try:
        if not camera_api.is_connected():
            return jsonify({"success": False, "error": "相機未連接"})
        
        if stream_running:
            return jsonify({"success": False, "error": "已在串流中"})
        
        print("啟動直接SDK串流...")
        
        # 清理之前的線程
        if stream_thread and stream_thread.is_alive():
            stream_running = False
            stream_thread.join(timeout=2.0)
        
        # 清空緩衝
        with frame_lock:
            latest_frame = None
        
        # 啟動相機串流
        if not camera_api.start_streaming():
            return jsonify({"success": False, "error": "啟動相機串流失敗"})
        
        # 短暫等待
        time.sleep(1.0)
        
        # 啟動直接SDK線程
        stream_running = True
        stream_thread = threading.Thread(target=direct_grab_thread, daemon=True, name="DirectSDKThread")
        stream_thread.start()
        
        print("直接SDK串流啟動成功")
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"啟動串流錯誤: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/stop_stream", methods=["POST"])
def stop_stream():
    global stream_running, stream_thread, latest_frame
    
    try:
        print("停止直接SDK串流...")
        
        stream_running = False
        if stream_thread and stream_thread.is_alive():
            stream_thread.join(timeout=3.0)
        
        with frame_lock:
            latest_frame = None
        
        if camera_api.is_streaming():
            camera_api.stop_streaming()
        
        print("直接SDK串流已停止")
        return jsonify({"success": True})
        
    except Exception as e:
        if "thread" not in str(e).lower():
            print(f"停止串流錯誤: {str(e)}")
        return jsonify({"success": True})

@app.route("/video_feed")
def video_feed():
    """MJPEG串流端點"""
    return Response(generate_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/snapshot")
def get_snapshot():
    """獲取快照"""
    global latest_frame
    
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

# 其他路由保持不變...
@app.route("/parameters", methods=["GET"])
def get_parameters():
    try:
        params = camera_api.get_parameters()
        if params:
            return jsonify({"success": True, "parameters": params.to_dict()})
        else:
            return jsonify({"success": False, "error": "無法獲取參數"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/parameters", methods=["POST"])
def set_parameters():
    try:
        data = request.get_json()
        params = CameraParameters()
        params.frame_rate = float(data.get("frame_rate", 30.0))
        params.exposure_time = float(data.get("exposure_time", 10000.0))
        params.gain = float(data.get("gain", 0.0))
        
        ok = camera_api.set_parameters(params)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/mode", methods=["POST"])
def set_mode():
    try:
        data = request.get_json()
        mode = data.get("mode", "continuous")
        cam_mode = CameraMode.CONTINUOUS if mode == "continuous" else CameraMode.TRIGGER
        ok = camera_api.set_mode(cam_mode)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/trigger", methods=["POST"])
def software_trigger():
    try:
        ok = camera_api.software_trigger()
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/capture", methods=["POST"])
def capture_image():
    try:
        data = request.get_json()
        format_type = data.get("format", "bmp")
        
        image_format = ImageFormat.BMP if format_type == "bmp" else ImageFormat.JPEG
        ok = camera_api.save_image(image_format)
        
        if ok:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.{format_type}"
            return jsonify({"success": True, "filename": filename})
        else:
            return jsonify({"success": False, "error": "保存圖像失敗"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/packet_size", methods=["POST"])
def optimize_packet_size():
    try:
        ok = camera_api.set_packet_size(0)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    print("啟動直接SDK解決方案...")
    print("請訪問 http://localhost:5000")
    
    app.config['JSON_AS_ASCII'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)