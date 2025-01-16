import cv2
import numpy as np

# 相機內參矩陣
K = np.array([
    [7.42157429, 0, 1.23308448],
    [0.0, 7.47157429, 0.99655374],
    [0.0, 0.0, 1]
])

# 畸變係數
D = np.array([[-0.111665041, 0.706682197, 0.000284510564, 0.000578235313, 0.0]])


# 3D 世界座標點

def rotate_x(matrix, angle_deg):
    """
    繞 X 軸旋轉
    :param matrix: 原始 3x3 矩陣
    :param angle_deg: 旋轉角度（度）
    :return: 繞 X 軸旋轉後的矩陣
    """
    angle_rad = np.radians(angle_deg)
    rotation_x = np.array([
        [1, 0, 0],
        [0, np.cos(angle_rad), -np.sin(angle_rad)],
        [0, np.sin(angle_rad), np.cos(angle_rad)]
    ])
    return np.dot(rotation_x, matrix)

def rotate_y(matrix, angle_deg):
    """
    繞 Y 軸旋轉
    :param matrix: 原始 3x3 矩陣
    :param angle_deg: 旋轉角度（度）
    :return: 繞 Y 軸旋轉後的矩陣
    """
    angle_rad = np.radians(angle_deg)
    rotation_y = np.array([
        [np.cos(angle_rad), 0, np.sin(angle_rad)],
        [0, 1, 0],
        [-np.sin(angle_rad), 0, np.cos(angle_rad)]
    ])
    return np.dot(rotation_y, matrix)

def rotate_z(matrix, angle_deg):
    """
    繞 Z 軸旋轉
    :param matrix: 原始 3x3 矩陣
    :param angle_deg: 旋轉角度（度）
    :return: 繞 Z 軸旋轉後的矩陣
    """
    angle_rad = np.radians(angle_deg)
    rotation_z = np.array([
        [np.cos(angle_rad), -np.sin(angle_rad), 0],
        [np.sin(angle_rad), np.cos(angle_rad), 0],
        [0, 0, 1]
    ])
    return np.dot(rotation_z, matrix)


import numpy as np

# 初始化
t = 0  # 點的編號
real_world_points = []  # 用於存放真實座標點的列表

# 生成真實座標點數據
for i in range(12):
    for j in range(17):
        x = 307.77 + (10 * i)  # x 坐標
        y = 202.58 - (10 * j)  # y 坐標
        z = 0  # 假設 z 坐標為 0
        real_world_points.append([x, y, z])  # 加入座標點
        t += 1

# 轉換為 NumPy 陣列
# 3D 世界座標點
object_points = np.array(real_world_points)
real_world_points = np.array(real_world_points)

