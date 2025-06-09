# CCD視覺檢測模組技術文檔

## 架構概述

CCD視覺檢測模組實現握手式狀態機控制，採用Modbus TCP Client架構。

```
主服務器 (ModbusTCP:502)
    |
    |-- TCP --> CCD1VisionCode_Enhanced.py (TCP Client)
                    |
                    |-- 直連 --> 相機設備 (192.168.1.8)
```

## 實現組件

### CCD1VisionCode_Enhanced.py - 主模組
- TCP Client連接主服務器 (默認127.0.0.1:502)
- 相機直連控制 (192.168.1.8)
- 寄存器映射基地址: 200
- 握手式狀態機交握
- 50ms輪詢間隔

### camera_manager.py - 相機管理API
- 海康威視SDK封裝
- 優化相機管理器
- 幀數據處理
- 性能監控

## 寄存器映射 (基地址200)

### 核心控制握手寄存器 (200-201)
| 地址 | 功能 | 數值定義 |
|------|------|----------|
| 200 | 控制指令 | 0=清空, 8=拍照, 16=拍照+檢測, 32=重新初始化 |
| 201 | 狀態寄存器 | bit0=Ready, bit1=Running, bit2=Alarm, bit3=Initialized |

### 檢測參數寄存器 (210-219)
| 地址 | 功能 | 說明 |
|------|------|------|
| 210 | 最小面積高位 | 32位面積設定高16位 |
| 211 | 最小面積低位 | 32位面積設定低16位 |
| 212 | 最小圓度 | 圓度設定值乘以1000 |
| 213 | 高斯核大小 | 圖像處理參數 |
| 214 | Canny低閾值 | 邊緣檢測參數 |
| 215 | Canny高閾值 | 邊緣檢測參數 |

### 檢測結果寄存器 (240-279)
| 地址 | 功能 | 說明 |
|------|------|------|
| 240 | 檢測圓形數量 | 最多5個 |
| 241-243 | 圓形1座標半徑 | X, Y, Radius |
| 244-246 | 圓形2座標半徑 | X, Y, Radius |
| 247-249 | 圓形3座標半徑 | X, Y, Radius |
| 250-252 | 圓形4座標半徑 | X, Y, Radius |
| 253-255 | 圓形5座標半徑 | X, Y, Radius |

### 統計資訊寄存器 (280-299)
| 地址 | 功能 | 說明 |
|------|------|------|
| 280 | 最後拍照耗時 | 毫秒單位 |
| 281 | 最後處理耗時 | 毫秒單位 |
| 282 | 最後總耗時 | 毫秒單位 |
| 283 | 操作計數器 | 累積操作次數 |
| 284 | 錯誤計數器 | 累積錯誤次數 |
| 285 | 連接計數器 | 累積連接次數 |
| 290 | 軟體版本主號 | 版本3 |
| 291 | 軟體版本次號 | 版本0 |
| 292 | 運行時間小時 | 系統運行時間 |
| 293 | 運行時間分鐘 | 系統運行時間 |

## 握手協議實現

### 狀態機定義
SystemStateMachine類實現4位狀態控制:
- Ready (bit0): 系統準備接受新指令
- Running (bit1): 系統正在執行操作
- Alarm (bit2): 系統異常或錯誤
- Initialized (bit3): 系統已完全初始化

### 握手交握流程
1. 系統初始化完成 → 狀態寄存器固定值1 (Ready=1)
2. PLC下達控制指令 → 檢查Ready=1
3. 開始執行 → Ready=0, Running=1
4. 執行完成 → Running=0
5. PLC清零指令 → Ready=1 (準備下次)
6. 異常發生 → Alarm=1, Initialized=0

### 控制指令映射
| 指令碼 | 功能 | 執行內容 |
|--------|------|----------|
| 0 | 清空控制 | 狀態機恢復Ready |
| 8 | 拍照 | 單純圖像捕獲 |
| 16 | 拍照+檢測 | 圖像捕獲與圓形檢測 |
| 32 | 重新初始化 | 相機重新初始化 |

## 圓形檢測演算法

### CircleDetector類實現
- 高斯濾波預處理
- Canny邊緣檢測
- 輪廓分析與圓度計算
- 最多輸出5個檢測結果

