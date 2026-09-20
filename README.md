# Medical Imaging Analysis System — Brain Tumor & Kidney Stone Detection

An AI-assisted medical imaging platform that analyzes MRI/CT scans to detect **brain tumors** and **kidney stones**, using a segmentation deep learning model (U-Net with a ResNet encoder) paired with **Grad-CAM explainability**, automated clinical-style reporting, and both a Streamlit UI and a FastAPI backend.

## Overview

Most tumor-detection demos stop at a binary prediction. This system goes further, aiming at what a real diagnostic-support tool needs:

- **Segmentation, not just classification** — a U-Net (ResNet encoder) locates *where* an anomaly is, not just whether one exists.
- **Explainability** — Grad-CAM heatmaps show which regions of the scan drove the model's prediction, so the output isn't a black box.
- **Quantified findings** — outputs include size, location, and severity estimates rather than a single confidence score.
- **Dual-organ support** — brain tumor and kidney stone analysis share the same platform and reporting pipeline.
- **Automated reporting** — findings are compiled into a professional medical-style report (`src/utils/report_generator.py`).

## Architecture

```
MRI/CT scan (image upload)
        │
        ▼
  Preprocessing            (scripts/prepare_data.py)
        │
        ▼
  Segmentation Model        U-Net + ResNet34 encoder (src/models/unet_resnet.py, kidney_model.py)
        │
        ├──► Grad-CAM        (src/utils/gradcam.py) → explainability heatmap
        │
        ▼
  Analysis Layer            (src/utils/analysis.py) → BrainTumorAnalyzer / KidneyStoneAnalyzer
        │                     → size, location, severity, risk stratification
        ▼
  Report Generator          (src/utils/report_generator.py) → structured medical-style report
        │
        ▼
  Delivery: Streamlit UI (streamlit_app.py)  or  FastAPI backend (api/app.py)
```

## Features

- **Two interfaces:**
  - **Streamlit web app** (`streamlit_app.py`) — upload a scan and get an interactive, visual analysis in the browser.
  - **FastAPI backend** (`api/app.py` + `api/index.html`) — a REST API for programmatic access or a custom front-end.
- **Grad-CAM visual explainability** for both segmentation and classification-style outputs.
- **Configurable training pipeline** (`config.yaml`) — image size, batch size, learning rate, encoder backbone, and output paths are all externalized.
- **Separate training entry points** per organ: `src/training/train.py` (brain) and `src/training/train_kidney.py` (kidney).

## Project Structure

```
mri-ct/
├── streamlit_app.py            # Streamlit web interface
├── predict.py                  # CLI inference entry point
├── config.yaml                 # Training configuration
├── start_server.bat            # Windows helper to launch the API server
├── api/
│   ├── app.py                  # FastAPI backend
│   └── index.html              # Minimal web UI served by the API
├── scripts/
│   ├── dowload_data.py         # Dataset download helper
│   └── prepare_data.py         # Preprocessing pipeline
├── models/unet_resnet.py
└── src/
    ├── models/                 # unet_resnet.py, kidney_model.py
    ├── training/                # engine.py, train.py, train_kidney.py
    ├── inference/predict.py
    └── utils/
        ├── analysis.py          # BrainTumorAnalyzer / KidneyStoneAnalyzer
        ├── gradcam.py           # Grad-CAM implementation
        ├── losses.py / metrics.py
        └── report_generator.py  # MedicalReportGenerator
```

## Tech Stack

| Purpose | Tool |
|---|---|
| Deep learning | PyTorch, segmentation model (U-Net + ResNet34) |
| Explainability | Grad-CAM |
| Web UI | Streamlit |
| API | FastAPI |
| Image processing | OpenCV, PIL |

## Getting Started

### Installation

```bash
git clone https://github.com/MohammedTabarakAhmed/mri-ct.git
cd mri-ct
pip install -r requirements.txt
```

### Run the Streamlit app (recommended)

```bash
streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501), upload a scan, and choose brain tumor or kidney stone analysis.

### Run the FastAPI backend

```bash
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
```

Visit [http://localhost:8000](http://localhost:8000).

### Train a model

```bash
python src/training/train.py           # brain tumor segmentation
python src/training/train_kidney.py    # kidney stone segmentation
```

Training parameters (image size, epochs, learning rate, encoder) are configured in `config.yaml`.

## Documentation

This repo includes several deep-dive documents alongside this overview:

- [`QUICKSTART.md`](./QUICKSTART.md) — fastest path to running the app
- [`IMPLEMENTATION_GUIDE.md`](./IMPLEMENTATION_GUIDE.md) — implementation details
- [`STREAMLIT_GUIDE.md`](./STREAMLIT_GUIDE.md) — using the Streamlit interface
- [`HOW_TO_ACCESS.md`](./HOW_TO_ACCESS.md) — access/deployment notes
- [`EXAMPLE_OUTPUTS.md`](./EXAMPLE_OUTPUTS.md) — sample analysis outputs
- [`README_ENHANCEMENTS.md`](./README_ENHANCEMENTS.md) — history of feature enhancements
- [`COMPLETION_CHECKLIST.md`](./COMPLETION_CHECKLIST.md) — project completion tracking

## Disclaimer

This project is for educational and portfolio purposes only. It is **not a certified medical device** and should not be used for real clinical diagnosis.

## License

Available for educational and personal portfolio use.
