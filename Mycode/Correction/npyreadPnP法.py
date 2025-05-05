import cv2
import numpy as np
import os

# ========== 相機內參與畸變 ==========
K = np.array([
    [5527.91522,    0.0,       1249.56097],
    [0.0,        5523.37409,    997.41524],
    [0.0,           0.0,          1.0]
])

D = np.array([
    -0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681
])

# ========== 讀取資料 ==========
current_dir = os.path.dirname(__file__)
corner_path = os.path.join(current_dir, "26_corner_points.npy")
world_path = os.path.join(current_dir, "world_points.npy")

corner_data = np.load(corner_path)   # shape: (N, 3)
world_data = np.load(world_path)     # shape: (N, 3)

# 檢查匹配：根據 id 對齊兩組資料
corner_dict = {int(row[0]): row[1:] for row in corner_data}
world_dict = {int(row[0]): row[1:] for row in world_data}

# 取共同點位（交集）
common_ids = sorted(set(corner_dict.keys()) & set(world_dict.keys()))
if len(common_ids) < 4:
    raise ValueError("共同點位不足以進行PnP（需至少4點）")

image_points = np.array([corner_dict[i] for i in common_ids], dtype=np.float32)
object_points = np.array([[*world_dict[i], 0.0] for i in common_ids], dtype=np.float32)  # 加入 Z=0

# ========== PnP 解算 ==========
success, rvec, tvec = cv2.solvePnP(object_points, image_points, K, D, flags=cv2.SOLVEPNP_ITERATIVE)

if success:
    print("PnP計算成功！")

    # 旋轉矩陣
    R, _ = cv2.Rodrigues(rvec)
    print("\n旋轉向量 (rvec):\n", rvec.flatten())
    print("\n平移向量 (tvec) 單位(mm):\n", tvec.flatten())
    print("\n旋轉矩陣 (R):\n", R)

    # 外參矩陣 [R | t]
    extrinsic = np.hstack((R, tvec))
    print("\n外參矩陣 [R|t]:\n", extrinsic)

    # 重投影誤差
    reprojected_points, _ = cv2.projectPoints(object_points, rvec, tvec, K, D)
    reprojected_points = reprojected_points.reshape(-1, 2)
    errors = np.linalg.norm(image_points - reprojected_points, axis=1)
    mean_error = np.mean(errors)

    print("\n重投影誤差:")
    for i, (pid, err) in enumerate(zip(common_ids, errors)):
        print(f"點 {pid}: 誤差 {err:.2f} 像素")
    print(f"\n平均重投影誤差: {mean_error:.2f} 像素")

    # 歐拉角計算
    def rotationMatrixToEulerAngles(R):
        sy = np.sqrt(R[0,0] ** 2 + R[1,0] ** 2)
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

    euler_rad = rotationMatrixToEulerAngles(R)
    euler_deg = np.degrees(euler_rad)
    print("\n歐拉角 (度):", euler_deg)

    # 相機位置
    camera_position = -R.T @ tvec
    print("\n相機在世界座標系中的位置 (mm):")
    print(camera_position.flatten())
else:
    print("PnP計算失敗！")
