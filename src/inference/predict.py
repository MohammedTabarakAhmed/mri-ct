import torch
import cv2
import numpy as np
from src.models.unet_resnet import get_model

def predict(image_path, model_path, save_path="outputs/prediction.png"):
    model = get_model()
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()

    img = cv2.imread(image_path)
    orig = img.copy()

    img = cv2.resize(img, (256, 256)) / 255.0
    img = torch.tensor(img).permute(2, 0, 1).unsqueeze(0).float()

    with torch.no_grad():
        pred = model(img)
        pred = torch.sigmoid(pred).squeeze().numpy()

    mask = (pred > 0.5).astype(np.uint8)
    mask = cv2.resize(mask, (orig.shape[1], orig.shape[0]))

    overlay = orig.copy()
    overlay[mask == 1] = [0, 0, 255]

    result = cv2.addWeighted(orig, 0.7, overlay, 0.3, 0)

    cv2.imwrite(save_path, result)
    print(f"Saved prediction at {save_path}")

if __name__ == "__main__":
    predict(
        image_path="test.jpg",
        model_path="outputs/models/model.pth"
    )