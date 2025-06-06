from pymodbus.client import ModbusTcpClient
import threading
import time
import logging

class VibrationPlate:
    """
    震動盤控制API類別
    支援ModbusTCP通訊協定
    """
    
    # 動作編碼映射
    ACTION_MAP = {
        'stop': 0,
        'up': 1,
        'down': 2,
        'left': 3,
        'right': 4,
        'upleft': 5,
        'downleft': 6,
        'upright': 7,
        'downright': 8,
        'horizontal': 9,
        'vertical': 10,
        'spread': 11
    }
    
    # 寄存器位址定義
    REGISTERS = {
        'single_action_trigger': 4,      # 單一動作觸發
        'vibration_status': 6,           # 震動盤狀態
        'backlight_test': 58,            # 背光測試開關
        'backlight_brightness': 46,      # 背光亮度
        
        # 強度寄存器 (20-30)
        'strength': {
            'up': 20, 'down': 21, 'left': 22, 'right': 23,
            'upleft': 24, 'downleft': 25, 'upright': 26, 'downright': 27,
            'horizontal': 28, 'vertical': 29, 'spread': 30
        },
        
        # 頻率寄存器 (60-70)
        'frequency': {
            'up': 60, 'down': 61, 'left': 62, 'right': 63,
            'upleft': 64, 'downleft': 65, 'upright': 66, 'downright': 67,
            'horizontal': 68, 'vertical': 69, 'spread': 70
        }
    }

    def __init__(self, ip, port, slave_id, auto_connect=True):
        """
        初始化震動盤控制器
        
        Args:
            ip: ModbusTCP伺服器IP位址
            port: ModbusTCP伺服器埠口
            slave_id: 從機ID
            auto_connect: 是否自動連線
        """
        self.ip = ip
        self.port = port
        self.slave_id = slave_id
        self.client = None
        self.connected = False
        self.lock = threading.Lock()
        
        # 設定日誌
        self.logger = logging.getLogger(f"VibrationPlate_{ip}")
        
        if auto_connect:
            self.connect()

    def connect(self):
        """連線到ModbusTCP伺服器"""
        try:
            if self.client:
                self.client.close()
            
            self.client = ModbusTcpClient(host=self.ip, port=self.port)
            
            if self.client.connect():
                self.connected = True
                self.logger.info(f"成功連線到震動盤 {self.ip}:{self.port} (從機ID: {self.slave_id})")
                return True
            else:
                self.connected = False
                self.logger.error(f"無法連線到震動盤 {self.ip}:{self.port}")
                return False
                
        except Exception as e:
            self.connected = False
            self.logger.error(f"連線異常: {e}")
            return False

    def disconnect(self):
        """中斷連線"""
        try:
            if self.client:
                self.client.close()
                self.connected = False
                self.logger.info("震動盤連線已中斷")
        except Exception as e:
            self.logger.error(f"中斷連線時發生錯誤: {e}")

    def is_connected(self):
        """檢查連線狀態"""
        return self.connected and self.client and self.client.is_socket_open()

    def write_register(self, address, value):
        """
        寫入單個寄存器
        
        Args:
            address: 寄存器位址
            value: 寫入值
            
        Returns:
            bool: 操作是否成功
        """
        if not self.is_connected():
            self.logger.warning("設備未連線，嘗試重新連線...")
            if not self.connect():
                return False

        try:
            with self.lock:
                response = self.client.write_register(
                    address=address, 
                    value=value, 
                    slave=self.slave_id
                )
                
                if response.isError():
                    self.logger.error(f"寫入寄存器 {address} 失敗: {response}")
                    return False
                else:
                    self.logger.debug(f"寄存器 {address} 設定為 {value}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"寫入寄存器異常: {e}")
            self.connected = False
            return False

    def read_register(self, address):
        """
        讀取單個寄存器
        
        Args:
            address: 寄存器位址
            
        Returns:
            int or None: 寄存器值，失敗返回None
        """
        if not self.is_connected():
            self.logger.warning("設備未連線，嘗試重新連線...")
            if not self.connect():
                return None

        try:
            with self.lock:
                response = self.client.read_holding_registers(
                    address=address, 
                    count=1, 
                    slave=self.slave_id
                )
                
                if response.isError():
                    self.logger.error(f"讀取寄存器 {address} 失敗: {response}")
                    return None
                else:
                    return response.registers[0]
                    
        except Exception as e:
            self.logger.error(f"讀取寄存器異常: {e}")
            self.connected = False
            return None

    def read_multiple_registers(self, start_address, count):
        """
        批量讀取寄存器
        
        Args:
            start_address: 起始位址
            count: 讀取數量
            
        Returns:
            list or None: 寄存器值列表，失敗返回None
        """
        if not self.is_connected():
            if not self.connect():
                return None

        try:
            with self.lock:
                response = self.client.read_holding_registers(
                    address=start_address, 
                    count=count, 
                    slave=self.slave_id
                )
                
                if response.isError():
                    self.logger.error(f"批量讀取寄存器失敗: {response}")
                    return None
                else:
                    return response.registers
                    
        except Exception as e:
            self.logger.error(f"批量讀取寄存器異常: {e}")
            self.connected = False
            return None

    def set_backlight(self, state):
        """
        設定背光開關
        
        Args:
            state: True開啟，False關閉
            
        Returns:
            bool: 操作是否成功
        """
        return self.write_register(self.REGISTERS['backlight_test'], int(bool(state)))

    def set_backlight_brightness(self, brightness):
        """
        設定背光亮度
        
        Args:
            brightness: 亮度值 (0-255)
            
        Returns:
            bool: 操作是否成功
        """
        brightness = max(0, min(255, int(brightness)))
        return self.write_register(self.REGISTERS['backlight_brightness'], brightness)

    def trigger_action(self, action):
        """
        觸發指定動作
        
        Args:
            action: 動作名稱或編碼
            
        Returns:
            bool: 操作是否成功
        """
        if isinstance(action, str):
            if action not in self.ACTION_MAP:
                self.logger.error(f"未知動作: {action}")
                return False
            action_code = self.ACTION_MAP[action]
        else:
            action_code = int(action)
            
        return self.write_register(self.REGISTERS['single_action_trigger'], action_code)

    def set_action_parameters(self, action, strength=None, frequency=None):
        """
        設定動作參數
        
        Args:
            action: 動作名稱
            strength: 強度值
            frequency: 頻率值
            
        Returns:
            bool: 操作是否成功
        """
        success = True
        
        if action not in self.REGISTERS['strength']:
            self.logger.error(f"未知動作: {action}")
            return False
            
        if strength is not None:
            strength = max(0, min(255, int(strength)))
            success &= self.write_register(self.REGISTERS['strength'][action], strength)
            
        if frequency is not None:
            frequency = max(0, min(255, int(frequency)))
            success &= self.write_register(self.REGISTERS['frequency'][action], frequency)
            
        return success

    def execute_action(self, action, strength=None, frequency=None, duration=None):
        """
        執行動作（設定參數並觸發）
        
        Args:
            action: 動作名稱
            strength: 強度值
            frequency: 頻率值
            duration: 持續時間(秒)，None表示不自動停止
            
        Returns:
            bool: 操作是否成功
        """
        # 設定參數
        if not self.set_action_parameters(action, strength, frequency):
            return False
            
        # 觸發動作
        if not self.trigger_action(action):
            return False
            
        # 如果指定了持續時間，則延時後停止
        if duration is not None:
            def stop_after_delay():
                time.sleep(duration)
                self.stop()
                
            threading.Thread(target=stop_after_delay, daemon=True).start()
            
        return True

    def stop(self):
        """停止所有動作"""
        success = self.trigger_action('stop')
        if success:
            self.logger.info("所有動作已停止")
        return success

    def get_status(self):
        """
        取得震動盤狀態
        
        Returns:
            dict: 狀態資訊
        """
        status = {
            'connected': self.is_connected(),
            'vibration_active': False,
            'backlight_brightness': 0,
            'action_parameters': {}
        }
        
        if not self.is_connected():
            return status
            
        # 讀取震動狀態
        vibration_status = self.read_register(self.REGISTERS['vibration_status'])
        if vibration_status is not None:
            status['vibration_active'] = bool(vibration_status)
            
        # 讀取背光亮度
        brightness = self.read_register(self.REGISTERS['backlight_brightness'])
        if brightness is not None:
            status['backlight_brightness'] = brightness
            
        # 讀取所有動作參數
        strength_registers = self.read_multiple_registers(20, 11)  # 強度寄存器20-30
        frequency_registers = self.read_multiple_registers(60, 11)  # 頻率寄存器60-70
        
        if strength_registers and frequency_registers:
            actions = ['up', 'down', 'left', 'right', 'upleft', 'downleft', 
                      'upright', 'downright', 'horizontal', 'vertical', 'spread']
            
            for i, action in enumerate(actions):
                status['action_parameters'][action] = {
                    'strength': strength_registers[i],
                    'frequency': frequency_registers[i]
                }
                
        return status

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()

    def __del__(self):
        """析構函數"""
        self.disconnect()