# 将像素坐标 (u, v) 转换为 NumPy 数组
# 2D 像素座標點
# 棋盤格角點像素座標（u, v）
image_points = np.array([
    [1201.81, 1418.52], [1202.14, 1344.56], [1202.53, 1270.53], [1202.74, 1196.70],
    [1203.23, 1122.58], [1203.50, 1048.67], [1203.92, 974.53], [1204.28, 900.87],
    [1204.63, 826.82], [1205.02, 752.98], [1205.39, 678.92], [1205.78, 605.23],
    [1206.16, 531.23], [1206.54, 457.76], [1206.85, 383.82], [1207.29, 310.25],
    [1207.64, 236.56], [1275.67, 1418.93], [1276.07, 1344.94], [1276.44, 1270.97],
    [1276.78, 1197.06], [1277.09, 1122.97], [1277.49, 1049.01], [1277.75, 975.05],
    [1278.23, 901.24], [1278.50, 827.29], [1278.89, 753.31], [1279.36, 679.37],
    [1279.63, 605.49], [1279.99, 531.61], [1280.43, 457.98], [1280.67, 384.26],
    [1281.13, 310.59], [1281.58, 236.84], [1349.97, 1419.33], [1350.34, 1345.43],
    [1350.70, 1271.38], [1350.92, 1197.39], [1351.45, 1123.42], [1351.68, 1049.35],
    [1352.08, 975.45], [1352.50, 901.50], [1352.77, 827.61], [1353.16, 753.61],
    [1353.52, 679.61], [1353.85, 605.80], [1354.18, 531.90], [1354.53, 458.36],
    [1354.80, 384.53], [1355.32, 310.95], [1355.47, 237.21], [1423.90, 1419.70],
    [1424.20, 1345.71], [1424.58, 1271.75], [1424.98, 1197.72], [1425.41, 1123.75],
    [1425.68, 1049.81], [1426.12, 975.69], [1426.35, 901.90], [1426.75, 827.95],
    [1427.02, 754.00], [1427.40, 680.14], [1427.68, 606.14], [1428.12, 532.37],
    [1428.36, 458.77], [1428.67, 384.95], [1428.96, 311.31], [1429.42, 237.55],
    [1497.85, 1420.11], [1498.19, 1346.13], [1498.58, 1272.12], [1498.93, 1198.17],
    [1499.31, 1124.19], [1499.62, 1050.10], [1499.96, 976.15], [1500.29, 902.32],
    [1500.61, 828.37], [1500.89, 754.43], [1501.31, 680.48], [1501.65, 606.57],
    [1501.80, 532.69], [1502.22, 459.10], [1502.49, 385.34], [1502.81, 311.67],
    [1503.21, 237.97], [1572.10, 1420.37], [1572.40, 1346.47], [1572.79, 1272.47],
    [1573.12, 1198.50], [1573.50, 1124.49], [1573.81, 1050.54], [1574.12, 976.42],
    [1574.49, 902.73], [1574.78, 828.75], [1575.12, 754.71], [1575.48, 680.78],
    [1575.69, 606.89], [1576.17, 533.10], [1576.31, 459.50], [1576.71, 385.66],
    [1576.82, 311.94], [1577.28, 238.28], [1645.92, 1420.69], [1646.29, 1346.71],
    [1646.70, 1272.75], [1647.03, 1198.79], [1647.40, 1124.84], [1647.72, 1050.79],
    [1648.13, 976.90], [1648.38, 903.01], [1648.70, 829.09], [1648.95, 755.18],
    [1649.31, 681.28], [1649.54, 607.45], [1649.83, 533.45], [1650.25, 459.79],
    [1650.41, 386.14], [1650.67, 312.44], [1650.87, 238.70], [1719.68, 1421.06],
    [1720.11, 1347.05], [1720.50, 1273.09], [1720.94, 1199.24], [1721.26, 1125.18],
    [1721.66, 1051.19], [1722.09, 977.28], [1722.31, 903.45], [1722.56, 829.51],
    [1722.80, 755.46], [1723.22, 681.59], [1723.40, 607.72], [1723.74, 533.72],
    [1723.85, 460.29], [1724.35, 386.46], [1724.42, 312.79], [1724.83, 239.07],
    [1793.61, 1421.43], [1793.95, 1347.41], [1794.40, 1273.44], [1794.74, 1199.49],
    [1795.21, 1125.53], [1795.44, 1051.56], [1795.79, 977.62], [1796.10, 903.79],
    [1796.44, 829.87], [1796.70, 756.00], [1796.90, 682.04], [1797.31, 608.22],
    [1797.54, 534.28], [1797.87, 460.67], [1797.99, 386.99], [1798.22, 313.26],
    [1798.41, 239.47], [1867.57, 1421.67], [1868.14, 1347.71], [1868.48, 1273.68],
    [1868.91, 1199.85], [1869.23, 1125.87], [1869.61, 1051.92], [1869.92, 977.88],
    [1870.20, 904.29], [1870.49, 830.28], [1870.71, 756.43], [1871.13, 682.40],
    [1871.29, 608.59], [1871.58, 534.77], [1871.78, 461.22], [1872.01, 387.43],
    [1872.26, 313.68], [1872.50, 239.96], [1941.46, 1421.94], [1941.77, 1347.97],
    [1942.21, 1274.16], [1942.59, 1200.16], [1943.02, 1126.25], [1943.29, 1052.31],
    [1943.59, 978.36], [1943.91, 904.61], [1944.33, 830.70], [1944.49, 756.73],
    [1944.80, 682.84], [1944.98, 609.08], [1945.39, 535.27], [1945.49, 461.67],
    [1945.72, 387.77], [1945.88, 314.22], [1946.09, 240.37], [2015.12, 1422.18],
    [2015.53, 1348.36], [2015.95, 1274.40], [2016.38, 1200.56], [2016.70, 1126.57],
    [2017.13, 1052.69], [2017.33, 978.66], [2017.71, 905.10], [2017.89, 831.04],
    [2018.28, 757.09], [2018.53, 683.31], [2018.72, 609.52], [2019.02, 535.58],
    [2019.31, 462.23], [2019.38, 388.30], [2019.68, 314.64], [2019.89, 240.90]
])

# 使用 solvePnP 計算外參矩陣
success, rvec, tvec = cv2.solvePnP(object_points, image_points, K, None)

