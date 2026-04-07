import os

def setup_kaggle():
    os.system("kaggle datasets download -d mateuszbuda/lgg-mri-segmentation")
    os.system("unzip lgg-mri-segmentation.zip -d data/raw")

if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    setup_kaggle()