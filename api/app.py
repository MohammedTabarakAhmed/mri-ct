import os
import sys
import torch
import cv2
import numpy as np
from datetime import datetime
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response, FileResponse
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from src.models.unet_resnet import get_model
from src.models.kidney_model import get_kidney_model
from src.utils.analysis import BrainTumorAnalyzer, KidneyStoneAnalyzer
from src.utils.gradcam import SegmentationGradCAM, GradCAM, create_combined_explanation
from src.utils.report_generator import MedicalReportGenerator

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

outputs_dir = os.path.join(BASE_DIR, "outputs")
os.makedirs(os.path.join(outputs_dir, "models"), exist_ok=True)
os.makedirs(os.path.join(outputs_dir, "mask"), exist_ok=True)
os.makedirs(os.path.join(outputs_dir, "gradcam"), exist_ok=True)
os.makedirs(os.path.join(outputs_dir, "reports"), exist_ok=True)

app.mount("/outputs", StaticFiles(directory=outputs_dir), name="outputs")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open(os.path.join(BASE_DIR, "api", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

brain_model = get_model()
brain_model.load_state_dict(
    torch.load(os.path.join(outputs_dir, "models", "model.pth"), map_location=device),
    strict=False,
)
brain_model.to(device).eval()

kidney_model = get_kidney_model()
kidney_model.load_state_dict(
    torch.load(os.path.join(outputs_dir, "models", "kidney_model.pth"), map_location=device),
    strict=False,
)
kidney_model.to(device).eval()

@app.post("/predict/brain")
async def predict_brain(file: UploadFile = File(...)):
    """Enhanced brain tumor analysis with detailed metrics, Grad-CAM, and medical report."""
    contents = await file.read()
    img = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    orig = img.copy()

    # Resize for model
    img_resized = cv2.resize(img, (256, 256)) / 255.0
    img_tensor = torch.tensor(img_resized).permute(2, 0, 1).unsqueeze(0).float().to(device)

    # Prediction
    with torch.no_grad():
        pred = brain_model(img_tensor)
        prob = torch.sigmoid(pred).squeeze().cpu().numpy()

    confidence = float(np.mean(prob))
    mask = (prob > 0.5).astype(np.uint8)
    mask = cv2.resize(mask, (orig.shape[1], orig.shape[0]))

    # Generate Grad-CAM for explainability
    try:
        grad_cam_gen = SegmentationGradCAM(brain_model, device=str(device))
        grad_cam = grad_cam_gen.generate(img_tensor)
        grad_cam_img = (grad_cam * 255).astype(np.uint8)
        grad_cam_colored = cv2.applyColorMap(grad_cam_img, cv2.COLORMAP_JET)
    except Exception as e:
        print(f"Warning: Grad-CAM generation failed: {e}")
        grad_cam = None
        grad_cam_colored = None

    # Create overlay visualization
    overlay = orig.copy()
    overlay[mask == 1] = [0, 0, 255]
    result = cv2.addWeighted(orig, 0.3, overlay, 0.7, 0)

    # Save visualizations
    base_filename = file.filename.rsplit('.', 1)[0]
    mask_filename = f"brain_{base_filename}_mask.png"
    cv2.imwrite(os.path.join(outputs_dir, "mask", mask_filename), result)

    grad_cam_filename = None
    if grad_cam_colored is not None:
        grad_cam_filename = f"brain_{base_filename}_gradcam.png"
        cv2.imwrite(os.path.join(outputs_dir, "gradcam", grad_cam_filename), grad_cam_colored)

    # Advanced analysis
    analyzer = BrainTumorAnalyzer(mask, orig, confidence)
    analysis = analyzer.generate_analysis_report()

    # Generate medical report
    report_gen = MedicalReportGenerator()
    medical_report = report_gen.generate_brain_report(analysis)
    report_path = report_gen.save_report(medical_report, os.path.join(outputs_dir, "reports"), "brain")
    report_json_path = report_gen.save_report_json(analysis, os.path.join(outputs_dir, "reports"), "brain")

    return {
        "status": "success",
        "prediction": "Tumor Detected" if analysis["tumor_detected"] else "Normal",
        "model_confidence": analysis["model_confidence"],
        "findings": {
            "tumor_detected": analysis["tumor_detected"],
            "affected_percentage": analysis["affected_percentage"],
            "severity_level": analysis["severity_level"],
            "size_metrics": analysis["size_metrics"],
            "location": analysis["location"],
            "shape_metrics": analysis["shape_metrics"],
        },
        "visualizations": {
            "segmentation_mask": f"/outputs/mask/{mask_filename}",
            "grad_cam": f"/outputs/gradcam/{grad_cam_filename}" if grad_cam_filename else None,
        },
        "recommendations": analysis["recommendations"],
        "clinical_notes": analysis["clinical_notes"],
        "report": {
            "text_path": f"/outputs/reports/{os.path.basename(report_path)}",
            "json_path": f"/outputs/reports/{os.path.basename(report_json_path)}",
            "report_id": report_gen.report_id,
        },
        "timestamp": datetime.now().isoformat(),
    }

@app.post("/predict/kidney")
async def predict_kidney(file: UploadFile = File(...)):
    """Enhanced kidney stone analysis with size estimation and medical report."""
    contents = await file.read()
    img = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    orig = img.copy()

    # Resize for model
    img_resized = cv2.resize(img, (224, 224)) / 255.0
    img_tensor = torch.tensor(img_resized).permute(2, 0, 1).unsqueeze(0).float().to(device)

    # Prediction
    with torch.no_grad():
        pred = kidney_model(img_tensor)
        probs = torch.softmax(pred, dim=1).cpu().numpy()[0]

    confidence = float(np.max(probs))
    
    # Generate Grad-CAM for explainability
    try:
        grad_cam_gen = GradCAM(kidney_model, target_layer="layer4", device=str(device))
        grad_cam = grad_cam_gen.generate(img_tensor)
        grad_cam_img = (grad_cam * 255).astype(np.uint8)
        grad_cam_colored = cv2.applyColorMap(grad_cam_img, cv2.COLORMAP_JET)
        grad_cam_colored = cv2.resize(grad_cam_colored, (orig.shape[1], orig.shape[0]))
        grad_cam_gen.remove_hooks()
    except Exception as e:
        print(f"Warning: Grad-CAM generation failed: {e}")
        grad_cam = None
        grad_cam_colored = None

    # Advanced analysis
    analyzer = KidneyStoneAnalyzer(probs, confidence)
    analysis = analyzer.generate_analysis_report()

    # Save Grad-CAM
    base_filename = file.filename.rsplit('.', 1)[0]
    grad_cam_filename = None
    if grad_cam_colored is not None:
        grad_cam_filename = f"kidney_{base_filename}_gradcam.png"
        cv2.imwrite(os.path.join(outputs_dir, "gradcam", grad_cam_filename), grad_cam_colored)

    # Generate medical report
    report_gen = MedicalReportGenerator()
    medical_report = report_gen.generate_kidney_report(analysis)
    report_path = report_gen.save_report(medical_report, os.path.join(outputs_dir, "reports"), "kidney")
    report_json_path = report_gen.save_report_json(analysis, os.path.join(outputs_dir, "reports"), "kidney")

    return {
        "status": "success",
        "prediction": "Stone Detected" if analysis["stone_detected"] else "Normal",
        "model_confidence": analysis["model_confidence"],
        "findings": {
            "stone_detected": analysis["stone_detected"],
            "size_analysis": analysis["size_analysis"],
            "severity": analysis["severity"],
            "location_and_composition": analysis["location_and_composition"],
        },
        "classification_probabilities": analysis["classification_probs"],
        "recommendations": analysis["recommendations"],
        "clinical_notes": analysis["clinical_notes"],
        "report": {
            "text_path": f"/outputs/reports/{os.path.basename(report_path)}",
            "json_path": f"/outputs/reports/{os.path.basename(report_json_path)}",
            "report_id": report_gen.report_id,
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/analyze/unified")
async def analyze_unified(brain_file: UploadFile = File(...), kidney_file: UploadFile = File(...)):
    """Unified analysis of both brain and kidney scans with combined report."""
    
    # Process brain image
    brain_contents = await brain_file.read()
    brain_img = cv2.imdecode(np.frombuffer(brain_contents, np.uint8), cv2.IMREAD_COLOR)
    brain_orig = brain_img.copy()

    brain_img_resized = cv2.resize(brain_img, (256, 256)) / 255.0
    brain_tensor = torch.tensor(brain_img_resized).permute(2, 0, 1).unsqueeze(0).float().to(device)

    with torch.no_grad():
        brain_pred = brain_model(brain_tensor)
        brain_prob = torch.sigmoid(brain_pred).squeeze().cpu().numpy()

    brain_confidence = float(np.mean(brain_prob))
    brain_mask = (brain_prob > 0.5).astype(np.uint8)
    brain_mask = cv2.resize(brain_mask, (brain_orig.shape[1], brain_orig.shape[0]))

    brain_analyzer = BrainTumorAnalyzer(brain_mask, brain_orig, brain_confidence)
    brain_analysis = brain_analyzer.generate_analysis_report()

    # Process kidney image
    kidney_contents = await kidney_file.read()
    kidney_img = cv2.imdecode(np.frombuffer(kidney_contents, np.uint8), cv2.IMREAD_COLOR)
    kidney_orig = kidney_img.copy()

    kidney_img_resized = cv2.resize(kidney_img, (224, 224)) / 255.0
    kidney_tensor = torch.tensor(kidney_img_resized).permute(2, 0, 1).unsqueeze(0).float().to(device)

    with torch.no_grad():
        kidney_pred = kidney_model(kidney_tensor)
        kidney_probs = torch.softmax(kidney_pred, dim=1).cpu().numpy()[0]

    kidney_confidence = float(np.max(kidney_probs))
    kidney_analyzer = KidneyStoneAnalyzer(kidney_probs, kidney_confidence)
    kidney_analysis = kidney_analyzer.generate_analysis_report()

    # Generate unified report
    report_gen = MedicalReportGenerator()
    unified_report = report_gen.generate_unified_report(brain_analysis, kidney_analysis, images_analyzed=2)
    report_path = report_gen.save_report(unified_report, os.path.join(outputs_dir, "reports"), "unified")
    report_json_path = report_gen.save_report_json({
        "brain": brain_analysis,
        "kidney": kidney_analysis,
    }, os.path.join(outputs_dir, "reports"), "unified")

    return {
        "status": "success",
        "analysis_type": "unified",
        "report_id": report_gen.report_id,
        "brain_findings": {
            "prediction": "Tumor Detected" if brain_analysis["tumor_detected"] else "Normal",
            "model_confidence": brain_analysis["model_confidence"],
            "affected_percentage": brain_analysis["affected_percentage"],
            "severity_level": brain_analysis["severity_level"],
            "size_metrics": brain_analysis["size_metrics"],
        },
        "kidney_findings": {
            "prediction": "Stone Detected" if kidney_analysis["stone_detected"] else "Normal",
            "model_confidence": kidney_analysis["model_confidence"],
            "size_analysis": kidney_analysis["size_analysis"],
            "severity": kidney_analysis["severity"],
        },
        "combined_report": {
            "text_path": f"/outputs/reports/{os.path.basename(report_path)}",
            "json_path": f"/outputs/reports/{os.path.basename(report_json_path)}",
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "device": device.__str__(),
        "models_loaded": True,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/info")
async def info():
    """API information endpoint."""
    return {
        "name": "Advanced Medical Imaging Analysis System",
        "version": "2.0",
        "endpoints": {
            "brain_analysis": "/predict/brain",
            "kidney_analysis": "/predict/kidney",
            "unified_analysis": "/analyze/unified",
            "health": "/health",
        },
        "features": [
            "Advanced medical metrics (size, location, severity)",
            "Grad-CAM explainability visualizations",
            "Medical-style clinical reports",
            "Unified multi-organ analysis",
            "Confidence scoring and risk stratification",
        ],
        "device": device.__str__(),
    }