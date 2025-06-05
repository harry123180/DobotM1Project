# 修正後的自動化生產線系統架構

## 🏗️ 實際硬體架構整合

### 整體架構圖
```
┌─────────────────────────────────────────────────────────────┐
│                CASE 入料機 PC (192.168.1.5)                │
│                    任務調度器 + 監控                         │
│                                                             │
│  ├── USB Port 1 (RS485總線)                                │
│  │   ├── 升降缸 (Slave 2)                                  │
│  │   ├── 旋轉缸 (Slave 3)                                  │
│  │   ├── 翻轉夾爪 (Slave 4)                                │
│  │   ├── 輸送帶限位電缸 (Slave 5)                          │
│  │   └── 機械臂夾爪 (Slave 6)                              │
│  │                                                         │
│  ├── USB Port 2 (RS232)                                    │
│  │   └── 新亞洲光源控制器                                   │
│  │       ├── Light 1 (輸送帶相機)                          │
│  │       ├── Light 2 (旋轉正上方相機)                      │
│  │       └── Light 3 (旋轉側邊相機)                        │
│  │                                                         │
│  └── EtherCAT軸卡                                          │
│      ├── 輸入模組 (X00~X06)                                │
│      └── TOYO滑台驅動器                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ POE 8 Port Switch
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
    ▼                 ▼                 ▼
┌─────────┐    ┌─────────────┐    ┌─────────────┐
│M1 Pro   │    │柔性振動盤    │    │相機群組      │
│機械臂    │    │192.168.1.7  │    │CCD1~CCD4    │
│192.168.1.6│  │            │    │.8/.9/.10/.11│
│         │    │            │    │             │
│IO控制:   │    │            │    │             │
│DI 9~15  │    │            │    │             │
│DO 1~5   │    │            │    │             │
└─────────┘    └─────────────┘    └─────────────┘
```

## 🔄 修正後的節點架構

### 1. 主控制節點 (CASE入料機PC)
```python
# scheduler/master_controller.py
class MasterController:
    """主控制器：統一任務調度和設備協調"""
    
    def __init__(self):
        # 網路設備客戶端
        self.robot_arm_client = RobotArmClient("192.168.1.6")
        self.vibration_bowl_client = VibrationBowlClient("192.168.1.7")
        self.vision_clients = {
            'ccd1': VisionClient("192.168.1.8"),   # 柔振相機
            'ccd2': VisionClient("192.168.1.9"),   # 輸送帶相機
            'ccd3': VisionClient("192.168.1.10"),  # 旋轉正上方
            'ccd4': VisionClient("192.168.1.11")   # 旋轉側邊
        }
        
        # 本地USB設備控制器
        self.rs485_controller = RS485Controller("/dev/ttyUSB0")  # USB Port 1
        self.rs232_light_controller = RS232Controller("/dev/ttyUSB1")  # USB Port 2
        self.ethercat_controller = EtherCATController("eth0")
        
        self.mqtt_client = MQTTClient()
        
    async def coordinate_production_cycle(self):
        """協調完整生產週期"""
        # 1. 柔性振動盤送料
        await self.vibration_bowl_client.start_feeding()
        
        # 2. 開啟光源並進行CCD1 視覺檢測
        await self.rs232_light_controller.turn_on_light(1)  # 本地控制光源
        parts_info = await self.vision_clients['ccd1'].detect_parts()
        
        # 3. 機械臂取料 (透過網路控制機械臂本體)
        await self.robot_arm_client.move_to_pick(parts_info.position)
        
        # 4. 控制夾爪夾取 (透過本地RS485)
        await self.rs485_controller.control_gripper(6, "close")  # Slave 6
        
        # 5. 後續流程...
```

