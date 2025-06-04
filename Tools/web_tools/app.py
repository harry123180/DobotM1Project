# -*- coding: utf-8 -*-
"""
Flask Web UI 相機控制系統
基於 Camera_API.py 的 Web 界面實現
"""

from flask import Flask, render_template, Response, request, jsonify
from Camera_API import create_camera_api, CameraMode, ImageFormat, CameraStatus, CameraParameters
import threading
import time
import cv2
import numpy as np
from ctypes import *
import base64
import io
from datetime import datetime

app = Flask(__name__)

# 全域變數
camera_api = create_camera_api()
camera_api.set_error_callback(lambda msg: print(f"[Camera Error] {msg}"))

# 串流相關變數
stream_thread = None
latest_frame = None
stream_running = False
frame_lock = threading.Lock()

# 設備列表快取
cached_devices = []

# ========== 輔助函數 ==========

def get_raw_frame(timeout=1000):
    """
    從相機獲取原始影像
    Returns:
        numpy array: BGR 格式的影像，失敗返回 None
    """
    if not camera_api.is_connected() or not camera_api.is_streaming():
        return None
    
    # 由於原始 API 沒有提供直接獲取 numpy array 的方法
    # 我們需要通過 camera_operation 對象來獲取
    cam_op = camera_api._camera_operation
    if cam_op is None:
        return None
        
    try:
        # 等待新的影像
        max_wait = 10  # 最多等待 10 次
        wait_count = 0
        
        while wait_count < max_wait:
            if hasattr(cam_op, 'buf_save_image') and cam_op.buf_save_image is not None:
                if hasattr(cam_op, 'st_frame_info') and cam_op.st_frame_info is not None:
                    break
            time.sleep(0.1)
            wait_count += 1
        
        if wait_count >= max_wait:
            return None
            
        # 獲取緩衝區鎖
        cam_op.buf_lock.acquire()
        
        try:
            # 獲取影像資訊
            if cam_op.st_frame_info is None:
                return None
                
            width = cam_op.st_frame_info.nWidth
            height = cam_op.st_frame_info.nHeight
            pixel_type = cam_op.st_frame_info.enPixelType
            frame_len = cam_op.st_frame_info.nFrameLen
            
            # 檢查緩衝區是否有效
            if cam_op.buf_save_image is None or frame_len == 0:
                return None
            
            # 複製影像數據
            image_buffer = bytes(cam_op.buf_save_image[:frame_len])
            
            # 轉換為 numpy array
            image = np.frombuffer(image_buffer, dtype=np.uint8)
            
            # 根據像素格式進行轉換
            # 常見的 Hikvision 相機像素格式
            if pixel_type == 0x01080001:  # Mono8
                if len(image) >= width * height:
                    image = image[:width * height].reshape((height, width))
                    # 轉換為 BGR 格式
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                else:
                    return None
            elif pixel_type == 0x01100003:  # Mono10
                # Mono10 需要特殊處理
                if len(image) >= width * height * 2:
                    image = image.view(np.uint16)[:width * height].reshape((height, width))
                    # 轉換為 8 位
                    image = (image >> 2).astype(np.uint8)
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                else:
                    return None
            elif pixel_type == 0x01100005:  # Mono12
                # Mono12 需要特殊處理
                if len(image) >= width * height * 2:
                    image = image.view(np.uint16)[:width * height].reshape((height, width))
                    # 轉換為 8 位
                    image = (image >> 4).astype(np.uint8)
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                else:
                    return None
            elif pixel_type == 0x02180014:  # RGB8 Packed
                if len(image) >= width * height * 3:
                    image = image[:width * height * 3].reshape((height, width, 3))
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                else:
                    return None
            elif pixel_type == 0x02180015:  # BGR8 Packed
                if len(image) >= width * height * 3:
                    image = image[:width * height * 3].reshape((height, width, 3))
                else:
                    return None
            elif pixel_type == 0x01080008:  # BayerRG8
                if len(image) >= width * height:
                    image = image[:width * height].reshape((height, width))
                    image = cv2.cvtColor(image, cv2.COLOR_BAYER_RG2BGR)
                else:
                    return None
            elif pixel_type == 0x01080009:  # BayerGB8
                if len(image) >= width * height:
                    image = image[:width * height].reshape((height, width))
                    image = cv2.cvtColor(image, cv2.COLOR_BAYER_GB2BGR)
                else:
                    return None
            elif pixel_type == 0x0108000A:  # BayerGR8
                if len(image) >= width * height:
                    image = image[:width * height].reshape((height, width))
                    image = cv2.cvtColor(image, cv2.COLOR_BAYER_GR2BGR)
                else:
                    return None
            elif pixel_type == 0x0108000B:  # BayerBG8
                if len(image) >= width * height:
                    image = image[:width * height].reshape((height, width))
                    image = cv2.cvtColor(image, cv2.COLOR_BAYER_BG2BGR)
                else:
                    return None
            else:
                # 未知格式，嘗試當作 Mono8 處理
                print(f"未知的像素格式: 0x{pixel_type:08X}")
                if len(image) >= width * height:
                    image = image[:width * height].reshape((height, width))
                    if len(image.shape) == 2:
                        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                else:
                    return None
            
            return image
            
        finally:
            cam_op.buf_lock.release()
            
    except Exception as e:
        if hasattr(cam_op, 'buf_lock') and cam_op.buf_lock.locked():
            cam_op.buf_lock.release()
        print(f"獲取影像錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return None

def grab_frames():
    """持續擷取影像的線程函數"""
    global latest_frame, stream_running
    
    frame_count = 0
    error_count = 0
    
    # 給相機一些時間來準備
    time.sleep(1.0)
    
    while stream_running:
        try:
            # 獲取原始影像
            raw = get_raw_frame(timeout=100)  # 減少超時時間以提高響應速度
            
            if raw is not None:
                # 重置錯誤計數
                error_count = 0
                
                # 確保影像大小正確
                if raw.shape[0] > 0 and raw.shape[1] > 0:
                    # 如果影像太大，縮小以加快處理速度
                    if raw.shape[1] > 1920:
                        scale = 1920.0 / raw.shape[1]
                        new_width = int(raw.shape[1] * scale)
                        new_height = int(raw.shape[0] * scale)
                        raw = cv2.resize(raw, (new_width, new_height))
                    
                    # 編碼為 JPEG
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
                    ret, jpeg = cv2.imencode('.jpg', raw, encode_param)
                    
                    if ret:
                        jpeg_bytes = jpeg.tobytes()
                        
                        # 存到全域變數
                        with frame_lock:
                            latest_frame = jpeg_bytes
                        
                        frame_count += 1
                        if frame_count % 30 == 0:  # 每30幀輸出一次狀態
                            print(f"已成功處理 {frame_count} 幀")
                else:
                    print("影像大小無效")
            else:
                error_count += 1
                if error_count > 50:  # 增加容忍度
                    print("連續多次無法獲取有效影像")
                    error_count = 0
                    time.sleep(0.5)
            
            # 控制處理速度
            time.sleep(0.01)  # 減少延遲
            
        except Exception as e:
            print(f"擷取影像異常: {str(e)}")
            import traceback
            traceback.print_exc()
            time.sleep(0.1)
    
    print("影像擷取線程已結束")

def generate_mjpeg():
    """生成 MJPEG 串流"""
    global latest_frame, stream_running
    
    no_frame_count = 0
    
    while stream_running:
        with frame_lock:
            frame = latest_frame
        
        if frame:
            no_frame_count = 0
            # MJPEG 格式
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        else:
            no_frame_count += 1
            if no_frame_count > 100:  # 超過100次沒有影像
                # 發送一個黑色影像作為佔位符
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                ret, jpeg = cv2.imencode('.jpg', black_frame)
                if ret:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
            
            time.sleep(0.01)

# ========== Flask 路由 ==========

@app.route("/")
def index():
    """主頁面"""
    return render_template("index.html")

@app.route("/devices", methods=["GET"])
def list_devices():
    """列出所有設備"""
    global cached_devices
    
    try:
        devices = camera_api.enumerate_devices()
        cached_devices = devices
        
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
        
        # 先斷開現有連接
        if camera_api.is_connected():
            camera_api.disconnect()
            time.sleep(0.5)
        
        ok = camera_api.connect(idx)
        
        if ok:
            # 獲取設備資訊
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
    """斷開相機連接"""
    global stream_running, stream_thread
    
    try:
        # 如果正在串流，先停止串流
        if stream_running or camera_api.is_streaming():
            print("正在串流中，先停止串流...")
            
            # 停止擷取線程
            stream_running = False
            if stream_thread and stream_thread.is_alive():
                stream_thread.join(timeout=2.0)
            
            # 停止相機串流
            try:
                camera_api.stop_streaming()
            except:
                pass  # 忽略停止串流時的錯誤
            
            # 等待一下確保串流完全停止
            time.sleep(0.5)
        
        # 斷開連接
        ok = camera_api.disconnect()
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
        
        # 獲取當前參數
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
        
        return jsonify({"success": ok})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/start_stream", methods=["POST"])
def start_stream():
    """開始串流"""
    global stream_thread, stream_running, latest_frame
    
    try:
        if not camera_api.is_connected():
            return jsonify({"success": False, "error": "相機未連接"})
        
        # 檢查是否已經在串流
        if camera_api.is_streaming() or stream_running:
            return jsonify({"success": False, "error": "相機已經在串流中"})
        
        # 確保之前的狀態已經清理
        if hasattr(camera_api, '_camera_operation') and camera_api._camera_operation:
            cam_op = camera_api._camera_operation
            # 重置狀態標誌
            cam_op.b_exit = False
            if hasattr(cam_op, 'thread_running'):
                cam_op.thread_running = False
            
            # 如果有殘留的線程，等待它結束
            if hasattr(cam_op, 'work_thread') and cam_op.work_thread and cam_op.work_thread.is_alive():
                print("等待之前的工作線程結束...")
                cam_op.work_thread.join(timeout=2.0)
        
        # 開始相機串流
        ok = camera_api.start_streaming()
        if not ok:
            return jsonify({"success": False, "error": "啟動串流失敗"})
        
        # 等待相機準備就緒
        time.sleep(0.5)
        
        # 嘗試獲取相機操作對象的像素格式資訊
        cam_op = camera_api._camera_operation
        if cam_op and hasattr(cam_op, 'st_frame_info') and cam_op.st_frame_info:
            pixel_type = cam_op.st_frame_info.enPixelType
            print(f"相機像素格式: 0x{pixel_type:08X}")
            print(f"影像大小: {cam_op.st_frame_info.nWidth} x {cam_op.st_frame_info.nHeight}")
        
        # 清空之前的影像
        with frame_lock:
            latest_frame = None
        
        # 啟動擷取線程
        stream_running = True
        stream_thread = threading.Thread(target=grab_frames, daemon=True)
        stream_thread.start()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"啟動串流錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

@app.route("/stop_stream", methods=["POST"])
def stop_stream():
    """停止串流"""
    global stream_running, stream_thread
    
    try:
        # 停止擷取線程
        stream_running = False
        if stream_thread and stream_thread.is_alive():
            stream_thread.join(timeout=2.0)
        
        # 停止相機串流 - 忽略線程相關錯誤
        try:
            camera_api.stop_streaming()
        except Exception as e:
            # 如果是線程相關錯誤，忽略它
            error_msg = str(e).lower()
            if "thread" in error_msg or "invalid thread id" in error_msg:
                print("忽略線程錯誤，串流已停止")
            else:
                # 其他錯誤還是要報告
                raise e
        
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/trigger", methods=["POST"])
def software_trigger():
    """軟觸發"""
    try:
        ok = camera_api.software_trigger()
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/capture", methods=["POST"])
def capture_image():
    """拍照保存"""
    try:
        data = request.get_json()
        format_type = data.get("format", "bmp")
        
        image_format = ImageFormat.BMP if format_type == "bmp" else ImageFormat.JPEG
        ok = camera_api.save_image(image_format)
        
        if ok:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.{format_type}"
            return jsonify({
                "success": True,
                "filename": filename
            })
        else:
            return jsonify({"success": False, "error": "保存圖像失敗"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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
    global latest_frame
    
    try:
        with frame_lock:
            frame = latest_frame
        
        if frame:
            # 轉換為 base64
            base64_image = base64.b64encode(frame).decode('utf-8')
            return jsonify({
                "success": True,
                "image": f"data:image/jpeg;base64,{base64_image}"
            })
        else:
            return jsonify({"success": False, "error": "無可用影像"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/packet_size", methods=["POST"])
def optimize_packet_size():
    """優化網路包大小"""
    try:
        ok = camera_api.set_packet_size(0)  # 0 表示自動優化
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
    
    # 設置 Flask 配置
    app.config['JSON_AS_ASCII'] = False  # 支援中文
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    # 啟動 Flask
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)