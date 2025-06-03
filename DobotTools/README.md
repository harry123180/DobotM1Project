# Dobot M1 Pro Web控制系統 - 完整版

## 🎯 修正內容

### ✅ 已修正的問題

1. **JOG軸編號問題**: 修正了關節模式下的軸編號映射，確保J1-J4對應正確
2. **緊急停止與清除錯誤**: 實現了完整的API和前端功能
3. **點位記錄功能**: 完善了點位保存、載入、移動功能
4. **腳本載入**: 改為直接在網頁上編輯Python腳本內容
5. **DO狀態顯示與控制**: 新增了DO狀態的即時顯示和點擊控制功能

### 🆕 新增功能

1. **ModbusTCP頁面**: 完整的TCP客戶端控制介面
2. **ModbusRTU頁面**: 完整的RTU主站控制介面  
3. **日誌系統**: 統一的操作和錯誤日誌記錄
4. **DO控制**: 點擊DO指示器可直接控制數位輸出

## 📋 功能特色

### 🤖 機器人控制
- ✅ **即時狀態監控**: 關節位置、笛卡爾坐標、電流、DI/DO狀態
- ✅ **JOG控制**: 關節/笛卡爾模式切換，支持鍵盤快捷鍵
- ✅ **點位管理**: A-Z點位自動管理，支持記錄和移動
- ✅ **緊急控制**: 緊急停止、復位、清除錯誤
- ✅ **自定義腳本**: 5個動作按鈕，支持Python腳本執行

### 📡 ModbusTCP控制
- ✅ **連接管理**: IP、端口、SlaveID設定
- ✅ **暫存器操作**: 單個/批量讀寫保持暫存器
- ✅ **自動刷新**: 可配置的自動讀取功能  
- ✅ **註解功能**: 為每個暫存器添加用途說明
- ✅ **即時監控**: 數值變化視覺化提示

### 📺 ModbusRTU控制
- ✅ **串口掃描**: 自動掃描可用COM端口
- ✅ **參數配置**: 波特率、數據位、校驗位、停止位
- ✅ **暫存器操作**: 完整的讀寫功能
- ✅ **自動刷新**: 與TCP版本相同的功能
- ✅ **註解管理**: 獨立的RTU暫存器註解

### 📊 日誌系統
- ✅ **統一日誌**: 機器人、ModbusTCP、ModbusRTU操作記錄
- ✅ **錯誤追蹤**: 詳細的錯誤信息和時間戳
- ✅ **即時顯示**: 右下角浮動日誌窗口

## 🚀 快速開始

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. 文件結構
```
dobot_web_controller/
├── app_enhanced.py          # 增強版Flask應用
├── dobot_api.py            # Dobot API庫
├── requirements.txt        # Python依賴
├── templates/
│   ├── index.html          # 主控制頁面  
│   ├── modbus_tcp.html     # ModbusTCP頁面
│   └── modbus_rtu.html     # ModbusRTU頁面
├── waypoints.json          # 點位保存文件
├── modbus_comments.json    # Modbus註解文件
├── system.log             # 系統日誌文件
└── files/                 # 告警文件目錄
    ├── alarm_controller.json
    └── alarm_servo.json
```

### 3. 運行系統
```bash
python app_enhanced.py
```

### 4. 訪問界面
- **主控制界面**: http://localhost:5000
- **ModbusTCP控制**: http://localhost:5000/modbus_tcp  
- **ModbusRTU控制**: http://localhost:5000/modbus_rtu

## 🛠️ 使用指南

### 機器人控制

1. **連接機器人**
   - 輸入IP地址(默認192.168.1.6)
   - 設置端口(Dashboard: 29999, Move: 30003, Feedback: 30004)
   - 點擊"連接"按鈕

2. **基本操作**
   - **使能/下使能**: 控制機器人電機狀態
   - **JOG控制**: 按住按鈕進行點動，支持關節/笛卡爾模式切換
   - **DO控制**: 點擊DO指示器直接控制數位輸出
   - **緊急停止**: 立即停止所有動作並下電

3. **點位管理**
   - 選擇點位 → 移動到位置 → 點擊"記錄當前點位"
   - 支持關節和笛卡爾兩種移動方式
   - A點為預設點位，不可刪除

4. **動作腳本**
   - 點擊"選擇腳本"編輯Python代碼
   - 支持dobot_controller、time模組
   - 多線程執行，不會阻塞界面

### ModbusTCP操作

1. **建立連接**
   - 輸入服務器IP和端口(默認502)
   - 設置Slave ID
   - 點擊"連接"建立TCP連接

2. **暫存器操作**
   - 設置起始地址和讀取數量
   - 啟用自動刷新可定期更新數據
   - 支持單個和批量寫入

3. **註解管理**
   - 為每個暫存器添加用途說明
   - 註解會自動保存到文件

### ModbusRTU操作

1. **串口設置**
   - 點擊"掃描"獲取可用COM端口
   - 選擇波特率(默認9600)
   - 設置數據格式(默認8,N,1)

2. **通信測試**
   - 連接後自動讀取暫存器驗證通信
   - 檢查日誌確認通信狀態

## 📝 腳本開發

