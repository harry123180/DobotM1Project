#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web Application for DH-Robotics Gripper Control
====================================================

Web界面應用程序，提供友好的UI來控制夾爪
"""

from flask import Flask, render_template, request, jsonify
import requests
import json
import logging
from datetime import datetime

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GripperWebApp:
    """夾爪Web應用程序"""
    
    def __init__(self, gateway_host='localhost', gateway_port=5001):
        """
        初始化Web應用程序
        
        Args:
            gateway_host (str): Gateway伺服器IP
            gateway_port (int): Gateway伺服器端口
        """
        self.app = Flask(__name__)
        self.gateway_url = f"http://{gateway_host}:{gateway_port}"
        self.setup_routes()
    
    def gateway_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """
        向Gateway發送請求
        
        Args:
            method (str): HTTP方法
            endpoint (str): API端點
            data (dict): 請求數據
            
        Returns:
            dict: 回應數據
        """
        url = f"{self.gateway_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, timeout=5)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, timeout=5)
            else:
                return {'success': False, 'message': f'不支援的HTTP方法: {method}'}
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Gateway請求失敗: {str(e)}")
            return {'success': False, 'message': f'Gateway連接失敗: {str(e)}'}
        except json.JSONDecodeError:
            return {'success': False, 'message': '回應格式錯誤'}
    
    def setup_routes(self):
        """設定Flask路由"""
        
        @self.app.route('/')
        def index():
            """主頁面"""
            return render_template('index.html')
        
        @self.app.route('/api/gateway/health')
        def gateway_health():
            """檢查Gateway健康狀態"""
            return jsonify(self.gateway_request('GET', '/health'))
        
        @self.app.route('/api/gateway/connect', methods=['POST'])
        def gateway_connect():
            """連接Gateway"""
            return jsonify(self.gateway_request('POST', '/connect'))
        
        @self.app.route('/api/gateway/disconnect', methods=['POST'])
        def gateway_disconnect():
            """斷開Gateway"""
            return jsonify(self.gateway_request('POST', '/disconnect'))
        
        @self.app.route('/api/devices')
        def get_devices():
            """獲取設備列表"""
            return jsonify(self.gateway_request('GET', '/devices'))
        
        # ========== 夾爪控制 API ==========
        
        @self.app.route('/api/gripper/<device_type>/initialize', methods=['POST'])
        def initialize_gripper(device_type):
            """初始化夾爪"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', f'/gripper/{device_type}/initialize', data))
        
        @self.app.route('/api/gripper/<device_type>/force', methods=['POST'])
        def set_gripper_force(device_type):
            """設定夾爪力值"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', f'/gripper/{device_type}/force', data))
        
        @self.app.route('/api/gripper/<device_type>/position', methods=['POST'])
        def set_gripper_position(device_type):
            """設定夾爪位置"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', f'/gripper/{device_type}/position', data))
        
        @self.app.route('/api/gripper/<device_type>/speed', methods=['POST'])
        def set_gripper_speed(device_type):
            """設定夾爪速度"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', f'/gripper/{device_type}/speed', data))
        
        @self.app.route('/api/gripper/<device_type>/open', methods=['POST'])
        def open_gripper(device_type):
            """張開夾爪"""
            return jsonify(self.gateway_request('POST', f'/gripper/{device_type}/open'))
        
        @self.app.route('/api/gripper/<device_type>/close', methods=['POST'])
        def close_gripper(device_type):
            """閉合夾爪"""
            return jsonify(self.gateway_request('POST', f'/gripper/{device_type}/close'))
        
        @self.app.route('/api/gripper/<device_type>/stop', methods=['POST'])
        def stop_gripper(device_type):
            """停止夾爪"""
            return jsonify(self.gateway_request('POST', f'/gripper/{device_type}/stop'))
        
        @self.app.route('/api/gripper/<device_type>/status')
        def get_gripper_status(device_type):
            """獲取夾爪狀態"""
            return jsonify(self.gateway_request('GET', f'/gripper/{device_type}/status'))
        
        # ========== PGHL控制 API ==========
        
        @self.app.route('/api/pghl/home', methods=['POST'])
        def pghl_home():
            """PGHL回零"""
            return jsonify(self.gateway_request('POST', '/pghl/home'))
        
        @self.app.route('/api/pghl/stop', methods=['POST'])
        def pghl_stop():
            """停止PGHL"""
            return jsonify(self.gateway_request('POST', '/pghl/stop'))
        
        @self.app.route('/api/pghl/push_force', methods=['POST'])
        def set_pghl_push_force():
            """設定PGHL推壓力值"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', '/pghl/push_force', data))
        
        @self.app.route('/api/pghl/push_length', methods=['POST'])
        def set_pghl_push_length():
            """設定PGHL推壓段長度"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', '/pghl/push_length', data))
        
        @self.app.route('/api/pghl/target_position', methods=['POST'])
        def set_pghl_target_position():
            """設定PGHL目標位置"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', '/pghl/target_position', data))
        
        @self.app.route('/api/pghl/max_speed', methods=['POST'])
        def set_pghl_max_speed():
            """設定PGHL最大速度"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', '/pghl/max_speed', data))
        
        @self.app.route('/api/pghl/acceleration', methods=['POST'])
        def set_pghl_acceleration():
            """設定PGHL加速度"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', '/pghl/acceleration', data))
        
        @self.app.route('/api/pghl/relative_position', methods=['POST'])
        def set_pghl_relative_position():
            """設定PGHL相對位置"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', '/pghl/relative_position', data))
        
        @self.app.route('/api/pghl/jog', methods=['POST'])
        def pghl_jog():
            """PGHL點動控制"""
            data = request.get_json() or {}
            return jsonify(self.gateway_request('POST', '/pghl/jog', data))
        
        @self.app.route('/api/pghl/status')
        def get_pghl_status():
            """獲取PGHL狀態"""
            return jsonify(self.gateway_request('GET', '/pghl/status'))
        
        # ========== 通用 API ==========
        
        @self.app.route('/api/save/<device_type>', methods=['POST'])
        def save_settings(device_type):
            """保存設定"""
            return jsonify(self.gateway_request('POST', f'/save/{device_type}'))
    
    def run(self, host='0.0.0.0', port=8081, debug=False):
        """啟動Web應用程序"""
        logger.info(f"🌐 啟動Web應用程序於 http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)

def main():
    """主程式"""
    try:
        # 建立Web應用程序實例
        web_app = GripperWebApp(gateway_host='localhost', gateway_port=5008)
        
        # 啟動Web伺服器
        web_app.run(host='0.0.0.0', port=8081, debug=False)
        
    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在關閉Web應用程序...")
    except Exception as e:
        logger.error(f"Web應用程序錯誤: {str(e)}")

if __name__ == '__main__':
    main()