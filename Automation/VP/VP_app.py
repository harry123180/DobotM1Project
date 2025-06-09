# -*- coding: utf-8 -*-
"""
VP_app.py - 震動盤Web UI控制應用
提供獨立的Web介面用於手動控制和參數調整震動盤
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
from datetime import datetime
from vibration_plate import VibrationPlate

class VibrationPlateWebApp:
    """震動盤Web控制應用"""
    
    def __init__(self):
        # 內建配置
        self.config = {
            "vibration_plate": {
                "ip": "192.168.1.7",
                "port": 1000,
                "slave_id": 10
            },
            "web_server": {
                "host": "0.0.0.0",
                "port": 5053,
                "debug": False
            },
            "defaults": {
                "brightness": 128,
                "strength": 100,
                "frequency": 100
            }
        }
        
        # 震動盤實例
        self.vibration_plate = None
        self.is_connected = False
        
        # 狀態監控
        self.status_monitor_thread = None
        self.monitoring = False
        
        # 初始化Flask應用
        self.init_flask_app()
        
    def init_flask_app(self):
        """初始化Flask應用"""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'vp_web_app_2024'
        
        # 初始化SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 註冊路由
        self.register_routes()
        self.register_socketio_events()
        
    def register_routes(self):
        """註冊Flask路由"""
        
        @self.app.route('/')
        def index():
            """主頁面"""
            return render_template('index.html', config=self.config)
        
        @self.app.route('/api/status')
        def get_status():
            """獲取系統狀態"""
            status = {
                'connected': self.is_connected,
                'vibration_plate': None,
                'config': self.config,
                'timestamp': datetime.now().isoformat()
            }
            
            if self.vibration_plate and self.is_connected:
                try:
                    vp_status = self.vibration_plate.get_status()
                    status['vibration_plate'] = vp_status
                except Exception as e:
                    print(f"獲取震動盤狀態失敗: {e}")
                    status['connected'] = False
                    self.is_connected = False
            
            return jsonify(status)
        
        @self.app.route('/api/connect', methods=['POST'])
        def connect_device():
            """連接震動盤"""
            data = request.get_json() or {}
            
            # 更新連接參數
            if 'ip' in data:
                self.config['vibration_plate']['ip'] = data['ip']
            if 'port' in data:
                self.config['vibration_plate']['port'] = int(data['port'])
            if 'slave_id' in data:
                self.config['vibration_plate']['slave_id'] = int(data['slave_id'])
            
            result = self.connect_vibration_plate()
            
            if result['success']:
                self.start_monitoring()
            
            return jsonify(result)
        
        @self.app.route('/api/disconnect', methods=['POST'])
        def disconnect_device():
            """斷開震動盤連接"""
            result = self.disconnect_vibration_plate()
            return jsonify(result)
        
        @self.app.route('/api/test_connection', methods=['POST'])
        def test_connection():
            """測試連接"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            try:
                test_result = self.vibration_plate.test_connection()
                return jsonify(test_result)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'測試失敗: {str(e)}'
                })
        
        @self.app.route('/api/action', methods=['POST'])
        def execute_action():
            """執行動作"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            data = request.get_json()
            action = data.get('action')
            strength = data.get('strength')
            frequency = data.get('frequency')
            duration = data.get('duration')
            
            try:
                success = self.vibration_plate.execute_action(
                    action, strength, frequency, duration
                )
                
                return jsonify({
                    'success': success,
                    'message': f'動作 {action} {"執行成功" if success else "執行失敗"}',
                    'action': action
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'執行動作失敗: {str(e)}'
                })
        
        @self.app.route('/api/stop', methods=['POST'])
        def stop_action():
            """停止動作"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            try:
                success = self.vibration_plate.stop()
                return jsonify({
                    'success': success,
                    'message': '停止成功' if success else '停止失敗'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'停止失敗: {str(e)}'
                })
        
        @self.app.route('/api/set_brightness', methods=['POST'])
        def set_brightness():
            """設定背光亮度"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            data = request.get_json()
            brightness = data.get('brightness', 128)
            
            try:
                success = self.vibration_plate.set_backlight_brightness(brightness)
                if success:
                    self.config['defaults']['brightness'] = brightness
                
                return jsonify({
                    'success': success,
                    'message': f'亮度設定{"成功" if success else "失敗"}',
                    'brightness': brightness
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'設定亮度失敗: {str(e)}'
                })
        
        @self.app.route('/api/set_backlight', methods=['POST'])
        def set_backlight():
            """設定背光開關"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            data = request.get_json()
            state = data.get('state', True)
            
            try:
                success = self.vibration_plate.set_backlight(state)
                return jsonify({
                    'success': success,
                    'message': f'背光{"開啟" if state else "關閉"}{"成功" if success else "失敗"}',
                    'state': state
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'設定背光失敗: {str(e)}'
                })
        
        @self.app.route('/api/set_action_params', methods=['POST'])
        def set_action_params():
            """設定動作參數"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            data = request.get_json()
            action = data.get('action')
            strength = data.get('strength')
            frequency = data.get('frequency')
            
            try:
                success = self.vibration_plate.set_action_parameters(
                    action, strength, frequency
                )
                
                return jsonify({
                    'success': success,
                    'message': f'{action} 參數設定{"成功" if success else "失敗"}',
                    'action': action,
                    'strength': strength,
                    'frequency': frequency
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'設定參數失敗: {str(e)}'
                })
        
        @self.app.route('/api/get_register_map', methods=['GET'])
        def get_register_map():
            """獲取寄存器映射"""
            if not self.vibration_plate:
                return jsonify({
                    'success': False,
                    'message': '震動盤未初始化'
                })
            
            try:
                register_map = self.vibration_plate.get_register_map()
                return jsonify({
                    'success': True,
                    'register_map': register_map
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'獲取寄存器映射失敗: {str(e)}'
                })
        
        @self.app.route('/api/update_config', methods=['POST'])
        def update_config():
            """更新配置"""
            data = request.get_json()
            
            try:
                # 更新配置
                if 'vibration_plate' in data:
                    self.config['vibration_plate'].update(data['vibration_plate'])
                
                if 'defaults' in data:
                    self.config['defaults'].update(data['defaults'])
                
                return jsonify({
                    'success': True,
                    'message': '配置更新成功',
                    'config': self.config
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'更新配置失敗: {str(e)}'
                })
        
        @self.app.route('/api/get_action_list', methods=['GET'])
        def get_action_list():
            """獲取可用動作列表"""
            if not self.vibration_plate:
                return jsonify({
                    'success': False,
                    'message': '震動盤未初始化'
                })
            
            try:
                action_list = self.vibration_plate.get_action_list()
                return jsonify({
                    'success': True,
                    'actions': action_list,
                    'message': '動作列表獲取成功'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'獲取動作列表失敗: {str(e)}'
                })
        
        @self.app.route('/api/read_device_status', methods=['GET'])
        def read_device_status():
            """讀取設備即時狀態"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            try:
                status = self.vibration_plate.get_status()
                return jsonify({
                    'success': True,
                    'status': status,
                    'message': '設備狀態讀取成功'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'讀取設備狀態失敗: {str(e)}'
                })
        
        @self.app.route('/api/batch_set_params', methods=['POST'])
        def batch_set_params():
            """批量設定動作參數"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            data = request.get_json()
            action_params = data.get('action_params', {})
            
            try:
                success_count = 0
                failed_actions = []
                
                for action, params in action_params.items():
                    strength = params.get('strength')
                    frequency = params.get('frequency')
                    
                    if self.vibration_plate.set_action_parameters(action, strength, frequency):
                        success_count += 1
                    else:
                        failed_actions.append(action)
                
                if failed_actions:
                    return jsonify({
                        'success': False,
                        'message': f'部分參數設定失敗: {", ".join(failed_actions)}',
                        'success_count': success_count,
                        'failed_actions': failed_actions
                    })
                else:
                    return jsonify({
                        'success': True,
                        'message': f'所有參數設定成功 ({success_count}個)',
                        'success_count': success_count
                    })
                    
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'批量設定參數失敗: {str(e)}'
                })
        
        @self.app.route('/api/reset_to_defaults', methods=['POST'])
        def reset_to_defaults():
            """重置到預設參數"""
            if not self.vibration_plate or not self.is_connected:
                return jsonify({
                    'success': False,
                    'message': '震動盤未連接'
                })
            
            try:
                defaults = self.config['defaults']
                actions = ['up', 'down', 'left', 'right', 'upleft', 'downleft',
                          'upright', 'downright', 'horizontal', 'vertical', 'spread']
                
                success_count = 0
                for action in actions:
                    if self.vibration_plate.set_action_parameters(
                        action, defaults['strength'], defaults['frequency']
                    ):
                        success_count += 1
                
                # 重置背光亮度
                brightness_success = self.vibration_plate.set_backlight_brightness(defaults['brightness'])
                
                return jsonify({
                    'success': success_count == len(actions) and brightness_success,
                    'message': f'重置完成: {success_count}/{len(actions)}個動作 + 背光{"成功" if brightness_success else "失敗"}',
                    'reset_count': success_count,
                    'brightness_reset': brightness_success
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'重置失敗: {str(e)}'
                })
    
    def register_socketio_events(self):
        """註冊SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客戶端連接"""
            print("客戶端已連接")
            emit('status_update', self.get_current_status())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客戶端斷開"""
            print("客戶端已斷開")
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """狀態請求"""
            emit('status_update', self.get_current_status())
    
    def connect_vibration_plate(self) -> dict:
        """連接震動盤"""
        try:
            if self.vibration_plate:
                self.vibration_plate.disconnect()
            
            vp_config = self.config['vibration_plate']
            self.vibration_plate = VibrationPlate(
                ip=vp_config['ip'],
                port=vp_config['port'],
                slave_id=vp_config['slave_id'],
                auto_connect=True
            )
            
            if self.vibration_plate.is_connected():
                self.is_connected = True
                print(f"震動盤連接成功: {vp_config['ip']}:{vp_config['port']}")
                
                # 初始化預設參數
                defaults = self.config['defaults']
                self.vibration_plate.set_backlight_brightness(defaults['brightness'])
                self.vibration_plate.set_backlight(True)
                
                return {
                    'success': True,
                    'message': '震動盤連接成功',
                    'device_info': vp_config
                }
            else:
                self.is_connected = False
                return {
                    'success': False,
                    'message': '震動盤連接失敗'
                }
                
        except Exception as e:
            self.is_connected = False
            print(f"連接震動盤失敗: {e}")
            return {
                'success': False,
                'message': f'連接失敗: {str(e)}'
            }
    
    def disconnect_vibration_plate(self) -> dict:
        """斷開震動盤連接"""
        try:
            self.stop_monitoring()
            
            if self.vibration_plate:
                self.vibration_plate.disconnect()
                self.vibration_plate = None
            
            self.is_connected = False
            print("震動盤連接已斷開")
            
            return {
                'success': True,
                'message': '震動盤連接已斷開'
            }
            
        except Exception as e:
            print(f"斷開連接失敗: {e}")
            return {
                'success': False,
                'message': f'斷開連接失敗: {str(e)}'
            }
    
    def start_monitoring(self):
        """開始狀態監控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.status_monitor_thread = threading.Thread(target=self.status_monitor_loop, daemon=True)
        self.status_monitor_thread.start()
        print("狀態監控已啟動")
    
    def stop_monitoring(self):
        """停止狀態監控"""
        self.monitoring = False
        if self.status_monitor_thread and self.status_monitor_thread.is_alive():
            self.status_monitor_thread.join(timeout=1)
        print("狀態監控已停止")
    
    def status_monitor_loop(self):
        """狀態監控循環"""
        while self.monitoring:
            try:
                if self.is_connected and self.vibration_plate:
                    # 檢查連接狀態
                    if not self.vibration_plate.is_connected():
                        self.is_connected = False
                        print("震動盤連接已斷開")
                    
                    # 發送狀態更新
                    status = self.get_current_status()
                    self.socketio.emit('status_update', status)
                
                time.sleep(2)  # 2秒更新一次
                
            except Exception as e:
                print(f"狀態監控異常: {e}")
                time.sleep(5)
    
    def get_current_status(self) -> dict:
        """獲取當前狀態"""
        status = {
            'connected': self.is_connected,
            'vibration_plate': None,
            'config': self.config,
            'timestamp': datetime.now().isoformat()
        }
        
        if self.vibration_plate and self.is_connected:
            try:
                vp_status = self.vibration_plate.get_status()
                status['vibration_plate'] = vp_status
            except Exception as e:
                print(f"獲取震動盤狀態失敗: {e}")
                status['connected'] = False
                self.is_connected = False
        
        return status
    
    def create_templates_directory(self):
        """創建templates目錄"""
        templates_dir = 'templates'
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
            print(f"已創建templates目錄: {templates_dir}")
    
    def run(self):
        """運行Web應用"""
        print("震動盤Web控制應用啟動中...")
        
        # 創建templates目錄
        self.create_templates_directory()
        
        web_config = self.config['web_server']
        print(f"Web服務器啟動 - http://{web_config['host']}:{web_config['port']}")
        print(f"預設震動盤地址: {self.config['vibration_plate']['ip']}:{self.config['vibration_plate']['port']}")
        print("功能列表:")
        print("  - 設備連接管理")
        print("  - 背光控制 (亮度調節)")
        print("  - 動作控制 (11種震動模式)")
        print("  - 參數設定 (強度/頻率)")
        print("  - 即時狀態監控")
        print("  - 批量參數設定")
        print("  - 寄存器映射查看")
        print("按 Ctrl+C 停止應用")
        
        try:
            self.socketio.run(
                self.app,
                host=web_config['host'],
                port=web_config['port'],
                debug=web_config['debug'],
                allow_unsafe_werkzeug=True
            )
        except Exception as e:
            print(f"Web服務器啟動失敗: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理資源"""
        print("正在清理資源...")
        self.stop_monitoring()
        if self.vibration_plate:
            try:
                # 停止所有動作
                self.vibration_plate.stop()
                self.vibration_plate.disconnect()
                print("震動盤已安全斷開")
            except:
                pass
        print("資源清理完成")


def create_index_html():
    """創建index.html檔案 (如果不存在)"""
    templates_dir = 'templates'
    index_path = os.path.join(templates_dir, 'index.html')
    
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    if not os.path.exists(index_path):
        print(f"注意: 未找到 {index_path}")
        print("請確保將 index.html 檔案放置在 templates/ 目錄中")
        print("或者從提供的 HTML 模板創建該檔案")
        return False
    
    return True


def main():
    """主函數"""
    print("=" * 60)
    print("震動盤Web控制應用")
    print("=" * 60)
    
    # 檢查HTML模板
    if not create_index_html():
        print("警告: HTML模板檔案缺失，Web介面可能無法正常顯示")
        print("繼續啟動應用...")
    
    # 創建應用實例
    app = VibrationPlateWebApp()
    
    try:
        # 運行應用
        app.run()
    except KeyboardInterrupt:
        print("\n收到中斷信號，正在關閉...")
    except Exception as e:
        print(f"應用運行異常: {e}")
    finally:
        app.cleanup()
        print("應用已安全關閉")


if __name__ == '__main__':
    main()