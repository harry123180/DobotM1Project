import cv2
import numpy as np
import glob
import matplotlib.pyplot as plt

# 定義棋盤格規格
CHECKERBOARD = (17, 12)
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# 定義世界坐標系中的 3D 點
objpoints = []
imgpoints = []

objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp = objp * 10  # 單位 10 mm

# 讀取所有圖像
images = glob.glob('C:\\Users\\123\\Documents\\GitHub\\DobotM1Project\\Mycode\\converted_jpgs\\*.jpg')
gray = None

for i, fname in enumerate(images):
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 查找棋盤角點
    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)
    if ret and corners.shape[0] == CHECKERBOARD[0] * CHECKERBOARD[1]:  # 確保角點數量一致
        objpoints.append(objp)
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        imgpoints.append(corners2)

        # 在圖像上畫出棋盤格角點
        img_with_points = cv2.drawChessboardCorners(img, CHECKERBOARD, corners2, ret)

        # 在角點上附加數字編號
        for idx, corner in enumerate(corners2):
            corner_pos = tuple(corner.ravel().astype(int))
            cv2.putText(img_with_points, str(idx), corner_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

        # 儲存結果圖像
        output_path = f"chessboard_image_{i}.png"
        cv2.imwrite(output_path, img_with_points)
        print(f"Saved annotated chessboard image: {output_path}")

# 展平 imgpoints
imgpoints_flat = [pts.reshape(-1, 2) for pts in imgpoints]

# 相機標定
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

print("重投影误差:\n")
print(ret)
print("内参 : \n")
print(mtx)
print("畸变 : \n")
print(dist)

# 計算重投影誤差和可視化
all_errors = []
plt.figure(figsize=(10, 6))

for i in range(len(objpoints)):
    imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
    imgpoints2 = imgpoints2.reshape(-1, 2)

    # 計算每張圖像的重投影誤差
    error_per_image = np.linalg.norm(imgpoints_flat[i] - imgpoints2, axis=1)
    mean_error_per_image = np.mean(error_per_image)
    all_errors.append(mean_error_per_image)

    # 繪製每張圖像的重投影誤差分布
    plt.plot(error_per_image, label=f"Image {i} Error")
    print(f"圖像 {i} 的平均重投影誤差: {mean_error_per_image:.4f}")

# 總平均重投影誤差
mean_reprojection_error = np.mean(all_errors)

plt.title("Reprojection Error per Image")
plt.xlabel("Point Index")
plt.ylabel("Reprojection Error (pixels)")
plt.legend()
plt.grid(True)
plt.show()

print("重投影误差 (Mean Reprojection Error):", mean_reprojection_error)

# 顯示每張圖像的平均重投影誤差
plt.figure(figsize=(10, 6))
plt.bar(range(len(all_errors)), all_errors, color='skyblue', label='Image Mean Error')
plt.axhline(y=mean_reprojection_error, color='r', linestyle='--', label='Overall Mean Error')
plt.title("Average Reprojection Error per Image")
plt.xlabel("Image Index")
plt.ylabel("Mean Reprojection Error (pixels)")
plt.legend()
plt.grid(True)
plt.show()
