# 自動化生產線系統架構

## 🎯 專案概述

這是一個基於 Python + MQTT + Flask 的分散式自動化生產線系統，包含視覺檢測、機械臂控制、輸送帶管理等多個協同工作的節點。系統採用事件驅動 + 優先級調度架構，確保高效穩定的生產流程。

## 🏗️ 系統架構

### 整體架構圖
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   震動入料盤     │    │   柔性震動盤      │    │   機械臂控制     │
│  feeder_bowl    │    │ vibration_bowl   │    │  robot_arm      │
│    :5001        │    │    :5002         │    │    :5003        │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                      │
          │              ┌───────▼────────┐             │
          │              │  MQTT Broker   │             │
          │              │   (Eclipse     │             │
          │              │   Mosquitto)   │             │
          │              └───────┬────────┘             │
          │                      │                      │
┌─────────▼───────┐    ┌─────────▼────────┐    ┌─────────▼───────┐
│    輸送帶        │    │   任務調度器      │    │   移載機構       │
│   conveyor      │    │task_scheduler    │    │  transfer       │
│    :5004        │    │    :5000         │    │    :5005        │
└─────────────────┘    └──────────────────┘    └─────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│    旋轉台        │    │    出料口        │    │   監控儀表板     │
│rotation_table   │    │  output_port     │    │   dashboard     │
│    :5006        │    │    :5007         │    │    :8080        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### 核心組件

- **MQTT Broker**: 系統通訊中樞 (Eclipse Mosquitto)
- **任務調度器**: 智慧任務分配和優先級管理
- **視覺節點**: CCD 相機控制和影像處理
- **控制節點**: 各種機械設備控制
- **Web 介面**: 每個節點的可視化監控和參數調整

## 🛠️ 技術堆疊

### 核心技術
- **Python 3.8+**: 主要開發語言
- **MQTT**: 節點間通訊協議
- **Flask**: Web 介面框架
- **OpenCV**: 視覺處理
- **NumPy**: 數值計算

### 主要函式庫

#### 通訊相關
```bash
paho-mqtt==1.6.1          # MQTT 客戶端
```

#### Web 介面
```bash
Flask==2.3.3              # Web 框架
Flask-CORS==4.0.0         # 跨域支援
Jinja2==3.1.2             # 模板引擎
```

#### 視覺處理
```bash
opencv-python==4.8.1.78   # 影像處理
numpy==1.24.3             # 數值計算
Pillow==10.0.1            # 影像格式支援
```

#### 並行處理
```bash
asyncio                   # 異步處理 (內建)
threading                 # 多執行緒 (內建)
concurrent.futures        # 並行執行 (內建)
queue                     # 執行緒安全佇列 (內建)
```

#### 工具函式庫
```bash
psutil==5.9.5             # 系統監控
dataclasses               # 資料結構 (內建)
json                      # JSON 處理 (內建)
time                      # 時間處理 (內建)
logging                   # 日誌記錄 (內建)
```

## 📁 專案結構

```
automation_system/
├── README.md
├── requirements.txt
├── config/
│   ├── mqtt_config.json
│   ├── system_config.json
│   └── node_configs/
│       ├── vibration_bowl_config.json
│       ├── robot_arm_config.json
│       └── ...
├── nodes/
│   ├── __init__.py
│   ├── base_node.py              # 基礎節點類別
│   ├── feeder_bowl_node.py       # 震動入料盤節點
│   ├── vibration_bowl_node.py    # 柔性震動盤節點 (含CCD1)
│   ├── robot_arm_node.py         # 機械臂節點
│   ├── conveyor_node.py          # 輸送帶節點 (含CCD2)
│   ├── transfer_node.py          # 移載機構節點
│   ├── rotation_table_node.py    # 旋轉台節點 (含CCD4)
│   └── output_port_node.py       # 出料口節點
├── scheduler/
│   ├── __init__.py
│   ├── task_scheduler.py         # 主要調度器
│   ├── priority_queue.py         # 優先級佇列
│   └── coordination_logic.py     # 協調邏輯
├── vision/
│   ├── __init__.py
│   ├── camera_controller.py      # 相機控制
│   ├── image_processor.py        # 影像處理
│   ├── vision_pipeline.py        # 處理管線
│   └── detection_algorithms.py   # 檢測演算法
├── communication/
│   ├── __init__.py
│   ├── mqtt_client.py           # MQTT 客戶端封裝
│   ├── message_types.py         # 訊息類型定義
│   └── protocol_handler.py      # 協議處理器
├── web/
│   ├── __init__.py
│   ├── flask_factory.py         # Flask 應用工廠
│   ├── templates/
│   │   ├── base.html
│   │   ├── node_dashboard.html
│   │   └── system_overview.html
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   └── api/
│       ├── __init__.py
│       ├── config_api.py        # 配置 API
│       ├── status_api.py        # 狀態 API
│       └── control_api.py       # 控制 API
├── utils/
│   ├── __init__.py
│   ├── config_manager.py        # 配置管理
│   ├── logger.py               # 日誌工具
│   ├── thread_utils.py         # 執行緒工具
│   └── data_structures.py      # 資料結構
├── dashboard/
│   ├── __init__.py
│   ├── dashboard_server.py     # 統一監控儀表板
│   └── aggregator.py          # 資料聚合器
├── tests/
│   ├── __init__.py
│   ├── test_nodes.py
│   ├── test_scheduler.py
│   ├── test_vision.py
│   └── test_communication.py
├── scripts/
│   ├── start_system.py         # 系統啟動腳本
│   ├── stop_system.py          # 系統停止腳本
│   ├── deploy_nodes.py         # 節點部署腳本
│   └── system_monitor.py       # 系統監控腳本
└── docs/
    ├── API.md
    ├── deployment.md
    ├── troubleshooting.md
    └── development_guide.md
```

