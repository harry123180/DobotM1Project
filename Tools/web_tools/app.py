from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO, emit
import threading
import time
import base64
import io
import os
from datetime import datetime
import json

# 導入相機相關模塊
from MvCameraControl_class import *
from MvErrorDefine_const import *
from CameraParams_header import *
from CamOperation_class import CameraOperation
import ctypes
import cv2
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'camera_control_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局變量
device_list = None
cam = None
obj_cam_operation = None
is_open = False
is_grabbing = False
selected_camera_index = 0
streaming_thread = None
stop_streaming = False

# 初始化SDK
MvCamera.MV_CC_Initialize()

def to_hex_str(num):
    """將錯誤碼轉換為十六進制字符串"""
    cha_dic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hex_str = ""
    if num < 0:
        num = num + 2 ** 32
    while num >= 16:
        digit = num % 16
        hex_str = cha_dic.get(digit, str(digit)) + hex_str
        num //= 16
    hex_str = cha_dic.get(num, str(num)) + hex_str
    return "0x" + hex_str

def decoding_char(c_ubyte_value):
    """解碼字符"""
    c_char_p_value = ctypes.cast(c_ubyte_value, ctypes.c_char_p)
    try:
        decode_str = c_char_p_value.value.decode('gbk')
    except UnicodeDecodeError:
        decode_str = str(c_char_p_value.value)
    return decode_str

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/enumerate_devices', methods=['GET'])
def enumerate_devices():
    """枚舉相機設備"""
    global device_list
    
    try:
        device_list = MV_CC_DEVICE_INFO_LIST()
        n_layer_type = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                       | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
        ret = MvCamera.MV_CC_EnumDevices(n_layer_type, device_list)
        
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'枚舉設備失敗: {to_hex_str(ret)}'
            })
        
        if device_list.nDeviceNum == 0:
            return jsonify({
                'success': True,
                'devices': [],
                'message': '未找到設備'
            })
        
        devices = []
        for i in range(device_list.nDeviceNum):
            mvcc_dev_info = cast(device_list.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            
            device_info = {
                'index': i,
                'type': '',
                'name': '',
                'model': '',
                'serial': '',
                'ip': ''
            }
            
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE:
                device_info['type'] = 'GigE'
                device_info['name'] = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName)
                device_info['model'] = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
                
                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                device_info['ip'] = f"{nip1}.{nip2}.{nip3}.{nip4}"
                
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                device_info['type'] = 'USB'
                device_info['name'] = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName)
                device_info['model'] = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName)
                
                serial_number = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    serial_number += chr(per)
                device_info['serial'] = serial_number
            
            devices.append(device_info)
        
        return jsonify({
            'success': True,
            'devices': devices
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'枚舉設備異常: {str(e)}'
        })

@app.route('/api/open_device', methods=['POST'])
def open_device():
    """打開相機設備"""
    global cam, obj_cam_operation, is_open, selected_camera_index
    
    try:
        data = request.get_json()
        camera_index = data.get('camera_index', 0)
        
        if is_open:
            return jsonify({
                'success': False,
                'error': '相機已經打開'
            })
        
        if device_list is None or camera_index >= device_list.nDeviceNum:
            return jsonify({
                'success': False,
                'error': '無效的相機索引'
            })
        
        selected_camera_index = camera_index
        cam = MvCamera()
        obj_cam_operation = CameraOperation(cam, device_list, camera_index)
        
        ret = obj_cam_operation.Open_device()
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'打開設備失敗: {to_hex_str(ret)}'
            })
        
        # 設置為連續模式
        obj_cam_operation.Set_trigger_mode(False)
        
        is_open = True
        
        return jsonify({
            'success': True,
            'message': '設備打開成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'打開設備異常: {str(e)}'
        })

@app.route('/api/close_device', methods=['POST'])
def close_device():
    """關閉相機設備"""
    global is_open, is_grabbing, obj_cam_operation, stop_streaming
    
    try:
        if not is_open:
            return jsonify({
                'success': False,
                'error': '設備未打開'
            })
        
        # 停止串流
        if is_grabbing:
            stop_streaming = True
            obj_cam_operation.Stop_grabbing()
            is_grabbing = False
        
        # 關閉設備
        obj_cam_operation.Close_device()
        is_open = False
        
        return jsonify({
            'success': True,
            'message': '設備關閉成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'關閉設備異常: {str(e)}'
        })

@app.route('/api/start_grabbing', methods=['POST'])
def start_grabbing():
    """開始圖像採集"""
    global is_grabbing, streaming_thread, stop_streaming
    
    try:
        if not is_open:
            return jsonify({
                'success': False,
                'error': '設備未打開'
            })
        
        if is_grabbing:
            return jsonify({
                'success': False,
                'error': '已經在採集中'
            })
        
        ret = obj_cam_operation.Start_grabbing()
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'開始採集失敗: {to_hex_str(ret)}'
            })
        
        is_grabbing = True
        stop_streaming = False
        
        # 啟動串流線程
        streaming_thread = threading.Thread(target=streaming_worker)
        streaming_thread.daemon = True
        streaming_thread.start()
        
        return jsonify({
            'success': True,
            'message': '開始採集成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'開始採集異常: {str(e)}'
        })

