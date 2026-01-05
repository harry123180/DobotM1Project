# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dobot M1 Pro 四軸工業機械臂 TCP/IP 控制範例專案。

## Environment

- **Python**: 3.12.4
- **Robot IP**: LAN1=192.168.1.6, LAN2=192.168.2.6
- **Controller Version**: V1.5.5.0+

## TCP Port Reference

| Port | Function | Description |
|------|----------|-------------|
| 29999 | Dashboard | 設置、狀態查詢指令 |
| 30003 | Move | 運動指令 |
| 30004 | Realtime Feedback | 8ms週期，1440字節狀態數據 |

## Core API Classes

```python
from dobot_api import DobotApiDashboard, DobotApiMove

# 建立連接
dashboard = DobotApiDashboard("192.168.1.6", 29999)
move = DobotApiMove("192.168.1.6", 30003)
```

### DobotApiDashboard (29999)

**控制指令**:
- `EnableRobot(*dynParams)` - 使能 (可選參數: 負載重量, 偏心X/Y/Z)
- `DisableRobot()` - 下使能
- `ClearError()` - 清除告警
- `ResetRobot()` - 停止
- `EmergencyStop()` - 緊急停止

**狀態查詢**:
- `RobotMode()` - 返回狀態碼 (5=使能空閒, 7=運行中, 9=有告警)
- `GetAngle()` - 獲取關節角度
- `GetPose()` - 獲取笛卡爾座標
- `GetErrorID()` - 獲取錯誤碼

**速度設置**:
- `SpeedFactor(1-100)` - 全局速度比例
- `SpeedJ(1-100)` / `AccJ(1-100)` - 關節運動速度/加速度
- `SpeedL(1-100)` / `AccL(1-100)` - 直線運動速度/加速度

**IO控制**:
- `DO(index, status)` - 數位輸出 (隊列)
- `DOExecute(index, status)` - 數位輸出 (立即)
- `DI(index)` - 讀取數位輸入

**其他**:
- `User(index)` / `Tool(index)` - 設置座標系
- `SetArmOrientation(0/1)` - 手系設置 (M1 Pro)
- `StartDrag()` / `StopDrag()` - 拖拽模式

### DobotApiMove (30003)

**基本運動** (所有運動指令為隊列指令):
- `MovJ(x, y, z, r, *dynParams)` - 關節運動
- `MovL(x, y, z, r, *dynParams)` - 直線運動
- `JointMovJ(j1, j2, j3, j4, *dynParams)` - 關節座標運動

**相對運動**:
- `RelMovJ(x, y, z, r)` - 相對關節運動
- `RelMovL(x, y, z, r)` - 相對直線運動
- `RelJointMovJ(j1, j2, j3, j4)` - 關節座標相對運動

**圓弧運動**:
- `Arc(x1,y1,z1,r1, x2,y2,z2,r2)` - 圓弧 (中間點→終點)
- `Circle(x1,y1,z1,r1, x2,y2,z2,r2, count)` - 整圓

**點動**:
- `MoveJog(axis_id)` - 點動 (J1+/J1-/X+/X-等)
- `MoveJog()` - 停止點動

**同步**:
- `Sync()` - 等待隊列完成
- `SyncAll()` - 等待所有指令完成 (含擴展軸)

## Basic Usage Example

```python
from dobot_api import DobotApiDashboard, DobotApiMove

# 連接
dashboard = DobotApiDashboard("192.168.1.6", 29999)
move = DobotApiMove("192.168.1.6", 30003)

# 使能
dashboard.EnableRobot()

# 設置速度
dashboard.SpeedFactor(50)

# 運動
move.MovJ(300, 200, 200, 0)
move.MovL(400, 200, 200, 0)
move.Sync()

# 下使能並關閉
dashboard.DisableRobot()
dashboard.close()
move.close()
```

## IO Control Example

```python
# 隊列指令 (隨運動隊列執行)
dashboard.DO(1, 1)  # DO1 置高

# 立即指令 (馬上執行)
dashboard.DOExecute(1, 1)

# 運動過程中觸發IO
move.MovLIO(300, 200, 200, 0, (0, 50, 1, 1))  # 50%位置時DO1置高
```

## Message Format

```
發送: 指令名稱(參數1,參數2,...,參數N)
接收: ErrorID,{返回值},指令名稱(參數);
```

## RobotMode Return Values

| Code | State |
|------|-------|
| 4 | 未使能 |
| 5 | 使能且空閒 |
| 6 | 拖拽模式 |
| 7 | 運行中 |
| 9 | 有未清除告警 |
| 10 | 暫停狀態 |

## Key Files

| Path | Purpose |
|------|---------|
| `Automation/M1Pro/dobot_api.py` | Dobot TCP API 封裝 |
| `Automation/M1Pro/DobotAPI.md` | 完整 API 技術文檔 |
| `ExampleCode/DobotDemo/` | 官方範例程式 |

## Notes

1. 清除告警後需呼叫 `dashboard.Continue()` 重新啟動
2. 隊列指令與立即指令執行順序不同
3. 實時反饋數據採用小端格式
4. 指令名稱大小寫需注意: `wait()` vs `Wait()`, `pause()` vs `Pause()`
