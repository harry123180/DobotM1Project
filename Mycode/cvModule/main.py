import threading
from MVSsetting import Camera
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove, MyType, alarmAlarmJsonFile
import cv2
import numpy as np
import time
import re

# 全域變數(當前座標)
current_actual = None
algorithm_queue = None
enableStatus_robot = None
robotErrorState = False
globalLockValue = threading.Lock()
target_obj_n = 0
target_array = []
cmd = []
robot_run = False # 機器人運作狀態
def initialize_robot():
    global dashboard, move, feed
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

# 定義視覺任務線程
def visual_task():
    global target_obj_n,robot_run,target_array,cmd

    camera = Camera(name="MyCamera", device_number=0, resolution=(2592, 1944), exposure_time=50000)
    try:
        # 初始化並配置相機
        camera.initialize_camera()

        prev_time = time.time()
        
        # 持續捕獲並顯示影像
        while True:
            start_time = time.time()
            if robot_run:
                time.sleep(0.1)  # 機器人運行時暫停辨識
                continue
            local_target_array = []  # 暫存局部辨識結果
            local_target_obj_n = 0
            bayer_image = camera.capture_image()

            #bayer_image = buf
            # 將 Bayer GR 8 格式轉換為 RGB 格式
            rgb_image = cv2.cvtColor(bayer_image, cv2.COLOR_BAYER_GR2RGB)
            rgb_image = cv2.resize(rgb_image, (0, 0), fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)

            # 將影像轉為灰階
            gray_image = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2GRAY)

            # Canny 邊緣檢測
            edges = cv2.Canny(gray_image, 50, 150)
            # 使用膨脹與腐蝕來連接斷開的邊緣
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))  # 橢圓形核
            edges_dilated = cv2.dilate(edges, kernel, iterations=2)  # 膨脹操作
            edges_closed = cv2.erode(edges_dilated, kernel, iterations=1)  # 腐蝕操作

            # 找到輪廓
            contours, _ = cv2.findContours(edges_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 建立一個空白影像來繪製輪廓
            output = np.zeros_like(rgb_image)
            # 遍歷每個輪廓並篩選圓形輪廓
            for contour in contours:
                # 計算輪廓的周長與面積
                perimeter = cv2.arcLength(contour, True)
                area = cv2.contourArea(contour)

                if perimeter == 0:
                    continue

                # 計算圓形度 (4 * pi * 面積 / 周長^2)
                circularity = (4 * np.pi * area) / (perimeter ** 2)

                # 若圓形度大於 0.75 且面積大於一定值，認為是圓形
                if circularity > 0.75 and area > 100:
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    cX, cY = int(x), int(y)

                    # 繪製圓心
                    cv2.circle(output, (cX, cY), 5, (0, 0, 255), -1)  # 圓心為紅色

                    # 在圓心右下角標註座標
                    text_position = (cX + 15, cY + 15)
                    real_x, real_y = camera.pixel_to_world(cX * 4, cY * 4)
                    text = f"({int(real_x)}, {int(real_y)})"
                    cv2.putText(output, text, text_position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)  # 綠色文字
                    # 繪製輪廓並填充
                    cv2.drawContours(output, [contour], -1, 255, thickness=cv2.FILLED)
                    if(robot_run == False):
                        #print(target_array)
                        local_target_array.append([real_x, real_y])
                        local_target_obj_n += 1

            # 計算 FPS
            end_time = time.time()
            fps = 1 / (end_time - prev_time)
            prev_time = end_time
            
            # 更新全域變數
            globalLockValue.acquire()
            if not robot_run:  # 只有在機器人未運行時更新
                target_array = local_target_array
                target_obj_n = local_target_obj_n
            globalLockValue.release()

            cmd = target_array
            print(f"辨識到目標數量: {len(cmd)}")
            # 將 FPS 顯示在圖像上
            cv2.putText(output, f"FPS: {fps:.2f} N : {target_obj_n}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 1)
            # 顯示處理後的影像
            cv2.namedWindow("ORG", cv2.WINDOW_NORMAL)  # 可調整大小
            cv2.resizeWindow("ORG", 800, 600)  # 設定視窗大小
            cv2.imshow("ORG", output)

            # 按下 'q' 鍵退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"發生錯誤: {e}")
        raise
    finally:
        # 釋放相機資源
        camera.release_camera()
        cv2.destroyAllWindows()

# 定義等待使用者輸入線程
def user_input_task():
    global cmd,robot_run
    while True:
        user_input = input("請輸入指令 (1 開始機器人運動): ")
        if user_input == "1":
            globalLockValue.acquire()
            local_cmd = list(cmd)  # 複製當前辨識結果
            robot_run = True
            globalLockValue.release()
            print(f"執行機器人運動，目標數量: {len(local_cmd)}")
            threading.Thread(target=robot_motion_task, args=(local_cmd,)).start()

# 定義機器人運動線程任務
def robot_motion_task(local_cmd):
    global robot_run ,target_obj_n,target_array
    prv = target_array
    prv_n = target_obj_n
    #robot_run = True
    print(f"目標物件有{target_obj_n}個")
    setting_p_H = [218.95, -210.78, 240, -187]
    setting_p_L = [218.95, -210.78, 214, -187]
    pre_p = [266.77, -73.45, 240, -115]
    RunPoint(move, setting_p_H)
    WaitArrive(setting_p_H)
    RunPoint(move, pre_p)
    WaitArrive(pre_p)
    for target in local_cmd:
        RunPoint(move, [target[0], target[1], 240, -187])
        WaitArrive([target[0], target[1], 240, -187])
        #time.sleep(1)
        RunPoint(move, [target[0], target[1], 214, -187])
        WaitArrive([target[0], target[1], 214, -187])
        #time.sleep(1)
        RunPoint(move, [target[0], target[1], 240, -187])
        WaitArrive([target[0], target[1], 240, -187])
    RunPoint(move, pre_p)
    WaitArrive(pre_p)
    RunPoint(move, setting_p_H)
    WaitArrive(setting_p_H)
    robot_run = False



# 機器人相關函數
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
            enableStatus_robot = feedInfo['EnableStatus'][0]
            robotErrorState = feedInfo['ErrorStatus'][0]
            globalLockValue.release()
        time.sleep(0.001)

def WaitArrive(point_list):
    while True:
        is_arrive = True
        globalLockValue.acquire()
        if current_actual is not None:
            for index in range(4):
                if (abs(current_actual[index] - point_list[index]) > 1):
                    is_arrive = False
            if is_arrive:
                globalLockValue.release()
                return
        globalLockValue.release()
        time.sleep(0.001)

def ClearRobotError(dashboard: DobotApiDashboard):
    global robotErrorState
    dataController, dataServo = alarmAlarmJsonFile()  # 讀取控制器和伺服警報碼
    while True:
        globalLockValue.acquire()
        if robotErrorState:
            numbers = re.findall(r'-?\d+', dashboard.GetErrorID())
            numbers = [int(num) for num in numbers]
            if (numbers[0] == 0):
                if (len(numbers) > 1):
                    for i in numbers[1:]:
                        alarmState = False
                        if i == -2:
                            print("機器警報 機器碰撞", i)
                            alarmState = True
                        if alarmState:
                            continue
                        for item in dataController:
                            if i == item["id"]:
                                print("機器警報 控制器錯誤ID", i, item["zh_TW"]["description"])
                                alarmState = True
                                break
                        if alarmState:
                            continue
                        for item in dataServo:
                            if i == item["id"]:
                                print("機器警報 伺服錯誤ID", i, item["zh_TW"]["description"])
                                break

                    choose = input("輸入1, 將清除錯誤, 機器繼續運行: ")
                    if int(choose) == 1:
                        dashboard.ClearError()
                        time.sleep(0.01)
                        dashboard.Continue()

        else:
            if int(enableStatus_robot[0]) == 1 and int(algorithm_queue[0]) == 0:
                dashboard.Continue()
        globalLockValue.release()
        time.sleep(5)

if __name__ == "__main__":
    try:
        # 初始化機器人
        initialize_robot()

        # 啟動視覺任務線程
        visual_thread = threading.Thread(target=visual_task)
        visual_thread.start()

        # 啟動使用者輸入線程
        input_thread = threading.Thread(target=user_input_task)
        input_thread.start()

        # 等待所有線程結束
        visual_thread.join()
        input_thread.join()

    except Exception as e:
        print(f"主程序發生錯誤: {e}")
