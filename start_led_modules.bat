@echo off
echo 啟動DobotM1專案模組...
cd /d "c:\Users\user\Documents\GitHub\DobotM1Project"

echo 1. 啟動ModbusTCP服務器...
start "ModbusTCP Server" python ModbusServer/TCPServer.py

timeout /t 3

echo 2. 啟動LED主模組...
start "LED Main" python Automation/light/LED_main.py

timeout /t 2

echo 3. 啟動LED Web應用...
start "LED App" python Automation/light/LED_app.py

echo 啟動完成！
echo Web介面: http://localhost:5008
pause
