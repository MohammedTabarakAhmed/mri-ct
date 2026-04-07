"""
Advanced medical image analysis utilities.
Provides enhanced analysis for brain tumors and kidney stones.
"""

import numpy as np
import cv2
from typing import Dict, Any, Tuple
from scipy import ndimage
from skimage import measure


class BrainTumorAnalyzer:
    """Analyzes brain tumor segmentation masks and provides medical metrics."""
    
    # Assume standard brain MRI dimensions and voxel spacing
    MM_PER_PIXEL = 0.8  # Standard MRI voxel size (adjustable based on actual scans)
    
    def __init__(self, mask: np.ndarray, original_image: np.ndarray, confidence: float):
        """
        Args:
            mask: Binary segmentation mask (0s and 1s)
            original_image: Original image for analysis
            confidence: Model confidence score (0-1)
        """
        self.mask = mask
        self.original_image = original_image
        self.confidence = confidence
    
    def estimate_tumor_size(self) -> Dict[str, Any]:
        """Estimate tumor size in pixels and mm."""
        tumor_pixels = np.sum(self.mask == 1)
        
        # Calculate size metrics
        size_pixels = tumor_pixels
        size_mm2 = size_pixels * (self.MM_PER_PIXEL ** 2)
        
        # Estimate diameter (assuming roughly circular tumor)
        if tumor_pixels > 0:
            diameter_pixels = 2 * np.sqrt(size_pixels / np.pi)
            diameter_mm = diameter_pixels * self.MM_PER_PIXEL
        else:
            diameter_mm = 0
        
        return {
            "area_pixels": int(size_pixels),
            "area_mm2": float(round(size_mm2, 2)),
            "estimated_diameter_mm": float(round(diameter_mm, 2)),
            "estimated_diameter_pixels": float(round(diameter_pixels, 2)) if tumor_pixels > 0 else 0,
        }
    
    def get_affected_percentage(self) -> float:
        """Calculate percentage of brain affected by tumor."""
        total_pixels = self.mask.size
        tumor_pixels = np.sum(self.mask == 1)
        percentage = (tumor_pixels / total_pixels) * 100
        return float(round(percentage, 2))
    
    def locate_tumor(self) -> Dict[str, Any]:
        """Identify tumor location (quadrants and region)."""
        h, w = self.mask.shape
        tumor_pixels = np.where(self.mask == 1)
        
        if len(tumor_pixels[0]) == 0:
            return {"location": "No tumor detected", "quadrants": []}
        
        # Find center of mass
        center_y = np.mean(tumor_pixels[0])
        center_x = np.mean(tumor_pixels[1])
        
        # Determine quadrants
        quadrants = []
        if center_x < w / 2:
            quadrants.append("Left")
        else:
            quadrants.append("Right")
        
        if center_y < h / 2:
            quadrants.append("Superior")
        else:
            quadrants.append("Inferior")
        
        # Estimate depth (anterior-posterior)
        # This requires 3D data; for 2D slices we'll provide it as supplementary info
        location_text = " ".join(quadrants)
        
        return {
            "location": location_text,
            "quadrants": quadrants,
            "center_coordinates": {
                "x_percent": float(round((center_x / w) * 100, 1)),
                "y_percent": float(round((center_y / h) * 100, 1)),
            },
        }
    
    def get_severity_level(self, affected_percentage: float) -> str:
        """Classify severity based on affected area."""
        if affected_percentage < 0.5:
            return "Minimal"
        elif affected_percentage < 2:
            return "Small"
        elif affected_percentage < 5:
            return "Moderate"
        elif affected_percentage < 10:
            return "Large"
        else:
            return "Critical"
    
    def get_compact_shape_metrics(self) -> Dict[str, float]:
        """Calculate shape-based metrics (compactness, solidity, etc.)."""
        tumor_pixels = np.sum(self.mask == 1)
        if tumor_pixels == 0:
            return {"compactness": 0, "solidity": 0, "eccentricity": 0}
        
        # Label connected components
        labeled, num_features = ndimage.label(self.mask)
        
        if num_features == 0:
            return {"compactness": 0, "solidity": 0, "eccentricity": 0}
        
        # Get largest component (main tumor)
        largest_label = np.argmax(np.bincount(labeled.flat)[1:]) + 1
        largest_component = (labeled == largest_label).astype(np.uint8)
        
        # Compute properties
        props = measure.regionprops(labeled)
        main_region = props[largest_label - 1]
        
        # Compactness (perimeter^2 / area) - lower is more compact
        perimeter = cv2.findContours(largest_component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        if len(perimeter) > 0:
            perimeter_len = cv2.arcLength(perimeter[0], True)
            compactness = float((perimeter_len ** 2) / (4 * np.pi * tumor_pixels))
        else:
            compactness = 0
        
        # Solidity (area / convex hull area)
        hull = cv2.convexHull(perimeter[0]) if len(perimeter) > 0 else None
        if hull is not None:
            hull_area = cv2.contourArea(hull)
            solidity = float(tumor_pixels / hull_area) if hull_area > 0 else 0
        else:
            solidity = 0
        
        # Eccentricity (elongation of shape)
        eccentricity = main_region.eccentricity
        
        return {
            "compactness": float(round(compactness, 3)),
            "solidity": float(round(solidity, 3)),
            "eccentricity": float(round(eccentricity, 3)),
        }
    
    def generate_analysis_report(self) -> Dict[str, Any]:
        """Generate comprehensive brain tumor analysis report."""
        size_metrics = self.estimate_tumor_size()
        affected_pct = self.get_affected_percentage()
        location = self.locate_tumor()
        severity = self.get_severity_level(affected_pct)
        shape_metrics = self.get_compact_shape_metrics()
        
        return {
            "tumor_detected": affected_pct > 0.1,
            "model_confidence": float(round(self.confidence, 3)),
            "size_metrics": size_metrics,
            "affected_percentage": affected_pct,
            "severity_level": severity,
            "location": location,
            "shape_metrics": shape_metrics,
            "recommendations": self._get_recommendations(severity, affected_pct),
            "clinical_notes": self._get_clinical_notes(severity, affected_pct),
        }
    
    def _get_recommendations(self, severity: str, affected_pct: float) -> list:
        """Generate clinical recommendations based on findings."""
        recommendations = []
        
        if severity == "Critical":
            recommendations.extend([
                "Immediate consultation with neuro-oncologist required",
                "Schedule advanced imaging (3D MRI/CT)",
                "Consider treatment planning within 48-72 hours",
                "Neurological assessment needed",
            ])
        elif severity == "Large":
            recommendations.extend([
                "Urgent neurosurgeon consultation",
                "Advanced imaging recommended",
                "Monitor neurological symptoms closely",
                "Treatment planning should be prioritized",
            ])
        elif severity == "Moderate":
            recommendations.extend([
                "Specialist evaluation recommended",
                "Repeat MRI in 1-2 months",
                "Monitor for symptom changes",
                "Consider treatment options discussion",
            ])
        elif severity in ["Small", "Minimal"]:
            recommendations.extend([
                "Follow-up MRI in 3 months",
                "Monitor for symptom development",
                "Clinical assessment recommended",
                "Avoid additional radiation exposure",
            ])
        
        recommendations.append("Consult with medical imaging specialist for interpretation")
        return recommendations
    
    def _get_clinical_notes(self, severity: str, affected_pct: float) -> str:
        """Generate clinical interpretation notes."""
        if affected_pct < 0.1:
            return "No significant tumor tissue detected on this imaging plane."
        elif severity == "Critical":
            return f"Large tumor mass detected affecting {affected_pct:.2f}% of brain area. Immediate clinical attention required."
        elif severity == "Large":
            return f"Significant tumor involvement detected affecting {affected_pct:.2f}% of brain area."
        elif severity == "Moderate":
            return f"Moderate tumor mass detected affecting {affected_pct:.2f}% of brain area."
        else:
            return f"Small tumor lesion detected affecting {affected_pct:.2f}% of brain area. May require monitoring."


class KidneyStoneAnalyzer:
    """Analyzes kidney stone classification and provides medical metrics."""
    
    MM_PER_PIXEL = 0.8  # Adjustable based on actual imaging
    
    def __init__(self, class_probs: np.ndarray, confidence: float):
        """
        Args:
            class_probs: Array of class probabilities [normal_prob, stone_prob]
            confidence: Model confidence score (max probability)
        """
        self.normal_prob = float(class_probs[0])
        self.stone_prob = float(class_probs[1])
        self.confidence = confidence
        self.has_stone = class_probs[1] > 0.5
    
    def estimate_stone_size(self) -> Dict[str, Any]:
        """Estimate stone size based on model confidence and probability."""
        # Use model probability as proxy for stone size
        # Higher probability suggests larger/more obvious stone
        
        if not self.has_stone:
            return {
                "detected": False,
                "size_category": "N/A",
                "estimated_size_mm": 0,
                "size_confidence": 0,
            }
        
        # Map confidence to size categories
        confidence_diff = self.stone_prob - self.normal_prob
        
        if confidence_diff < 0.15:
            size_category = "Very Small (<5mm)"
            estimated_mm = 3
        elif confidence_diff < 0.30:
            size_category = "Small (5-10mm)"
            estimated_mm = 7
        elif confidence_diff < 0.50:
            size_category = "Medium (10-20mm)"
            estimated_mm = 15
        elif confidence_diff < 0.70:
            size_category = "Large (20-30mm)"
            estimated_mm = 25
        else:
            size_category = "Very Large (>30mm)"
            estimated_mm = 35
        
        return {
            "detected": True,
            "size_category": size_category,
            "estimated_size_mm": estimated_mm,
            "size_confidence": float(round(confidence_diff, 3)),
        }
    
    def classify_severity(self) -> Dict[str, Any]:
        """Classify stone severity based on size and confidence."""
        if not self.has_stone:
            return {
                "level": "No Stone",
                "risk_score": 0.0,
                "immediate_risk": False,
            }
        
        confidence_diff = self.stone_prob - self.normal_prob
        
        if confidence_diff > 0.60:
            severity = "Critical"
            risk_score = 0.9
            immediate_risk = True
        elif confidence_diff > 0.40:
            severity = "High"
            risk_score = 0.7
            immediate_risk = True
        elif confidence_diff > 0.20:
            severity = "Moderate"
            risk_score = 0.5
            immediate_risk = False
        else:
            severity = "Low"
            risk_score = 0.2
            immediate_risk = False
        
        return {
            "level": severity,
            "risk_score": round(risk_score, 2),
            "immediate_risk": immediate_risk,
        }
    
    def infer_location_and_composition(self) -> Dict[str, str]:
        """Infer likely stone location and composition characteristics."""
        if not self.has_stone:
            return {
                "likely_location": "N/A",
                "composition_likely": "N/A",
                "characteristic": "N/A",
            }
        
        confidence_diff = self.stone_prob - self.normal_prob
        
        # These are probabilistic inferences - actual imaging provides details
        if confidence_diff < 0.25:
            location = "Possibly calyceal or early ureteral"
            composition = "Likely calcium oxalate or uric acid"
            characteristic = "May migrate; monitoring recommended"
        elif confidence_diff < 0.45:
            location = "Likely renal pelvis or ureter"
            composition = "Likely staghorn or mixed stones"
            characteristic = "Moderate obstruction risk"
        else:
            location = "Probable middle ureter"
            composition = "Likely larger crystalline deposit"
            characteristic = "Higher obstruction and infection risk"
        
        return {
            "likely_location": location,
            "composition_likely": composition,
            "characteristic": characteristic,
        }
    
    def generate_analysis_report(self) -> Dict[str, Any]:
        """Generate comprehensive kidney stone analysis report."""
        size_info = self.estimate_stone_size()
        severity_info = self.classify_severity()
        location_info = self.infer_location_and_composition()
        
        return {
            "stone_detected": self.has_stone,
            "model_confidence": float(round(self.confidence, 3)),
            "classification_probs": {
                "normal": float(round(self.normal_prob, 3)),
                "stone": float(round(self.stone_prob, 3)),
            },
            "size_analysis": size_info,
            "severity": severity_info,
            "location_and_composition": location_info,
            "recommendations": self._get_recommendations(severity_info["level"], size_info),
            "clinical_notes": self._get_clinical_notes(severity_info, size_info),
        }
    
    def _get_recommendations(self, severity: str, size_info: Dict) -> list:
        """Generate clinical recommendations."""
        recommendations = []
        
        if not self.has_stone:
            recommendations.extend([
                "Maintain adequate hydration (2-3L daily)",
                "Continue regular urological follow-ups",
                "Monitor for any signs of urinary symptoms",
                "Preventive measures: low sodium, moderate oxalate diet",
            ])
        elif severity == "Critical":
            recommendations.extend([
                "Immediate urologist consultation required",
                "Consider urgent imaging (CT without contrast)",
                "Evaluate for intervention options (URS, ESWL, percutaneous)",
                "Monitor for signs of infection/sepsis",
                "Pain management consultation if needed",
            ])
        elif severity == "High":
            recommendations.extend([
                "Urgent urologist appointment (within 48-72 hours)",
                "Confirm with CT imaging",
                "Assess for symptoms (pain, hematuria, infection)",
                "Discuss treatment options",
                "Hydration and pain management",
            ])
        elif severity == "Moderate":
            recommendations.extend([
                "Schedule urologist consultation within 1-2 weeks",
                "Symptomatic management (hydration, analgesics)",
                "Monitor for complications",
                "Dietary modifications recommended",
                "Follow-up imaging in 4-6 weeks",
            ])
        else:  # Low
            recommendations.extend([
                "Routine urological follow-up",
                "Increase fluid intake (2-3L daily)",
                "Dietary management (low sodium, oxalate, purine)",
                "Monitor for symptom development",
                "Repeat imaging if symptoms develop",
            ])
        
        return recommendations
    
    def _get_clinical_notes(self, severity_info: Dict, size_info: Dict) -> str:
        """Generate clinical interpretation notes."""
        if not self.has_stone:
            return "No kidney stone detected. Kidneys appear normal."
        
        severity = severity_info["level"]
        size_cat = size_info["size_category"]
        
        if severity == "Critical":
            return f"Large kidney stone detected ({size_cat}). This is a clinically significant finding requiring urgent evaluation and likely intervention."
        elif severity == "High":
            return f"Significant kidney stone identified ({size_cat}). Clinical correlation with symptoms is recommended. Treatment evaluation indicated."
        elif severity == "Moderate":
            return f"Kidney stone present ({size_cat}). Clinical significance depends on location and symptoms. Conservative management with close follow-up or intervention may be considered."
        else:
            return f"Small kidney stone detected ({size_cat}). Often asymptomatic. Routine follow-up and preventive measures recommended."
