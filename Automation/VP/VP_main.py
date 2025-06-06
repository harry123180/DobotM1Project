from flask import Flask, render_template, request, jsonify
from vibration_plate import VibrationPlate
import threading
import time
import logging
import signal
import sys
import asyncio
from datetime import datetime
from pymodbus.client import ModbusTcpClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VibrationPlateController:
    """震動盤控制器主類"""
    
    def __init__(self):
        # 預設配置
        self.config = {
            'vp_ip': '192.168.1.7',          # 震動盤IP
            'vp_port': 1000,                 # 震動盤埠口
            'vp_slave_id': 10,               # 震動盤從機ID
            'modbus_server_ip': '127.0.0.1', # ModbusTCP伺服器IP
            'modbus_server_port': 502,       # ModbusTCP伺服器埠口
            'modbus_slave_id': 1,            # ModbusTCP從機ID
            'web_port': 5050,                # Web服務埠口
            'default_brightness': 128,        # 預設背光亮度
            'default_frequency': 100,         # 預設震動頻率
            'default_strength': 100           # 預設震動強度
        }
        
        # 狀態變數
        self.vibration_plate = None
        self.modbus_client = None
        self.running = False
        
        # 控制寄存器定義 (可由外部ModbusTCP伺服器控制)
        self.control_registers = {
            'backlight_brightness': 100,     # 背光亮度控制
            'default_frequency': 101,        # 預設頻率控制
            'default_strength': 102,         # 預設強度控制
            'action_trigger': 103,           # 動作觸發控制
            'emergency_stop': 104,           # 急停控制
            'connection_status': 105,        # 連線狀態 (回寫)
            'vibration_status': 106,         # 震動狀態 (回寫)
            'enable_control': 107,           # 啟用外部控制
            
            # 各動作強度控制寄存器 (110-120)
            'up_strength': 110,
            'down_strength': 111,
            'left_strength': 112,
            'right_strength': 113,
            'upleft_strength': 114,
            'downleft_strength': 115,
            'upright_strength': 116,
            'downright_strength': 117,
            'horizontal_strength': 118,
            'vertical_strength': 119,
            'spread_strength': 120,
            
            # 各動作頻率控制寄存器 (130-140)
            'up_frequency': 130,
            'down_frequency': 131,
            'left_frequency': 132,
            'right_frequency': 133,
            'upleft_frequency': 134,
            'downleft_frequency': 135,
            'upright_frequency': 136,
            'downright_frequency': 137,
            'horizontal_frequency': 138,
            'vertical_frequency': 139,
            'spread_frequency': 140,
        }
        
        # 同步狀態
        self.last_register_values = {}
        self.last_update = datetime.now()
        
        # 執行緒控制
        self.modbus_monitor_thread = None
        self.status_update_thread = None
        
        self.init_flask_app()
        
    def init_flask_app(self):
        """初始化Flask應用"""
        self.app = Flask(__name__)
        self.app.secret_key = 'vibration_plate_controller_2024'
        
        # 註冊路由
        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/api/status', 'get_status', self.get_status, methods=['GET'])
        self.app.add_url_rule('/api/connect', 'connect_vp', self.connect_vp, methods=['POST'])
        self.app.add_url_rule('/api/disconnect', 'disconnect_vp', self.disconnect_vp, methods=['POST'])
        self.app.add_url_rule('/api/connect_modbus', 'connect_modbus', self.connect_modbus, methods=['POST'])
        self.app.add_url_rule('/api/disconnect_modbus', 'disconnect_modbus', self.disconnect_modbus, methods=['POST'])
        self.app.add_url_rule('/api/action', 'trigger_action', self.trigger_action, methods=['POST'])
        self.app.add_url_rule('/api/stop', 'stop_action', self.stop_action, methods=['POST'])
        self.app.add_url_rule('/api/set_brightness', 'set_brightness', self.set_brightness, methods=['POST'])
        self.app.add_url_rule('/api/set_defaults', 'set_defaults', self.set_defaults, methods=['POST'])
        self.app.add_url_rule('/api/set_action_params', 'set_action_params', self.set_action_params, methods=['POST'])
        self.app.add_url_rule('/api/config', 'update_config', self.update_config, methods=['POST'])
            
    def connect_modbus_server(self):
        """連線到ModbusTCP伺服器"""
        try:
            if self.modbus_client:
                self.modbus_client.close()
                
            self.modbus_client = ModbusTcpClient(
                host=self.config['modbus_server_ip'], 
                port=self.config['modbus_server_port']
            )
            
            if self.modbus_client.connect():
                logger.info(f"成功連線到ModbusTCP伺服器 {self.config['modbus_server_ip']}:{self.config['modbus_server_port']}")
                return True
            else:
                logger.error(f"無法連線到ModbusTCP伺服器")
                return False
                
        except Exception as e:
            logger.error(f"連線ModbusTCP伺服器失敗: {e}")
            return False
            
    def read_modbus_register(self, address):
        """讀取ModbusTCP寄存器"""
        if not self.modbus_client or not self.modbus_client.is_socket_open():
            return None
            
        try:
            response = self.modbus_client.read_holding_registers(
                address=address, 
                count=1, 
                slave=self.config['modbus_slave_id']
            )
            
            if response.isError():
                logger.warning(f"讀取寄存器 {address} 失敗: {response}")
                return None
            else:
                return response.registers[0]
                
        except Exception as e:
            logger.error(f"讀取寄存器異常: {e}")
            return None
            
    def write_modbus_register(self, address, value):
        """寫入ModbusTCP寄存器"""
        if not self.modbus_client or not self.modbus_client.is_socket_open():
            return False
            
        try:
            response = self.modbus_client.write_register(
                address=address, 
                value=value, 
                slave=self.config['modbus_slave_id']
            )
            
            if response.isError():
                logger.warning(f"寫入寄存器 {address} 失敗: {response}")
                return False
            else:
                return True
                
        except Exception as e:
            logger.error(f"寫入寄存器異常: {e}")
            return False
            
    def connect_vibration_plate(self):
        """連線震動盤"""
        try:
            if self.vibration_plate:
                self.vibration_plate.disconnect()
                
            self.vibration_plate = VibrationPlate(
                ip=self.config['vp_ip'],
                port=self.config['vp_port'],
                slave_id=self.config['vp_slave_id'],
                auto_connect=True
            )
            
            if self.vibration_plate.is_connected():
                # 初始化預設參數
                self.vibration_plate.set_backlight_brightness(self.config['default_brightness'])
                
                # 設定所有動作的預設參數
                actions = ['up', 'down', 'left', 'right', 'upleft', 'downleft', 
                          'upright', 'downright', 'horizontal', 'vertical', 'spread']
                
                for action in actions:
                    self.vibration_plate.set_action_parameters(
                        action, 
                        strength=self.config['default_strength'],
                        frequency=self.config['default_frequency']
                    )
                
                # 回寫連線狀態到ModbusTCP伺服器
                self.write_modbus_register(self.control_registers['connection_status'], 1)
                
                logger.info("震動盤連線成功並完成初始化")
                return True
            else:
                self.write_modbus_register(self.control_registers['connection_status'], 0)
                return False
                
        except Exception as e:
            logger.error(f"連線震動盤失敗: {e}")
            self.write_modbus_register(self.control_registers['connection_status'], 0)
            return False
            
    def start_modbus_monitor(self):
        """啟動ModbusTCP監控執行緒"""
        def monitor_loop():
            while self.running:
                try:
                    self.process_modbus_commands()
                    time.sleep(0.05)  # 50ms更新間隔
                except Exception as e:
                    logger.error(f"ModbusTCP監控異常: {e}")
                    time.sleep(1)
                    
        self.modbus_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.modbus_monitor_thread.start()
        logger.info("ModbusTCP監控執行緒已啟動")
        
    def process_modbus_commands(self):
        """處理ModbusTCP指令 (異步處理)"""
        if not self.modbus_client or not self.modbus_client.is_socket_open():
            return
            
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return
            
        try:
            # 檢查是否啟用外部控制
            enable_control = self.read_modbus_register(self.control_registers['enable_control'])
            if not enable_control:
                return
                
            # 檢查背光亮度變化
            brightness = self.read_modbus_register(self.control_registers['backlight_brightness'])
            if brightness is not None and brightness != self.last_register_values.get('brightness', -1):
                self.vibration_plate.set_backlight_brightness(brightness)
                self.config['default_brightness'] = brightness
                self.last_register_values['brightness'] = brightness
                logger.info(f"外部設定背光亮度: {brightness}")
                
            # 檢查預設頻率變化
            default_freq = self.read_modbus_register(self.control_registers['default_frequency'])
            if default_freq is not None and default_freq != self.last_register_values.get('default_freq', -1):
                self.config['default_frequency'] = default_freq
                self.last_register_values['default_freq'] = default_freq
                logger.info(f"外部設定預設頻率: {default_freq}")
                
            # 檢查預設強度變化
            default_strength = self.read_modbus_register(self.control_registers['default_strength'])
            if default_strength is not None and default_strength != self.last_register_values.get('default_strength', -1):
                self.config['default_strength'] = default_strength
                self.last_register_values['default_strength'] = default_strength
                logger.info(f"外部設定預設強度: {default_strength}")
                
            # 檢查動作觸發
            action_trigger = self.read_modbus_register(self.control_registers['action_trigger'])
            if action_trigger is not None and action_trigger > 0 and action_trigger != self.last_register_values.get('action_trigger', -1):
                actions = ['stop', 'up', 'down', 'left', 'right', 'upleft', 'downleft', 
                          'upright', 'downright', 'horizontal', 'vertical', 'spread']
                if action_trigger < len(actions):
                    action_name = actions[action_trigger]
                    
                    # 使用動作專屬參數或預設參數
                    strength = self.get_action_strength(action_name)
                    frequency = self.get_action_frequency(action_name)
                    
                    if action_name == 'stop':
                        self.vibration_plate.stop()
                    else:
                        self.vibration_plate.execute_action(action_name, strength, frequency)
                    
                    logger.info(f"外部觸發動作: {action_name} (強度:{strength}, 頻率:{frequency})")
                    
                self.last_register_values['action_trigger'] = action_trigger
                # 清除觸發器 (寫回0)
                self.write_modbus_register(self.control_registers['action_trigger'], 0)
                
            # 檢查急停
            emergency_stop = self.read_modbus_register(self.control_registers['emergency_stop'])
            if emergency_stop is not None and emergency_stop > 0 and emergency_stop != self.last_register_values.get('emergency_stop', -1):
                self.vibration_plate.stop()
                logger.info("外部急停觸發")
                self.last_register_values['emergency_stop'] = emergency_stop
                # 清除急停 (寫回0)
                self.write_modbus_register(self.control_registers['emergency_stop'], 0)
                
            # 同步各動作參數變化
            self.sync_action_parameters()
            
            # 更新狀態回寫
            self.update_status_to_modbus()
                
        except Exception as e:
            logger.error(f"處理ModbusTCP指令失敗: {e}")
            
    def get_action_strength(self, action):
        """取得動作強度"""
        if action == 'stop':
            return 0
            
        strength_reg = f"{action}_strength"
        if strength_reg in self.control_registers:
            strength = self.read_modbus_register(self.control_registers[strength_reg])
            if strength is not None and strength > 0:
                return strength
                
        return self.config['default_strength']
        
    def get_action_frequency(self, action):
        """取得動作頻率"""
        if action == 'stop':
            return 0
            
        frequency_reg = f"{action}_frequency"
        if frequency_reg in self.control_registers:
            frequency = self.read_modbus_register(self.control_registers[frequency_reg])
            if frequency is not None and frequency > 0:
                return frequency
                
        return self.config['default_frequency']
        
    def sync_action_parameters(self):
        """同步動作參數變化"""
        actions = ['up', 'down', 'left', 'right', 'upleft', 'downleft', 
                  'upright', 'downright', 'horizontal', 'vertical', 'spread']
        
        for action in actions:
            # 檢查強度變化
            strength_reg = f"{action}_strength"
            if strength_reg in self.control_registers:
                strength = self.read_modbus_register(self.control_registers[strength_reg])
                if strength is not None and strength != self.last_register_values.get(strength_reg, -1):
                    if strength > 0:
                        self.vibration_plate.set_action_parameters(action, strength=strength)
                        logger.info(f"外部設定 {action} 強度: {strength}")
                    self.last_register_values[strength_reg] = strength
                    
            # 檢查頻率變化
            frequency_reg = f"{action}_frequency"
            if frequency_reg in self.control_registers:
                frequency = self.read_modbus_register(self.control_registers[frequency_reg])
                if frequency is not None and frequency != self.last_register_values.get(frequency_reg, -1):
                    if frequency > 0:
                        self.vibration_plate.set_action_parameters(action, frequency=frequency)
                        logger.info(f"外部設定 {action} 頻率: {frequency}")
                    self.last_register_values[frequency_reg] = frequency
                    
    def update_status_to_modbus(self):
        """更新狀態到ModbusTCP伺服器"""
        if self.vibration_plate and self.vibration_plate.is_connected():
            try:
                status = self.vibration_plate.get_status()
                self.write_modbus_register(self.control_registers['connection_status'], 1 if status['connected'] else 0)
                self.write_modbus_register(self.control_registers['vibration_status'], 1 if status['vibration_active'] else 0)
            except Exception as e:
                logger.error(f"更新狀態到ModbusTCP失敗: {e}")
        else:
            self.write_modbus_register(self.control_registers['connection_status'], 0)
            self.write_modbus_register(self.control_registers['vibration_status'], 0)

    def start_status_monitor(self):
        """啟動狀態監控執行緒"""
        def monitor_loop():
            while self.running:
                try:
                    self.last_update = datetime.now()
                    time.sleep(1)  # 1秒更新間隔
                except Exception as e:
                    logger.error(f"狀態監控異常: {e}")
                    time.sleep(1)
                    
        self.status_update_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.status_update_thread.start()

    # Flask路由處理函數
    def index(self):
        """主頁面"""
        register_info = {
            'control_registers': self.control_registers,
            'config': self.config
        }
        return render_template('index.html', register_info=register_info)
        
    def get_status(self):
        """取得系統狀態API"""
        status = {
            'vp_connected': False,
            'modbus_connected': False,
            'vibration_active': False,
            'backlight_brightness': self.config['default_brightness'],
            'default_frequency': self.config['default_frequency'],
            'default_strength': self.config['default_strength'],
            'action_parameters': {},
            'server_running': self.running,
            'config': self.config,
            'control_registers': self.control_registers,
            'last_update': self.last_update.isoformat()
        }
        
        # 震動盤狀態
        if self.vibration_plate and self.vibration_plate.is_connected():
            vp_status = self.vibration_plate.get_status()
            status['vp_connected'] = vp_status['connected']
            status['vibration_active'] = vp_status['vibration_active']
            status['action_parameters'] = vp_status.get('action_parameters', {})
            
        # ModbusTCP狀態
        if self.modbus_client and self.modbus_client.is_socket_open():
            status['modbus_connected'] = True
            
        return jsonify(status)
        
    def connect_vp(self):
        """連線震動盤API"""
        success = self.connect_vibration_plate()
        return jsonify({'success': success, 'message': '連線成功' if success else '連線失敗'})
        
    def disconnect_vp(self):
        """中斷震動盤連線API"""
        if self.vibration_plate:
            self.vibration_plate.disconnect()
            self.write_modbus_register(self.control_registers['connection_status'], 0)
        return jsonify({'success': True, 'message': '已中斷連線'})
        
    def connect_modbus(self):
        """連線ModbusTCP伺服器API"""
        success = self.connect_modbus_server()
        return jsonify({'success': success, 'message': 'ModbusTCP連線成功' if success else 'ModbusTCP連線失敗'})
        
    def disconnect_modbus(self):
        """中斷ModbusTCP連線API"""
        if self.modbus_client:
            self.modbus_client.close()
        return jsonify({'success': True, 'message': 'ModbusTCP已中斷連線'})
        
    def trigger_action(self):
        """觸發動作API"""
        data = request.get_json()
        action = data.get('action')
        strength = data.get('strength')
        frequency = data.get('frequency')
        duration = data.get('duration')
        
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        try:
            success = self.vibration_plate.execute_action(action, strength, frequency, duration)
            return jsonify({'success': success, 'message': f'動作 {action} 執行{"成功" if success else "失敗"}'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'執行失敗: {str(e)}'})
            
    def stop_action(self):
        """停止動作API"""
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        success = self.vibration_plate.stop()
        return jsonify({'success': success, 'message': '停止成功' if success else '停止失敗'})
        
    def set_brightness(self):
        """設定背光亮度API"""
        data = request.get_json()
        brightness = data.get('brightness', 128)
        
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        success = self.vibration_plate.set_backlight_brightness(brightness)
        if success:
            self.config['default_brightness'] = brightness
            
        return jsonify({'success': success, 'message': '亮度設定成功' if success else '亮度設定失敗'})
        
    def set_defaults(self):
        """設定預設參數API"""
        data = request.get_json()
        frequency = data.get('frequency', self.config['default_frequency'])
        strength = data.get('strength', self.config['default_strength'])
        
        self.config['default_frequency'] = frequency
        self.config['default_strength'] = strength
        
        return jsonify({'success': True, 'message': '預設參數設定成功'})
        
    def set_action_params(self):
        """設定動作參數API"""
        data = request.get_json()
        action = data.get('action')
        strength = data.get('strength')
        frequency = data.get('frequency')
        
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        success = self.vibration_plate.set_action_parameters(action, strength, frequency)
        
        return jsonify({'success': success, 'message': '參數設定成功' if success else '參數設定失敗'})

    def update_config(self):
        """更新設定API"""
        data = request.get_json()
        
        if 'modbus_server_ip' in data:
            self.config['modbus_server_ip'] = data['modbus_server_ip']
        if 'modbus_server_port' in data:
            self.config['modbus_server_port'] = int(data['modbus_server_port'])
        if 'modbus_slave_id' in data:
            self.config['modbus_slave_id'] = int(data['modbus_slave_id'])
            
        return jsonify({'success': True, 'message': '設定更新成功'})

    def run(self):
        """執行主程式"""
        self.running = True
        
        # 啟動狀態監控
        self.start_status_monitor()
        
        # 嘗試連線ModbusTCP伺服器
        logger.info("正在連線ModbusTCP伺服器...")
        if self.connect_modbus_server():
            # 啟動ModbusTCP監控
            self.start_modbus_monitor()
        
        # 嘗試連線震動盤
        logger.info("正在連線震動盤...")
        self.connect_vibration_plate()
        
        # 註冊信號處理
        def signal_handler(sig, frame):
            logger.info("收到停止信號，正在關閉...")
            self.shutdown()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 啟動Flask Web伺服器
        logger.info(f"啟動Web伺服器 - http://localhost:{self.config['web_port']}")
        try:
            self.app.run(
                host='0.0.0.0',
                port=self.config['web_port'],
                debug=False,
                threaded=True
            )
        except Exception as e:
            logger.error(f"Web伺服器啟動失敗: {e}")
            
    def shutdown(self):
        """關閉程式"""
        self.running = False
        
        if self.vibration_plate:
            self.vibration_plate.stop()
            self.vibration_plate.disconnect()
            
        if self.modbus_client:
            self.modbus_client.close()
            
        logger.info("程式已關閉")

