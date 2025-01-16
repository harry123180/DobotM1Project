import numpy as np
# 帶入參數並計算真實世界座標

# 測試參數
K = np.array([
    [5527.91522, 0.00000, 1249.56097],
    [0.00000, 5523.37409, 997.41524],
    [0.00000, 0.00000, 1.00000]
])

R = np.array([
    [-0.33587388, -0.0982096, -0.93677298],
    [-0.75920111, -0.56042717, 0.33096082],
    [-0.55749656, 0.82236018, 0.11367201]
])

t = np.array([[206.36788893], [126.36569683], [993.2264883]])

# 校正後的像素點和深度
u, v = 1201.81, 1418.52 # 校正後的像素座標
depth = 710  # 假設深度 Z_c 為 1000

# 定義函數
def pixel_to_world(u, v, depth, K, R, t):
    uv_homogeneous = np.array([u, v, 1])  # 齊次像素坐標 (u, v, 1)
    K_inv = np.linalg.inv(K)  # 計算內參矩陣的逆矩陣
    cam_coords = depth * np.dot(K_inv, uv_homogeneous)  # 相機坐標 (X_c, Y_c, Z_c)

    # 將相機坐標轉換到世界坐標系
    cam_coords = cam_coords.reshape(3, 1)  # 確保為列向量
    world_coords = np.dot(np.linalg.inv(R), (cam_coords - t))  # 世界坐標系 (X_w, Y_w, Z_w)

    return world_coords.flatten()

# 計算真實世界坐標
world_coords = pixel_to_world(u, v, depth, K, R, t)
print(world_coords)
