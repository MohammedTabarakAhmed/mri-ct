"""
Grad-CAM (Gradient-weighted Class Activation Maps) for model explainability.
Generates visual explanations of model decisions.
"""

import torch
import torch.nn.functional as F
import numpy as np
import cv2
from typing import Callable, List, Tuple


class GradCAM:
    """Generate Grad-CAM explanations for convolutional neural networks."""
    
    def __init__(self, model: torch.nn.Module, target_layer: str, device: str = "cpu"):
        """
        Args:
            model: PyTorch model
            target_layer: Name of target layer (e.g., 'layer4' for ResNet)
            device: 'cuda' or 'cpu'
        """
        self.model = model
        self.device = device
        self.target_layer_name = target_layer
        self.gradients = []
        self.activations = []
        self.hooks = []
        self._register_hooks()
    
    def _register_hooks(self):
        """Register forward and backward hooks on target layer."""
        target_layer = self._get_layer_by_name(self.model, self.target_layer_name)
        
        if target_layer is None:
            raise ValueError(f"Layer {self.target_layer_name} not found in model")
        
        def forward_hook(module, input, output):
            self.activations.append(output.detach())
        
        def backward_hook(module, grad_input, grad_output):
            self.gradients.append(grad_output[0].detach())
        
        forward_h = target_layer.register_forward_hook(forward_hook)
        backward_h = target_layer.register_full_backward_hook(backward_hook)
        
        self.hooks.append(forward_h)
        self.hooks.append(backward_h)
    
    def _get_layer_by_name(self, model: torch.nn.Module, layer_name: str):
        """Recursively find layer by name."""
        for name, module in model.named_modules():
            if name.endswith(layer_name) or name == layer_name:
                return module
        return None
    
    def remove_hooks(self):
        """Remove registered hooks."""
        for hook in self.hooks:
            hook.remove()
    
    def generate(self, input_tensor: torch.Tensor, class_idx: int = None) -> np.ndarray:
        """
        Generate Grad-CAM map.
        
        Args:
            input_tensor: Input image tensor (1, C, H, W)
            class_idx: Target class index (None for max prediction)
        
        Returns:
            Grad-CAM heatmap (H, W)
        """
        self.model.eval()
        
        # Forward pass
        with torch.enable_grad():
            logits = self.model(input_tensor)
            
            if class_idx is None:
                class_idx = logits.argmax(dim=1).item()
            
            target = logits[0, class_idx]
            
            # Backward pass
            self.model.zero_grad()
            target.backward()
        
        # Get gradients and activations
        gradients = self.gradients[-1].cpu().numpy()[0]  # (C, H, W)
        activations = self.activations[-1].cpu().numpy()[0]  # (C, H, W)
        
        # Compute weights (average pooled gradients)
        weights = gradients.mean(axis=(1, 2))  # (C,)
        
        # Compute weighted sum of activations
        grad_cam = np.sum(weights[:, np.newaxis, np.newaxis] * activations, axis=0)
        grad_cam = np.maximum(grad_cam, 0)  # ReLU
        
        # Normalize
        grad_cam_min = grad_cam.min()
        grad_cam_max = grad_cam.max()
        if grad_cam_max > grad_cam_min:
            grad_cam = (grad_cam - grad_cam_min) / (grad_cam_max - grad_cam_min)
        
        # Resize to input size
        grad_cam = cv2.resize(grad_cam, (input_tensor.shape[3], input_tensor.shape[2]))
        
        self.gradients.clear()
        self.activations.clear()
        
        return grad_cam
    
    def visualize(self, input_image: np.ndarray, grad_cam: np.ndarray, 
                  alpha: float = 0.5, colormap: int = cv2.COLORMAP_JET) -> np.ndarray:
        """
        Overlay Grad-CAM on original image.
        
        Args:
            input_image: Original image (H, W, 3) in BGR format, values 0-255
            grad_cam: Grad-CAM heatmap (H, W) normalized to 0-1
            alpha: Transparency factor
            colormap: OpenCV colormap constant
        
        Returns:
            Overlaid image (H, W, 3)
        """
        # Normalize grad_cam to 0-255
        heatmap = np.uint8(255 * grad_cam)
        
        # Apply colormap
        heatmap_colored = cv2.applyColorMap(heatmap, colormap)
        
        # Overlay on original image
        overlay = cv2.addWeighted(input_image, 1 - alpha, heatmap_colored, alpha, 0)
        
        return overlay


