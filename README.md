# DobotM1Project
## 一些寫給自己的重要訊息

* 機械臂的LAN1 IP是 **192.168.1.6** LAN2 IP是**192.168.2.6**
* Python開發環境3.12.4
* pytorch版本 2.4.1
* 顯示卡型號RTX 4060Ti
* CUDA版本12.1.0
* cuDnn版本9.1.0
* 測試單GPU多模型的執行速度
opencvtest.py 測試完成mks driver done 


# 待辦事項

1. 相機標定
2. 影像流觸發運算



| 機械臂 | 欄位2 | 欄位3 |
| :-- | --: |:--:|
| 置左  | 置右 | 置中 |
## 重投影误差 (Reprojection Error)

$$ RE = 0.7145324159629237 $$
## 内参矩阵 (Intrinsic Parameters)
$$
\mathbf{K} =
\begin{bmatrix}
5182.30692 & 0.00000 & 1203.18707 \\
0.00000 & 5222.57059 & 1236.24816 \\
0.00000 & 0.00000 & 1.00000
\end{bmatrix}
$$
## 畸变系数 (Distortion Coefficients)
$$
\mathbf{D} =
\begin{bmatrix}
-0.05605587 & -0.20169196 & -0.00238904 & -0.00015880 & 3.00955822
\end{bmatrix}
$$