### 檢測參數配置
```python
class DetectionParams:
    min_area: float = 50000.0
    min_roundness: float = 0.8
    gaussian_kernel_size: int = 9
    gaussian_sigma: float = 2.0
    canny_low: int = 20
    canny_high: int = 60
```

### 結果數據結構
```python
class VisionResult:
    circle_count: int
    circles: List[Dict[str, Any]]
    processing_time: float
    capture_time: float
    total_time: float
    timestamp: str
    success: bool
    error_message: Optional[str]
```

## 相機管理實現

### OptimizedCamera類
- 海康威視SDK封裝
- 單相機完整生命週期管理
- 幀緩存機制
- 性能監控統計

### CameraConfig配置
```python
class CameraConfig:
    name: str = "cam_1"
    ip: str = "192.168.1.8"
    exposure_time: float = 20000.0
    gain: float = 200.0
    frame_rate: float = 30.0
    pixel_format: PixelFormat = BAYER_GR8
    width: int = 2592
    height: int = 1944
```

## 線程架構

### 主要線程
- **主線程**: Flask Web應用
- **握手同步線程**: _handshake_sync_loop (50ms輪詢)
- **指令執行線程**: _execute_command_async (異步執行)

### 線程安全機制
- SystemStateMachine使用self.lock保護狀態
- 指令執行狀態command_processing防重入
- 相機操作使用threading.RLock

## Flask Web介面

### 核心API路由
- POST /api/modbus/set_server - 設置Modbus服務器地址
- POST /api/modbus/connect - 連接Modbus服務器
- GET /api/modbus/registers - 讀取所有寄存器即時數值
- POST /api/modbus/manual_command - 手動發送控制指令
- POST /api/initialize - 初始化相機連接
- POST /api/capture_and_detect - 執行拍照檢測

### Web介面功能
- 運行在localhost:5051
- SocketIO即時通訊
- 狀態監控顯示
- 參數調整介面
- 手動控制功能

## 依賴模組版本

### 核心依賴
- PyModbus 3.9.2 (Modbus TCP Client)
- OpenCV (圖像處理)
- NumPy (數值計算)
- Flask + SocketIO (Web介面)

### 海康威視SDK
- MvCameraControl_class
- CameraParams_const
- CameraParams_header
- MvErrorDefine_const
- PixelType_header

## 錯誤處理機制

### 連接管理
- Modbus TCP自動重連 (reconnect_delay: 5秒)
- 相機連接異常處理
- 超時控制 (read_timeout: 3秒)

### 狀態異常處理
- 通訊錯誤計數統計
- Alarm狀態自動設置
- 錯誤資訊記錄與回報

### 異常恢復
- 重新初始化指令 (32)
- 狀態機重置機制
- 資源釋放與重建

## 配置管理

### 模組配置
- 無獨立配置檔案
- 硬編碼預設參數
- 運行時動態調整

### 預設配置值
```python
# Modbus連接
server_ip = "192.168.1.100"
server_port = 502
base_address = 200

# 相機配置  
camera_ip = "192.168.1.8"
exposure_time = 20000.0
gain = 200.0

# 檢測參數
min_area = 50000.0
min_roundness = 0.8
```

## 部署配置

### 運行順序
1. 啟動主Modbus TCP Server (端口502)
2. 啟動CCD1VisionCode_Enhanced.py
3. 訪問Web介面 (localhost:5051)
4. 設置Modbus服務器地址並連接
5. 初始化相機連接
6. 系統進入握手模式等待PLC指令

### 檔案結構
```
Vision/
├── CCD1VisionCode_Enhanced.py    # 主程序
├── camera_manager.py             # 相機管理API
└── templates/
    └── ccd_vision_enhanced.html   # Web介面模板
```

## 測試驗證

### 連接測試
1. Modbus TCP連接狀態檢查
2. 相機設備連接驗證
3. 寄存器讀寫功能測試

### 功能測試
1. 握手協議狀態機驗證
2. 控制指令執行確認
3. 圓形檢測演算法準確性
4. 錯誤處理機制測試

