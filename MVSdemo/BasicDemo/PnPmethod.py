import cv2
import numpy as np
"""
# 相機內參矩陣
K = np.array([
    [7.42157429, 0, 1.23308448],
    [0.0, 7.47157429, 0.99655374],
    [0.0, 0.0, 1]
])

# 畸變係數
D = np.array([[-0.111665041, 0.706682197, 0.000284510564, 0.000578235313, 0.0]])

"""
# 相機內參矩陣
K = np.array([
    [7.35533899e+00, 0, 1.24451771e+00],
    [0.0, 7.35687528e+00, 1.02655760e+00],
    [0.0, 0.0, 1.0]
])

# 畸變係數
D = np.array([[-9.63028822e-02, 2.74658814e-01, 1.36385496e-03, 5.80934112e-04, 2.95541140e+00]])

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
        x = 309.01 - (10 * i)  # x 坐標
        y = 205.55 - (10 * j)  # y 坐標
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
    [1193.48, 1418.47], [1194.37, 1344.48], [1195.41, 1270.36], [1196.27, 1196.47],
    [1197.29, 1122.29], [1198.15, 1048.27], [1199.24, 974.07], [1200.25, 900.27],
    [1201.18, 826.15], [1202.13, 752.16], [1203.23, 678.07], [1204.24, 604.16],
    [1205.16, 530.08], [1206.16, 456.66], [1207.11, 382.60], [1208.17, 308.93],
    [1209.12, 235.22], [1267.41, 1419.57], [1268.36, 1345.49], [1269.41, 1271.45],
    [1270.43, 1197.43], [1271.24, 1123.26], [1272.30, 1049.22], [1273.24, 975.17],
    [1274.25, 901.27], [1275.16, 827.18], [1276.16, 753.13], [1277.19, 679.10],
    [1278.18, 605.18], [1279.12, 531.14], [1280.12, 457.51], [1281.07, 383.57],
    [1282.06, 309.86], [1283.07, 236.17], [1341.82, 1420.54], [1342.78, 1346.62],
    [1343.69, 1272.42], [1344.61, 1198.42], [1345.71, 1124.31], [1346.57, 1050.16],
    [1347.56, 976.20], [1348.55, 902.16], [1349.46, 828.16], [1350.56, 754.06],
    [1351.52, 679.99], [1352.41, 605.99], [1353.39, 532.02], [1354.32, 458.41],
    [1355.25, 384.49], [1356.34, 310.85], [1357.11, 237.03], [1415.80, 1421.55],
    [1416.69, 1347.48], [1417.71, 1273.45], [1418.69, 1199.36], [1419.75, 1125.30],
    [1420.68, 1051.23], [1421.66, 977.05], [1422.50, 903.18], [1423.57, 829.10],
    [1424.47, 755.01], [1425.41, 681.07], [1426.42, 607.04], [1427.35, 533.11],
    [1428.26, 459.46], [1429.20, 385.57], [1430.07, 311.77], [1431.06, 237.94],
    [1489.81, 1422.53], [1490.76, 1348.52], [1491.73, 1274.42], [1492.81, 1200.40],
    [1493.70, 1126.30], [1494.69, 1052.12], [1495.65, 978.11], [1496.57, 904.17],
    [1497.51, 830.08], [1498.44, 756.06], [1499.43, 681.95], [1500.42, 608.04],
    [1501.27, 534.13], [1502.22, 460.38], [1503.13, 386.47], [1504.08, 312.74],
    [1504.97, 238.96], [1564.12, 1423.43], [1565.06, 1349.47], [1566.14, 1275.37],
    [1567.04, 1201.34], [1568.08, 1127.21], [1569.00, 1053.18], [1569.82, 978.98],
    [1570.87, 905.15], [1571.74, 831.11], [1572.58, 757.02], [1573.65, 683.03],
    [1574.61, 608.93], [1575.57, 535.07], [1576.43, 461.45], [1577.39, 387.47],
    [1578.18, 313.73], [1579.22, 239.85], [1638.05, 1424.44], [1639.07, 1350.33],
    [1640.10, 1276.35], [1641.07, 1202.21], [1641.97, 1128.28], [1643.04, 1054.05],
    [1643.98, 980.02], [1644.84, 906.14], [1645.77, 832.04], [1646.66, 758.02],
    [1647.62, 684.00], [1648.56, 610.00], [1649.40, 536.08], [1650.38, 462.36],
    [1651.20, 388.52], [1652.09, 314.74], [1652.89, 240.95], [1711.95, 1425.36],
    [1713.04, 1351.34], [1713.98, 1277.30], [1715.06, 1203.30], [1715.98, 1129.18],
    [1717.08, 1055.08], [1718.01, 981.06], [1718.94, 907.13], [1719.75, 833.12],
    [1720.61, 758.96], [1721.64, 684.96], [1722.47, 611.07], [1723.35, 536.99],
    [1724.18, 463.38], [1725.24, 389.52], [1725.87, 315.68], [1726.87, 241.89],
    [1785.95, 1426.36], [1786.98, 1352.27], [1788.09, 1278.22], [1789.03, 1204.18],
    [1790.06, 1130.09], [1790.91, 1056.11], [1791.90, 982.01], [1792.82, 908.19],
    [1793.71, 834.14], [1794.67, 760.13], [1795.50, 686.01], [1796.39, 612.10],
    [1797.27, 538.14], [1798.24, 464.43], [1799.00, 390.61], [1799.79, 316.79],
    [1800.52, 243.00], [1860.06, 1427.21], [1861.24, 1353.19], [1862.22, 1279.12],
    [1863.19, 1205.20], [1864.20, 1131.09], [1865.18, 1057.06], [1866.10, 982.87],
    [1867.02, 909.22], [1867.88, 835.05], [1868.77, 761.10], [1869.67, 687.04],
    [1870.57, 613.10], [1871.44, 539.24], [1872.27, 465.49], [1873.15, 391.65],
    [1873.87, 317.84], [1874.78, 243.98], [1934.02, 1428.10], [1935.07, 1354.08],
    [1936.04, 1280.17], [1937.03, 1206.17], [1938.07, 1132.05], [1938.94, 1058.01],
    [1939.97, 983.96], [1940.83, 910.12], [1941.69, 836.20], [1942.59, 762.13],
    [1943.62, 688.12], [1944.36, 614.20], [1945.31, 540.30], [1946.14, 466.57],
    [1946.91, 392.64], [1947.67, 318.95], [1948.47, 245.10], [2007.78, 1428.97],
    [2008.81, 1355.06], [2009.88, 1281.00], [2010.93, 1207.10], [2011.85, 1132.94],
    [2012.88, 1059.05], [2013.65, 984.95], [2014.72, 911.23], [2015.53, 837.10],
    [2016.40, 763.11], [2017.34, 689.16], [2018.20, 615.28], [2019.05, 541.23],
    [2019.87, 467.76], [2020.60, 393.69], [2021.56, 320.09], [2022.32, 246.21]
])

