import cv2
import numpy as np
import os

# 單張圖片路徑
image_path = 'C:\\Users\\123\\Documents\\GitHub\\DobotM1Project\\Mycode\\Correction\\26.jpg'

# 棋盤格規格
CHECKERBOARD = (17, 12)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# 讀取圖像
img = cv2.imread(image_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 找出棋盤角點
ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

if ret and corners.shape[0] == CHECKERBOARD[0] * CHECKERBOARD[1]:
    # 精煉角點位置
    corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

    # 繪製角點
    img_with_points = cv2.drawChessboardCorners(img.copy(), CHECKERBOARD, corners2, ret)

    # 儲存點位資料 (id, x, y)
    point_data = []
    for idx, corner in enumerate(corners2):
        x, y = corner.ravel()
        point_data.append([idx, x, y])
        corner_pos = tuple(corner.ravel().astype(int))
        cv2.putText(img_with_points, str(idx), corner_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

    # 顯示圖像（視窗可手動縮放）
    cv2.namedWindow("Chessboard with Corner Index", cv2.WINDOW_NORMAL)
    cv2.imshow("Chessboard with Corner Index", img_with_points)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # 取得原圖所在資料夾與檔名
    img_dir = os.path.dirname(image_path)
    base_filename = os.path.splitext(os.path.basename(image_path))[0]

    # 儲存標註圖像
    output_img_path = os.path.join(img_dir, base_filename + "_annotated.png")
    cv2.imwrite(output_img_path, img_with_points)
    print(f"已儲存標註圖像：{output_img_path}")

    # 儲存點位資料為 numpy 格式
    points_array = np.array(point_data, dtype=np.float32)
    output_npy_path = os.path.join(img_dir, base_filename + "_corner_points.npy")
    np.save(output_npy_path, points_array)
    print(f"已儲存角點座標資料：{output_npy_path}")

else:
    print("未偵測到完整的棋盤格角點。")