class SegmentationGradCAM:
    """Grad-CAM for segmentation models (U-Net style)."""
    
    def __init__(self, model: torch.nn.Module, encoder_layer: str = "encoder", 
                 device: str = "cpu"):
        """
        Args:
            model: Segmentation model (with encoder)
            encoder_layer: Name of encoder module
            device: 'cuda' or 'cpu'
        """
        self.model = model
        self.device = device
        self.encoder_layer = encoder_layer
        self.gradients = []
        self.activations = []
        self.hook = None
        self._register_hook()
    
    def _register_hook(self):
        """Register forward hook on encoder."""
        def forward_hook(module, input, output):
            self.activations.append(output.detach())
        
        def backward_hook(module, grad_input, grad_output):
            self.gradients.append(grad_output[0].detach())
        
        # For segmentation models, try to hook into encoder
        try:
            # Try common encoder names for segmentation
            encoder = None
            for name, module in self.model.named_modules():
                if "encoder" in name.lower() or "backbone" in name.lower():
                    encoder = module
                    break
            
            if encoder is None:
                # Fallback to first main layer
                for name, module in self.model.named_modules():
                    if len(list(module.children())) > 0:
                        encoder = module
                        break
            
            if encoder is not None:
                forward_h = encoder.register_forward_hook(forward_hook)
                backward_h = encoder.register_full_backward_hook(backward_hook)
                self.hook = (forward_h, backward_h)
        except Exception as e:
            print(f"Warning: Could not register hook: {e}")
    
    def generate(self, input_tensor: torch.Tensor) -> np.ndarray:
        """
        Generate Grad-CAM for segmentation output.
        
        Args:
            input_tensor: Input image tensor (1, C, H, W)
        
        Returns:
            Grad-CAM heatmap (H, W)
        """
        self.model.eval()
        
        with torch.enable_grad():
            logits = self.model(input_tensor)
            
            # For segmentation, use mean of output as optimization target
            target = logits.mean()
            
            self.model.zero_grad()
            target.backward(retain_graph=True)
        
        if len(self.gradients) == 0 or len(self.activations) == 0:
            # Fallback: return simple activation based heatmap
            output_map = torch.sigmoid(logits[0]).squeeze().detach().cpu().numpy()
            return output_map
        
        gradients = self.gradients[-1].cpu().numpy()[0]
        activations = self.activations[-1].cpu().numpy()[0]
        
        # Handle different tensor shapes
        if gradients.ndim == 3:  # (C, H, W)
            weights = gradients.mean(axis=(1, 2))
            grad_cam = np.sum(weights[:, np.newaxis, np.newaxis] * activations, axis=0)
        else:
            grad_cam = gradients.squeeze()
        
        grad_cam = np.maximum(grad_cam, 0)
        
        # Normalize
        if grad_cam.max() > grad_cam.min():
            grad_cam = (grad_cam - grad_cam.min()) / (grad_cam.max() - grad_cam.min())
        
        # Resize to input size
        grad_cam = cv2.resize(grad_cam, (input_tensor.shape[3], input_tensor.shape[2]))
        
        self.gradients.clear()
        self.activations.clear()
        
        return grad_cam


def create_combined_explanation(original_image: np.ndarray, 
                                grad_cam: np.ndarray,
                                prediction_mask: np.ndarray = None,
                                title: str = "Model Explanation") -> np.ndarray:
    """
    Create combined visualization with multiple explanation views.
    
    Args:
        original_image: Original image
        grad_cam: Grad-CAM heatmap
        prediction_mask: Optional prediction mask
        title: Title for visualization
    
    Returns:
        Combined visualization image
    """
    h, w = original_image.shape[:2]
    
    # Normalize grad_cam
    grad_cam_norm = (grad_cam - grad_cam.min()) / (grad_cam.max() - grad_cam.min() + 1e-8)
    
    # Create heatmap
    heatmap = np.uint8(255 * grad_cam_norm)
    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    
    # Overlay on original
    overlay = cv2.addWeighted(original_image, 0.6, heatmap_colored, 0.4, 0)
    
    # Create combined image (side by side)
    combined = np.hstack([original_image, overlay])
    
    if prediction_mask is not None:
        mask_colored = cv2.cvtColor((prediction_mask * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        combined = np.hstack([combined, mask_colored])
    
    return combined


def create_attention_map(grad_cam: np.ndarray, percentile: int = 90) -> np.ndarray:
    """
    Create binary attention map from Grad-CAM.
    
    Args:
        grad_cam: Grad-CAM heatmap
        percentile: Percentile threshold for attention
    
    Returns:
        Binary attention map
    """
    threshold = np.percentile(grad_cam, percentile)
    attention_map = (grad_cam > threshold).astype(np.uint8)
    return attention_map