# 使用 solvePnP 計算外參矩陣
success, rvec, tvec = cv2.solvePnP(object_points, image_points, K, None)

if success:
    #print("PnP 求解成功！")
    print("旋轉向量 (rvec):", rvec.flatten(),type(rvec.flatten()),rvec.flatten().shape)
    print("平移向量 (tvec):", tvec.flatten(),type(tvec.flatten()),tvec.flatten().shape)

    # 將旋轉向量轉換為旋轉矩陣
    R, _ = cv2.Rodrigues(rvec)
    print("旋轉矩陣 (R):\n", R)

    # 將外參矩陣組合為 [R | t]
    extrinsic_matrix = np.hstack((R, tvec))
    print("外參矩陣 [R | t]:\n", extrinsic_matrix)
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

# 旋轉矩陣和平移向量
R = np.array([
    [-9.99913875e-01,  -1.31241329e-02, -3.55145363e-06],
    [ -1.31241329e-02,  9.99913875e-01, -2.47572387e-06],
    [3.58363949e-06, -2.42890090e-06, -1.00000000e+00]
])

t = np.array([[352.96520021], [-109.49788733], [0.86068216]])
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
plt.xlim([-500, 2592])  # 設定 X 軸範圍
plt.ylim([-500, 1944])  # 設定 Y 軸範圍
plt.legend()
plt.grid(True)
plt.show()
real_dx = real_world_points[0][0] - real_world_points[1][0]
real_dy = real_world_points[0][1] - real_world_points[1][1]
trans_dx = transformed_points[0][0] - transformed_points[1][0]
trans_dy = transformed_points[0][1] - transformed_points[1][1]
print(f"real dx ={real_dx} , real dy = {real_dy} trans dx = { trans_dx} trans dy = { trans_dy}")
print(transformed_points[0])