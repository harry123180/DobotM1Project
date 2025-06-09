# ManagerServerUI.py
# Modbus TCP Server 管理介面 - Flask UI 客戶端
# 版本：1.0.0

import logging
import os
import sys
import requests
import time
import json
import traceback
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

# 設定日誌
def setup_logging():
    """設定日誌配置"""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # 檔案日誌處理器
    file_handler = logging.FileHandler('manager_ui.log', encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    
    # 控制台日誌處理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # 設定根記錄器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 抑制一些第三方庫的詳細日誌
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

class ModbusServerUIManager:
    def __init__(self):
        # ServerApp API 配置
        self.server_api_host = "localhost"
        self.server_api_port = 8001
        self.server_api_base_url = f"http://{self.server_api_host}:{self.server_api_port}/api"
        
        # UI 伺服器配置
        self.ui_port = 8000
        
        # 創建templates目錄
        self.create_directories()
        
        # Flask應用配置
        template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.flask_app = Flask(__name__, template_folder=template_folder)
        
        # 設定路由
        self.setup_routes()
        
        # 連接狀態
        self.server_connected = False
        self.last_check_time = 0
        
        logging.info("Modbus Server UI Manager 初始化完成")
    
    def create_directories(self):
        """創建必要的目錄結構"""
        directories = ['templates']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def check_server_connection(self):
        """檢查與ServerApp的連接狀態"""
        try:
            current_time = time.time()
            # 每5秒檢查一次連接狀態
            if current_time - self.last_check_time < 5:
                return self.server_connected
            
            response = requests.get(f"{self.server_api_base_url}/status", timeout=3)
            self.server_connected = response.status_code == 200
            self.last_check_time = current_time
            
            if not self.server_connected:
                logging.warning(f"無法連接到ServerApp: HTTP {response.status_code}")
        except Exception as e:
            self.server_connected = False
            self.last_check_time = current_time
            logging.warning(f"無法連接到ServerApp: {e}")
        
        return self.server_connected
    
    def api_request(self, method, endpoint, data=None, params=None):
        """向ServerApp發送API請求"""
        try:
            url = f"{self.server_api_base_url}{endpoint}"
            
            if method.upper() == 'GET':
                response = requests.get(url, params=params, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"不支援的HTTP方法: {method}")
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"API請求失敗: {method} {endpoint}, 狀態碼: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"API請求錯誤: {method} {endpoint}, 錯誤: {e}")
            return None
    
    def setup_routes(self):
        """設定Flask路由"""
        
        @self.flask_app.errorhandler(Exception)
        def handle_exception(e):
            logging.error(f"UI介面錯誤: {e}\n{traceback.format_exc()}")
            return jsonify({'error': 'Internal server error'}), 500
        
        @self.flask_app.route('/')
        def index():
            """主頁面"""
            return render_template('index.html')
        
        @self.flask_app.route('/api/ui/status')
        def ui_status():
            """UI狀態檢查"""
            server_connected = self.check_server_connection()
            server_status = None
            
            if server_connected:
                server_status = self.api_request('GET', '/status')
            
            return jsonify({
                'ui_running': True,
                'server_connected': server_connected,
                'server_status': server_status,
                'server_api_url': self.server_api_base_url,
                'ui_version': '1.0.0'
            })
        
        @self.flask_app.route('/api/ui/server_status')
        def proxy_server_status():
            """代理ServerApp狀態請求"""
            if not self.check_server_connection():
                return jsonify({'error': 'ServerApp未連接'}), 503
            
            result = self.api_request('GET', '/status')
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': '無法獲取伺服器狀態'}), 500
        
        @self.flask_app.route('/api/ui/slave_id', methods=['POST'])
        def proxy_set_slave_id():
            """代理設定SlaveID請求"""
            if not self.check_server_connection():
                return jsonify({'error': 'ServerApp未連接'}), 503
            
            data = request.get_json()
            result = self.api_request('POST', '/slave_id', data)
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': '設定SlaveID失敗'}), 500
        
        @self.flask_app.route('/api/ui/register/<int:address>')
        def proxy_get_register(address):
            """代理獲取暫存器請求"""
            if not self.check_server_connection():
                return jsonify({'error': 'ServerApp未連接'}), 503
            
            result = self.api_request('GET', f'/register/{address}')
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': '讀取暫存器失敗'}), 500
        
        @self.flask_app.route('/api/ui/register/<int:address>', methods=['POST'])
        def proxy_set_register(address):
            """代理設定暫存器請求"""
            if not self.check_server_connection():
                return jsonify({'error': 'ServerApp未連接'}), 503
            
            data = request.get_json()
            result = self.api_request('POST', f'/register/{address}', data)
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': '寫入暫存器失敗'}), 500
        
        @self.flask_app.route('/api/ui/registers', methods=['POST'])
        def proxy_set_multiple_registers():
            """代理批量設定暫存器請求"""
            if not self.check_server_connection():
                return jsonify({'error': 'ServerApp未連接'}), 503
            
            data = request.get_json()
            result = self.api_request('POST', '/registers', data)
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': '批量寫入暫存器失敗'}), 500
        
        @self.flask_app.route('/api/ui/register_range')
        def proxy_get_register_range():
            """代理獲取暫存器範圍請求"""
            if not self.check_server_connection():
                return jsonify({'error': 'ServerApp未連接'}), 503
            
            params = {
                'start': request.args.get('start', 0),
                'count': request.args.get('count', 20)
            }
            result = self.api_request('GET', '/register_range', params=params)
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': '獲取暫存器範圍失敗'}), 500
        
        @self.flask_app.route('/api/ui/comment/<int:address>', methods=['POST'])
        def proxy_update_comment(address):
            """代理更新註解請求"""
            if not self.check_server_connection():
                return jsonify({'error': 'ServerApp未連接'}), 503
            
            data = request.get_json()
            result = self.api_request('POST', f'/comment/{address}', data)
            if result:
                return jsonify(result)
            else:
                return jsonify({'error': '更新註解失敗'}), 500
    
    def run(self):
        """啟動UI管理介面"""
        try:
            logging.info("=== Modbus Server UI Manager 啟動 ===")
            logging.info(f"UI 端口: {self.ui_port}")
            logging.info(f"ServerApp API: {self.server_api_base_url}")
            
            # 檢查ServerApp連接
            if self.check_server_connection():
                logging.info("✓ 已連接到ServerApp")
            else:
                logging.warning("⚠ 無法連接到ServerApp，請確保ServerApp正在運行")
            
            # 啟動Flask應用
            logging.info(f"啟動UI管理介面於 http://localhost:{self.ui_port}")
            self.flask_app.run(
                host='0.0.0.0',
                port=self.ui_port,
                debug=False,
                use_reloader=False,
                threaded=True
            )
            
        except Exception as e:
            logging.error(f"UI管理介面啟動失敗: {e}\n{traceback.format_exc()}")
            raise

def main():
    """主函數"""
    try:
        # 設定日誌
        setup_logging()
        
        # 打印啟動資訊
        print("=" * 60)
        print("  Modbus Server UI Manager")
        print("=" * 60)
        print(f"  版本: 1.0.0")
        print(f"  UI 埠: 8000")
        print(f"  ServerApp API: http://localhost:8001/api")
        print(f"  管理網址: http://localhost:8000")
        print("=" * 60)
        print("  請確保 ServerApp.py 正在運行於 8001 端口")
        print("  按 Ctrl+C 可關閉UI管理介面")
        print("=" * 60)
        
        # 創建並運行UI管理器
        ui_manager = ModbusServerUIManager()
        ui_manager.run()
        
    except KeyboardInterrupt:
        logging.info("收到中斷信號，正在關閉UI管理介面...")
    except Exception as e:
        logging.error(f"UI管理介面啟動失敗: {e}\n{traceback.format_exc()}")
        print(f"\n❌ 啟動失敗: {e}")
        print("請檢查 manager_ui.log 檔案獲取詳細錯誤資訊")
        input("按 Enter 鍵退出...")
        sys.exit(1)

if __name__ == "__main__":
    main()