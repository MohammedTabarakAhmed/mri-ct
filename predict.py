import os
import random
import traceback
import torch
import torchvision.transforms as transforms
from torchvision.models import resnet18
from PIL import Image
import cv2
import segmentation_models_pytorch as smp
import numpy as np
from fastapi import FastAPI, UploadFile, File

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

app = FastAPI()

# ================= Kidney Model =================
kidney_model_path = "outputs/models/kidney_model.pth"
kidney_classes = ["Normal", "stone"]

# Load Kidney Model
try:
    kidney_model = resnet18(weights=None, num_classes=2)
    kidney_model.load_state_dict(torch.load(kidney_model_path, map_location=device))
    kidney_model.to(device)
    kidney_model.eval()
except Exception as e:
    print("Failed to load kidney model:")
    traceback.print_exc()
    kidney_model = None

# ================= Brain Model =================
brain_model_path = "outputs/models/model.pth"

# Load Brain Model
try:
    brain_model = smp.Unet(
        encoder_name="resnet18",
        encoder_weights="imagenet",
        in_channels=3,
        classes=1
    )
    brain_model.load_state_dict(torch.load(brain_model_path, map_location=device), strict=False)
    brain_model.to(device)
    brain_model.eval()
    print("Brain model loaded successfully!")
except Exception as e:
    print("Failed to load brain model:")
    traceback.print_exc()
    brain_model = None

# ================= Kidney Endpoint =================
@app.post("/predict/kidney")
async def predict_kidney(file: UploadFile = File(...)):
    if not kidney_model:
        return {"error": "Kidney model not loaded"}
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    img = cv2.resize(img, (224, 224)) / 255.0
    img = torch.tensor(img).permute(2,0,1).unsqueeze(0).float().to(device)
    with torch.no_grad():
        pred = kidney_model(img)
        label = torch.argmax(pred, dim=1).item()
    result = "Stone" if label == 1 else "Normal"
    suggestion = ("Possible kidney stone detected. Consult a urologist."
                  if result == "Stone" else "No stone detected. Maintain healthy hydration.")
    return {"prediction": result, "suggestion": suggestion}

# ================= Brain Endpoint =================
@app.post("/predict/brain")
async def predict_brain(file: UploadFile = File(...)):
    if not brain_model:
        return {"error": "Brain model not loaded"}
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    orig = img.copy()
    img = cv2.resize(img, (256, 256)) / 255.0
    img = torch.tensor(img).permute(2,0,1).unsqueeze(0).float().to(device)
    with torch.no_grad():
        mask_pred = brain_model(img)
    mask_pred_np = torch.sigmoid(mask_pred).squeeze().cpu().numpy()
    mask = (mask_pred_np > 0.5).astype(np.uint8)
    mask = cv2.resize(mask, (orig.shape[1], orig.shape[0]))
    overlay = orig.copy()
    overlay[mask == 1] = [0,0,255]
    result = cv2.addWeighted(orig, 0.7, overlay, 0.3, 0)
    save_path = "outputs/brain_result.png"
    os.makedirs("outputs", exist_ok=True)
    cv2.imwrite(save_path, result)
    tumor_detected = int(mask.sum()) > 500
    suggestion = ("Possible tumor detected. Please consult a neurologist."
                  if tumor_detected else "No tumor detected. Continue regular monitoring.")
    return {"tumor_detected": tumor_detected, "output_image": save_path, "suggestion": suggestion}