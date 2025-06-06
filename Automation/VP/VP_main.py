from flask import Flask, render_template, request, jsonify
from vibration_plate import VibrationPlate
import threading
import time
import logging
import signal
import sys
from datetime import datetime
from pymodbus.client import ModbusTcpClient

# 設定日誌
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
        self.backlight_on = True  # 背光開關狀態
        self.external_control_enabled = False  # 外部控制啟用狀態
        
        # 控制寄存器定義 (可由外部ModbusTCP伺服器控制)
        self.control_registers = {
            # 基本控制寄存器 (100-109)
            'backlight_brightness': 100,     # 背光亮度控制 (0-255)
            'default_frequency': 101,        # 預設頻率控制 (0-255)
            'default_strength': 102,         # 預設強度控制 (0-255)
            'action_trigger': 103,           # 動作觸發控制 (0-11, 0=停止)
            'emergency_stop': 104,           # 急停控制 (寫入任意值觸發)
            'connection_status': 105,        # 連線狀態 (0=未連線, 1=已連線) [只讀]
            'vibration_status': 106,         # 震動狀態 (0=停止, 1=運行) [只讀]
            'enable_control': 107,           # 啟用外部控制 (0=停用, 1=啟用)
            'backlight_switch': 108,         # 背光開關控制 (0=關閉, 1=開啟)
            
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
        self.app.add_url_rule('/api/toggle_backlight', 'toggle_backlight', self.toggle_backlight, methods=['POST'])
        self.app.add_url_rule('/api/set_defaults', 'set_defaults', self.set_defaults, methods=['POST'])
        self.app.add_url_rule('/api/set_action_params', 'set_action_params', self.set_action_params, methods=['POST'])
        self.app.add_url_rule('/api/config', 'update_config', self.update_config, methods=['POST'])
        self.app.add_url_rule('/api/register_values', 'get_register_values', self.get_register_values, methods=['GET'])
        self.app.add_url_rule('/api/set_external_control', 'set_external_control', self.set_external_control, methods=['POST'])
            
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
                # 初始化寄存器
                self.init_modbus_registers()
                return True
            else:
                logger.error(f"無法連線到ModbusTCP伺服器")
                return False
                
        except Exception as e:
            logger.error(f"連線ModbusTCP伺服器失敗: {e}")
            return False

    def init_modbus_registers(self):
        """初始化ModbusTCP寄存器"""
        try:
            # 初始化基本參數
            self.write_modbus_register(self.control_registers['backlight_brightness'], self.config['default_brightness'])
            self.write_modbus_register(self.control_registers['default_frequency'], self.config['default_frequency'])
            self.write_modbus_register(self.control_registers['default_strength'], self.config['default_strength'])
            self.write_modbus_register(self.control_registers['backlight_switch'], int(self.backlight_on))
            self.write_modbus_register(self.control_registers['enable_control'], int(self.external_control_enabled))
            logger.info("ModbusTCP寄存器初始化完成")
        except Exception as e:
            logger.error(f"ModbusTCP寄存器初始化失敗: {e}")
            
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
                logger.debug(f"讀取寄存器 {address} 失敗: {response}")
                return None
            else:
                return response.registers[0]
                
        except Exception as e:
            logger.debug(f"讀取寄存器異常: {e}")
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
                logger.debug(f"寫入寄存器 {address} 失敗: {response}")
                return False
            else:
                return True
                
        except Exception as e:
            logger.debug(f"寫入寄存器異常: {e}")
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
                # 🔧 修正：初始化時設定背光狀態
                self.vibration_plate.set_backlight(self.backlight_on)
                
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
            # 🔧 修正：先檢查外部控制狀態變化
            enable_control = self.read_modbus_register(self.control_registers['enable_control'])
            if enable_control is not None:
                old_external_control = self.external_control_enabled
                self.external_control_enabled = bool(enable_control)
                
                # 如果外部控制狀態改變，記錄日誌
                if old_external_control != self.external_control_enabled:
                    logger.info(f"外部控制狀態變更: {'啟用' if self.external_control_enabled else '停用'}")

            # 🔧 修正：只有在外部控制啟用時才處理外部指令
            if not self.external_control_enabled:
                # 外部控制停用時，仍然更新狀態但不處理控制指令
                self.update_status_to_modbus()
                return
                
            # 檢查背光開關變化
            backlight_switch = self.read_modbus_register(self.control_registers['backlight_switch'])
            if backlight_switch is not None and backlight_switch != self.last_register_values.get('backlight_switch', -1):
                # 🔧 修正：直接調用震動盤的背光控制
                success = self.vibration_plate.set_backlight(bool(backlight_switch))
                if success:
                    self.backlight_on = bool(backlight_switch)
                    logger.info(f"外部設定背光開關: {'開啟' if backlight_switch else '關閉'}")
                else:
                    logger.warning(f"外部設定背光開關失敗")
                self.last_register_values['backlight_switch'] = backlight_switch
                
            # 檢查背光亮度變化
            brightness = self.read_modbus_register(self.control_registers['backlight_brightness'])
            if brightness is not None and brightness != self.last_register_values.get('brightness', -1):
                success = self.vibration_plate.set_backlight_brightness(brightness)
                if success:
                    self.config['default_brightness'] = brightness
                    logger.info(f"外部設定背光亮度: {brightness}")
                self.last_register_values['brightness'] = brightness
                
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
                        logger.debug(f"外部設定 {action} 強度: {strength}")
                    self.last_register_values[strength_reg] = strength
                    
            # 檢查頻率變化
            frequency_reg = f"{action}_frequency"
            if frequency_reg in self.control_registers:
                frequency = self.read_modbus_register(self.control_registers[frequency_reg])
                if frequency is not None and frequency != self.last_register_values.get(frequency_reg, -1):
                    if frequency > 0:
                        self.vibration_plate.set_action_parameters(action, frequency=frequency)
                        logger.debug(f"外部設定 {action} 頻率: {frequency}")
                    self.last_register_values[frequency_reg] = frequency
                    
    def update_status_to_modbus(self):
        """更新狀態到ModbusTCP伺服器"""
        try:
            if self.vibration_plate and self.vibration_plate.is_connected():
                status = self.vibration_plate.get_status()
                self.write_modbus_register(self.control_registers['connection_status'], 1 if status['connected'] else 0)
                self.write_modbus_register(self.control_registers['vibration_status'], 1 if status['vibration_active'] else 0)
                # 🔧 修正：同步背光狀態到ModbusTCP
                self.write_modbus_register(self.control_registers['backlight_switch'], int(self.backlight_on))
            else:
                self.write_modbus_register(self.control_registers['connection_status'], 0)
                self.write_modbus_register(self.control_registers['vibration_status'], 0)
        except Exception as e:
            logger.debug(f"更新狀態到ModbusTCP失敗: {e}")

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
            'backlight_on': self.backlight_on,
            'external_control_enabled': self.external_control_enabled,  # 🔧 新增
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

    def get_register_values(self):
        """取得所有寄存器數值API"""
        try:
            if not self.modbus_client or not self.modbus_client.is_socket_open():
                return jsonify({'connected': False, 'registers': {}})
                
            registers = {}
            
            # 基本寄存器 (100-108)
            for addr in range(100, 109):
                value = self.read_modbus_register(addr)
                registers[addr] = value if value is not None else 0
                
            # 動作強度寄存器 (110-120)
            for addr in range(110, 121):
                value = self.read_modbus_register(addr)
                registers[addr] = value if value is not None else 0
                
            # 動作頻率寄存器 (130-140)
            for addr in range(130, 141):
                value = self.read_modbus_register(addr)
                registers[addr] = value if value is not None else 0
                
            return jsonify({
                'connected': True,
                'registers': registers,
                'external_control_enabled': self.external_control_enabled
            })
            
        except Exception as e:
            logger.error(f"取得寄存器數值失敗: {e}")
            return jsonify({'connected': False, 'registers': {}, 'error': str(e)})

    def set_external_control(self):
        """設定外部控制API"""
        try:
            data = request.get_json()
            enable = data.get('enable', False)
            
            if not self.modbus_client or not self.modbus_client.is_socket_open():
                return jsonify({'success': False, 'message': 'ModbusTCP未連線'})
                
            # 寫入寄存器107
            success = self.write_modbus_register(self.control_registers['enable_control'], 1 if enable else 0)
            
            if success:
                self.external_control_enabled = enable
                logger.info(f"外部控制{'啟用' if enable else '停用'}")
                
            return jsonify({
                'success': success, 
                'message': f'外部控制已{"啟用" if enable else "停用"}' if success else '設定失敗',
                'external_control_enabled': self.external_control_enabled
            })
        except Exception as e:
            logger.error(f"設定外部控制失敗: {e}")
            return jsonify({'success': False, 'message': f'設定失敗: {str(e)}'})
        
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
        
        # 🔧 修正：檢查外部控制狀態
        if self.external_control_enabled:
            return jsonify({'success': False, 'message': '外部控制已啟用，本地操作被禁用'})
        
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        try:
            success = self.vibration_plate.execute_action(action, strength, frequency, duration)
            return jsonify({'success': success, 'message': f'動作 {action} 執行{"成功" if success else "失敗"}'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'執行失敗: {str(e)}'})
            
    def stop_action(self):
        """停止動作API"""
        # 🔧 修正：急停功能不受外部控制限制
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        success = self.vibration_plate.stop()
        return jsonify({'success': success, 'message': '停止成功' if success else '停止失敗'})
        
    def set_brightness(self):
        """設定背光亮度API"""
        data = request.get_json()
        brightness = data.get('brightness', 128)
        
        # 🔧 修正：檢查外部控制狀態
        if self.external_control_enabled:
            return jsonify({'success': False, 'message': '外部控制已啟用，本地操作被禁用'})
        
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        success = self.vibration_plate.set_backlight_brightness(brightness)
        if success:
            self.config['default_brightness'] = brightness
            # 同步到ModbusTCP
            self.write_modbus_register(self.control_registers['backlight_brightness'], brightness)
            
        return jsonify({'success': success, 'message': '亮度設定成功' if success else '亮度設定失敗'})
        
    def toggle_backlight(self):
        """切換背光開關API"""
        data = request.get_json()
        state = data.get('state', not self.backlight_on)  # 如果沒指定狀態則切換
        
        # 🔧 修正：檢查外部控制狀態
        if self.external_control_enabled:
            return jsonify({'success': False, 'message': '外部控制已啟用，本地操作被禁用'})
        
        if not self.vibration_plate or not self.vibration_plate.is_connected():
            return jsonify({'success': False, 'message': '震動盤未連線'})
            
        success = self.vibration_plate.set_backlight(state)
        if success:
            self.backlight_on = state
            # 更新ModbusTCP寄存器
            self.write_modbus_register(self.control_registers['backlight_switch'], int(state))
            
        return jsonify({
            'success': success, 
            'message': f'背光{"開啟" if state else "關閉"}成功' if success else '背光開關設定失敗',
            'backlight_on': self.backlight_on
        })
        
    def set_defaults(self):
        """設定預設參數API"""
        data = request.get_json()
        frequency = data.get('frequency', self.config['default_frequency'])
        strength = data.get('strength', self.config['default_strength'])
        
        # 🔧 修正：檢查外部控制狀態
        if self.external_control_enabled:
            return jsonify({'success': False, 'message': '外部控制已啟用，本地操作被禁用'})
        
        self.config['default_frequency'] = frequency
        self.config['default_strength'] = strength
        
        # 同步到ModbusTCP
        self.write_modbus_register(self.control_registers['default_frequency'], frequency)
        self.write_modbus_register(self.control_registers['default_strength'], strength)
        
        return jsonify({'success': True, 'message': '預設參數設定成功'})
        
    def set_action_params(self):
        """設定動作參數API"""
        data = request.get_json()
        action = data.get('action')
        strength = data.get('strength')
        frequency = data.get('frequency')
        
        # 🔧 修正：檢查外部控制狀態
        if self.external_control_enabled:
            return jsonify({'success': False, 'message': '外部控制已啟用，本地操作被禁用'})
        
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

if __name__ == '__main__':
    try:
        # 啟動控制器
        controller = VibrationPlateController()
        controller.run()
        
    except KeyboardInterrupt:
        logger.info("收到中斷信號")
    except Exception as e:
        logger.error(f"程式啟動失敗: {e}")
    finally:
        if 'controller' in locals():
            controller.shutdown()