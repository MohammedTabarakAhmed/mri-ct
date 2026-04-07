import torch
import torch.nn as nn
import torchvision.models as models

def get_kidney_model():
    # Use ResNet18 pretrained
    model = models.resnet18(pretrained=True)
    # Change final layer for 2 classes: Normal / Stone
    model.fc = nn.Linear(model.fc.in_features, 2)
    return model