# HTML模板
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>震動盤控制系統</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
            min-height: 100vh;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #ff4444;
            animation: pulse 2s infinite;
        }
        
        .status-dot.connected { background: #44ff44; }
        .status-dot.vibrating { background: #ffaa00; }
        
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.2); opacity: 0.7; }
            100% { transform: scale(1); opacity: 1; }
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }
        
        .card h3 {
            margin-bottom: 20px;
            font-size: 1.4em;
            color: #fff;
            border-bottom: 2px solid rgba(255,255,255,0.3);
            padding-bottom: 10px;
        }
        
        .control-group {
            margin-bottom: 20px;
        }
        
        .control-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #e0e0e0;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        input[type="number"], input[type="range"], input[type="text"], select {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 8px;
            background: rgba(255,255,255,0.2);
            color: #fff;
            font-size: 14px;
        }
        
        input[type="number"]:focus, input[type="range"]:focus, input[type="text"]:focus, select:focus {
            outline: none;
            background: rgba(255,255,255,0.3);
            box-shadow: 0 0 10px rgba(255,255,255,0.3);
        }
        
        select option {
            background: #2a5298;
            color: #fff;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-success {
            background: linear-gradient(45deg, #56ab2f 0%, #a8e6cf 100%);
            color: white;
        }
        
        .btn-danger {
            background: linear-gradient(45deg, #ff416c 0%, #ff4b2b 100%);
            color: white;
        }
        
        .btn-warning {
            background: linear-gradient(45deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .action-buttons {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 20px;
        }
        
        .action-btn {
            padding: 15px;
            background: linear-gradient(45deg, #4facfe 0%, #00f2fe 100%);
            border: none;
            border-radius: 10px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .action-btn:before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .action-btn:hover:before {
            left: 100%;
        }
        
        .emergency-stop {
            background: linear-gradient(45deg, #ff0844 0%, #ffb199 100%);
            font-size: 1.2em;
            padding: 20px;
            border-radius: 15px;
            grid-column: span 3;
            position: relative;
            overflow: hidden;
        }
        
        .register-info {
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        
        .register-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        .register-table th,
        .register-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }
        
        .register-table th {
            background: rgba(255,255,255,0.1);
            font-weight: 600;
        }
        
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 10px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            transform: translateX(400px);
            transition: transform 0.3s ease;
        }
        
        .toast.show {
            transform: translateX(0);
        }
        
        .toast.success {
            background: linear-gradient(45deg, #56ab2f 0%, #a8e6cf 100%);
        }
        
        .toast.error {
            background: linear-gradient(45deg, #ff416c 0%, #ff4b2b 100%);
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .parameter-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .param-item {
            background: rgba(0,0,0,0.2);
            padding: 15px;
            border-radius: 8px;
        }
        
        .value-display {
            background: rgba(255,255,255,0.1);
            padding: 8px 12px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-weight: bold;
            margin-left: 10px;
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            
            .action-buttons {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .header h1 {
                font-size: 1.8em;
            }
            
            .status-bar {
                flex-direction: column;
                gap: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>震動盤控制系統</h1>
            <p>專業級工業震動盤遠端控制平台</p>
        </div>
        
        <div class="status-bar">
            <div class="status-indicator">
                <div class="status-dot" id="vpConnectionStatus"></div>
                <span id="vpConnectionText">震動盤: 未連線</span>
            </div>
            <div class="status-indicator">
                <div class="status-dot" id="modbusConnectionStatus"></div>
                <span id="modbusConnectionText">ModbusTCP: 未連線</span>
            </div>
            <div class="status-indicator">
                <div class="status-dot" id="vibrationStatus"></div>
                <span id="vibrationText">震動狀態: 停止</span>
            </div>
            <div class="status-indicator">
                <span id="lastUpdate">最後更新: --</span>
            </div>
        </div>
        
        <div class="grid">
            <!-- ModbusTCP連線設定 -->
            <div class="card">
                <h3>ModbusTCP伺服器設定</h3>
                <div class="control-group">
                    <label for="modbusServerIp">伺服器IP位址</label>
                    <input type="text" id="modbusServerIp" value="{{ register_info.config.modbus_server_ip }}">
                </div>
                <div class="control-group">
                    <label for="modbusServerPort">埠口</label>
                    <input type="number" id="modbusServerPort" value="{{ register_info.config.modbus_server_port }}">
                </div>
                <div class="control-group">
                    <label for="modbusSlaveId">從機ID</label>
                    <input type="number" id="modbusSlaveId" value="{{ register_info.config.modbus_slave_id }}">
                </div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="updateModbusConfig()">更新設定</button>
                    <button class="btn btn-success" onclick="connectModbus()">連線</button>
                    <button class="btn btn-danger" onclick="disconnectModbus()">中斷</button>
                </div>
            </div>
            
            <!-- 震動盤連線控制 -->
            <div class="card">
                <h3>震動盤連線控制</h3>
                <div class="control-group">
                    <label>震動盤位址: <span class="value-display">{{ register_info.config.vp_ip }}:{{ register_info.config.vp_port }}</span></label>
                    <label>從機ID: <span class="value-display">{{ register_info.config.vp_slave_id }}</span></label>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button class="btn btn-success" onclick="connectVP()">連線設備</button>
                    <button class="btn btn-danger" onclick="disconnectVP()">中斷連線</button>
                </div>
            </div>
            
            <!-- 背光控制 -->
            <div class="card">
                <h3>背光控制</h3>
                <div class="control-group">
                    <label for="brightness">背光亮度 (0-255)</label>
                    <div class="input-group">
                        <input type="range" id="brightnessSlider" min="0" max="255" value="128" onchange="updateBrightness()">
                        <input type="number" id="brightnessValue" min="0" max="255" value="128" onchange="setBrightnessFromInput()">
                    </div>
                </div>
                <button class="btn btn-primary" onclick="setBrightness()">套用亮度</button>
            </div>
            
            <!-- 預設參數 -->
            <div class="card">
                <h3>預設參數</h3>
                <div class="control-group">
                    <label for="defaultFreq">預設頻率 (0-255)</label>
                    <input type="number" id="defaultFreq" min="0" max="255" value="100">
                </div>
                <div class="control-group">
                    <label for="defaultStrength">預設強度 (0-255)</label>
                    <input type="number" id="defaultStrength" min="0" max="255" value="100">
                </div>
                <button class="btn btn-primary" onclick="setDefaults()">儲存預設值</button>
            </div>
            
            <!-- 動作參數設定 -->
            <div class="card">
                <h3>動作參數設定</h3>
                <div class="control-group">
                    <label for="actionSelect">選擇動作</label>
                    <select id="actionSelect">
                        <option value="up">向上</option>
                        <option value="down">向下</option>
                        <option value="left">向左</option>
                        <option value="right">向右</option>
                        <option value="upleft">左上</option>
                        <option value="downleft">左下</option>
                        <option value="upright">右上</option>
                        <option value="downright">右下</option>
                        <option value="horizontal">水平</option>
                        <option value="vertical">垂直</option>
                        <option value="spread">散開</option>
                    </select>
                </div>
                <div class="control-group">
                    <label for="actionStrength">強度 (0-255)</label>
                    <input type="number" id="actionStrength" min="0" max="255" value="100">
                </div>
                <div class="control-group">
                    <label for="actionFrequency">頻率 (0-255)</label>
                    <input type="number" id="actionFrequency" min="0" max="255" value="100">
                </div>
                <button class="btn btn-primary" onclick="setActionParams()">設定參數</button>
            </div>
        </div>
        
        <!-- 動作控制區域 -->
        <div class="card">
            <h3>動作控制</h3>
            <div class="action-buttons">
                <button class="action-btn" onclick="triggerAction('upleft')">左上</button>
                <button class="action-btn" onclick="triggerAction('up')">向上</button>
                <button class="action-btn" onclick="triggerAction('upright')">右上</button>
                
                <button class="action-btn" onclick="triggerAction('left')">向左</button>
                <button class="action-btn" onclick="triggerAction('stop')" style="background: linear-gradient(45deg, #666 0%, #999 100%);">停止</button>
                <button class="action-btn" onclick="triggerAction('right')">向右</button>
                
                <button class="action-btn" onclick="triggerAction('downleft')">左下</button>
                <button class="action-btn" onclick="triggerAction('down')">向下</button>
                <button class="action-btn" onclick="triggerAction('downright')">右下</button>
                
                <button class="action-btn" onclick="triggerAction('horizontal')">水平</button>
                <button class="action-btn" onclick="triggerAction('vertical')">垂直</button>
                <button class="action-btn" onclick="triggerAction('spread')">散開</button>
                
                <button class="action-btn emergency-stop" onclick="emergencyStop()">緊急停止</button>
            </div>
        </div>
        
        <!-- ModbusTCP寄存器資訊 -->
        <div class="card register-info">
            <h3>ModbusTCP寄存器映射表</h3>
            <p>外部設備可透過以下寄存器位址控制震動盤：</p>
            <p><strong>伺服器位址:</strong> {{ register_info.config.modbus_server_ip }}:{{ register_info.config.modbus_server_port }}</p>
            
            <table class="register-table">
                <thead>
                    <tr>
                        <th>功能</th>
                        <th>寄存器位址</th>
                        <th>說明</th>
                        <th>讀寫</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td>背光亮度控制</td><td>{{ register_info.control_registers.backlight_brightness }}</td><td>0-255</td><td>讀寫</td></tr>
                    <tr><td>預設頻率控制</td><td>{{ register_info.control_registers.default_frequency }}</td><td>0-255</td><td>讀寫</td></tr>
                    <tr><td>預設強度控制</td><td>{{ register_info.control_registers.default_strength }}</td><td>0-255</td><td>讀寫</td></tr>
                    <tr><td>動作觸發</td><td>{{ register_info.control_registers.action_trigger }}</td><td>0-11 (0=停止, 1-11=動作)</td><td>寫</td></tr>
                    <tr><td>緊急停止</td><td>{{ register_info.control_registers.emergency_stop }}</td><td>寫入任意值觸發停止</td><td>寫</td></tr>
                    <tr><td>啟用外部控制</td><td>{{ register_info.control_registers.enable_control }}</td><td>0=停用, 1=啟用</td><td>讀寫</td></tr>
                    <tr><td>連線狀態</td><td>{{ register_info.control_registers.connection_status }}</td><td>0=未連線, 1=已連線</td><td>讀</td></tr>
                    <tr><td>震動狀態</td><td>{{ register_info.control_registers.vibration_status }}</td><td>0=停止, 1=運行</td><td>讀</td></tr>
                </tbody>
            </table>
            
            <details style="margin-top: 20px;">
                <summary style="cursor: pointer; font-weight: 600;">動作強度寄存器 (110-120)</summary>
                <div class="parameter-grid">
                    <div class="param-item">向上強度: {{ register_info.control_registers.up_strength }}</div>
                    <div class="param-item">向下強度: {{ register_info.control_registers.down_strength }}</div>
                    <div class="param-item">向左強度: {{ register_info.control_registers.left_strength }}</div>
                    <div class="param-item">向右強度: {{ register_info.control_registers.right_strength }}</div>
                    <div class="param-item">左上強度: {{ register_info.control_registers.upleft_strength }}</div>
                    <div class="param-item">左下強度: {{ register_info.control_registers.downleft_strength }}</div>
                    <div class="param-item">右上強度: {{ register_info.control_registers.upright_strength }}</div>
                    <div class="param-item">右下強度: {{ register_info.control_registers.downright_strength }}</div>
                    <div class="param-item">水平強度: {{ register_info.control_registers.horizontal_strength }}</div>
                    <div class="param-item">垂直強度: {{ register_info.control_registers.vertical_strength }}</div>
                    <div class="param-item">散開強度: {{ register_info.control_registers.spread_strength }}</div>
                </div>
            </details>
            
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; font-weight: 600;">動作頻率寄存器 (130-140)</summary>
                <div class="parameter-grid">
                    <div class="param-item">向上頻率: {{ register_info.control_registers.up_frequency }}</div>
                    <div class="param-item">向下頻率: {{ register_info.control_registers.down_frequency }}</div>
                    <div class="param-item">向左頻率: {{ register_info.control_registers.left_frequency }}</div>
                    <div class="param-item">向右頻率: {{ register_info.control_registers.right_frequency }}</div>
                    <div class="param-item">左上頻率: {{ register_info.control_registers.upleft_frequency }}</div>
                    <div class="param-item">左下頻率: {{ register_info.control_registers.downleft_frequency }}</div>
                    <div class="param-item">右上頻率: {{ register_info.control_registers.upright_frequency }}</div>
                    <div class="param-item">右下頻率: {{ register_info.control_registers.downright_frequency }}</div>
                    <div class="param-item">水平頻率: {{ register_info.control_registers.horizontal_frequency }}</div>
                    <div class="param-item">垂直頻率: {{ register_info.control_registers.vertical_frequency }}</div>
                    <div class="param-item">散開頻率: {{ register_info.control_registers.spread_frequency }}</div>
                </div>
            </details>
        </div>
    </div>

    <script>
        let statusUpdateInterval;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            updateStatus();
            startStatusUpdates();
            
            // 亮度滑塊和輸入框同步
            document.getElementById('brightnessSlider').addEventListener('input', function() {
                document.getElementById('brightnessValue').value = this.value;
            });
        });
        
        // 開始狀態更新
        function startStatusUpdates() {
            statusUpdateInterval = setInterval(updateStatus, 2000); // 2秒更新一次
        }
        
        // 更新系統狀態
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                
                // 更新震動盤連線狀態
                const vpConnectionDot = document.getElementById('vpConnectionStatus');
                const vpConnectionText = document.getElementById('vpConnectionText');
                if (status.vp_connected) {
                    vpConnectionDot.className = 'status-dot connected';
                    vpConnectionText.textContent = '震動盤: 已連線';
                } else {
                    vpConnectionDot.className = 'status-dot';
                    vpConnectionText.textContent = '震動盤: 未連線';
                }
                
                // 更新ModbusTCP連線狀態
                const modbusConnectionDot = document.getElementById('modbusConnectionStatus');
                const modbusConnectionText = document.getElementById('modbusConnectionText');
                if (status.modbus_connected) {
                    modbusConnectionDot.className = 'status-dot connected';
                    modbusConnectionText.textContent = 'ModbusTCP: 已連線';
                } else {
                    modbusConnectionDot.className = 'status-dot';
                    modbusConnectionText.textContent = 'ModbusTCP: 未連線';
                }
                
                // 更新震動狀態
                const vibrationDot = document.getElementById('vibrationStatus');
                const vibrationText = document.getElementById('vibrationText');
                if (status.vibration_active) {
                    vibrationDot.className = 'status-dot vibrating';
                    vibrationText.textContent = '震動狀態: 運行中';
                } else {
                    vibrationDot.className = 'status-dot';
                    vibrationText.textContent = '震動狀態: 停止';
                }
                
                // 更新最後更新時間
                const lastUpdate = new Date(status.last_update);
                document.getElementById('lastUpdate').textContent = 
                    '最後更新: ' + lastUpdate.toLocaleTimeString();
                
                // 更新參數值
                if (status.backlight_brightness !== undefined) {
                    document.getElementById('brightnessSlider').value = status.backlight_brightness;
                    document.getElementById('brightnessValue').value = status.backlight_brightness;
                }
                
                if (status.default_frequency !== undefined) {
                    document.getElementById('defaultFreq').value = status.default_frequency;
                }
                
                if (status.default_strength !== undefined) {
                    document.getElementById('defaultStrength').value = status.default_strength;
                }
                
            } catch (error) {
                console.error('狀態更新失敗:', error);
            }
        }
        
        // 顯示提示訊息
        function showToast(message, type = 'success') {
            // 移除現有toast
            const existingToast = document.querySelector('.toast');
            if (existingToast) {
                existingToast.remove();
            }
            
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);
            
            // 顯示動畫
            setTimeout(() => toast.classList.add('show'), 100);
            
            // 自動隱藏
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        // API呼叫函數
        async function apiCall(url, data = null, method = 'POST') {
            try {
                const options = {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json',
                    }
                };
                
                if (data) {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(url, options);
                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                } else {
                    showToast(result.message, 'error');
                }
                
                // 立即更新狀態
                setTimeout(updateStatus, 100);
                
                return result;
            } catch (error) {
                showToast('網路錯誤: ' + error.message, 'error');
                return { success: false, message: error.message };
            }
        }
        
        // 更新ModbusTCP設定
        async function updateModbusConfig() {
            const ip = document.getElementById('modbusServerIp').value;
            const port = document.getElementById('modbusServerPort').value;
            const slaveId = document.getElementById('modbusSlaveId').value;
            
            await apiCall('/api/config', {
                modbus_server_ip: ip,
                modbus_server_port: parseInt(port),
                modbus_slave_id: parseInt(slaveId)
            });
        }
        
        // 連線ModbusTCP
        async function connectModbus() {
            await apiCall('/api/connect_modbus');
        }
        
        // 中斷ModbusTCP連線
        async function disconnectModbus() {
            await apiCall('/api/disconnect_modbus');
        }
        
        // 連線震動盤
        async function connectVP() {
            await apiCall('/api/connect');
        }
        
        // 中斷震動盤連線
        async function disconnectVP() {
            await apiCall('/api/disconnect');
        }
        
        // 觸發動作
        async function triggerAction(action) {
            const strength = document.getElementById('defaultStrength').value;
            const frequency = document.getElementById('defaultFreq').value;
            
            await apiCall('/api/action', {
                action: action,
                strength: parseInt(strength),
                frequency: parseInt(frequency)
            });
        }
        
        // 緊急停止
        async function emergencyStop() {
            await apiCall('/api/stop');
        }
        
        // 設定背光亮度
        async function setBrightness() {
            const brightness = document.getElementById('brightnessValue').value;
            await apiCall('/api/set_brightness', {
                brightness: parseInt(brightness)
            });
        }
        
        // 從輸入框設定亮度
        function setBrightnessFromInput() {
            const value = document.getElementById('brightnessValue').value;
            document.getElementById('brightnessSlider').value = value;
        }
        
        // 更新亮度顯示
        function updateBrightness() {
            const value = document.getElementById('brightnessSlider').value;
            document.getElementById('brightnessValue').value = value;
        }
        
        // 設定預設參數
        async function setDefaults() {
            const frequency = document.getElementById('defaultFreq').value;
            const strength = document.getElementById('defaultStrength').value;
            
            await apiCall('/api/set_defaults', {
                frequency: parseInt(frequency),
                strength: parseInt(strength)
            });
        }
        
        // 設定動作參數
        async function setActionParams() {
            const action = document.getElementById('actionSelect').value;
            const strength = document.getElementById('actionStrength').value;
            const frequency = document.getElementById('actionFrequency').value;
            
            await apiCall('/api/set_action_params', {
                action: action,
                strength: parseInt(strength),
                frequency: parseInt(frequency)
            });
        }
        
        // 鍵盤快捷鍵支援
        document.addEventListener('keydown', function(event) {
            if (event.ctrlKey || event.altKey) return;
            
            switch(event.key) {
                case 'ArrowUp':
                    event.preventDefault();
                    triggerAction('up');
                    break;
                case 'ArrowDown':
                    event.preventDefault();
                    triggerAction('down');
                    break;
                case 'ArrowLeft':
                    event.preventDefault();
                    triggerAction('left');
                    break;
                case 'ArrowRight':
                    event.preventDefault();
                    triggerAction('right');
                    break;
                case ' ':
                case 'Escape':
                    event.preventDefault();
                    emergencyStop();
                    break;
            }
        });
        
        // 頁面卸載時清理
        window.addEventListener('beforeunload', function() {
            if (statusUpdateInterval) {
                clearInterval(statusUpdateInterval);
            }
        });
    </script>
</body>
</html>'''

# 建立模板檔案夾和檔案
import os

def create_templates():
    """建立模板檔案夾和HTML檔案"""
    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    with open(os.path.join(templates_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(HTML_TEMPLATE)

if __name__ == '__main__':
    # 建立模板檔案
    create_templates()
    
    # 啟動控制器
    controller = VibrationPlateController()
    
    try:
        controller.run()
    except KeyboardInterrupt:
        logger.info("收到中斷信號")
    finally:
        controller.shutdown()