if success:
    #print("PnP 求解成功！")
    #print("旋轉向量 (rvec):", rvec.flatten(),type(rvec.flatten()),rvec.flatten().shape)
    #print("平移向量 (tvec):", tvec.flatten(),type(tvec.flatten()),tvec.flatten().shape)

    # 將旋轉向量轉換為旋轉矩陣
    R, _ = cv2.Rodrigues(rvec)
    #print("旋轉矩陣 (R):\n", R)

    # 將外參矩陣組合為 [R | t]
    extrinsic_matrix = np.hstack((R, tvec))
    #print("外參矩陣 [R | t]:\n", extrinsic_matrix)
else:
    print("PnP 求解失敗！")

import matplotlib.pyplot as plt


# 外参矩阵 R 和 t
"""
R = np.array([
    [0.15309632, -0.98190597, -0.11145486],
    [-0.03286641, 0.10766279, -0.99364406],
    [0.98766458, 0.15578637, -0.01578894]
])
"""

R = np.array([[ 9.99999756e-01, -6.98131644e-04,  0.00000000e+00],
              [ 6.98131644e-04,  9.99999756e-01,  0.00000000e+00],
              [ 0.00000000e+00,  0.00000000e+00,  1.00000000e+00]])

t = np.array([[-265.16868344-80], [-108.02824767], [654.6123158]])
# 像素座標轉換到世界坐標
transformed_points = []
image_points_np = []
for u, v in image_points:
    image_points_np.append(np.array([u,v]))
    uv_homogeneous = np.array([u, v, 720])  # 齊次像素座標
    K_inv = np.linalg.inv(K)  # 相機內參矩陣的逆矩陣
    cam_coords = np.dot(K_inv, uv_homogeneous)  # 相機坐標 (假設深度為1)
    world_coords = np.dot(R.T, cam_coords - t.ravel())  # 世界坐標
    transformed_points.append(world_coords[:2])

image_points_np = np.array(image_points_np)
transformed_points = np.array(transformed_points)

import matplotlib.cm as cm
import matplotlib.colors as mcolors
# 定義顏色映射
colormap = cm.get_cmap('viridis')  # 使用 Viridis 漸變色
norm = mcolors.Normalize(vmin=0, vmax=255)  # 正規化範圍 0 ~ 255

# 繪製函數
def plot_points_with_gradient(points, label, size=50):
    for idx, point in enumerate(points):
        color = colormap(norm(idx))  # 根據點數索引獲取顏色
        plt.scatter(point[0], point[1], color=color, s=size, edgecolor='black', label=label if idx == 0 else None)

# 可視化
plt.figure(figsize=(10, 10))

# 像素座標 (綠色漸變)
plt.scatter(image_points[:, 0], image_points[:, 1], color='green', label='Pixel Coordinates (Image)', s=50)
plt.scatter(image_points[0, 0], image_points[0, 1], color='gold', label='Image Points (First)', s=100, edgecolor='black')
plt.scatter(image_points[1, 0], image_points[1, 1], color='brown', label='Image Points (Second)', s=100, edgecolor='black')
plt.scatter(image_points[-1, 0], image_points[-1, 1], color='purple', label='Image Points (Last)', s=100, edgecolor='black')

# 真實世界座標 (藍色漸變)
plt.scatter(real_world_points[:, 0], real_world_points[:, 1], color='blue', label='Real World Coordinates', s=50)
plt.scatter(real_world_points[0, 0], real_world_points[0, 1], color='gold', s=100, edgecolor='black')
plt.scatter(real_world_points[1, 0], real_world_points[1, 1], color='brown', s=100, edgecolor='black')
plt.scatter(real_world_points[-1, 0], real_world_points[-1, 1], color='purple', s=100, edgecolor='black')

# 轉換後的真實世界座標 (橘色漸變)
plt.scatter(transformed_points[:, 0], transformed_points[:, 1], color='orange', label='Transformed World Coordinates', s=50)
plt.scatter(transformed_points[0, 0], transformed_points[0, 1], color='gold', s=100, edgecolor='black')
plt.scatter(transformed_points[1, 0], transformed_points[1, 1], color='brown', s=100, edgecolor='black')
plt.scatter(transformed_points[-1, 0], transformed_points[-1, 1], color='purple', s=100, edgecolor='black')
# 標題和圖例
plt.title('Coordinate Visualization with Gradient Colors')
plt.xlabel('X Coordinate')
plt.ylabel('Y Coordinate')
plt.legend()
plt.grid(True)
plt.show()
real_dx = real_world_points[0][0] - real_world_points[1][0]
real_dy = real_world_points[0][1] - real_world_points[1][1]
trans_dx = transformed_points[0][0] - transformed_points[1][0]
trans_dy = transformed_points[0][1] - transformed_points[1][1]
print(f"real dx ={real_dx} , real dy = {real_dy} trans dx = { trans_dx} trans dy = { trans_dy}")
