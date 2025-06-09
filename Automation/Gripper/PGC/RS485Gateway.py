import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import websockets
from pymodbus.client import ModbusSerialClient
from pymodbus import __version__

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PGC_Gripper:
    def __init__(self, port='COM5', baudrate=115200, parity='N', stopbits=1, unit_id=6):
        self.port = port
        self.baudrate = baudrate
        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            stopbits=stopbits,
            parity=parity,
            timeout=1
        )
        self.unit_id = unit_id
        self.connected = False
        self.connect()
    
    def connect(self):
        """連接到設備"""
        try:
            if self.client.connect():
                self.connected = True
                logger.info(f"✅ Connected to gripper on {self.port} @ {self.baudrate}bps")
                return True
            else:
                self.connected = False
                logger.error("❌ Could not connect to PGC gripper")
                return False
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            self.connected = False
            return False
    
    def write_register(self, address, value):
        """寫入暫存器"""
        if not self.connected:
            return {"success": False, "error": "Device not connected"}
        
        try:
            result = self.client.write_register(address=address, value=value, slave=self.unit_id)
            if result.isError():
                error_msg = f"Failed to write {value} to register {address} (unit {self.unit_id})"
                logger.warning(f"⚠️ {error_msg}")
                return {"success": False, "error": error_msg}
            else:
                success_msg = f"Wrote {value} to register {address} (unit {self.unit_id})"
                logger.info(f"✅ {success_msg}")
                return {"success": True, "message": success_msg}
        except Exception as e:
            error_msg = f"Exception writing register: {e}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
    
    def initialize(self, mode=0x01):
        """初始化夾爪，mode=0x01為回零，mode=0xA5為完全初始化"""
        return self.write_register(0x0100, mode)
    
    def stop(self):
        """停止當前動作"""
        result = self.write_register(0x0100, 0)
        if result["success"]:
            logger.info("🛑 動作已停止")
        return result
    
    def set_position(self, value):
        """設定夾爪位置（0~1000，千分比）"""
        if not 0 <= value <= 1000:
            return {"success": False, "error": "Position must be between 0 and 1000"}
        return self.write_register(0x0103, value)
    
    def set_force(self, value):
        """設定夾爪力道（20~100，百分比）"""
        if not 20 <= value <= 100:
            return {"success": False, "error": "Force must be between 20 and 100"}
        return self.write_register(0x0101, value)
    
    def set_speed(self, value):
        """設定夾爪速度（1~100，百分比）"""
        if not 1 <= value <= 100:
            return {"success": False, "error": "Speed must be between 1 and 100"}
        return self.write_register(0x0104, value)
    
    def open(self):
        """張開夾爪（位置1000）"""
        return self.set_position(1000)
    
    def close(self):
        """閉合夾爪（位置0）"""
        return self.set_position(0)
    
    def get_status(self):
        """獲取設備狀態"""
        return {
            "connected": self.connected,
            "port": self.port,
            "baudrate": self.baudrate,
            "unit_id": self.unit_id,
            "timestamp": datetime.now().isoformat()
        }
    
    def disconnect(self):
        """斷開連接"""
        try:
            self.client.close()
            self.connected = False
            logger.info("🔌 Serial connection closed.")
            return {"success": True, "message": "Connection closed"}
        except Exception as e:
            logger.error(f"❌ Disconnect error: {e}")
            return {"success": False, "error": str(e)}

class RS485Gateway:
    def __init__(self, port='COM5', baudrate=115200, websocket_port=5005):
        self.gripper = PGC_Gripper(port=port, baudrate=baudrate)
        self.websocket_port = websocket_port
        self.clients = set()
        
    async def register_client(self, websocket):
        """註冊 WebSocket 客戶端"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        # 發送初始狀態
        await websocket.send(json.dumps({
            "type": "status",
            "data": self.gripper.get_status()
        }))
    
    async def unregister_client(self, websocket):
        """取消註冊 WebSocket 客戶端"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
    
    async def broadcast_status(self):
        """廣播狀態給所有客戶端"""
        if self.clients:
            status = self.gripper.get_status()
            message = json.dumps({"type": "status", "data": status})
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )
    
    async def handle_command(self, websocket, message):
        """處理來自客戶端的命令"""
        try:
            data = json.loads(message)
            command = data.get("command")
            params = data.get("params", {})
            
            logger.info(f"Received command: {command} with params: {params}")
            
            # 執行命令
            if command == "initialize":
                mode = params.get("mode", 0x01)
                result = self.gripper.initialize(mode)
            elif command == "stop":
                result = self.gripper.stop()
            elif command == "set_position":
                value = params.get("value", 0)
                result = self.gripper.set_position(value)
            elif command == "set_force":
                value = params.get("value", 50)
                result = self.gripper.set_force(value)
            elif command == "set_speed":
                value = params.get("value", 50)
                result = self.gripper.set_speed(value)
            elif command == "open":
                result = self.gripper.open()
            elif command == "close":
                result = self.gripper.close()
            elif command == "get_status":
                result = {"success": True, "data": self.gripper.get_status()}
            elif command == "disconnect":
                result = self.gripper.disconnect()
            else:
                result = {"success": False, "error": f"Unknown command: {command}"}
            
            # 發送結果回客戶端
            await websocket.send(json.dumps({
                "type": "response",
                "command": command,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }))
            
            # 廣播狀態更新
            await self.broadcast_status()
            
        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON format"
            }))
        except Exception as e:
            logger.error(f"Error handling command: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
    
    async def handle_websocket(self, websocket):
        """處理 WebSocket 連接"""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_command(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def start_server(self):
        """啟動 WebSocket 伺服器"""
        logger.info(f"Starting RS485 Gateway on port {self.websocket_port}")
        logger.info(f"PyModbus version: {__version__}")
        
        server = await websockets.serve(
            self.handle_websocket,
            "localhost",
            self.websocket_port
        )
        
        logger.info(f"🚀 RS485 Gateway server started on ws://localhost:{self.websocket_port}")
        
        # 定期廣播狀態
        async def periodic_status():
            while True:
                await asyncio.sleep(5)  # 每5秒廣播一次狀態
                await self.broadcast_status()
        
        # 同時運行伺服器和定期狀態廣播
        await asyncio.gather(
            server.wait_closed(),
            periodic_status()
        )

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RS485 Gateway for PGC Gripper')
    parser.add_argument('--port', default='COM5', help='Serial port (default: COM5)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baudrate (default: 115200)')
    parser.add_argument('--websocket-port', type=int, default=5005, help='WebSocket port (default: 5005)')
    
    args = parser.parse_args()
    
    gateway = RS485Gateway(
        port=args.port,
        baudrate=args.baudrate,
        websocket_port=args.websocket_port
    )
    
    try:
        asyncio.run(gateway.start_server())
    except KeyboardInterrupt:
        logger.info("🛑 Gateway stopped by user")
    except Exception as e:
        logger.error(f"❌ Gateway error: {e}")

if __name__ == "__main__":
    main()