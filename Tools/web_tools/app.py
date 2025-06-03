# -*- coding: utf-8 -*-
"""
Camera Web Control - Flask後端伺服器
基於Camera_API.py的Web化相機控制系統
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO, emit
import threading
import time
import json
import os
from datetime import datetime
from typing import Dict, Any, List

# 導入自定義API
from Camera_API import (
    CameraAPI, CameraInfo, CameraMode, ImageFormat, 
    CameraStatus, CameraParameters, create_camera_api
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'camera_control_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

class CameraWebController:
    """相機Web控制器"""
    
    def __init__(self):
        # 初始化相機API
        self.camera_api = create_camera_api()
        self.camera_api.set_error_callback(self.on_error)
        
        # 狀態變數
        self.devices: List[CameraInfo] = []
        self.current_params = CameraParameters()
        self.status_update_thread = None
        self.status_running = False
        self.trigger_count = 0
        self.save_count = 0
        
        # 創建圖像保存目錄
        self.image_save_path = "saved_images"
        if not os.path.exists(self.image_save_path):
            os.makedirs(self.image_save_path)
            
        # 啟動狀態更新線程
        self.start_status_update()
    
    def start_status_update(self):
        """啟動狀態更新線程"""
        self.status_running = True
        self.status_update_thread = threading.Thread(target=self.status_update_loop, daemon=True)
        self.status_update_thread.start()
    
    def status_update_loop(self):
        """狀態更新循環"""
        while self.status_running:
            try:
                # 獲取當前狀態
                status_data = self.get_current_status()
                # 發送狀態更新到前端
                socketio.emit('status_update', status_data)
                time.sleep(1.0)  # 每秒更新一次
            except Exception as e:
                self.log_message(f"狀態更新錯誤: {str(e)}", "error")
                time.sleep(2.0)
    
    def get_current_status(self) -> Dict[str, Any]:
        """獲取當前系統狀態"""
        status = self.camera_api.get_status()
        is_connected = self.camera_api.is_connected()
        is_streaming = self.camera_api.is_streaming()
        current_mode = self.camera_api.get_mode()
        device_info = self.camera_api.get_device_info()
        
        return {
            'connection_status': status.value,
            'is_connected': is_connected,
            'is_streaming': is_streaming,
            'current_mode': current_mode.value,
            'device_info': {
                'name': device_info.device_name if device_info else "無",
                'type': device_info.device_type if device_info else "無",
                'serial': device_info.serial_number if device_info else "",
                'ip': device_info.ip_address if device_info else ""
            } if device_info else None,
            'trigger_count': self.trigger_count,
            'save_count': self.save_count,
            'current_params': {
                'exposure_time': self.current_params.exposure_time,
                'gain': self.current_params.gain,
                'frame_rate': self.current_params.frame_rate,
                'packet_size': self.current_params.packet_size
            }
        }
    
    def log_message(self, message: str, level: str = "info"):
        """發送日誌訊息到前端"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_data = {
            'timestamp': timestamp,
            'message': message,
            'level': level
        }
        socketio.emit('log_message', log_data)
    
    def on_error(self, error_msg: str):
        """錯誤回調函數"""
        self.log_message(error_msg, "error")
        
    def save_image_with_custom_name(self, format_type: ImageFormat) -> tuple:
        """保存圖像並返回文件路徑和狀態"""
        try:
            if not self.camera_api.is_streaming():
                return False, "請先開始串流"
            
            # 生成唯一的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = "bmp" if format_type == ImageFormat.BMP else "jpg"
            filename = f"camera_image_{timestamp}_{self.save_count + 1:04d}.{extension}"
            filepath = os.path.join(self.image_save_path, filename)
            
            # 確保目錄存在
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # 嘗試保存圖像
            success = self.camera_api.save_image(format_type)
            
            if success:
                # 檢查是否有生成的圖像文件需要重命名
                try:
                    # 原始保存的文件名（由Camera_API生成）
                    original_files = []
                    for ext in ['bmp', 'jpg']:
                        for i in range(10):  # 檢查最近的幾個文件
                            original_file = f"{i}.{ext}"
                            if os.path.exists(original_file):
                                original_files.append(original_file)
                    
                    # 如果找到原始文件，重命名它
                    if original_files:
                        latest_file = max(original_files, key=os.path.getctime)
                        if os.path.exists(latest_file):
                            os.rename(latest_file, filepath)
                            return True, filepath
                    
                    # 如果沒有找到原始文件，返回成功但文件路徑可能不正確
                    return True, f"圖像已保存（系統默認路徑）"
                    
                except Exception as rename_error:
                    self.log_message(f"重命名文件錯誤: {str(rename_error)}", "warning")
                    return True, f"圖像已保存（重命名失敗）"
            else:
                return False, "保存圖像失敗"
                
        except Exception as e:
            return False, f"保存圖像錯誤: {str(e)}"

