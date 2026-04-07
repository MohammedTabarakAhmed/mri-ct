import torch
from torch.utils.data import DataLoader
from src.datasets.dataset import MedicalDataset
from src.models.unet_resnet import get_model
from src.training.engine import train_one_epoch
from src.utils.losses import get_loss


device = "cuda" if torch.cuda.is_available() else "cpu"

dataset = MedicalDataset(
    "data/processed/images",
    "data/processed/masks"
)

loader = DataLoader(dataset, batch_size=4, shuffle=True)

model = get_model().to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
loss_fn = get_loss()

for epoch in range(3):
    loss = train_one_epoch(model, loader, optimizer, loss_fn, device)
    print(f"Epoch {epoch+1} Loss: {loss}")

import os
os.makedirs("outputs/models", exist_ok=True)

torch.save(model.state_dict(), "outputs/models/model.pth")