### 2. 機械臂節點 (M1 Pro機械臂PC)
```python
# nodes/robot_arm_node.py
class RobotArmNode(BaseNode):
    """機械臂節點：只控制機械臂本體運動和IO讀寫"""
    
    def __init__(self):
        super().__init__()
        self.robot_arm = M1ProController()  # 機械臂本體控制
        self.io_controller = IOController()  # 本地IO控制 (DI/DO)
        
    def setup_hardware(self):
        """初始化機械臂硬體"""
        # 機械臂初始化
        self.robot_arm.initialize()
        
        # IO配置
        self.digital_inputs = {
            9: "搖搖桶左上感測器",
            10: "搖搖桶左下感測器", 
            11: "搖搖桶右上感測器",
            12: "搖搖桶右下感測器",
            13: "到位感測器",
            14: "翻轉0度感測器",
            15: "翻轉180度感測器"
        }
        
        self.digital_outputs = {
            1: "搖搖桶5/2電磁閥",
            2: "輸送帶驅動IO",
            3: "NG氣槍5/2電磁閥", 
            4: "直振開關",
            5: "翻轉氣缸5/2電磁閥"
        }
        
    async def process_task(self, task):
        """處理任務請求"""
        if task.type == "MOVE_TO_POSITION":
            await self._move_to_position(task.position)
        elif task.type == "READ_SENSORS":
            return await self._read_all_sensors()
        elif task.type == "CONTROL_OUTPUT":
            await self._control_output(task.output_id, task.state)
            
    async def _move_to_position(self, position):
        """移動到指定位置"""
        await self.robot_arm.move_to_position(position)
        await self.publish_status("POSITION_REACHED", position)
        
    async def _read_all_sensors(self):
        """讀取所有感測器狀態"""
        sensor_status = {}
        for pin, description in self.digital_inputs.items():
            sensor_status[pin] = self.io_controller.read_digital_input(pin)
        return sensor_status
        
    async def _control_output(self, output_id, state):
        """控制數位輸出"""
        self.io_controller.write_digital_output(output_id, state)
        await self.publish_status("OUTPUT_CONTROLLED", {
            "output_id": output_id, 
            "state": state
        })
```

### 3. CASE入料機PC的設備控制模組
```python
# hardware/local_device_controller.py
class LocalDeviceController:
    """CASE入料機PC本地設備控制器"""
    
    def __init__(self):
        # USB設備控制器
        self.rs485_controller = RS485Controller("/dev/ttyUSB0")
        self.rs232_light_controller = RS232LightController("/dev/ttyUSB1") 
        self.ethercat_controller = EtherCATController("eth0")
        
        # 設備映射
        self.rs485_devices = {
            'lift_cylinder': 2,      # 升降缸 Slave 2
            'rotation_cylinder': 3,  # 旋轉缸 Slave 3
            'flip_gripper': 4,      # 翻轉夾爪 Slave 4
            'conveyor_limit': 5,    # 輸送帶限位電缸 Slave 5
            'robot_gripper': 6      # 機械臂夾爪 Slave 6
        }
        
        self.light_channels = {
            'conveyor_camera': 1,    # Light 1 輸送帶相機
            'rotation_top': 2,       # Light 2 旋轉正上方相機
            'rotation_side': 3       # Light 3 旋轉側邊相機
        }
        
    async def control_rs485_device(self, device_name: str, command: dict):
        """控制RS485設備"""
        if device_name not in self.rs485_devices:
            raise ValueError(f"Unknown RS485 device: {device_name}")
            
        slave_id = self.rs485_devices[device_name]
        return await self.rs485_controller.send_command(slave_id, command)
        
    async def control_light(self, light_name: str, action: str, brightness: int = 100):
        """控制光源"""
        if light_name not in self.light_channels:
            raise ValueError(f"Unknown light: {light_name}")
            
        channel = self.light_channels[light_name]
        
        if action == "on":
            await self.rs232_light_controller.turn_on(channel, brightness)
        elif action == "off":
            await self.rs232_light_controller.turn_off(channel)
        else:
            raise ValueError(f"Invalid light action: {action}")
            
    async def read_ethercat_inputs(self):
        """讀取EtherCAT輸入"""
        inputs = {}
        input_map = {
            'X00': 'Door1',
            'X01': 'Door2', 
            'X03': 'Door3',
            'X04': 'TOYO左',
            'X05': 'TOYODog',
            'X06': 'TOYO右'
        }
        
        for address, description in input_map.items():
            inputs[description] = await self.ethercat_controller.read_input(address)
            
        return inputs
        
    async def control_toyo_slider(self, position: float, speed: float = 100):
        """控制TOYO滑台"""
        await self.ethercat_controller.move_axis(
            axis_id=1, 
            position=position, 
            speed=speed
        )
```

## 🔧 MQTT 主題重新設計

