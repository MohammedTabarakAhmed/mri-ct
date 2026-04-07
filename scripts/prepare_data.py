import os
import cv2
from tqdm import tqdm

RAW_DIR = "data/raw/kaggle_3m"
IMG_OUT = "data/processed/images"
MASK_OUT = "data/processed/masks"

os.makedirs(IMG_OUT, exist_ok=True)
os.makedirs(MASK_OUT, exist_ok=True)

count = 0

for patient in os.listdir(RAW_DIR):
    patient_path = os.path.join(RAW_DIR, patient)

    if not os.path.isdir(patient_path):
        continue

    for file in os.listdir(patient_path):
        if "_mask" in file:
            mask_path = os.path.join(patient_path, file)
            img_path = mask_path.replace("_mask", "")

            if os.path.exists(img_path):
                img = cv2.imread(img_path)
                mask = cv2.imread(mask_path, 0)

                img = cv2.resize(img, (256, 256))
                mask = cv2.resize(mask, (256, 256))

                cv2.imwrite(f"{IMG_OUT}/{count}.png", img)
                cv2.imwrite(f"{MASK_OUT}/{count}.png", mask)

                count += 1

print(f"Processed {count} images")