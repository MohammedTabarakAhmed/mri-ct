"""
Advanced Medical Imaging Analysis System - Streamlit Web Application
A professional medical AI interface for brain tumor and kidney stone analysis
"""

import streamlit as st
import cv2
import numpy as np
import torch
import os
import sys
from datetime import datetime
from pathlib import Path
from PIL import Image
import json

# Add project to path
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from src.models.unet_resnet import get_model
from src.models.kidney_model import get_kidney_model
from src.utils.analysis import BrainTumorAnalyzer, KidneyStoneAnalyzer
from src.utils.gradcam import SegmentationGradCAM, GradCAM
from src.utils.report_generator import MedicalReportGenerator

# Page configuration
st.set_page_config(
    page_title="Advanced Medical Imaging Analysis",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
    <style>
    .main-title {
        font-size: 3em;
        color: #667eea;
        text-align: center;
        margin-bottom: 10px;
        font-weight: bold;
    }
    .subtitle {
        font-size: 1.3em;
        color: #666;
        text-align: center;
        margin-bottom: 30px;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        text-align: center;
    }
    .finding-box {
        background: #f7f9fc;
        border-left: 4px solid #667eea;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .finding-box.critical {
        border-left-color: #ff6b6b;
        background: #ffe0e0;
    }
    .finding-box.warning {
        border-left-color: #ffa500;
        background: #fff3e0;
    }
    .recommendation {
        background: #fffbea;
        border-left: 4px solid #ffa500;
        padding: 12px;
        margin: 8px 0;
        border-radius: 5px;
        color: #333333;
    }
    .clinical-note {
        background: #fff9e6;
        border: 2px solid #ffd700;
        padding: 15px;
        border-radius: 8px;
        margin: 15px 0;
        font-style: italic;
        color: #855500;
    }
    .tab-title {
        font-size: 1.8em;
        color: #333;
        margin-bottom: 20px;
        font-weight: bold;
        border-bottom: 3px solid #667eea;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if "device" not in st.session_state:
    st.session_state.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    st.session_state.models_loaded = False
    st.session_state.brain_model = None
    st.session_state.kidney_model = None


# Custom JSON encoder for numpy types and booleans
class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that can serialize numpy types and booleans"""
    def default(self, obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


@st.cache_resource
def load_models():
    """Load pre-trained models"""
    try:
        device = st.session_state.device
        outputs_dir = BASE_DIR / "outputs"
        
        # Load brain model
        brain_model = get_model()
        brain_model.load_state_dict(
            torch.load(outputs_dir / "models" / "model.pth", map_location=device),
            strict=False,
        )
        brain_model.to(device).eval()
        
        # Load kidney model
        kidney_model = get_kidney_model()
        kidney_model.load_state_dict(
            torch.load(outputs_dir / "models" / "kidney_model.pth", map_location=device),
            strict=False,
        )
        kidney_model.to(device).eval()
        
        return brain_model, kidney_model
    except Exception as e:
        st.error(f"Error loading models: {e}")
        return None, None


def display_header():
    """Display application header"""
    st.markdown('<div class="main-title">🏥 Advanced Medical Imaging Analysis System</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">AI-Powered Diagnostic Support with Explainability</div>', unsafe_allow_html=True)
    st.divider()


def analyze_brain(image_file, brain_model):
    """Analyze brain MRI/CT image"""
    try:
        # Read image
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        orig = img.copy()
        
        # Preprocess
        img_resized = cv2.resize(img, (256, 256)) / 255.0
        img_tensor = torch.tensor(img_resized).permute(2, 0, 1).unsqueeze(0).float().to(st.session_state.device)
        
        # Predict
        with torch.no_grad():
            pred = brain_model(img_tensor)
            prob = torch.sigmoid(pred).squeeze().cpu().numpy()
        
        confidence = float(np.mean(prob))
        mask = (prob > 0.5).astype(np.uint8)
        mask = cv2.resize(mask, (orig.shape[1], orig.shape[0]))
        
        # Generate Grad-CAM
        grad_cam_img = None
        try:
            grad_cam_gen = SegmentationGradCAM(brain_model, device=str(st.session_state.device))
            grad_cam = grad_cam_gen.generate(img_tensor)
            grad_cam_img = (grad_cam * 255).astype(np.uint8)
            grad_cam_colored = cv2.applyColorMap(grad_cam_img, cv2.COLORMAP_JET)
        except:
            grad_cam_colored = None
        
        # Create visualization
        overlay = orig.copy()
        overlay[mask == 1] = [0, 0, 255]
        result = cv2.addWeighted(orig, 0.3, overlay, 0.7, 0)
        
        # Run analysis
        analyzer = BrainTumorAnalyzer(mask, orig, confidence)
        analysis = analyzer.generate_analysis_report()
        
        # Generate report
        report_gen = MedicalReportGenerator()
        medical_report = report_gen.generate_brain_report(analysis)
        
        return {
            "success": True,
            "analysis": analysis,
            "visualization": result,
            "grad_cam": grad_cam_colored,
            "report": medical_report,
            "report_gen": report_gen,
            "original": orig,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_kidney(image_file, kidney_model):
    """Analyze kidney ultrasound/CT image"""
    try:
        # Read image
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        orig = img.copy()
        
        # Preprocess
        img_resized = cv2.resize(img, (224, 224)) / 255.0
        img_tensor = torch.tensor(img_resized).permute(2, 0, 1).unsqueeze(0).float().to(st.session_state.device)
        
        # Predict
        with torch.no_grad():
            pred = kidney_model(img_tensor)
            probs = torch.softmax(pred, dim=1).cpu().numpy()[0]
        
        confidence = float(np.max(probs))
        
        # Generate Grad-CAM
        grad_cam_colored = None
        try:
            grad_cam_gen = GradCAM(kidney_model, target_layer="layer4", device=str(st.session_state.device))
            grad_cam = grad_cam_gen.generate(img_tensor)
            grad_cam_img = (grad_cam * 255).astype(np.uint8)
            grad_cam_colored = cv2.applyColorMap(grad_cam_img, cv2.COLORMAP_JET)
            grad_cam_colored = cv2.resize(grad_cam_colored, (orig.shape[1], orig.shape[0]))
            grad_cam_gen.remove_hooks()
        except:
            grad_cam_colored = None
        
        # Run analysis
        analyzer = KidneyStoneAnalyzer(probs, confidence)
        analysis = analyzer.generate_analysis_report()
        
        # Generate report
        report_gen = MedicalReportGenerator()
        medical_report = report_gen.generate_kidney_report(analysis)
        
        return {
            "success": True,
            "analysis": analysis,
            "grad_cam": grad_cam_colored,
            "report": medical_report,
            "report_gen": report_gen,
            "original": orig,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def display_brain_results(results):
    """Display brain analysis results"""
    if not results["success"]:
        st.error(f"Analysis failed: {results['error']}")
        return
    
    analysis = results["analysis"]
    
    # Prediction banner
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if analysis["tumor_detected"]:
            st.error(f"🚨 **Tumor Detected** - Confidence: {analysis['model_confidence']*100:.1f}%")
        else:
            st.success(f"✅ **No Tumor Detected** - Confidence: {analysis['model_confidence']*100:.1f}%")
    
    st.divider()
    
    # Main metrics
    st.markdown("### 📊 Tumor Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Severity Level", analysis["severity_level"], help="Tumor severity classification")
    with col2:
        st.metric("Affected Area", f"{analysis['affected_percentage']:.2f}%", help="Percentage of brain affected")
    with col3:
        st.metric("Diameter (mm)", f"{analysis['size_metrics']['estimated_diameter_mm']:.2f}", help="Estimated tumor diameter")
    with col4:
        st.metric("Area (mm²)", f"{analysis['size_metrics']['area_mm2']:.1f}", help="Estimated tumor area")
    
    # Location information
    st.markdown("### 📍 Location Analysis")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Primary Location:** {analysis['location']['location']}")
        st.write(f"**Quadrants:** {', '.join(analysis['location']['quadrants'])}")
    with col2:
        st.write(f"**Center Position (% from top-left):**")
        st.write(f"X: {analysis['location']['center_coordinates']['x_percent']:.1f}% | Y: {analysis['location']['center_coordinates']['y_percent']:.1f}%")
    
    # Shape analysis
    st.markdown("### 🔍 Shape Analysis")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Compactness", f"{analysis['shape_metrics']['compactness']:.3f}", help="Shape regularity (lower = more compact)")
    with col2:
        st.metric("Solidity", f"{analysis['shape_metrics']['solidity']:.3f}", help="Fill density (higher = more uniform)")
    with col3:
        st.metric("Eccentricity", f"{analysis['shape_metrics']['eccentricity']:.3f}", help="Elongation (0=circle, 1=line)")
    
    st.divider()
    
    # Visualizations
    st.markdown("### 📸 Visual Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Segmentation Mask")
        st.image(results["visualization"], use_column_width=True, caption="Tumor highlighted in red overlay")
    
    with col2:
        st.subheader("Grad-CAM Heatmap")
        if results["grad_cam"] is not None:
            st.image(results["grad_cam"], use_column_width=True, caption="Model decision explanation (red=high importance)")
        else:
            st.info("Grad-CAM visualization not available")
    
    st.divider()
    
    # Recommendations
    st.markdown("### 💡 Clinical Recommendations")
    if "recommendations" in analysis and analysis["recommendations"]:
        for i, rec in enumerate(analysis["recommendations"], 1):
            st.markdown(f'<div class="recommendation">✓ {rec}</div>', unsafe_allow_html=True)
    else:
        st.info("No specific recommendations available at this time.")
    
    # Clinical notes
    st.markdown("### 📝 Clinical Notes")
    if "clinical_notes" in analysis and analysis["clinical_notes"]:
        st.markdown(f'<div class="clinical-note">{analysis["clinical_notes"]}</div>', unsafe_allow_html=True)
    else:
        st.info("No clinical notes available.")
    
    # Download report
    st.divider()
    st.markdown("### 📄 Download Report")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Download Text Report",
            data=results["report"],
            file_name=f"brain_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
        )
    with col2:
        st.download_button(
            label="📥 Download JSON Report",
            data=json.dumps(analysis, indent=2, cls=NumpyEncoder),
            file_name=f"brain_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )


def display_kidney_results(results):
    """Display kidney analysis results"""
    if not results["success"]:
        st.error(f"Analysis failed: {results['error']}")
        return
    
    analysis = results["analysis"]
    
    # Prediction banner
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if analysis["stone_detected"]:
            st.error(f"🚨 **Stone Detected** - Confidence: {analysis['model_confidence']*100:.1f}%")
        else:
            st.success(f"✅ **No Stone Detected** - Confidence: {analysis['model_confidence']*100:.1f}%")
    
    st.divider()
    
    # Main metrics
    st.markdown("### 📊 Stone Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Severity Level", analysis["severity"]["level"])
    with col2:
        st.metric("Size Category", analysis["size_analysis"]["size_category"])
    with col3:
        st.metric("Estimated Size", f"~{analysis['size_analysis']['estimated_size_mm']} mm")
    with col4:
        st.metric("Risk Score", f"{analysis['severity']['risk_score']:.2f}")
    
    # Classification probabilities
    st.markdown("### 🎯 Classification Confidence")
    col1, col2 = st.columns(2)
    with col1:
        normal_pct = analysis["classification_probs"]["normal"] * 100
        st.progress(analysis["classification_probs"]["normal"], text=f"Normal: {normal_pct:.1f}%")
    with col2:
        stone_pct = analysis["classification_probs"]["stone"] * 100
        st.progress(analysis["classification_probs"]["stone"], text=f"Stone: {stone_pct:.1f}%")
    
    # Location and composition
    st.markdown("### 📍 Location & Composition")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Likely Location:**")
        st.write(analysis["location_and_composition"]["likely_location"])
    with col2:
        st.write(f"**Probable Composition:**")
        st.write(analysis["location_and_composition"]["composition_likely"])
    
    st.write(f"**Characteristic:** {analysis['location_and_composition']['characteristic']}")
    
    st.divider()
    
    # Visualizations
    if results["grad_cam"] is not None:
        st.markdown("### 📸 Grad-CAM Heatmap")
        st.image(results["grad_cam"], use_column_width=True, caption="Model decision explanation (red=high importance)")
        st.divider()
    
    # Recommendations
    st.markdown("### 💡 Clinical Recommendations")
    if "recommendations" in analysis and analysis["recommendations"]:
        for i, rec in enumerate(analysis["recommendations"], 1):
            st.markdown(f'<div class="recommendation">✓ {rec}</div>', unsafe_allow_html=True)
    else:
        st.info("No specific recommendations available at this time.")
    
    # Clinical notes
    st.markdown("### 📝 Clinical Notes")
    if "clinical_notes" in analysis and analysis["clinical_notes"]:
        st.markdown(f'<div class="clinical-note">{analysis["clinical_notes"]}</div>', unsafe_allow_html=True)
    else:
        st.info("No clinical notes available.")
    
    # Download report
    st.divider()
    st.markdown("### 📄 Download Report")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Download Text Report",
            data=results["report"],
            file_name=f"kidney_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
        )
    with col2:
        st.download_button(
            label="📥 Download JSON Report",
            data=json.dumps(analysis, indent=2, cls=NumpyEncoder),
            file_name=f"kidney_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )


def page_home():
    """Home page"""
    display_header()
    
    st.markdown("""
    Welcome to the Advanced Medical Imaging Analysis System - a professional AI-powered diagnostic support platform.
    
    ### 🎯 Features
    
    - **🧠 Brain Tumor Analysis**: Detailed metrics including size, location, and severity
    - **🫘 Kidney Stone Analysis**: Stone detection with size estimation and risk scoring
    - **🔍 Model Explainability**: Grad-CAM heatmaps showing model reasoning
    - **📊 Professional Reports**: Clinical-grade analysis with recommendations
    - **📱 Unified Analysis**: Analyze multiple organs together
    
    ### 🚀 How to Use
    
    1. Select **Brain Analysis** or **Kidney Analysis** from the sidebar
    2. Upload your medical image (JPG, PNG, etc.)
    3. View detailed findings with visualizations
    4. Download professional medical reports
    
    ### ⚠️ Important Disclaimer
    
    This system is a **clinical support tool only**, not a diagnostic system. All results must be reviewed 
    by qualified medical professionals. This tool should not replace professional medical consultation.
    
    ---
    
    **Device:** GPU ✅ if available else CPU  
    **Status:** Ready for analysis
    """)


def page_brain_analysis():
    """Brain analysis page"""
    st.markdown('<div class="tab-title">🧠 Brain Tumor Analysis</div>', unsafe_allow_html=True)
    
    # Load models
    brain_model, _ = load_models()
    if brain_model is None:
        st.error("Failed to load brain model")
        return
    
    # File upload
    st.markdown("### Upload Brain MRI/CT Image")
    uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png", "bmp"], key="brain_upload")
    
    if uploaded_file is not None:
        # Show uploaded image
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Uploaded Image")
            image = Image.open(uploaded_file)
            st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("📋 Image Info")
            st.write(f"**Filename:** {uploaded_file.name}")
            st.write(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
            st.write(f"**Format:** {uploaded_file.type}")
        
        # Analyze button
        if st.button("🔬 Analyze Brain Image", type="primary", use_container_width=True):
            with st.spinner("🔄 Analyzing brain image... This may take a few seconds"):
                # Reset file pointer
                uploaded_file.seek(0)
                results = analyze_brain(uploaded_file, brain_model)
            
            st.divider()
            display_brain_results(results)


def page_kidney_analysis():
    """Kidney analysis page"""
    st.markdown('<div class="tab-title">🫘 Kidney Stone Analysis</div>', unsafe_allow_html=True)
    
    # Load models
    _, kidney_model = load_models()
    if kidney_model is None:
        st.error("Failed to load kidney model")
        return
    
    # File upload
    st.markdown("### Upload Kidney Ultrasound/CT Image")
    uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png", "bmp"], key="kidney_upload")
    
    if uploaded_file is not None:
        # Show uploaded image
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Uploaded Image")
            image = Image.open(uploaded_file)
            st.image(image, use_column_width=True)
        
        with col2:
            st.subheader("📋 Image Info")
            st.write(f"**Filename:** {uploaded_file.name}")
            st.write(f"**Size:** {uploaded_file.size / 1024:.1f} KB")
            st.write(f"**Format:** {uploaded_file.type}")
        
        # Analyze button
        if st.button("🔬 Analyze Kidney Image", type="primary", use_container_width=True):
            with st.spinner("🔄 Analyzing kidney image... This may take a few seconds"):
                # Reset file pointer
                uploaded_file.seek(0)
                results = analyze_kidney(uploaded_file, kidney_model)
            
            st.divider()
            display_kidney_results(results)


def page_about():
    """About page"""
    st.markdown('<div class="tab-title">ℹ️ About This System</div>', unsafe_allow_html=True)
    
    st.markdown("""
    ## Advanced Medical Imaging Analysis System v2.0
    
    ### 🔬 Technology Stack
    
    - **Deep Learning**: PyTorch, U-Net, ResNet
    - **Model Explainability**: Grad-CAM
    - **Web Framework**: Streamlit
    - **Image Processing**: OpenCV, scikit-image
    - **Report Generation**: Jinja2 templating
    
    ### 🧠 Brain Model
    
    - **Architecture**: U-Net with ResNet-34 encoder
    - **Task**: Semantic segmentation of brain tumors
    - **Input**: 256×256 MRI/CT images
    - **Output**: Binary tumor/normal classification
    
    ### 🫘 Kidney Model
    
    - **Architecture**: ResNet-18 classifier
    - **Task**: Binary classification (normal/stone)
    - **Input**: 224×224 ultrasound/CT images
    - **Output**: Probability of stone presence
    
    ### 📊 Analysis Metrics
    
    #### Brain Tumor Analysis:
    - Tumor size (diameter in mm, area in mm²)
    - Affected brain percentage
    - Location (quadrants and coordinates)
    - Severity classification (5 levels)
    - Shape characteristics (compactness, solidity, eccentricity)
    - Clinical recommendations
    
    #### Kidney Stone Analysis:
    - Stone detection confidence
    - Size category (Very Small to Very Large)
    - Severity level (5 classifications)
    - Risk score (0-1 scale)
    - Likely location (calyceal, pelvis, ureter)
    - Composition probability
    - Treatment recommendations
    
    ### 🔍 Explainability Features
    
    **Grad-CAM (Gradient-weighted Class Activation Maps)**
    - Visualizes which image regions influenced model decisions
    - Color intensity shows attention: red (high) to blue (low)
    - Helps clinicians understand model reasoning
    - Supports both CNN and U-Net architectures
    
    ### 📄 Report Generation
    
    - Professional medical-grade formatting
    - Text and JSON output formats
    - Unique report IDs for tracking
    - Structured findings and recommendations
    - Clinical disclaimers
    
    ### 🏥 Clinical Applications
    
    - Screening support for radiologists
    - Research and education
    - Automated analysis of large datasets
    - Clinical decision support
    
    ### ⚠️ Important Notes
    
    - This is a **support tool**, not a diagnostic system
    - Results must be reviewed by qualified professionals
    - Should not replace clinical judgment
    - Intended for institutional use with proper validation
    
    ### 👥 Team
    
    Developed as an academic medical AI project demonstrating:
    - Deep learning for medical imaging
    - Model interpretability techniques
    - Professional software engineering
    - Healthcare AI best practices
    
    ---
    
    **Version**: 2.0  
    **Last Updated**: April 2026  
    **Status**: Production-Ready
    """)


def main():
    """Main application"""
    # Sidebar navigation
    with st.sidebar:
        st.image("https://via.placeholder.com/150?text=Medical+AI", use_column_width=True)
        st.markdown("---")
        
        page = st.radio(
            "📚 Navigation",
            ["🏠 Home", "🧠 Brain Analysis", "🫘 Kidney Analysis", "ℹ️ About"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Device info
        device_type = "🟢 GPU" if torch.cuda.is_available() else "🟡 CPU"
        st.markdown(f"**Device:** {device_type}")
        st.markdown(f"**Models Status:** {'✅ Loaded' if st.session_state.brain_model else '⏳ Loading...'}")
    
    # Page routing
    if page == "🏠 Home":
        page_home()
    elif page == "🧠 Brain Analysis":
        page_brain_analysis()
    elif page == "🫘 Kidney Analysis":
        page_kidney_analysis()
    elif page == "ℹ️ About":
        page_about()


if __name__ == "__main__":
    main()