```python
# communication/topics.py
MQTT_TOPICS = {
    # 主控制相關
    "master_control": {
        "task_assignment": "automation/master/tasks/assign",
        "coordination": "automation/master/coordinate",
        "system_status": "automation/master/status"
    },
    
    # 機械臂整合節點
    "robot_integrated": {
        "status": "automation/robot/status",
        "control": "automation/robot/control",
        "io_status": "automation/robot/io/status",
        "rs485_control": "automation/robot/rs485/control",
        "lighting_control": "automation/robot/lighting/control"
    },
    
    # 視覺節點群組
    "vision": {
        "ccd1_results": "automation/vision/ccd1/results",
        "ccd2_results": "automation/vision/ccd2/results", 
        "ccd3_results": "automation/vision/ccd3/results",
        "ccd4_results": "automation/vision/ccd4/results",
        "lighting_request": "automation/lighting/request"
    },
    
    # 柔性振動盤
    "vibration_bowl": {
        "control": "automation/vibration_bowl/control",
        "status": "automation/vibration_bowl/status"
    }
}
```

## 📁 調整後的專案結構

```
automation_system/
├── master_controller/           # 主控制器 (CASE入料機PC)
│   ├── task_scheduler.py       # 任務調度器
│   ├── production_coordinator.py # 生產協調器
│   └── system_monitor.py       # 系統監控
├── nodes/
│   ├── integrated_robot_node.py # 整合式機械臂節點
│   ├── vision_node.py          # 視覺節點模板
│   ├── vibration_bowl_node.py  # 柔性振動盤節點
│   └── camera_nodes/           # 各相機節點
│       ├── ccd1_node.py        # 柔振相機
│       ├── ccd2_node.py        # 輸送帶相機  
│       ├── ccd3_node.py        # 旋轉正上方相機
│       └── ccd4_node.py        # 旋轉側邊相機
├── hardware/                   # 硬體控制層
│   ├── robot_controller.py     # M1 Pro機械臂控制
│   ├── io_controller.py        # IO控制
│   ├── rs485_controller.py     # RS485總線控制
│   ├── rs232_controller.py     # RS232設備控制
│   └── ethercat_controller.py  # EtherCAT軸卡控制
└── protocols/                  # 通訊協議
    ├── modbus_protocol.py      # Modbus協議
    ├── ethercat_protocol.py    # EtherCAT協議
    └── camera_protocol.py     # 相機通訊協議
```

## 🚀 部署配置

### 主控制器配置 (CASE入料機PC - 192.168.1.5)
```json
{
    "master_controller": {
        "ip": "192.168.1.5",
        "mqtt_broker_port": 1883,
        "web_dashboard_port": 8080,
        "coordination_interval": 0.1
    },
    "local_hardware": {
        "rs485_port": "/dev/ttyUSB0",
        "rs232_port": "/dev/ttyUSB1", 
        "ethercat_interface": "eth0",
        "rs485_devices": {
            "lift_cylinder": 2,
            "rotation_cylinder": 3,
            "flip_gripper": 4,
            "conveyor_limit": 5,
            "robot_gripper": 6
        },
        "light_channels": {
            "conveyor_camera": 1,
            "rotation_top": 2,
            "rotation_side": 3
        }
    },
    "network_nodes": {
        "robot_arm": "192.168.1.6",
        "vibration_bowl": "192.168.1.7",
        "cameras": {
            "ccd1": "192.168.1.8",
            "ccd2": "192.168.1.9", 
            "ccd3": "192.168.1.10",
            "ccd4": "192.168.1.11"
        }
    }
}
```

### 機械臂節點配置 (M1 Pro - 192.168.1.6)
```json
{
    "robot_arm": {
        "ip": "192.168.1.6",
        "web_port": 5003,
        "hardware": {
            "robot_type": "M1_Pro",
            "io_configuration": {
                "digital_inputs": {
                    "9": "搖搖桶左上感測器",
                    "10": "搖搖桶左下感測器",
                    "11": "搖搖桶右上感測器", 
                    "12": "搖搖桶右下感測器",
                    "13": "到位感測器",
                    "14": "翻轉0度感測器",
                    "15": "翻轉180度感測器"
                },
                "digital_outputs": {
                    "1": "搖搖桶5/2電磁閥",
                    "2": "輸送帶驅動IO",
                    "3": "NG氣槍5/2電磁閥",
                    "4": "直振開關", 
                    "5": "翻轉氣缸5/2電磁閥"
                }
            }
        },
        "capabilities": [
            "robot_movement",
            "io_control",
            "sensor_reading"
        ]
    }
}
```

這樣的架構調整更符合您的實際硬體配置，避免了控制權衝突，同時保持了系統的模組化和擴展性。