# 创建全局控制器实例
camera_controller = CameraWebController()

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """客戶端連接"""
    camera_controller.log_message("Web客戶端已連接", "info")
    # 發送當前狀態
    emit('status_update', camera_controller.get_current_status())

@socketio.on('disconnect')
def handle_disconnect():
    """客戶端斷開連接"""
    camera_controller.log_message("Web客戶端已斷開", "info")

@socketio.on('refresh_devices')
def handle_refresh_devices():
    """刷新設備列表"""
    try:
        camera_controller.log_message("正在枚舉設備...", "info")
        camera_controller.devices = camera_controller.camera_api.enumerate_devices()
        
        devices_data = []
        for i, device in enumerate(camera_controller.devices):
            devices_data.append({
                'index': i,
                'name': device.device_name,
                'type': device.device_type,
                'serial': device.serial_number,
                'ip': device.ip_address,
                'display_name': str(device)
            })
        
        if devices_data:
            camera_controller.log_message(f"找到 {len(devices_data)} 個設備", "success")
        else:
            camera_controller.log_message("未找到可用設備", "warning")
        
        emit('devices_list', {'devices': devices_data})
        
    except Exception as e:
        camera_controller.log_message(f"枚舉設備失敗: {str(e)}", "error")

@socketio.on('connect_device')
def handle_connect_device(data):
    """连接设备"""
    try:
        device_index = data.get('device_index')
        if device_index is None or device_index < 0:
            camera_controller.log_message("请选择一个设备", "warning")
            return
        
        camera_controller.log_message(f"正在连接设备 {device_index}...", "info")
        
        if camera_controller.camera_api.connect(device_index):
            device = camera_controller.devices[device_index]
            camera_controller.log_message(f"设备连接成功: {device.device_name}", "success")
            
            # 自动获取参数
            params = camera_controller.camera_api.get_parameters()
            if params:
                camera_controller.current_params = params
                emit('parameters_updated', {
                    'exposure_time': params.exposure_time,
                    'gain': params.gain,
                    'frame_rate': params.frame_rate,
                    'packet_size': params.packet_size
                })
        else:
            camera_controller.log_message("设备连接失败", "error")
            
    except Exception as e:
        camera_controller.log_message(f"连接设备错误: {str(e)}", "error")

@socketio.on('disconnect_device')
def handle_disconnect_device():
    """断开设备"""
    try:
        if camera_controller.camera_api.disconnect():
            camera_controller.log_message("设备已断开", "info")
        else:
            camera_controller.log_message("断开设备失败", "error")
    except Exception as e:
        camera_controller.log_message(f"断开设备错误: {str(e)}", "error")

@socketio.on('optimize_packet_size')
def handle_optimize_packet_size():
    """优化网络包大小"""
    try:
        if camera_controller.camera_api.set_packet_size(0):
            camera_controller.log_message("网络包大小已优化", "success")
        else:
            camera_controller.log_message("优化包大小失败", "error")
    except Exception as e:
        camera_controller.log_message(f"优化包大小错误: {str(e)}", "error")

@socketio.on('get_parameters')
def handle_get_parameters():
    """获取相机参数"""
    try:
        params = camera_controller.camera_api.get_parameters()
        if params:
            camera_controller.current_params = params
            emit('parameters_updated', {
                'exposure_time': params.exposure_time,
                'gain': params.gain,
                'frame_rate': params.frame_rate,
                'packet_size': params.packet_size
            })
            camera_controller.log_message("参数获取成功", "success")
        else:
            camera_controller.log_message("获取参数失败", "error")
    except Exception as e:
        camera_controller.log_message(f"获取参数错误: {str(e)}", "error")

@socketio.on('set_parameters')
def handle_set_parameters(data):
    """设置相机参数"""
    try:
        params = CameraParameters()
        params.exposure_time = float(data.get('exposure_time', 10000))
        params.gain = float(data.get('gain', 0))
        params.frame_rate = float(data.get('frame_rate', 30))
        
        if camera_controller.camera_api.set_parameters(params):
            camera_controller.current_params = params
            camera_controller.log_message("参数设置成功", "success")
        else:
            camera_controller.log_message("参数设置失败", "error")
            
    except Exception as e:
        camera_controller.log_message(f"设置参数错误: {str(e)}", "error")