### DO4閃爍示例腳本
```python
import time

def main():
    print("開始DO4閃爍")
    
    # 使能機器人
    dobot_controller.enable_robot()
    time.sleep(1)
    
    # 閃爍4次，每次3秒
    for i in range(4):
        print(f"閃爍第 {i+1} 次")
        
        # 高電平3秒
        dobot_controller.add_command({
            'type': 'do',
            'params': {'index': 4, 'status': 1}
        })
        time.sleep(3)
        
        # 低電平3秒  
        dobot_controller.add_command({
            'type': 'do',
            'params': {'index': 4, 'status': 0}
        })
        time.sleep(3)
    
    print("DO4閃爍完成")

if __name__ == "__main__":
    main()
```

### 允許的操作
```python
# 機器人控制
dobot_controller.enable_robot()
dobot_controller.disable_robot()
dobot_controller.add_command({'type': 'movj', 'params': {...}})
dobot_controller.add_command({'type': 'do', 'params': {'index': 1, 'status': 1}})

# 狀態讀取
pos = dobot_controller.robot_state['joint_positions']
di = dobot_controller.robot_state['digital_inputs']

# 時間控制
import time
time.sleep(1)
```

## ⌨️ 鍵盤快捷鍵

| 按鍵 | 關節模式 | 笛卡爾模式 |
|------|----------|------------|
| ↑ | J2+ | Z+ |
| ↓ | J2- | Z- |  
| ← | J1- | X- |
| → | J1+ | X+ |
| Page Up | J3+ | Y+ |
| Page Down | J3- | Y- |
| Home | J4+ | R+ |
| End | J4- | R- |

## 🔧 故障排除

### 常見問題

1. **機器人連接失敗**
   - 檢查IP地址和端口設置
   - 確認機器人控制器已開機
   - 檢查網絡連接和防火牆

2. **JOG無法使用**  
   - 確保機器人已連接且使能
   - 檢查機器人是否處於錯誤狀態
   - 嘗試清除錯誤後重新使能

3. **ModbusTCP連接失敗**
   - 確認目標設備IP和端口
   - 檢查網絡連通性
   - 驗證Slave ID設置

4. **ModbusRTU通信錯誤**
   - 檢查串口參數設置
   - 確認COM端口未被占用
   - 驗證設備地址和通信參數

5. **腳本執行失敗**
   - 檢查腳本語法錯誤
   - 確認使用的模組是否被允許
   - 查看日誌獲取詳細錯誤信息

### 日誌分析
- 主界面右下角顯示實時日誌
- 系統日誌保存在system.log文件中
- 不同類型日誌用顏色區分(成功/警告/錯誤)

## 🔒 安全機制

### 腳本安全
- AST語法樹分析防止惡意代碼
- 限制允許的模組和函數
- 沙盒執行環境

### 通信安全  
- TCP連接超時保護
- 串口通信錯誤重試
- 指令隊列防止指令堆積

### 系統保護
- 緊急停止優先級最高
- 自動斷線檢測和重連
- 完整的錯誤處理和日誌記錄

## 📈 性能優化

- WebSocket即時通信(8ms更新)
- 指令隊列FIFO處理
- 多線程架構避免阻塞
- 前端數據緩存和增量更新

## 🆕 版本更新

- **版本**: 2.0.0  
- **兼容性**: Dobot M1 Pro四軸機器人
- **新增**: ModbusTCP/RTU完整支持
- **修正**: JOG軸映射、腳本功能、點位管理
- **優化**: 用戶體驗和錯誤處理

## 📞 技術支持

如遇到技術問題，請檢查：
1. 系統日誌文件中的錯誤信息
2. 瀏覽器開發者工具的網絡和控制台錯誤
3. 機器人控制器的狀態和錯誤碼

## 🎯 下一步發展

- [ ] 軌跡規劃和路徑優化
- [ ] 更多Modbus功能碼支持
- [ ] 數據可視化和統計
- [ ] 遠程監控和報警
- [ ] 移動端適配優化本執行失敗**
   - 檢查腳本語法
   - 確認使用的庫是否被允許
   - 查看系統日誌獲取詳細錯誤

4. **狀態更新異常**
   - 檢查WebSocket連接
   - 重新載入頁面
   - 檢查網絡連接

### 日誌查看
- Web界面右下角顯示實時日誌
- 後端控制台輸出詳細錯誤信息
- 使用瀏覽器開發者工具查看網絡請求

## 開發者說明

### 擴展API
```python
# 在app.py中添加新的API端點
@app.route('/api/custom/function', methods=['POST'])
def custom_function():
    # 自定義功能實現
    return jsonify({'success': True})
```

### 自定義腳本命令
```python
# 在DobotController類中添加新方法
def custom_command(self, params):
    # 自定義指令實現
    self.add_command({'type': 'custom', 'params': params})
```

### 前端擴展
```javascript
// 在index.html中添加新功能
function customFunction() {
    fetch('/api/custom/function', {method: 'POST'})
    .then(response => response.json())
    .then(data => console.log(data));
}
```

## 版本資訊

- **版本**: 1.0.0
- **兼容性**: Dobot M1 Pro (四軸機器人)
- **Python版本**: 3.7+
- **瀏覽器支持**: Chrome 80+, Firefox 70+, Safari 13+

## 授權條款

本項目為內部開發工具，請勿用於商業用途。