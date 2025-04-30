import cv2
import numpy as np

# 相機內參矩陣 (更新後)
K = np.array([
    [5527.91522,    0.0,       1249.56097],
    [0.0,        5523.37409,    997.41524],
    [0.0,           0.0,          1.0]
])

# 畸變係數 (更新後)
D = np.array([
    -0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681
])

# 目標點信息
target_points = [0, 1, 2, 6, 91, 85]

# 這些點的像素座標 (從您的輸出結果)
image_coords = {
    0: [1015.33, 1772.74],
    1: [1019.41, 1670.46],
    2: [1023.86, 1567.90],
    6: [1041.06, 1159.16],
    91: [1552.26, 1180.86],
    85: [1527.08, 1795.55]
}

# 更新後的真實世界座標 (單位: mm)
# 格式: 點位索引: [X, Y, Z]
world_coords = {
    0: [38.75, -349.44, 0],
    1: [28.75, -349.44, 0],
    2: [18.75, -349.44, 0],
    6: [-23.25, -349.44, 0],
    91: [-23.25, -301.44, 0],
    85: [36.75, -300.24, 0]
}

# 準備PnP需要的輸入數據
object_points = np.array([world_coords[p] for p in target_points], dtype=np.float32)
image_points = np.array([image_coords[p] for p in target_points], dtype=np.float32)

# 使用solvePnP計算外參 (添加畸變係數)
success, rvec, tvec = cv2.solvePnP(object_points, 
                                  image_points, 
                                  K, D,
                                  flags=cv2.SOLVEPNP_ITERATIVE)

if success:
    print("PnP計算成功！")
    
    # 將旋轉向量轉換為旋轉矩陣
    R, _ = cv2.Rodrigues(rvec)
    
    print("\n旋轉向量 (rvec):")
    print(rvec.flatten())
    
    print("\n平移向量 (tvec) 單位(mm):")
    print(tvec.flatten())
    
    print("\n旋轉矩陣 (R):")
    print(R)
    
    print("\n外參矩陣 [R|t]:")
    extrinsic = np.hstack((R, tvec))
    print(extrinsic)
    
    # 計算重投影誤差
    reprojected_points, _ = cv2.projectPoints(object_points, rvec, tvec, K, D)
    reprojected_points = reprojected_points.reshape(-1, 2)
    
    errors = np.linalg.norm(image_points - reprojected_points, axis=1)
    mean_error = np.mean(errors)
    
    print("\n重投影誤差 (像素):")
    for i, (point, error) in enumerate(zip(target_points, errors)):
        print(f"點 {point}: {error:.4f} 像素")
    print(f"\n平均重投影誤差: {mean_error:.4f} 像素")
    
    # 可視化檢查
    print("\n檢查點位對應關係:")
    for i, point in enumerate(target_points):
        print(f"點 {point}:")
        print(f"  世界座標 (mm): {object_points[i]}")
        print(f"  像素座標: {image_points[i]}")
        print(f"  重投影像素座標: {reprojected_points[i].round(2)}")
        print(f"  誤差: {errors[i]:.2f} 像素")
else:
    print("PnP計算失敗！")

# 將旋轉矩陣轉換為歐拉角（可選）
def rotationMatrixToEulerAngles(R):
    sy = np.sqrt(R[0,0] * R[0,0] + R[1,0] * R[1,0])
    singular = sy < 1e-6

    if not singular:
        x = np.arctan2(R[2,1], R[2,2])
        y = np.arctan2(-R[2,0], sy)
        z = np.arctan2(R[1,0], R[0,0])
    else:
        x = np.arctan2(-R[1,2], R[1,1])
        y = np.arctan2(-R[2,0], sy)
        z = 0

    return np.array([x, y, z])

if success:
    euler_angles = rotationMatrixToEulerAngles(R)
    print("\n歐拉角 (弧度):", euler_angles)
    print("歐拉角 (度):", np.degrees(euler_angles))
    
    # 計算相機在世界座標系中的位置
    camera_position = -R.T @ tvec
    print("\n相機在世界座標系中的位置 (mm):")
    print(camera_position.flatten())