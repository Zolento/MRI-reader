"""
Image Processor - Handles all image enhancement operations
Supports contrast, brightness, log transform, rotation, and zoom
"""

import numpy as np
from typing import Tuple
from scipy.ndimage import rotate, zoom as scipy_zoom


class ImageProcessor:
    """
    Image processing class for MRI image enhancement
    
    All operations work on 2D numpy arrays and return processed images
    """
    
    def __init__(self):
        # Default parameters
        self.contrast = 1.0
        self.brightness = 0.0
        self.use_log = False
        self.rotation_angle = 0.0
        self.rotation_90_times = 0  # Number of 90-degree rotations
        self.zoom_factor = 1.0
        self.flip_h = False
        self.flip_v = False
    
    def reset(self):
        """Reset all parameters to defaults"""
        self.contrast = 1.0
        self.brightness = 0.0
        self.use_log = False
        self.rotation_angle = 0.0
        self.rotation_90_times = 0
        self.zoom_factor = 1.0
        self.flip_h = False
        self.flip_v = False
    
    def process(self, image: np.ndarray) -> np.ndarray:
        """
        Apply all enhancements to the image

        Args:
            image: 2D numpy array

        Returns:
            Processed 2D numpy array
        """
        # Handle complex input - take magnitude
        if np.iscomplexobj(image):
            image = np.abs(image)

        result = image.copy().astype(np.float64)

        # Clean up NaN and Inf values
        result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=0.0)

        # Apply log transform first (if enabled)
        if self.use_log:
            result = self._apply_log(result)

        # Normalize to [0, 1] before contrast/brightness
        if result.max() > result.min():
            result = (result - result.min()) / (result.max() - result.min())
        else:
            result = np.zeros_like(result)

        # Apply contrast and brightness on normalized data
        result = self._apply_contrast_brightness(result)

        # Apply rotation (arbitrary angle)
        if self.rotation_angle != 0:
            result = self._apply_rotation(result, self.rotation_angle)

        # Apply 90-degree rotation
        if self.rotation_90_times != 0:
            result = self.rotate_90(result, self.rotation_90_times)

        # Apply zoom
        if self.zoom_factor != 1.0:
            result = self._apply_zoom(result, self.zoom_factor)

        # Apply flip (after zoom to maintain correct dimensions)
        if self.flip_h:
            result = self.flip_horizontal(result)
        if self.flip_v:
            result = self.flip_vertical(result)

        return result
    
    def _apply_log(self, image: np.ndarray) -> np.ndarray:
        """
        Apply logarithmic transform
        Useful for viewing k-space data
        """
        # Ensure all values are positive before log
        image_clean = np.maximum(image, 0)
        
        # Add small epsilon to avoid log(0)
        epsilon = 1e-8
        result = np.log(image_clean + epsilon)
        
        # Normalize back to 0-1 range
        if result.max() > result.min():
            result = (result - result.min()) / (result.max() - result.min())
        
        # Clean up any NaN/Inf
        result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=0.0)
        
        return result
    
    def _apply_contrast_brightness(self, image: np.ndarray) -> np.ndarray:
        """
        Apply contrast and brightness adjustments

        Formula: result = image * contrast + brightness
        Input should already be normalized to [0, 1]
        """
        result = image * self.contrast + self.brightness

        # Clip to valid range
        result = np.clip(result, 0, 1)

        return result
    
    def _apply_rotation(self, image: np.ndarray, angle: float) -> np.ndarray:
        """
        Rotate image by specified angle
        
        Args:
            image: 2D array
            angle: rotation angle in degrees
        """
        # Use scipy rotate with order=1 (bilinear interpolation)
        result = rotate(image, angle=angle, reshape=False, order=1, mode='constant', cval=0)
        return result
    
    def _apply_zoom(self, image: np.ndarray, factor: float) -> np.ndarray:
        """
        Zoom image by specified factor
        
        Args:
            image: 2D array
            factor: zoom factor (>1 zooms in, <1 zooms out)
        """
        # Calculate zoom for each dimension
        zoom_factors = (factor, factor)
        
        # Apply zoom
        result = scipy_zoom(image, zoom_factors, order=1, mode='constant', cval=0)
        
        # Resize back to original shape
        result = self._resize_to_original(result, image.shape)
        
        return result
    
    def _resize_to_original(self, image: np.ndarray, original_shape: Tuple[int, int]) -> np.ndarray:
        """
        Resize image to original shape by center cropping or padding
        """
        if image.shape == original_shape:
            return image
        
        result = np.zeros(original_shape, dtype=image.dtype)
        
        # Calculate crop/pad amounts
        h_diff = image.shape[0] - original_shape[0]
        w_diff = image.shape[1] - original_shape[1]
        
        if h_diff > 0:
            # Image is larger, crop vertically
            start_h = h_diff // 2
            end_h = start_h + original_shape[0]
            image = image[start_h:end_h, :]
        elif h_diff < 0:
            # Image is smaller, pad vertically
            pad_h = -h_diff
            pad_top = pad_h // 2
            pad_bottom = pad_h - pad_top
            image = np.pad(image, ((pad_top, pad_bottom), (0, 0)), mode='constant')
        
        if image.shape[1] > original_shape[1]:
            # Image is larger, crop horizontally
            start_w = (image.shape[1] - original_shape[1]) // 2
            end_w = start_w + original_shape[1]
            image = image[:, start_w:end_w]
        elif image.shape[1] < original_shape[1]:
            # Image is smaller, pad horizontally
            pad_w = original_shape[1] - image.shape[1]
            pad_left = pad_w // 2
            pad_right = pad_w - pad_left
            image = np.pad(image, ((0, 0), (pad_left, pad_right)), mode='constant')
        
        return image
    
    def rotate_90(self, image: np.ndarray, times: int = 1) -> np.ndarray:
        """
        Rotate image by 90 degrees
        
        Args:
            image: 2D array
            times: number of 90-degree rotations
        """
        return np.rot90(image, k=times)
    
    def flip_horizontal(self, image: np.ndarray) -> np.ndarray:
        """Flip image horizontally"""
        return np.fliplr(image)
    
    def flip_vertical(self, image: np.ndarray) -> np.ndarray:
        """Flip image vertically"""
        return np.flipud(image)
    
    @staticmethod
    def normalize_image(image: np.ndarray) -> np.ndarray:
        """
        Normalize image to 0-1 range
        """
        if image.max() == image.min():
            return np.zeros_like(image)
        
        normalized = (image - image.min()) / (image.max() - image.min())
        return normalized
    
    @staticmethod
    def convert_to_8bit(image: np.ndarray) -> np.ndarray:
        """
        Convert floating point image (0-1) to 8-bit (0-255)
        """
        # Ensure image is in 0-1 range
        image_clipped = np.clip(image, 0, 1)
        return (image_clipped * 255).astype(np.uint8)
