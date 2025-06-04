# 整合式工業控制系統

一個集成機器人控制、相機視覺和ModBus通訊的完整工業自動化解決方案。

## 🚀 功能特色

### 🤖 Dobot M1 Pro 機器人控制
- 即時位置監控與狀態顯示
- JOG控制（關節模式/笛卡爾模式）
- 點位管理與軌跡規劃
- 自定義動作腳本執行
- 數位I/O操作
- 安全保護功能

### 📹 Hikvision 相機控制
- 即時影像串流
- 相機參數調整（曝光、增益、幀率）
- 觸發模式/連續模式
- 影像保存（BMP/JPEG）
- 設備自動識別

### 🔌 ModBus 通訊
- 支援 ModBus TCP 和 RTU 協定
- 暫存器讀寫操作
- 自動刷新功能
- 批量操作支援
- 通訊狀態監控

## 📋 系統需求

### Python 環境
- Python 3.7 或更高版本
- Windows 10/11 (推薦)

### 核心套件
```bash
pip install flask flask-socketio
```

### 機器人控制（可選）
```bash
# 需要 Dobot API 相關模組
# dobot_api.py 和相關依賴
```

### 相機控制（可選）
```bash
# 需要 Hikvision SDK 相關模組
# MvCameraControl_class.py 和相關 DLL 文件
```

### ModBus 通訊（可選）
```bash
pip install pymodbus pyserial
```

## 🛠️ 安裝步驟

1. **下載專案**
   ```bash
   git clone <repository-url>
   cd integrated-control-system
   ```

2. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   ```

3. **設置模組**
   - 將 Dobot API 相關文件放置在專案根目錄
   - 將 Hikvision SDK 相關文件放置在專案根目錄
   - 確保所需的 DLL 文件在系統路徑中

4. **啟動系統**
   ```bash
   python main_app.py
   ```

5. **訪問界面**
   ```
   http://localhost:5000
   ```

## 📁 專案結構

```
project/
├── main_app.py              # 主應用程式
├── templates/               # HTML 模板
│   ├── main_index.html     # 主選單頁面
│   ├── robot_index.html    # 機器人控制頁面
│   ├── camera_index.html   # 相機控制頁面
│   ├── modbus_tcp.html     # ModBus TCP 頁面
│   ├── modbus_rtu.html     # ModBus RTU 頁面
│   └── error.html          # 錯誤頁面
├── static/                  # 靜態資源（如有需要）
├── dobot_api.py            # Dobot API（需要）
├── Camera_API.py           # 相機 API（需要）
├── MvCameraControl_class.py # Hikvision SDK（需要）
├── waypoints.json          # 點位資料（自動生成）
├── modbus_comments.json    # ModBus 註解（自動生成）
├── system.log              # 系統日誌（自動生成）
└── requirements.txt        # Python 依賴
```

## 🔧 配置說明

### 機器人配置
- 預設IP：192.168.1.6
- Dashboard Port：29999
- Move Port：30003
- Feedback Port：30004

### 相機配置
- 支援 GigE 和 USB3 相機
- 自動設備識別
- 可調整參數：曝光時間、增益、幀率

### ModBus 配置
- TCP：預設端口 502
- RTU：支援多種波特率和串口參數
- Slave ID 可配置

## 🖥️ 使用指南

### 1. 啟動系統
運行 `python main_app.py` 後，系統會顯示各模組的可用狀態。

### 2. 機器人控制
1. 點擊「Dobot M1 Pro 控制」進入機器人控制界面
2. 輸入機器人 IP 並點擊「連接」
3. 連接成功後點擊「使能」啟動機器人
4. 使用 JOG 控制進行手動操作
5. 可記錄點位並執行自定義腳本

### 3. 相機控制
1. 點擊「Hikvision 相機控制」進入相機界面
2. 點擊「重新整理」掃描可用設備
3. 選擇設備並點擊「連接」
4. 點擊「開始串流」查看即時影像
5. 可調整參數並進行拍照保存

### 4. ModBus 通訊
1. 點擊「ModBus TCP」或「ModBus RTU」
2. 配置連接參數並連接
3. 進行暫存器讀寫操作
4. 可設置自動刷新和批量操作

## ⚠️ 注意事項

### 安全須知
- 使用機器人前請確保安全區域清空
- 首次使用建議降低速度進行測試
- 緊急情況可使用「緊急停止」功能

### 故障排除
- 如果模組顯示「不可用」，請檢查相關依賴是否已安裝
- 機器人連接失敗請檢查網路設置和IP位址
- 相機無法識別請檢查USB連接或網路設置
- ModBus 通訊失敗請檢查設備地址和通訊參數

### 效能優化
- 建議在專用網路環境中使用
- 對於高頻率操作，可調整刷新間隔
- 定期清理日誌文件以節省空間

## 🔄 更新日誌

### v1.0.0
- 初始版本發布
- 集成三大功能模組
- 提供完整的Web界面
- 支援跨平臺部署

## 📞 技術支援

如遇到問題或需要技術支援，請聯繫：
- 電子郵件：support@company.com
- 技術文檔：[文檔連結]
- 問題回報：[Issue 連結]

## 📄 授權條款

本專案採用 MIT 授權條款，詳見 LICENSE 文件。

---

**© 2024 整合式工業控制系統 | 台灣製造**