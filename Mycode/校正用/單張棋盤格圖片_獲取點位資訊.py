import cv2
import numpy as np
from PIL import Image

# 定義棋盤格規格
CHECKERBOARD = (17, 12)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# 定義棋盤格 3D 點
objp = np.zeros((1, CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[0, :, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp = objp * 10  # 單位 10mm

# 相機內參矩陣
K = np.array([
    [5.48972546e+03, 0, 1.28728459e+03],
    [0.0, 5.48928732e+03, 9.41806709e+02],
    [0.0, 0.0, 1.0]
])

# 畸變係數
D = np.array([[-2.71633064e-02, -3.01872792e-01, 4.02247668e-03, -1.81802326e-05, 2.59132126e+00]])

# 目標點列表
target = [0,1,2,6,91,85]

# 單張圖片路徑
image_path = 'C:\\Users\\123\\Documents\\GitHub\\DobotM1Project\\Mycode\\converted_jpgs\\290.jpg'
img = cv2.imread(image_path)

if img is None:
    print("無法讀取圖片，請確認路徑正確。")
else:
    # 校正畸變
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    cv2.namedWindow('MyWindow', cv2.WINDOW_NORMAL)
    cv2.imshow("MyWindow", gray)
    cv2.waitKey(0)
    
    # 查找棋盤角點
    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, cv2.CALIB_CB_ADAPTIVE_THRESH +
                                           cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE)

    if ret:
        print("成功檢測到棋盤角點。")
        
        # 優化角點位置
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        
        # 檢查目標點
        total_corners = CHECKERBOARD[0] * CHECKERBOARD[1]
        for point in target:
            if point < total_corners and point < len(corners2):
                corner = corners2[point]
                pixel_x, pixel_y = corner.ravel()
                print(f"點 {point} 的像素座標: ({pixel_x:.2f}, {pixel_y:.2f})")
            else:
                print(f"沒有這個點: {point}")
        
        # 繪製棋盤格角點
        img_with_corners = cv2.drawChessboardCorners(img, CHECKERBOARD, corners2, ret)

        # 在角點上繪製編號
        for idx, corner in enumerate(corners2):
            corner_pos = tuple(corner.ravel().astype(int))
            cv2.putText(img_with_corners, str(idx), corner_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

        # 顯示結果
        cv2.namedWindow('Chessboard with Corners', cv2.WINDOW_NORMAL)
        cv2.imshow("Chessboard with Corners", img_with_corners)
        cv2.waitKey(0)

        # 儲存結果圖像
        output_path = "chessboard_with_corners.png"
        cv2.imwrite(output_path, img_with_corners)
        print(f"結果圖像已儲存為: {output_path}")
    else:
        print("未檢測到棋盤角點，請確認圖片是否正確包含棋盤格。")

if cv2.waitKey(1) & 0xFF == ord('q'):
    cv2.destroyAllWindows()