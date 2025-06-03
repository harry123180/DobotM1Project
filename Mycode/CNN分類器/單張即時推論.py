import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
from pathlib import Path

# ===== CNN 架構必須與訓練一致 =====
class SimpleCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 16 * 16, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x):
        return self.fc(self.conv(x))

# ===== 載入模型 =====
model_path = Path(__file__).parent / "trained_model.pth"
model = SimpleCNN()
model.load_state_dict(torch.load(model_path, map_location="cpu"))
model.eval()

# ===== 圖片轉換流程 =====
transform = transforms.Compose([
    transforms.Resize((128, 128)),     # 必須與訓練一致
    transforms.ToTensor(),
])

# ===== 讀取你要測試的圖片 =====
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent

img_path = root_dir /"output_circles_Back"/ "1_2.bmp"  # 改成你的圖片檔案名
img = Image.open(img_path).convert("L")         # 轉成灰階
img_tensor = transform(img).unsqueeze(0)        # 增加 batch 維度

# ===== 執行推論 =====
with torch.no_grad():
    output = model(img_tensor)
    predicted = torch.argmax(output, dim=1).item()

# ===== 顯示結果 =====
label_name = ["A", "B"]
print(f"✅ 推論結果：{label_name[predicted]}")
