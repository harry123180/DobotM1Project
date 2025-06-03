# -*- coding: utf-8 -*-
"""
Camera Web Control - Flask后端服务器
基于Camera_API.py的Web化相机控制系统
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import json
from datetime import datetime
from typing import Dict, Any, List

# 导入自定义API
from Camera_API import (
    CameraAPI, CameraInfo, CameraMode, ImageFormat, 
    CameraStatus, CameraParameters, create_camera_api
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'camera_control_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

class CameraWebController:
    """相机Web控制器"""
    
    def __init__(self):
        # 初始化相机API
        self.camera_api = create_camera_api()
        self.camera_api.set_error_callback(self.on_error)
        
        # 状态变量
        self.devices: List[CameraInfo] = []
        self.current_params = CameraParameters()
        self.status_update_thread = None
        self.status_running = False
        self.trigger_count = 0
        self.save_count = 0
        
        # 启动状态更新线程
        self.start_status_update()
    
    def start_status_update(self):
        """启动状态更新线程"""
        self.status_running = True
        self.status_update_thread = threading.Thread(target=self.status_update_loop, daemon=True)
        self.status_update_thread.start()
    
    def status_update_loop(self):
        """状态更新循环"""
        while self.status_running:
            try:
                # 获取当前状态
                status_data = self.get_current_status()
                # 发送状态更新到前端
                socketio.emit('status_update', status_data)
                time.sleep(1.0)  # 每秒更新一次
            except Exception as e:
                self.log_message(f"状态更新错误: {str(e)}", "error")
                time.sleep(2.0)
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前系统状态"""
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
                'name': device_info.device_name if device_info else "无",
                'type': device_info.device_type if device_info else "无",
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
        """发送日志消息到前端"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_data = {
            'timestamp': timestamp,
            'message': message,
            'level': level
        }
        socketio.emit('log_message', log_data)
    
    def on_error(self, error_msg: str):
        """错误回调函数"""
        self.log_message(error_msg, "error")

# 创建全局控制器实例
camera_controller = CameraWebController()

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    camera_controller.log_message("Web客户端已连接", "info")
    # 发送当前状态
    emit('status_update', camera_controller.get_current_status())

@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接"""
    camera_controller.log_message("Web客户端已断开", "info")

@socketio.on('refresh_devices')
def handle_refresh_devices():
    """刷新设备列表"""
    try:
        camera_controller.log_message("正在枚举设备...", "info")
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
            camera_controller.log_message(f"找到 {len(devices_data)} 个设备", "success")
        else:
            camera_controller.log_message("未找到可用设备", "warning")
        
        emit('devices_list', {'devices': devices_data})
        
    except Exception as e:
        camera_controller.log_message(f"枚举设备失败: {str(e)}", "error")

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
    """保存图像"""
    try:
        format_str = data.get('format', 'bmp')
        image_format = ImageFormat.BMP if format_str == 'bmp' else ImageFormat.JPEG
        
        if camera_controller.camera_api.save_image(image_format):
            camera_controller.save_count += 1
            camera_controller.log_message(f"图像保存成功 ({format_str.upper()}) - 第 {camera_controller.save_count} 张", "success")
        else:
            camera_controller.log_message("图像保存失败", "error")
            
    except Exception as e:
        camera_controller.log_message(f"保存图像错误: {str(e)}", "error")

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
    # 启动Flask应用
    print("启动相机控制Web服务器...")
    print("访问地址: http://localhost:5000")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        camera_controller.status_running = False
        if camera_controller.camera_api:
            camera_controller.camera_api.disconnect()
        print("服务器已关闭")