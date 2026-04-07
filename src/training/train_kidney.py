# src/training/train_kidney.py
import os
import torch
from torch.utils.data import DataLoader
from src.models.kidney_model import get_kidney_model
from src.datasets.kidney_dataset import KidneyDataset
import torch.optim as optim
import torch.nn as nn

# Ensure output folder exists
os.makedirs("outputs/models", exist_ok=True)

# =========================
# Dataset and DataLoader
# =========================
dataset_path = "data/raw/kidney"  # root folder containing 'Normal' and 'stone'
train_dataset = KidneyDataset(dataset_path)
if len(train_dataset) == 0:
    raise ValueError(f"No images found in {dataset_path}. Check your folders!")

train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)

# =========================
# Model
# =========================
model = get_kidney_model()
model.train()

# =========================
# Loss and Optimizer
# =========================
criterion = nn.CrossEntropyLoss()  # for classification: 2 classes
optimizer = optim.Adam(model.parameters(), lr=1e-4)

# =========================
# Training Loop
# =========================
num_epochs = 5  # increase as needed
for epoch in range(num_epochs):
    print(f"Starting epoch {epoch+1}/{num_epochs}")  # <- add this
    total_loss = 0
    correct = 0
    total = 0

    for imgs, labels in train_loader:
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
    
        print("Batch loss:", loss.item())  # you’ll see updates per batch

        # compute accuracy for batch
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

    epoch_loss = total_loss / len(train_loader)
    epoch_acc = 100 * correct / total
    print(f"Epoch {epoch+1}/{num_epochs} - Loss: {epoch_loss:.4f} - Accuracy: {epoch_acc:.2f}%")

# =========================
# Save Model
# =========================
model_path = "outputs/models/kidney_model.pth"
torch.save(model.state_dict(), model_path)
print(f"Kidney stone classification model saved at {model_path}")