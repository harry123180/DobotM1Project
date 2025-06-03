from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt
from itertools import chain

# === 圖片路徑 ===
root_dir = Path(__file__).resolve().parent.parent.parent
train_A = root_dir / "circle_split_dataset" / "A_train"
train_B = root_dir / "circle_split_dataset" / "B_train"
test_A  = root_dir / "circle_split_dataset" / "A_test"
test_B  = root_dir / "circle_split_dataset" / "B_test"

# === 支援多副檔名抓圖工具 ===
def get_all_images(folder: Path):
    return list(chain.from_iterable([
        folder.glob("*.bmp"),
        folder.glob("*.jpg"),
        folder.glob("*.jpeg"),
        folder.glob("*.png")
    ]))
print(f"🔍 A_train path = {train_A}")
print(f"🔍 B_train path = {train_B}")
print(f"A_train 圖片數：{len(get_all_images(train_A))}")
print(f"B_train 圖片數：{len(get_all_images(train_B))}")
# === 自訂資料集 ===
class CircleDataset(Dataset):
    def __init__(self, pathA, pathB, transform=None):
        self.samples = []
        self.transform = transform
        for img_path in get_all_images(pathA):
            self.samples.append((img_path, 0))
        for img_path in get_all_images(pathB):
            self.samples.append((img_path, 1))

        if len(self.samples) == 0:
            raise RuntimeError(f"❌ 沒有載入任何圖片，請確認資料夾 {pathA} 或 {pathB} 中有圖檔！")

    def __len__(self): return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert("L")
        if self.transform:
            image = self.transform(image)
        return image, label

# === 影像轉換 ===
transform = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
])

# === 資料載入 ===
train_dataset = CircleDataset(train_A, train_B, transform)
test_dataset  = CircleDataset(test_A, test_B, transform)
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
test_loader  = DataLoader(test_dataset, batch_size=1)

# === CNN 模型 ===
class SimpleCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 16 * 16, 128), nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x): return self.fc(self.conv(x))

# === 模型訓練 ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = SimpleCNN().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

loss_log = []
for epoch in range(100):
    model.train()
    total_loss = 0
    for imgs, labels in train_loader:
        imgs, labels = imgs.to(device), labels.to(device)
        preds = model(imgs)
        loss = criterion(preds, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    avg_loss = total_loss / len(train_loader)
    loss_log.append(avg_loss)
    print(f"Epoch {epoch+1}/100 - Loss: {avg_loss:.4f}")

# === 儲存模型 ===
torch.save(model.state_dict(), root_dir / "trained_model.pth")
print("✅ 模型已儲存")

# === 測試準確度 ===
model.eval()
y_true, y_pred = [], []
with torch.no_grad():
    for imgs, labels in test_loader:
        imgs = imgs.to(device)
        out = model(imgs)
        pred = torch.argmax(out, dim=1).cpu().item()
        y_pred.append(pred)
        y_true.append(labels.item())

acc = accuracy_score(y_true, y_pred)
print(f"✅ 測試集準確率：{acc:.2%}")

# === 顯示訓練損失曲線 ===
plt.plot(loss_log)
plt.title("Training Loss")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.grid()
plt.show()
