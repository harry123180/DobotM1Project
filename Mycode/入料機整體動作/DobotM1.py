import threading
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove, MyType,alarmAlarmJsonFile
from vibration_plate import Vibration_plate
from time import sleep
import numpy as np
import re
from pgc_gripper_control import PGC_Gripper
from Vision import initialize_all_cameras, shutdown_all, GetObjectPosition
# 全域變數(當前座標)
current_actual = None
algorithm_queue = None
enableStatus_robot = None
robotErrorState = False
globalLockValue = threading.Lock()

def ConnectRobot():
    
    try:
        ip = "192.168.1.6"
        dashboardPort = 29999
        movePort = 30003
        feedPort = 30004
        print("正在建立連線...")
        dashboard = DobotApiDashboard(ip, dashboardPort)
        move = DobotApiMove(ip, movePort)
        feed = DobotApi(ip, feedPort)
        print(">.<連線成功>!<")
        return dashboard, move, feed
    except Exception as e:
        print(":(連線失敗:(")
        raise e

def RunPoint(move: DobotApiMove, point_list: list):
    move.MovJ(point_list[0], point_list[1], point_list[2], point_list[3])

def GetFeed(feed: DobotApi):
    global current_actual
    global algorithm_queue
    global enableStatus_robot
    global robotErrorState
    hasRead = 0
    while True:
        data = bytes()
        while hasRead < 1440:
            temp = feed.socket_dobot.recv(1440 - hasRead)
            if len(temp) > 0:
                hasRead += len(temp)
                data += temp
        hasRead = 0
        feedInfo = np.frombuffer(data, dtype=MyType)
        if hex((feedInfo['test_value'][0])) == '0x123456789abcdef':
            globalLockValue.acquire()
            # 更新屬性
            current_actual = feedInfo["tool_vector_actual"][0]
            algorithm_queue = feedInfo['isRunQueuedCmd'][0]
            enableStatus_robot=feedInfo['EnableStatus'][0]
            robotErrorState= feedInfo['ErrorStatus'][0]
            globalLockValue.release()
        sleep(0.001)

def WaitArrive(point_list):
    while True:
        is_arrive = True
        globalLockValue.acquire()
        if current_actual is not None:
            for index in range(4):
                if (abs(current_actual[index] - point_list[index]) > 1):
                    is_arrive = False
            if is_arrive :
                globalLockValue.release()
                return
        globalLockValue.release()  
        sleep(0.001)

def ClearRobotError(dashboard: DobotApiDashboard):
    global robotErrorState
    dataController,dataServo =alarmAlarmJsonFile()    # 讀取控制器和伺服警報碼
    while True:
      globalLockValue.acquire()
      if robotErrorState:
                numbers = re.findall(r'-?\d+', dashboard.GetErrorID())
                numbers= [int(num) for num in numbers]
                if (numbers[0] == 0):
                  if (len(numbers)>1):
                    for i in numbers[1:]:
                      alarmState=False
                      if i==-2:
                          print("機器警報 機器碰撞 ",i)
                          alarmState=True
                      if alarmState:
                          continue                
                      for item in dataController:
                        if  i==item["id"]:
                            print("機器警報 控制器錯誤ID",i,item["zh_TW"]["description"])
                            alarmState=True
                            break 
                      if alarmState:
                          continue
                      for item in dataServo:
                        if  i==item["id"]:
                            print("機器警報 伺服錯誤ID",i,item["zh_TW"]["description"])
                            break  
                       
                    choose = input("輸入1, 將清除錯誤, 機器繼續運行: ")     
                    if  int(choose)==1:
                        dashboard.ClearError()
                        sleep(0.01)
                        dashboard.Continue()

      else:  
         if int(enableStatus_robot[0])==1 and int(algorithm_queue[0])==0:
            dashboard.Continue()
      globalLockValue.release()
      sleep(5)
       
if __name__ == '__main__':
    gripper = PGC_Gripper(port='COM3', baudrate=115200, parity='N', stopbits=1, unit_id=1)
    VP = Vibration_plate("192.188.2.88", 1000, 10)
    initialize_all_cameras()#初始化相機
    sleep(2)
    #gripper.initialize()
    dashboard, move, feed = ConnectRobot()
    print("開始使能...")
    dashboard.EnableRobot()
    print("完成使能:)")
    feed_thread = threading.Thread(target=GetFeed, args=(feed,))
    feed_thread.setDaemon(True)
    feed_thread.start()
    feed_thread1 = threading.Thread(target=ClearRobotError, args=(dashboard,))
    feed_thread1.setDaemon(True)
    feed_thread1.start()
    print("循環執行...")
    
    VP_H = [-13.77,-339.45, 243.00, -143]
    CV_H = [260,-280,243,-143]
    CV_L = [260,-280,222,-143]
    CV_VP_MID = [105,-296,243,-143]
    #移到中繼點上方 等待
    RunPoint(move, CV_VP_MID)
    WaitArrive(CV_VP_MID)
    sleep(1)
    VP.backlight(1)
    positions = GetObjectPosition()
    print(positions[0][0],positions[0][1])
    point_a = [positions[0][0], positions[0][1], 243, -143]
    point_b = [positions[0][0],positions[0][1], 141, -143]
    sleep(1)
    VP.backlight(0)
    dashboard.DO(9, 1)
    gripper.set_force(10)
    gripper.set_speed(100)
    #閉夾爪
    gripper.set_position(0)
    #移到物件上方
    RunPoint(move, point_a)
    WaitArrive(point_a)
    sleep(1)
    #下降
    RunPoint(move, point_b)
    WaitArrive(point_b)
    #開夾爪
    gripper.set_position(400)
    sleep(2)
    #移到物件上方
    RunPoint(move, point_a)
    WaitArrive(point_a)
    #移動到中繼點
    RunPoint(move, CV_VP_MID)
    WaitArrive(CV_VP_MID)
    #移動到輸送帶上方
    RunPoint(move, CV_H)
    WaitArrive(CV_H)
    #移動到輸送帶放置點
    RunPoint(move, CV_L)
    WaitArrive(CV_L)
    #閉夾爪
    gripper.set_position(0)
    sleep(1)
    #移動到輸送帶上方
    RunPoint(move, CV_H)
    WaitArrive(CV_H)
    #移動到中繼點
    RunPoint(move, CV_VP_MID)
    WaitArrive(CV_VP_MID)