@app.route('/api/stop_grabbing', methods=['POST'])
def stop_grabbing():
    """停止圖像採集"""
    global is_grabbing, stop_streaming
    
    try:
        if not is_grabbing:
            return jsonify({
                'success': False,
                'error': '未在採集中'
            })
        
        stop_streaming = True
        ret = obj_cam_operation.Stop_grabbing()
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'停止採集失敗: {to_hex_str(ret)}'
            })
        
        is_grabbing = False
        
        return jsonify({
            'success': True,
            'message': '停止採集成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'停止採集異常: {str(e)}'
        })

@app.route('/api/set_trigger_mode', methods=['POST'])
def set_trigger_mode():
    """設置觸發模式"""
    try:
        if not is_open:
            return jsonify({
                'success': False,
                'error': '設備未打開'
            })
        
        data = request.get_json()
        trigger_mode = data.get('trigger_mode', False)
        
        ret = obj_cam_operation.Set_trigger_mode(trigger_mode)
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'設置觸發模式失敗: {to_hex_str(ret)}'
            })
        
        mode_text = "觸發模式" if trigger_mode else "連續模式"
        return jsonify({
            'success': True,
            'message': f'設置為{mode_text}成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'設置觸發模式異常: {str(e)}'
        })

@app.route('/api/software_trigger', methods=['POST'])
def software_trigger():
    """軟觸發一次"""
    try:
        if not is_open:
            return jsonify({
                'success': False,
                'error': '設備未打開'
            })
        
        if not is_grabbing:
            return jsonify({
                'success': False,
                'error': '未在採集中'
            })
        
        ret = obj_cam_operation.Trigger_once()
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'軟觸發失敗: {to_hex_str(ret)}'
            })
        
        return jsonify({
            'success': True,
            'message': '軟觸發成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'軟觸發異常: {str(e)}'
        })

@app.route('/api/save_image', methods=['POST'])
def save_image():
    """保存圖像"""
    try:
        if not is_open or not is_grabbing:
            return jsonify({
                'success': False,
                'error': '設備未打開或未在採集中'
            })
        
        ret = obj_cam_operation.Save_Bmp()
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'保存圖像失敗: {to_hex_str(ret)}'
            })
        
        return jsonify({
            'success': True,
            'message': '圖像保存成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'保存圖像異常: {str(e)}'
        })

@app.route('/api/get_parameters', methods=['GET'])
def get_parameters():
    """獲取相機參數"""
    try:
        if not is_open:
            return jsonify({
                'success': False,
                'error': '設備未打開'
            })
        
        ret = obj_cam_operation.Get_parameter()
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'獲取參數失敗: {to_hex_str(ret)}'
            })
        
        return jsonify({
            'success': True,
            'parameters': {
                'exposure_time': obj_cam_operation.exposure_time,
                'gain': obj_cam_operation.gain,
                'frame_rate': obj_cam_operation.frame_rate
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'獲取參數異常: {str(e)}'
        })

@app.route('/api/set_parameters', methods=['POST'])
def set_parameters():
    """設置相機參數"""
    try:
        if not is_open:
            return jsonify({
                'success': False,
                'error': '設備未打開'
            })
        
        data = request.get_json()
        frame_rate = data.get('frame_rate')
        exposure_time = data.get('exposure_time')
        gain = data.get('gain')
        
        ret = obj_cam_operation.Set_parameter(frame_rate, exposure_time, gain)
        if ret != 0:
            return jsonify({
                'success': False,
                'error': f'設置參數失敗: {to_hex_str(ret)}'
            })
        
        return jsonify({
            'success': True,
            'message': '參數設置成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'設置參數異常: {str(e)}'
        })

@app.route('/api/status', methods=['GET'])
def get_status():
    """獲取系統狀態"""
    return jsonify({
        'is_open': is_open,
        'is_grabbing': is_grabbing,
        'selected_camera': selected_camera_index if is_open else None
    })

def streaming_worker():
    """串流工作線程"""
    global stop_streaming
    
    while not stop_streaming and is_grabbing:
        try:
            # 這裡需要實現圖像獲取和傳輸邏輯
            # 由於原始代碼中沒有直接的圖像數據獲取方法，
            # 這裡提供一個基本框架
            time.sleep(0.033)  # 約30fps
            
            # 發送狀態更新
            socketio.emit('camera_status', {
                'is_streaming': True,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"Streaming error: {e}")
            break

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('camera_status', {
        'is_open': is_open,
        'is_grabbing': is_grabbing
    })

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    try:
        # 確保模板目錄存在
        if not os.path.exists('templates'):
            os.makedirs('templates')
        
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    finally:
        # 清理資源
        if is_open:
            if is_grabbing:
                stop_streaming = True
                obj_cam_operation.Stop_grabbing()
            obj_cam_operation.Close_device()
        MvCamera.MV_CC_Finalize()