## 🚀 快速開始

### 1. 環境準備

#### 安裝 Python 依賴
```bash
# 建立虛擬環境
python -m venv automation_env
source automation_env/bin/activate  # Linux/Mac
# automation_env\Scripts\activate   # Windows

# 安裝依賴
pip install -r requirements.txt
```

#### 安裝 MQTT Broker
```bash
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients

# CentOS/RHEL
sudo yum install mosquitto mosquitto-clients

# macOS
brew install mosquitto

# 或使用 Docker
docker run -it -p 1883:1883 -p 9001:9001 eclipse-mosquitto
```

### 2. 配置系統

#### MQTT 配置 (config/mqtt_config.json)
```json
{
  "broker_host": "localhost",
  "broker_port": 1883,
  "keepalive": 60,
  "qos": 1,
  "retain": false,
  "topics": {
    "task_requests": "automation/tasks/requests",
    "task_assignments": "automation/tasks/assignments",
    "status_updates": "automation/status/+",
    "system_broadcast": "automation/system/broadcast"
  }
}
```

#### 系統配置 (config/system_config.json)
```json
{
  "system_name": "Automation Production Line",
  "task_scheduler": {
    "priority_levels": 6,
    "max_queue_size": 100,
    "processing_interval": 0.1
  },
  "nodes": {
    "vibration_bowl": {
      "enabled": true,
      "host": "192.168.1.10",
      "web_port": 5002
    },
    "robot_arm": {
      "enabled": true,
      "host": "192.168.1.11",
      "web_port": 5003
    }
  }
}
```

### 3. 啟動系統

#### 方法一：使用啟動腳本
```bash
# 啟動完整系統
python scripts/start_system.py

# 啟動特定節點
python scripts/start_system.py --nodes vibration_bowl,robot_arm
```

#### 方法二：手動啟動
```bash
# 1. 啟動 MQTT Broker
mosquitto -p 1883

# 2. 啟動任務調度器
python scheduler/task_scheduler.py

# 3. 啟動各節點
python nodes/vibration_bowl_node.py
python nodes/robot_arm_node.py
python nodes/conveyor_node.py
# ... 其他節點

# 4. 啟動監控儀表板
python dashboard/dashboard_server.py
```

### 4. 存取介面

- **系統監控儀表板**: http://localhost:8080
- **任務調度器**: http://localhost:5000
- **柔性震動盤節點**: http://localhost:5002
- **機械臂節點**: http://localhost:5003
- **輸送帶節點**: http://localhost:5004
- **其他節點**: 依序遞增 port

## 🔧 核心功能

### 任務調度系統

#### 優先級定義
```python
class TaskPriority(Enum):
    EMERGENCY = 0      # 緊急停止、安全相關
    CRITICAL = 1       # 出料口清理、防阻塞
    HIGH = 2          # 旋轉台完成、視覺辨識完成
    NORMAL = 3        # 一般搬運、移載操作
    LOW = 4           # 維護、清理、補料
```

#### 調度演算法
- **加權優先級調度**: 綜合考慮優先級、等待時間、移動成本
- **防阻塞機制**: 出料口優先、管線暢通檢查
- **路徑最佳化**: 最短移動時間、批次處理
- **預測性調度**: 基於歷史數據和狀態預測

### 視覺處理系統

#### 處理管線
1. **影像擷取**: 網路軟觸發 → np.array 轉換
2. **預處理**: ROI 提取、降噪、增強
3. **特徵檢測**: 物件識別、位置計算、方向判斷
4. **結果處理**: 座標轉換、信心度評估、結果快取

#### 最佳化策略
- **並行處理**: 擷取、處理、結果發布三執行緒並行
- **預先準備**: 相機預熱、模板預載、記憶體預配置
- **智慧觸發**: 基於系統狀態的條件觸發
- **早期終止**: 快速預檢查避免無效處理

### 通訊架構

