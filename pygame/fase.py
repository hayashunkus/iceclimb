import matplotlib.pyplot as plt
import numpy as np

# 円を描画（顔）
theta = np.linspace(0, 2 * np.pi, 100)
x = np.cos(theta)
y = np.sin(theta)

# 描画
plt.figure(figsize=(5, 5))
plt.plot(x, y, label="Face")  # 顔の輪郭
plt.scatter([0.3, -0.3], [0.5, 0.5], color="black", s=100, label="Eyes")  # 目
plt.plot([0, 0.2], [-0.2, -0.4], color="red", label="Mouth")  # 口
plt.axis("equal")
plt.legend()
plt.show()
