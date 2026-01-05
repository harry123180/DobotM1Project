# Dobot M1 Pro 學習專案

Dobot M1 Pro 四軸工業機械臂的 Python 控制範例與學習資源。

## 機械臂規格

- **型號**: Dobot M1 Pro (四軸 SCARA)
- **控制器版本**: V1.5.5.0+
- **通訊協議**: TCP/IP
- **預設 IP**: 192.168.1.6 (LAN1) / 192.168.2.6 (LAN2)

## 快速開始

### 1. 環境準備

```bash
pip install -r requirements.txt
```

### 2. 連接機械臂

```python
from Automation.M1Pro.dobot_api import DobotApiDashboard, DobotApiMove

# 建立連接
dashboard = DobotApiDashboard("192.168.1.6", 29999)
move = DobotApiMove("192.168.1.6", 30003)

# 使能機械臂
dashboard.EnableRobot()
```

### 3. 基本運動控制

```python
# 設置速度 (1-100%)
dashboard.SpeedFactor(50)

# 關節運動 (MovJ) - 點到點最快路徑
move.MovJ(300, 200, 200, 0)

# 直線運動 (MovL) - 直線軌跡
move.MovL(400, 200, 200, 0)

# 等待運動完成
move.Sync()

# 下使能並關閉連接
dashboard.DisableRobot()
dashboard.close()
move.close()
```

## TCP 端口說明

| 端口 | 功能 | 用途 |
|------|------|------|
| 29999 | Dashboard | 設置、狀態查詢、IO控制 |
| 30003 | Move | 運動指令 |
| 30004 | Realtime | 即時反饋 (8ms週期) |

## 常用 API

### Dashboard (29999) - 控制與狀態

```python
dashboard.EnableRobot()      # 使能
dashboard.DisableRobot()     # 下使能
dashboard.ClearError()       # 清除告警
dashboard.EmergencyStop()    # 緊急停止
dashboard.RobotMode()        # 查詢狀態
dashboard.GetPose()          # 獲取座標
dashboard.GetAngle()         # 獲取關節角度
dashboard.DO(index, status)  # 數位輸出
dashboard.DI(index)          # 數位輸入
```

### Move (30003) - 運動控制

```python
move.MovJ(x, y, z, r)        # 關節運動
move.MovL(x, y, z, r)        # 直線運動
move.JointMovJ(j1,j2,j3,j4)  # 關節座標運動
move.MoveJog("J1+")          # 點動
move.MoveJog()               # 停止點動
move.Sync()                  # 等待完成
```

## 機械臂狀態碼

```python
status = dashboard.RobotMode()
# 4: 未使能
# 5: 使能且空閒 (可執行運動)
# 7: 運行中
# 9: 有告警 (需 ClearError)
# 10: 暫停中
```

## 專案結構

```
DobotM1Project/
├── README.md                 # 本文件
├── CLAUDE.md                 # Claude Code 參考
├── requirements.txt          # Python 依賴
├── Automation/
│   └── M1Pro/
│       ├── dobot_api.py      # 核心 API (重要!)
│       └── DobotAPI.md       # 完整 API 文檔
├── ExampleCode/
│   └── DobotDemo/            # 官方範例程式
└── 一些文檔/
    └── 關於DobotM1Pro/
        ├── Dobot M1 Pro用户手册V1.4.pdf
        └── TCP_IP远程控制接口文档.pdf
```

## 學習路徑

1. **閱讀官方手冊** - `一些文檔/關於DobotM1Pro/`
2. **理解 API** - `Automation/M1Pro/DobotAPI.md`
3. **運行範例** - `ExampleCode/DobotDemo/`
4. **實際操作** - 從簡單的 MovJ/MovL 開始

## 安全注意事項

- 首次運行前確認機械臂周圍無障礙物
- 使用低速度 (`SpeedFactor(10)`) 進行測試
- 熟悉緊急停止按鈕位置
- 出現告警時先 `ClearError()` 再 `Continue()`

## 參考資源

- [Dobot 官方網站](https://www.dobot.cc/)
- `Automation/M1Pro/DobotAPI.md` - 完整 API 說明
- `一些文檔/關於DobotM1Pro/TCP_IP远程控制接口文档.pdf` - 官方通訊協議
