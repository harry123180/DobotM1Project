import numpy as np
# 帶入參數並計算真實世界座標

# 測試參數
# 相機內參矩陣
K = np.array([
    [7.42157429, 0, 1.23308448],
    [0.0, 7.47157429, 0.99655374],
    [0.0, 0.0, 1]
])

# 畸變係數
D = np.array([[-0.111665041, 0.706682197, 0.000284510564, 0.000578235313, 0.0]])
R = np.array([[ 9.99999756e-01, -6.98131644e-04,  0.00000000e+00],
              [ 6.98131644e-04,  9.99999756e-01,  0.00000000e+00],
              [ 0.00000000e+00,  0.00000000e+00,  1.00000000e+00]])

t = np.array([[-265.16868344+80], [-108.02824767], [654.6123158]])

# 校正後的像素點和深度
u, v = 1522, 1406 # 校正後的像素座標[1502.81, 311.67],
depth = 720  # 假設深度 Z_c 為 1000

# 定義函數
def pixel_to_world(u, v, depth, K, R, t):
    uv_homogeneous = np.array([u, v, 720])  # 齊次像素坐標 (u, v, 1)
    K_inv = np.linalg.inv(K)  # 計算內參矩陣的逆矩陣
    cam_coords = np.dot(K_inv, uv_homogeneous)  # 相機坐標 (X_c, Y_c, Z_c)

    # 將相機坐標轉換到世界坐標系
    #cam_coords = cam_coords.reshape(3, 1)  # 確保為列向量
    world_coords = np.dot(R.T, cam_coords - t.ravel())  # 世界坐標  # 世界坐標系 (X_w, Y_w, Z_w)

    return world_coords.flatten()

# 計算真實世界坐標
world_coords = pixel_to_world(u, v, depth, K, R, t)
print(world_coords)