### 性能監控
1. 拍照耗時統計
2. 檢測處理時間
3. 握手響應延遲
4. 系統穩定性驗證

## 已知限制

### 硬體依賴
- 需要海康威視SDK完整安裝
- 相機必須支援TCP/IP連接
- 網路延遲影響響應時間

### 軟體限制
- 最多檢測5個圓形
- 固定圓形檢測演算法
- 無持久化配置機制

### 系統限制
- 單相機支援
- 同步執行模式
- 無負載平衡機制

## 開發問題修正記錄

### 1. 狀態機初始值問題 (已修正)
**錯誤**: 狀態寄存器初始值不固定
**修正**: 強制設置初始值為1 (Ready=1, 其他位=0)
```python
# 修正實現
initial_status = 0b0001
self.state_machine.status_register = initial_status
```

### 2. 握手協議時序錯誤 (已修正)
**錯誤**: Running狀態未正確清除
**修正**: 指令執行完成後確保Running=0，等待PLC清零指令恢復Ready

### 3. 相機連接異常處理 (已修正)
**錯誤**: 相機斷線未設置Alarm狀態
**修正**: 相機異常時自動設置Alarm=1, Initialized=0

### 4. 線程同步問題 (已修正)
**錯誤**: 多線程訪問狀態機競爭條件
**修正**: 使用threading.Lock保護狀態機操作
```python
def set_bit(self, bit_pos: StatusBits, value: bool):
    with self.lock:
        # 原子化操作
```

### 5. 指令重複執行問題 (已修正)
**錯誤**: 同一指令被重複執行
**修正**: 實現command_processing標誌防重入
- last_control_command追蹤已處理指令
- command_processing防止重複執行

## 狀態機交握實現細節

### EnhancedModbusTcpClientService核心方法
```python
def _handshake_sync_loop(self):
    # 50ms高頻輪詢
    # 1. 更新狀態寄存器到PLC
    # 2. 讀取控制指令並處理握手邏輯
    # 3. 定期更新統計資訊
```

### 指令執行流程
```python
def _handle_action_command(self, command: ControlCommand):
    # 1. 檢查Ready狀態
    # 2. 設置Running狀態，清除Ready
    # 3. 異步執行指令
    # 4. 完成後清除Running狀態
```

### 異常處理機制
```python
def _update_initialization_status(self):
    # 檢查Modbus和相機連接狀態
    # 設置Initialized和Alarm位
    # 確保狀態一致性
```

## API介面文檔

### CCD1VisionController關鍵方法
```python
def set_modbus_server(self, ip: str, port: int) -> Dict[str, Any]
def connect_modbus(self) -> Dict[str, Any]  
def initialize_camera(self, ip_address: str) -> Dict[str, Any]
def capture_and_detect(self) -> VisionResult
def update_detection_params(self, **kwargs)
def get_status(self) -> Dict[str, Any]
```

### SystemStateMachine狀態控制
```python
def is_ready(self) -> bool
def is_running(self) -> bool
def is_alarm(self) -> bool
def is_initialized(self) -> bool
def set_ready(self, ready: bool)
def set_running(self, running: bool)
def reset_to_idle(self)
```

## 運行狀態輸出

### 系統啟動輸出
```
CCD1 視覺控制系統啟動中 (運動控制握手版本)
系統架構: Modbus TCP Client - 運動控制握手模式
連接模式: 主動連接外部PLC/HMI設備
握手協議: 指令/狀態模式，50ms高頻輪詢
Web介面啟動中... http://localhost:5051
```

### 握手協議運行日誌
```
收到新控制指令: 16 (上次: 0)
開始處理控制指令: 16
執行拍照+檢測指令
檢測成功，找到 3 個圓形
控制指令 16 執行完成
恢復Ready狀態
```

## 記憶體管理

### 線程生命週期
- daemon模式線程自動回收
- 握手同步線程正確退出機制
- 相機資源釋放管理

### 幀數據管理
- 固定大小幀緩存隊列
- 舊幀自動丟棄機制
- numpy數組記憶體回收

### 資源釋放
```python
def disconnect(self):
    # 停止握手同步線程
    # 斷開相機連接
    # 關閉Modbus連接
    # 釋放所有資源
```