#### MQTT 主題結構
```
automation/
├── tasks/
│   ├── requests          # 任務請求
│   ├── assignments       # 任務分配
│   └── completed         # 任務完成
├── nodes/
│   ├── {node_id}/
│   │   ├── status        # 節點狀態
│   │   ├── config        # 配置更新
│   │   └── control       # 控制指令
├── vision/
│   ├── ccd1/parts_detected
│   ├── ccd2/orientation_classified
│   └── ccd4/rotation_complete
├── system/
│   ├── broadcast         # 系統廣播
│   ├── emergency         # 緊急停止
│   └── coordination      # 協調訊息
```

## 📊 監控與運維

### Web 介面功能

#### 節點儀表板
- **即時狀態**: 運行狀態、任務進度、效能指標
- **參數調整**: 即時修改處理參數、閾值設定
- **手動控制**: 測試觸發、手動操作、調試功能
- **歷史數據**: 處理時間、成功率、錯誤日誌

#### 系統總覽
- **拓撲監控**: 節點連接狀態、通訊延遲
- **任務佇列**: 當前任務、等待佇列、處理統計
- **效能分析**: 產能統計、瓶頸分析、最佳化建議
- **警報管理**: 異常檢測、故障預警、恢復建議

### 日誌系統
```python
# 日誌配置
LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/automation.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
        'console': {
            'class': 'logging.StreamHandler',
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file', 'console']
    }
}
```

## 🔄 部署策略

### 開發環境
```bash
# 單機部署
python scripts/start_system.py --mode development
```

### 生產環境

#### 分散式部署
```bash
# 節點1: 任務調度器 + 監控
python scheduler/task_scheduler.py --production
python dashboard/dashboard_server.py --production

# 節點2: 視覺處理節點
python nodes/vibration_bowl_node.py --production
python nodes/conveyor_node.py --production

# 節點3: 控制節點
python nodes/robot_arm_node.py --production
python nodes/transfer_node.py --production
```

#### Docker 部署
```dockerfile
# Dockerfile
FROM python:3.8-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "scripts/start_system.py", "--production"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  mqtt-broker:
    image: eclipse-mosquitto:latest
    ports:
      - "1883:1883"
      - "9001:9001"
  
  task-scheduler:
    build: .
    command: python scheduler/task_scheduler.py
    depends_on:
      - mqtt-broker
  
  vibration-bowl:
    build: .
    command: python nodes/vibration_bowl_node.py
    depends_on:
      - mqtt-broker
    ports:
      - "5002:5002"
```

## 🧪 測試

### 單元測試
```bash
# 執行所有測試
python -m pytest tests/

# 執行特定測試
python -m pytest tests/test_nodes.py -v

# 測試覆蓋率
python -m pytest --cov=nodes tests/
```

### 整合測試
```bash
# 啟動測試環境
python scripts/start_test_environment.py

# 執行整合測試
python tests/integration_tests.py
```

## 📈 效能調校

### 系統最佳化
- **執行緒優先級**: 核心業務 > Web 介面
- **CPU 親和性**: 綁定關鍵執行緒到特定核心
- **記憶體管理**: 預分配緩衝區、避免動態分配
- **網路最佳化**: 專用網路介面、QoS 設定

### 視覺處理最佳化
- **ROI 限制**: 只處理感興趣區域
- **多解析度**: 先低解析度定位，再高解析度精確檢測
- **演算法選擇**: 針對特定物件選擇最快演算法
- **並行處理**: 多執行緒管線化處理

## 🚨 故障排除

### 常見問題

#### MQTT 連接問題
```bash
# 檢查 MQTT 服務
mosquitto_sub -h localhost -t automation/+/status

# 測試發布
mosquitto_pub -h localhost -t automation/test -m "hello"
```

#### 節點無響應
```bash
# 檢查節點狀態
curl http://localhost:5002/api/status

# 檢查系統日誌
tail -f logs/automation.log
```

#### 效能問題
```bash
# 監控系統資源
python scripts/system_monitor.py

# 分析處理瓶頸
python utils/performance_analyzer.py
```

## 🤝 開發指南

### 新增節點
1. 繼承 `BaseNode` 類別
2. 實現 `setup_hardware()`, `process_task()` 方法
3. 設定 MQTT 主題和 Flask 路由
4. 更新系統配置

### 自定義視覺演算法
1. 在 `vision/detection_algorithms.py` 新增演算法
2. 更新 `VisionProcessor` 選擇邏輯
3. 調整參數配置介面

### API 擴展
1. 在對應的 `web/api/` 模組新增 API
2. 更新 Flask 路由註冊
3. 更新前端介面

## 📄 授權

MIT License

## 👥 貢獻者

- 專案負責人: [Your Name]
- 視覺演算法: [Vision Team]
- 控制系統: [Control Team]
- Web 開發: [Frontend Team]

## 📞 聯絡資訊

- 專案文檔: [Project Wiki]
- 問題回報: [Issue Tracker]
- 技術支援: [Support Email]

---

**最後更新**: 2025年6月
**版本**: v1.0.0