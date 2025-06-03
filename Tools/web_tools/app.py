# -*- coding: utf-8 -*-
"""
改進的Flask Web相機控制應用程式
更好地整合camera_manager.py和原始SDK功能
"""

import os
import sys
import json
import base64
import threading
import time
import numpy as np
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, send_file
from flask_cors import CORS
import cv2
from ctypes import *

# 導入相機相關模組
from camera_manager import CameraManager
from MvCameraControl_class import *
from CameraParams_header import *
from MvErrorDefine_const import *

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hikvision-camera-secret'
CORS(app)

# 全域變數
camera_manager = None
streaming_thread = None
is_streaming = False
frame_buffer = None
frame_lock = threading.Lock()
trigger_count = 0
save_count = 0
current_mode = "continuous"
frame_info = None

# 初始化相機管理器
def init_camera():
    global camera_manager
    try:
        camera_manager = CameraManager()
        return True
    except Exception as e:
        print(f"初始化相機失敗: {str(e)}")
        return False

# 影像串流生成器
def generate_frames():
    """生成MJPEG串流"""
    global frame_buffer, frame_info
    
    while is_streaming:
        try:
            if camera_manager and camera_manager.connected:
                # 根據模式獲取影像
                if current_mode == "continuous":
                    # 連續模式：使用GetOneFrameTimeout
                    stFrameInfo = MV_FRAME_OUT_INFO_EX()
                    memset(byref(stFrameInfo), 0, sizeof(stFrameInfo))
                    
                    # 計算緩衝區大小
                    nPayloadSize = camera_manager.cam.MV_CC_GetIntValue("PayloadSize")
                    if nPayloadSize is None:
                        nPayloadSize = 2592 * 1944 * 3  # 預設值
                    
                    pData = (c_ubyte * nPayloadSize)()
                    
                    ret = camera_manager.cam.MV_CC_GetOneFrameTimeout(
                        pData, nPayloadSize, byref(stFrameInfo), 1000
                    )
                    
                    if ret == 0:
                        # 成功獲取影像
                        image = np.frombuffer(pData, dtype=np.uint8, count=stFrameInfo.nFrameLen)
                        
                        # 根據像素格式處理影像
                        if stFrameInfo.enPixelType == PixelType_Gvsp_Mono8:
                            image = image.reshape((stFrameInfo.nHeight, stFrameInfo.nWidth))
                            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
                        elif stFrameInfo.enPixelType == PixelType_Gvsp_RGB8_Packed:
                            image = image.reshape((stFrameInfo.nHeight, stFrameInfo.nWidth, 3))
                        else:
                            # 需要轉換格式
                            image = convert_pixel_format(pData, stFrameInfo)
                        
                        # 更新影像緩衝區
                        with frame_lock:
                            frame_buffer = image.copy()
                            frame_info = {
                                'width': stFrameInfo.nWidth,
                                'height': stFrameInfo.nHeight,
                                'frame_num': stFrameInfo.nFrameNum,
                                'timestamp': time.time()
                            }
                else:
                    # 觸發模式：等待觸發
                    time.sleep(0.1)
                
                # 生成JPEG串流
                if frame_buffer is not None:
                    with frame_lock:
                        ret, buffer = cv2.imencode('.jpg', frame_buffer, 
                                                 [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ret:
                            frame = buffer.tobytes()
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            
            time.sleep(0.01)  # 控制CPU使用率
            
        except Exception as e:
            print(f"串流錯誤: {str(e)}")
            time.sleep(0.1)

def convert_pixel_format(pData, stFrameInfo):
    """轉換像素格式為RGB"""
    try:
        # 創建轉換參數
        stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
        memset(byref(stConvertParam), 0, sizeof(stConvertParam))
        
        stConvertParam.nWidth = stFrameInfo.nWidth
        stConvertParam.nHeight = stFrameInfo.nHeight
        stConvertParam.enSrcPixelType = stFrameInfo.enPixelType
        stConvertParam.pSrcData = pData
        stConvertParam.nSrcDataLen = stFrameInfo.nFrameLen
        stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
        stConvertParam.nDstBufferSize = stFrameInfo.nWidth * stFrameInfo.nHeight * 3
        stConvertParam.pDstBuffer = (c_ubyte * stConvertParam.nDstBufferSize)()
        
        ret = camera_manager.cam.MV_CC_ConvertPixelType(stConvertParam)
        if ret == 0:
            image = np.frombuffer(stConvertParam.pDstBuffer, dtype=np.uint8)
            image = image.reshape((stFrameInfo.nHeight, stFrameInfo.nWidth, 3))
            return image
        else:
            # 轉換失敗，返回灰度圖
            image = np.frombuffer(pData, dtype=np.uint8, count=stFrameInfo.nFrameLen)
            image = image.reshape((stFrameInfo.nHeight, stFrameInfo.nWidth))
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            
    except Exception as e:
        print(f"像素格式轉換錯誤: {str(e)}")
        return None

# 路由定義
@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """影像串流端點"""
    if is_streaming:
        return Response(generate_frames(),
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return '', 204

# API端點
@app.route('/api/enumerate_devices', methods=['GET'])
def enumerate_devices():
    """枚舉設備"""
    try:
        devices = camera_manager.enum_devices()
        device_list = []
        
        for idx, ip in devices:
            device_info = {
                'index': idx,
                'name': f'相機 {idx}',
                'ip': ip,
                'type': 'GigE'
            }
            
            # 獲取更詳細的設備資訊
            if idx < camera_manager.device_list.nDeviceNum:
                pDeviceInfo = cast(camera_manager.device_list.pDeviceInfo[idx], 
                                 POINTER(MV_CC_DEVICE_INFO))
                stDeviceInfo = pDeviceInfo.contents
                
                if stDeviceInfo.nTLayerType == MV_GIGE_DEVICE:
                    device_info['model'] = stDeviceInfo.SpecialInfo.stGigEInfo.chModelName.decode('ascii', 'ignore')
                    device_info['serial'] = stDeviceInfo.SpecialInfo.stGigEInfo.chSerialNumber.decode('ascii', 'ignore')
            
            device_list.append(device_info)
        
        return jsonify({'success': True, 'devices': device_list})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/connect', methods=['POST'])
def connect_device():
    """連接設備"""
    global current_mode
    try:
        data = request.json
        device_index = data.get('device_index', 0)
        
        # 連接設備
        camera_manager.connect(device_index)
        
        # 設置最佳包大小（對GigE相機）
        optimal_size = camera_manager.cam.MV_CC_GetOptimalPacketSize()
        if optimal_size > 0:
            camera_manager.cam.MV_CC_SetIntValue("GevSCPSPacketSize", optimal_size)
        
        # 設置觸發模式為關閉（預設連續模式）
        camera_manager.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        current_mode = "continuous"
        
        # 開始取流
        ret = camera_manager.cam.MV_CC_StartGrabbing()
        if ret != 0:
            raise Exception(f"開始取流失敗: 0x{ret:08x}")
        
        return jsonify({
            'success': True, 
            'message': f'成功連接到設備 {device_index}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/disconnect', methods=['POST'])
def disconnect_device():
    """斷開設備"""
    global is_streaming
    try:
        if is_streaming:
            stop_streaming_internal()
        
        # 停止取流
        if camera_manager.cam:
            camera_manager.cam.MV_CC_StopGrabbing()
        
        camera_manager.close()
        return jsonify({'success': True, 'message': '設備已斷開'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_parameters', methods=['GET'])
def get_parameters():
    """獲取參數"""
    try:
        if not camera_manager.connected:
            return jsonify({'success': False, 'error': '設備未連接'})
        
        # 獲取參數
        stFloatValue = MVCC_FLOATVALUE()
        
        # 曝光時間
        memset(byref(stFloatValue), 0, sizeof(MVCC_FLOATVALUE))
        ret = camera_manager.cam.MV_CC_GetFloatValue("ExposureTime", stFloatValue)
        exposure_time = stFloatValue.fCurValue if ret == 0 else 10000
        
        # 增益
        memset(byref(stFloatValue), 0, sizeof(MVCC_FLOATVALUE))
        ret = camera_manager.cam.MV_CC_GetFloatValue("Gain", stFloatValue)
        gain = stFloatValue.fCurValue if ret == 0 else 0
        
        # 幀率
        memset(byref(stFloatValue), 0, sizeof(MVCC_FLOATVALUE))
        ret = camera_manager.cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stFloatValue)
        frame_rate = stFloatValue.fCurValue if ret == 0 else 30
        
        return jsonify({
            'success': True,
            'parameters': {
                'exposure_time': exposure_time,
                'gain': gain,
                'frame_rate': frame_rate
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/set_parameters', methods=['POST'])
def set_parameters():
    """設置參數"""
    try:
        if not camera_manager.connected:
            return jsonify({'success': False, 'error': '設備未連接'})
        
        data = request.json
        
        # 關閉自動曝光
        camera_manager.cam.MV_CC_SetEnumValue("ExposureAuto", 0)
        
        # 設置參數
        if 'exposure_time' in data:
            ret = camera_manager.cam.MV_CC_SetFloatValue("ExposureTime", float(data['exposure_time']))
            if ret != 0:
                print(f"設置曝光時間失敗: 0x{ret:08x}")
        
        if 'gain' in data:
            ret = camera_manager.cam.MV_CC_SetFloatValue("Gain", float(data['gain']))
            if ret != 0:
                print(f"設置增益失敗: 0x{ret:08x}")
        
        if 'frame_rate' in data:
            ret = camera_manager.cam.MV_CC_SetFloatValue("AcquisitionFrameRate", float(data['frame_rate']))
            if ret != 0:
                print(f"設置幀率失敗: 0x{ret:08x}")
        
        return jsonify({'success': True, 'message': '參數設置成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/set_mode', methods=['POST'])
def set_mode():
    """設置工作模式"""
    global current_mode
    try:
        if not camera_manager.connected:
            return jsonify({'success': False, 'error': '設備未連接'})
        
        data = request.json
        mode = data.get('mode', 'continuous')
        
        if mode == 'trigger':
            # 設置為觸發模式
            ret = camera_manager.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
            if ret != 0:
                raise Exception(f"設置觸發模式失敗: 0x{ret:08x}")
            
            # 設置軟觸發源
            ret = camera_manager.cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_SOFTWARE)
            if ret != 0:
                raise Exception(f"設置觸發源失敗: 0x{ret:08x}")
            
            current_mode = 'trigger'
            mode_text = '觸發模式'
        else:
            # 設置為連續模式
            ret = camera_manager.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            if ret != 0:
                raise Exception(f"設置連續模式失敗: 0x{ret:08x}")
            
            current_mode = 'continuous'
            mode_text = '連續模式'
        
        return jsonify({'success': True, 'message': f'已切換到{mode_text}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/start_streaming', methods=['POST'])
def start_streaming():
    """開始串流"""
    global is_streaming
    try:
        if not camera_manager.connected:
            return jsonify({'success': False, 'error': '設備未連接'})
        
        if not is_streaming:
            is_streaming = True
        
        return jsonify({'success': True, 'message': '串流已啟動'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop_streaming', methods=['POST'])
def stop_streaming():
    """停止串流"""
    global is_streaming
    try:
        is_streaming = False
        return jsonify({'success': True, 'message': '串流已停止'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def stop_streaming_internal():
    """內部停止串流函數"""
    global is_streaming
    is_streaming = False

@app.route('/api/software_trigger', methods=['POST'])
def software_trigger():
    """軟觸發"""
    global trigger_count, frame_buffer, frame_info
    try:
        if not camera_manager.connected:
            return jsonify({'success': False, 'error': '設備未連接'})
        
        if current_mode != 'trigger':
            return jsonify({'success': False, 'error': '請先切換到觸發模式'})
        
        # 執行軟觸發
        ret = camera_manager.cam.MV_CC_SetCommandValue("TriggerSoftware")
        if ret != 0:
            raise Exception(f"軟觸發失敗: 0x{ret:08x}")
        
        # 等待並獲取觸發的影像
        time.sleep(0.1)  # 短暫等待
        
        # 獲取觸發後的影像
        stFrameInfo = MV_FRAME_OUT_INFO_EX()
        memset(byref(stFrameInfo), 0, sizeof(stFrameInfo))
        
        nPayloadSize = camera_manager.cam.MV_CC_GetIntValue("PayloadSize")
        if nPayloadSize is None:
            nPayloadSize = 2592 * 1944 * 3
        
        pData = (c_ubyte * nPayloadSize)()
        
        ret = camera_manager.cam.MV_CC_GetOneFrameTimeout(pData, nPayloadSize, byref(stFrameInfo), 1000)
        
        if ret == 0:
            # 處理影像
            image = np.frombuffer(pData, dtype=np.uint8, count=stFrameInfo.nFrameLen)
            
            if stFrameInfo.enPixelType == PixelType_Gvsp_Mono8:
                image = image.reshape((stFrameInfo.nHeight, stFrameInfo.nWidth))
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                image = convert_pixel_format(pData, stFrameInfo)
            
            # 更新全域影像緩衝區
            with frame_lock:
                frame_buffer = image.copy()
                frame_info = {
                    'width': stFrameInfo.nWidth,
                    'height': stFrameInfo.nHeight,
                    'frame_num': stFrameInfo.nFrameNum,
                    'timestamp': time.time()
                }
        
        trigger_count += 1
        
        return jsonify({
            'success': True, 
            'message': '觸發成功',
            'trigger_count': trigger_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save_image', methods=['POST'])
def save_image():
    """保存圖像"""
    global save_count, frame_buffer
    try:
        if frame_buffer is None:
            return jsonify({'success': False, 'error': '無可用影像'})
        
        data = request.json
        format_type = data.get('format', 'bmp')
        
        # 生成檔案名稱
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'capture_{timestamp}_{save_count}.{format_type}'
        filepath = os.path.join('captures', filename)
        
        # 確保目錄存在
        os.makedirs('captures', exist_ok=True)
        
        # 保存影像
        with frame_lock:
            if format_type == 'jpeg':
                cv2.imwrite(filepath, frame_buffer, [cv2.IMWRITE_JPEG_QUALITY, 95])
            else:  # BMP
                cv2.imwrite(filepath, frame_buffer)
        
        save_count += 1
        
        return jsonify({
            'success': True,
            'message': f'影像已保存: {filename}',
            'save_count': save_count,
            'filepath': filepath
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_status', methods=['GET'])
def get_status():
    """獲取系統狀態"""
    try:
        status = {
            'connected': camera_manager.connected if camera_manager else False,
            'streaming': is_streaming,
            'mode': current_mode,
            'trigger_count': trigger_count,
            'save_count': save_count
        }
        
        # 如果有影像資訊，加入狀態
        if frame_info:
            status['frame_info'] = frame_info
        
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_device_info', methods=['GET'])
def get_device_info():
    """獲取設備詳細資訊"""
    try:
        if not camera_manager.connected:
            return jsonify({'success': False, 'error': '設備未連接'})
        
        # 獲取設備資訊
        stDeviceInfo = MV_CC_DEVICE_INFO()
        ret = camera_manager.cam.MV_CC_GetDeviceInfo(stDeviceInfo)
        
        info = {
            'connected': True,
            'type': 'Unknown'
        }
        
        if ret == 0:
            if stDeviceInfo.nTLayerType == MV_GIGE_DEVICE:
                gige_info = stDeviceInfo.SpecialInfo.stGigEInfo
                info.update({
                    'type': 'GigE',
                    'model': gige_info.chModelName.decode('ascii', 'ignore'),
                    'serial': gige_info.chSerialNumber.decode('ascii', 'ignore'),
                    'manufacturer': gige_info.chManufacturerName.decode('ascii', 'ignore'),
                    'version': gige_info.chDeviceVersion.decode('ascii', 'ignore'),
                    'user_name': gige_info.chUserDefinedName.decode('ascii', 'ignore')
                })
            elif stDeviceInfo.nTLayerType == MV_USB_DEVICE:
                usb_info = stDeviceInfo.SpecialInfo.stUsb3VInfo
                info.update({
                    'type': 'USB3',
                    'model': usb_info.chModelName.decode('ascii', 'ignore'),
                    'serial': usb_info.chSerialNumber.decode('ascii', 'ignore'),
                    'manufacturer': usb_info.chManufacturerName.decode('ascii', 'ignore'),
                    'version': usb_info.chDeviceVersion.decode('ascii', 'ignore'),
                    'user_name': usb_info.chUserDefinedName.decode('ascii', 'ignore')
                })
        
        return jsonify({'success': True, 'device_info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/optimize_packet_size', methods=['POST'])
def optimize_packet_size():
    """優化網路包大小（GigE相機）"""
    try:
        if not camera_manager.connected:
            return jsonify({'success': False, 'error': '設備未連接'})
        
        # 獲取最佳包大小
        optimal_size = camera_manager.cam.MV_CC_GetOptimalPacketSize()
        if optimal_size > 0:
            ret = camera_manager.cam.MV_CC_SetIntValue("GevSCPSPacketSize", optimal_size)
            if ret == 0:
                return jsonify({
                    'success': True, 
                    'message': f'包大小已優化為 {optimal_size} bytes'
                })
            else:
                raise Exception(f"設置包大小失敗: 0x{ret:08x}")
        else:
            return jsonify({'success': False, 'error': '無法獲取最佳包大小'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_connection', methods=['POST'])
def reset_connection():
    """重置連接"""
    global is_streaming, frame_buffer, trigger_count, save_count
    try:
        # 記錄當前設備索引
        current_device = request.json.get('device_index', 0) if request.json else 0
        
        # 停止串流
        if is_streaming:
            stop_streaming_internal()
        
        # 斷開連接
        if camera_manager.cam:
            camera_manager.cam.MV_CC_StopGrabbing()
        camera_manager.close()
        
        # 重置狀態
        frame_buffer = None
        trigger_count = 0
        save_count = 0
        
        # 等待一下
        time.sleep(1)
        
        # 重新連接
        camera_manager.connect(current_device)
        
        # 重新設置參數
        optimal_size = camera_manager.cam.MV_CC_GetOptimalPacketSize()
        if optimal_size > 0:
            camera_manager.cam.MV_CC_SetIntValue("GevSCPSPacketSize", optimal_size)
        
        # 開始取流
        ret = camera_manager.cam.MV_CC_StartGrabbing()
        if ret != 0:
            raise Exception(f"開始取流失敗: 0x{ret:08x}")
        
        return jsonify({'success': True, 'message': '連接已重置'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download_image/<filename>')
def download_image(filename):
    """下載保存的影像"""
    try:
        filepath = os.path.join('captures', filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'success': False, 'error': '檔案不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 錯誤處理
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': '找不到請求的資源'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': '伺服器內部錯誤'}), 500

# 清理函數
def cleanup():
    """清理資源"""
    global is_streaming
    try:
        is_streaming = False
        if camera_manager:
            if camera_manager.cam:
                camera_manager.cam.MV_CC_StopGrabbing()
            camera_manager.close()
    except:
        pass

# 主程式
if __name__ == '__main__':
    # 初始化相機
    if not init_camera():
        print("警告: 相機初始化失敗，部分功能可能無法使用")
    
    # 註冊清理函數
    import atexit
    atexit.register(cleanup)
    
    # 創建captures目錄
    os.makedirs('captures', exist_ok=True)
    
    # 啟動Flask應用
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        cleanup()
        print("\n應用程式已關閉")