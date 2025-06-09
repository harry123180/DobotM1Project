"""
XC100_Manager - XC100滑台控制器專用管理類
基於實際Toyo-Single軟體的通訊協議實現
"""
import time
import threading
from typing import Optional, Dict, Any, Tuple
from pymodbus.client import ModbusSerialClient
from pymodbus import ModbusException
import logging

logger = logging.getLogger(__name__)

class XC100_Manager:
    """XC100滑台控制器管理類"""
    
    def __init__(self):
        # Modbus連線參數
        self.client: Optional[ModbusSerialClient] = None
        self.is_connected = False
        self.station_id = 2  # 預設站號2 (SW_ID=1時)
        
        # 設備狀態
        self.device_status = {
            "servo_status": False,      # 伺服狀態 (100CH)
            "alarm_status": 0,          # 警報狀態 (1005H)
            "action_status": 0,         # 動作狀態 (1000H)
            "current_position": 0.0,    # 目前位置 (1008H-1009H)
            "error_status": 0,          # 錯誤狀態 (100DH)
            "inposition": False,        # 到位狀態 (1001H)
            "ready": False,             # 就緒狀態
            "running": False,           # 運行狀態
            "initialized": False        # 初始化完成狀態
        }
        
        # 監控執行緒
        self.monitoring = False
        self.monitor_thread = None
        self.status_lock = threading.Lock()
        
        # 操作狀態
        self.last_command_time = 0
        self.command_timeout = 10.0  # 指令超時時間
        
    def connect(self, port: str, baudrate: int = 115200, station_id: int = 2) -> Dict[str, Any]:
        """連接XC100設備"""
        try:
            if self.is_connected:
                self.disconnect()
            
            self.station_id = station_id
            
            # 建立Modbus客戶端 - 使用ASCII模式 (根據Toyo-Single軟體)
            self.client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                timeout=3,
                parity='N',
                stopbits=1,
                bytesize=8,
                # XC100使用ASCII模式
            )
            
            if self.client.connect():
                self.is_connected = True
                
                # 測試連線
                if self._test_connection():
                    self._start_monitoring()
                    logger.info(f"XC100連線成功: {port}, 站號: {station_id}")
                    return {"success": True, "message": f"連線成功 {port}"}
                else:
                    return {"success": False, "message": "連線成功但無法通訊，請檢查站號設定"}
            else:
                return {"success": False, "message": "連線失敗"}
                
        except Exception as e:
            logger.error(f"連線錯誤: {e}")
            return {"success": False, "message": f"連線錯誤: {str(e)}"}
    
    def disconnect(self) -> None:
        """斷開連線"""
        self._stop_monitoring()
        
        if self.client:
            self.client.close()
            self.client = None
            
        self.is_connected = False
        self._reset_status()
        logger.info("XC100連線已斷開")
    
    def _test_connection(self) -> bool:
        """測試連線"""
        try:
            # 嘗試讀取伺服狀態 - 修正API調用
            result = self.client.read_holding_registers(
                address=0x100C, 
                count=1, 
                slave=self.station_id
            )
            return not result.isError()
        except Exception:
            return False
    
    def _reset_status(self) -> None:
        """重設狀態"""
        with self.status_lock:
            self.device_status.update({
                "servo_status": False,
                "alarm_status": 0,
                "action_status": 0,
                "current_position": 0.0,
                "error_status": 0,
                "inposition": False,
                "ready": False,
                "running": False,
                "initialized": False
            })
    
    def _start_monitoring(self) -> None:
        """啟動狀態監控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("XC100狀態監控已啟動")
    
    def _stop_monitoring(self) -> None:
        """停止狀態監控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("XC100狀態監控已停止")
    
    def _monitor_loop(self) -> None:
        """監控執行緒主迴圈"""
        consecutive_errors = 0
        max_errors = 5
        
        while self.monitoring and self.is_connected:
            try:
                self._read_all_status()
                consecutive_errors = 0
                time.sleep(0.5)  # 500ms更新週期
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"監控錯誤 ({consecutive_errors}/{max_errors}): {e}")
                
                if consecutive_errors >= max_errors:
                    logger.error("連續錯誤過多，停止監控")
                    with self.status_lock:
                        self.device_status["ready"] = False
                        self.device_status["alarm_status"] = 1
                    break
                    
                time.sleep(2)
    
    def _read_all_status(self) -> None:
        """讀取所有設備狀態"""
        if not self.client or not self.is_connected:
            return
            
        with self.status_lock:
            try:
                # 讀取伺服狀態 (100CH) - 修正pymodbus 3.9.2 API調用
                result = self.client.read_holding_registers(
                    address=0x100C, 
                    count=1, 
                    slave=self.station_id
                )
                if not result.isError():
                    self.device_status["servo_status"] = bool(result.registers[0])
                
                # 讀取警報狀態 (1005H)
                result = self.client.read_holding_registers(
                    address=0x1005, 
                    count=1, 
                    slave=self.station_id
                )
                if not result.isError():
                    self.device_status["alarm_status"] = result.registers[0]
                
                # 讀取動作狀態 (1000H)
                result = self.client.read_holding_registers(
                    address=0x1000, 
                    count=1, 
                    slave=self.station_id
                )
                if not result.isError():
                    self.device_status["action_status"] = result.registers[0]
                    self.device_status["running"] = (result.registers[0] == 1)
                
                # 讀取錯誤狀態 (100DH)
                result = self.client.read_holding_registers(
                    address=0x100D, 
                    count=1, 
                    slave=self.station_id
                )
                if not result.isError():
                    self.device_status["error_status"] = result.registers[0]
                
                # 讀取到位狀態 (1001H)
                result = self.client.read_holding_registers(
                    address=0x1001, 
                    count=1, 
                    slave=self.station_id
                )
                if not result.isError():
                    self.device_status["inposition"] = bool(result.registers[0])
                
                # 讀取目前位置 (1008H-1009H, 32位元)
                result = self.client.read_holding_registers(
                    address=0x1008, 
                    count=2, 
                    slave=self.station_id
                )
                if not result.isError():
                    # 組合32位元位置 (高位在前)
                    position_raw = (result.registers[0] << 16) | result.registers[1]
                    # 處理有號數
                    if position_raw > 0x7FFFFFFF:
                        position_raw -= 0x100000000
                    # 轉換為mm (1 pulse = 0.01mm)
                    self.device_status["current_position"] = position_raw * 0.01
                
                # 計算綜合狀態
                self.device_status["ready"] = (
                    self.device_status["servo_status"] and
                    self.device_status["alarm_status"] == 0 and
                    self.device_status["error_status"] == 0 and
                    not self.device_status["running"]
                )
                
                self.device_status["initialized"] = (
                    self.device_status["servo_status"] and
                    self.device_status["alarm_status"] == 0 and
                    self.device_status["error_status"] == 0
                )
                
            except Exception as e:
                logger.error(f"讀取狀態錯誤: {e}")
                self.device_status["ready"] = False
    
    def get_status(self) -> Dict[str, Any]:
        """獲取設備狀態"""
        with self.status_lock:
            return self.device_status.copy()
    
    def _write_register(self, address: int, value: int) -> bool:
        """寫入單個暫存器"""
        if not self.client or not self.is_connected:
            return False
            
        try:
            result = self.client.write_register(
                address=address, 
                value=value, 
                slave=self.station_id
            )
            success = not result.isError()
            if success:
                self.last_command_time = time.time()
                logger.info(f"寫入暫存器: {address:04X}H = {value}")
            return success
        except Exception as e:
            logger.error(f"寫入暫存器失敗: {e}")
            return False
    
    def _write_registers(self, address: int, values: list) -> bool:
        """寫入多個暫存器"""
        if not self.client or not self.is_connected:
            return False
            
        try:
            result = self.client.write_registers(
                address=address, 
                values=values, 
                slave=self.station_id
            )
            success = not result.isError()
            if success:
                self.last_command_time = time.time()
                logger.info(f"寫入暫存器: {address:04X}H = {values}")
            return success
        except Exception as e:
            logger.error(f"寫入多個暫存器失敗: {e}")
            return False
    
    def _wait_for_ready(self, timeout: float = 5.0) -> bool:
        """等待設備就緒"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_status()
            if status["ready"]:
                return True
            time.sleep(0.1)
        return False
    
    def _wait_for_completion(self, timeout: float = 30.0) -> bool:
        """等待動作完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_status()
            if not status["running"] and status["ready"]:
                return True
            time.sleep(0.1)
        return False
    
    # === 基本控制指令 ===
    
    def servo_on(self) -> Dict[str, Any]:
        """伺服ON"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        try:
            # 寫入2011H = 0 (伺服ON)
            if self._write_register(0x2011, 0):
                # 等待狀態更新
                time.sleep(0.5)
                status = self.get_status()
                if status["servo_status"]:
                    return {"success": True, "message": "伺服ON成功"}
                else:
                    return {"success": False, "message": "伺服ON指令發送但狀態未變更"}
            else:
                return {"success": False, "message": "伺服ON指令發送失敗"}
        except Exception as e:
            return {"success": False, "message": f"伺服ON錯誤: {str(e)}"}
    
    def servo_off(self) -> Dict[str, Any]:
        """伺服OFF"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        try:
            # 寫入2011H = 1 (伺服OFF)
            if self._write_register(0x2011, 1):
                time.sleep(0.5)
                status = self.get_status()
                if not status["servo_status"]:
                    return {"success": True, "message": "伺服OFF成功"}
                else:
                    return {"success": False, "message": "伺服OFF指令發送但狀態未變更"}
            else:
                return {"success": False, "message": "伺服OFF指令發送失敗"}
        except Exception as e:
            return {"success": False, "message": f"伺服OFF錯誤: {str(e)}"}
    
    def home_return(self, wait_completion: bool = True) -> Dict[str, Any]:
        """原點復歸"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        status = self.get_status()
        if not status["servo_status"]:
            return {"success": False, "message": "請先執行伺服ON"}
        
        if status["error_status"] != 0:
            return {"success": False, "message": f"設備錯誤狀態: {status['error_status']}"}
        
        try:
            # 寫入201EH = 3 (原點復歸)
            if self._write_register(0x201E, 3):
                if wait_completion:
                    # 等待動作完成
                    if self._wait_for_completion(timeout=60.0):
                        return {"success": True, "message": "原點復歸完成"}
                    else:
                        return {"success": False, "message": "原點復歸超時"}
                else:
                    return {"success": True, "message": "原點復歸指令已發送"}
            else:
                return {"success": False, "message": "原點復歸指令發送失敗"}
        except Exception as e:
            return {"success": False, "message": f"原點復歸錯誤: {str(e)}"}
    
    def move_absolute(self, position_mm: float, wait_completion: bool = True) -> Dict[str, Any]:
        """絕對位置移動"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        status = self.get_status()
        if not status["ready"]:
            return {"success": False, "message": "設備未就緒"}
        
        try:
            # 轉換為pulse (1mm = 100 pulse)
            position_pulse = int(position_mm * 100)
            
            # 分解為32位元 (高位、低位)
            high_word = (position_pulse >> 16) & 0xFFFF
            low_word = position_pulse & 0xFFFF
            
            # 寫入絕對移動位置 (2002H-2003H)
            if self._write_registers(0x2002, [high_word, low_word]):
                # 執行絕對移動 (201EH = 1)
                if self._write_register(0x201E, 1):
                    if wait_completion:
                        if self._wait_for_completion(timeout=30.0):
                            return {"success": True, "message": f"移動到{position_mm}mm完成"}
                        else:
                            return {"success": False, "message": "移動超時"}
                    else:
                        return {"success": True, "message": f"移動到{position_mm}mm指令已發送"}
                else:
                    return {"success": False, "message": "移動指令發送失敗"}
            else:
                return {"success": False, "message": "位置設定失敗"}
        except Exception as e:
            return {"success": False, "message": f"絕對移動錯誤: {str(e)}"}
    
    def move_relative(self, distance_mm: float, wait_completion: bool = True) -> Dict[str, Any]:
        """相對位置移動"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        status = self.get_status()
        if not status["ready"]:
            return {"success": False, "message": "設備未就緒"}
        
        try:
            # 轉換為pulse
            distance_pulse = int(distance_mm * 100)
            
            # 分解為32位元
            high_word = (distance_pulse >> 16) & 0xFFFF
            low_word = distance_pulse & 0xFFFF
            
            # 寫入相對移動量 (2000H-2001H)
            if self._write_registers(0x2000, [high_word, low_word]):
                # 執行相對移動 (201EH = 0)
                if self._write_register(0x201E, 0):
                    if wait_completion:
                        if self._wait_for_completion(timeout=30.0):
                            return {"success": True, "message": f"相對移動{distance_mm}mm完成"}
                        else:
                            return {"success": False, "message": "移動超時"}
                    else:
                        return {"success": True, "message": f"相對移動{distance_mm}mm指令已發送"}
                else:
                    return {"success": False, "message": "移動指令發送失敗"}
            else:
                return {"success": False, "message": "移動量設定失敗"}
        except Exception as e:
            return {"success": False, "message": f"相對移動錯誤: {str(e)}"}
    
    def emergency_stop(self) -> Dict[str, Any]:
        """緊急停止"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        try:
            # 寫入201EH = 9 (緊急停止)
            if self._write_register(0x201E, 9):
                return {"success": True, "message": "緊急停止指令已發送"}
            else:
                return {"success": False, "message": "緊急停止指令發送失敗"}
        except Exception as e:
            return {"success": False, "message": f"緊急停止錯誤: {str(e)}"}
    
    def clear_alarm(self) -> Dict[str, Any]:
        """清除警報"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        try:
            # 寫入201EH = 6 (警報重置)
            if self._write_register(0x201E, 6):
                time.sleep(1)  # 等待清除完成
                status = self.get_status()
                if status["alarm_status"] == 0:
                    return {"success": True, "message": "警報已清除"}
                else:
                    return {"success": False, "message": "警報清除失敗"}
            else:
                return {"success": False, "message": "警報清除指令發送失敗"}
        except Exception as e:
            return {"success": False, "message": f"清除警報錯誤: {str(e)}"}
    
    # === 高級控制方法 ===
    
    def initialize_device(self) -> Dict[str, Any]:
        """完整初始化設備"""
        try:
            logger.info("開始XC100設備初始化")
            
            # 1. 檢查連線
            if not self.is_connected:
                return {"success": False, "message": "設備未連線"}
            
            # 2. 清除警報
            alarm_result = self.clear_alarm()
            if not alarm_result["success"]:
                logger.warning(f"清除警報失敗: {alarm_result['message']}")
            
            # 3. 伺服ON
            servo_result = self.servo_on()
            if not servo_result["success"]:
                return {"success": False, "message": f"伺服ON失敗: {servo_result['message']}"}
            
            # 4. 原點復歸
            home_result = self.home_return(wait_completion=True)
            if not home_result["success"]:
                return {"success": False, "message": f"原點復歸失敗: {home_result['message']}"}
            
            logger.info("XC100設備初始化完成")
            return {"success": True, "message": "設備初始化完成"}
            
        except Exception as e:
            logger.error(f"設備初始化錯誤: {e}")
            return {"success": False, "message": f"初始化錯誤: {str(e)}"}
    
    def move_to_positions(self, positions: list, wait_each: bool = True) -> Dict[str, Any]:
        """移動到多個位置"""
        if not self.is_connected:
            return {"success": False, "message": "設備未連線"}
        
        results = []
        for i, pos in enumerate(positions):
            logger.info(f"移動到位置 {i+1}/{len(positions)}: {pos}mm")
            result = self.move_absolute(pos, wait_completion=wait_each)
            results.append(result)
            
            if not result["success"]:
                return {
                    "success": False, 
                    "message": f"移動到位置{pos}mm失敗: {result['message']}",
                    "completed_positions": i,
                    "results": results
                }
        
        return {
            "success": True, 
            "message": f"完成所有{len(positions)}個位置移動",
            "results": results
        }
    
    def get_error_description(self, error_code: int) -> str:
        """獲取錯誤代碼描述"""
        error_descriptions = {
            0: "沒有錯誤",
            1: "在動作中接收動作指令",
            2: "上下限錯誤",
            3: "位置錯誤",
            4: "格式錯誤",
            5: "控制模式錯誤",
            6: "斷電重開",
            7: "初始化未完成",
            8: "Servo ON/OFF 錯誤",
            9: "LOCK",
            10: "軟體極限",
            11: "參數寫入權限不足",
            12: "原點復歸未完成",
            13: "剎車已解除"
        }
        return error_descriptions.get(error_code, f"未知錯誤代碼: {error_code}")
    
    def get_alarm_description(self, alarm_code: int) -> str:
        """獲取警報代碼描述"""
        alarm_descriptions = {
            0: "無警報",
            1: "迴路錯誤",
            2: "計數滿",
            3: "過速度",
            4: "增益值調整不良",
            5: "過電壓",
            6: "初期化異常",
            7: "EEPROM異常",
            8: "主迴路電源電壓不足",
            9: "過電流",
            10: "回生異常",
            11: "緊急停止",
            12: "馬達斷線",
            13: "編碼器斷線",
            14: "保護電流值",
            15: "電源再投入",
            17: "動作逾時"
        }
        return alarm_descriptions.get(alarm_code, f"未知警報代碼: {alarm_code}")
    
    def __del__(self):
        """析構函數"""
        if self.is_connected:
            self.disconnect()

# 使用範例
if __name__ == "__main__":
    # 建立XC100管理器
    xc100 = XC100_Manager()
    
    # 連線
    result = xc100.connect("COM6", 115200, 2)
    print(f"連線結果: {result}")
    
    if result["success"]:
        # 初始化設備
        init_result = xc100.initialize_device()
        print(f"初始化結果: {init_result}")
        
        if init_result["success"]:
            # 移動測試
            move_result = xc100.move_absolute(10.0)
            print(f"移動結果: {move_result}")
            
            # 獲取狀態
            status = xc100.get_status()
            print(f"設備狀態: {status}")
        
        # 斷線
        xc100.disconnect()