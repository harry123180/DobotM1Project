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
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
])

# ===== 遍歷所有圖片 =====
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
input_dir = root_dir / "output_circles_B"

label_name = ["A", "B"]

for img_path in sorted(input_dir.glob("*.bmp")):
    try:
        img = Image.open(img_path).convert("L")
        img_tensor = transform(img).unsqueeze(0)
        with torch.no_grad():
            output = model(img_tensor)
            predicted = torch.argmax(output, dim=1).item()
        print(f"🖼️ {img_path.name} → 推論結果：{label_name[predicted]}")
    except Exception as e:
        print(f"❌ 無法處理圖片 {img_path.name}：{e}")