@socketio.on('set_mode')
def handle_set_mode(data):
    """设置工作模式"""
    try:
        if not camera_controller.camera_api.is_connected():
            camera_controller.log_message("请先连接设备", "warning")
            return
        
        mode_str = data.get('mode', 'continuous')
        mode = CameraMode.CONTINUOUS if mode_str == 'continuous' else CameraMode.TRIGGER
        
        was_streaming = camera_controller.camera_api.is_streaming()
        
        mode_text = "连续模式" if mode == CameraMode.CONTINUOUS else "触发模式"
        camera_controller.log_message(f"正在切换到{mode_text}...", "info")
        
        if camera_controller.camera_api.set_mode(mode):
            camera_controller.log_message(f"模式切换成功: {mode_text}", "success")
            
            if was_streaming and not camera_controller.camera_api.is_streaming():
                camera_controller.log_message("模式切换完成，请重新点击'开始串流'", "info")
        else:
            camera_controller.log_message("模式切换失败", "error")
            
    except Exception as e:
        camera_controller.log_message(f"设置模式错误: {str(e)}", "error")

@socketio.on('start_streaming')
def handle_start_streaming():
    """开始串流"""
    try:
        if camera_controller.camera_api.start_streaming():
            camera_controller.log_message("串流启动成功", "success")
        else:
            camera_controller.log_message("串流启动失败", "error")
    except Exception as e:
        camera_controller.log_message(f"启动串流错误: {str(e)}", "error")

@socketio.on('stop_streaming')
def handle_stop_streaming():
    """停止串流"""
    try:
        if camera_controller.camera_api.stop_streaming():
            camera_controller.log_message("串流已停止", "info")
        else:
            camera_controller.log_message("停止串流失败", "error")
    except Exception as e:
        camera_controller.log_message(f"停止串流错误: {str(e)}", "error")

@socketio.on('software_trigger')
def handle_software_trigger():
    """软触发"""
    try:
        if camera_controller.camera_api.software_trigger():
            camera_controller.trigger_count += 1
            camera_controller.log_message(f"软触发成功 (第 {camera_controller.trigger_count} 次)", "success")
        else:
            camera_controller.log_message("软触发失败", "error")
    except Exception as e:
        camera_controller.log_message(f"软触发错误: {str(e)}", "error")

@socketio.on('reset_trigger_count')
def handle_reset_trigger_count():
    """重置触发计数"""
    camera_controller.trigger_count = 0
    camera_controller.log_message("触发计数已重置", "info")

@socketio.on('save_image')
def handle_save_image(data):
    """保存圖像"""
    try:
        format_str = data.get('format', 'bmp')
        image_format = ImageFormat.BMP if format_str == 'bmp' else ImageFormat.JPEG
        
        # 使用改進的保存方法
        success, result_info = camera_controller.save_image_with_custom_name(image_format)
        
        if success:
            camera_controller.save_count += 1
            camera_controller.log_message(f"圖像保存成功 ({format_str.upper()}) - 第 {camera_controller.save_count} 張", "success")
            camera_controller.log_message(f"保存路徑: {result_info}", "info")
            
            # 發送保存成功的詳細資訊
            emit('image_saved', {
                'success': True,
                'count': camera_controller.save_count,
                'format': format_str.upper(),
                'path': result_info
            })
        else:
            camera_controller.log_message(f"圖像保存失敗: {result_info}", "error")
            emit('image_saved', {
                'success': False,
                'error': result_info
            })
            
    except Exception as e:
        error_msg = f"保存圖像錯誤: {str(e)}"
        camera_controller.log_message(error_msg, "error")
        emit('image_saved', {
            'success': False,
            'error': error_msg
        })

@socketio.on('reset_connection')
def handle_reset_connection(data):
    """重置连接"""
    try:
        camera_controller.log_message("正在重置连接...", "info")
        
        device_index = data.get('device_index', -1)
        
        # 断开连接
        camera_controller.camera_api.disconnect()
        
        # 等待
        time.sleep(1.0)
        
        # 重新连接
        if device_index >= 0:
            if camera_controller.camera_api.connect(device_index):
                device = camera_controller.devices[device_index]
                camera_controller.log_message(f"重置连接成功: {device.device_name}", "success")
            else:
                camera_controller.log_message("重置连接失败", "error")
                
    except Exception as e:
        camera_controller.log_message(f"重置连接错误: {str(e)}", "error")

if __name__ == '__main__':
    # 啟動Flask應用程式
    print("啟動相機控制Web伺服器...")
    print("訪問地址: http://localhost:5000")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n正在關閉伺服器...")
        camera_controller.status_running = False
        if camera_controller.camera_api:
            camera_controller.camera_api.disconnect()
        print("伺服器已關閉")