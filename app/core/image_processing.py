import cv2
import numpy as np
from PIL import Image
import io
import logging
from typing import Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

np.random.seed(42)
cv2.setRNGSeed(42)


class ImageProcessor:
    """Handles image preprocessing for bill documents"""
    
    def __init__(self, target_dpi: int = 300, min_resolution: int = 800):
        self.target_dpi = target_dpi
        self.min_resolution = min_resolution
    
    def load_image_from_url(self, image_bytes: bytes) -> np.ndarray:
        """Load image from bytes"""
        try:
            # Check if bytes look like HTML (error page)
            if image_bytes.startswith(b'<!DOCTYPE') or image_bytes.startswith(b'<html'):
                raise ValueError("Downloaded content is HTML, not an image file. Check if URL is accessible.")
            
            # Check if it's a valid image format
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        except ValueError as e:
            logger.error(f"Error loading image: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            logger.error(f"First 100 bytes: {image_bytes[:100]}")
            raise ValueError(f"Failed to load image: {e}")
    
    def check_resolution(self, image: np.ndarray) -> Tuple[int, int]:
        """Check image resolution"""
        height, width = image.shape[:2]
        return width, height
    
    def upscale_image(self, image: np.ndarray, target_width: int = None) -> np.ndarray:
        """Upscale low-resolution images using deterministic interpolation"""
        height, width = image.shape[:2]
        
        if target_width is None:
            target_width = max(self.min_resolution, width)
        
        if width < self.min_resolution:
            scale = target_width / width
            new_height = int(height * scale)
            upscaled = cv2.resize(image, (target_width, new_height), 
                                 interpolation=cv2.INTER_LINEAR)
            logger.info(f"Upscaled image from {width}x{height} to {target_width}x{new_height}")
            return upscaled
        
        return image
    
    def deskew_image(self, image: np.ndarray) -> np.ndarray:
        """Deskew tilted document images with deterministic approach"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
            
            if lines is not None and len(lines) > 0:
                angles = []
                for line in lines:
                    theta = line[0][1]
                    angle_deg = np.degrees(theta) - 90
                    if angle_deg > 45:
                        angle_deg -= 180
                    elif angle_deg < -45:
                        angle_deg += 180
                    angles.append(angle_deg)
                
                angle = np.median(angles)
                
                if abs(angle) > 1 and abs(angle) <= 45:
                    height, width = image.shape[:2]
                    center = (width // 2, height // 2)
                    
                    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                    
                    deskewed = cv2.warpAffine(
                        image, rotation_matrix, (width, height),
                        borderMode=cv2.BORDER_REFLECT_101,
                        flags=cv2.INTER_LINEAR
                    )
                    logger.info(f"Deskewed image by {angle:.2f} degrees")
                    return deskewed
        except Exception as e:
            logger.warning(f"Deskewing failed: {e}. Returning original image.")
        
        return image
    
    def binarize_image(self, image: np.ndarray) -> np.ndarray:
        """Convert to grayscale and apply binarization to remove background artifacts"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            binary = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            
            denoised = cv2.medianBlur(binary, 3)
            
            logger.info("Applied binarization and denoising")
            return denoised
        except Exception as e:
            logger.warning(f"Binarization failed: {e}. Returning original image.")
            return image
    
    def sharpen_image(self, image: np.ndarray) -> np.ndarray:
        """Apply sharpening filter to enhance text clarity"""
        try:
            kernel = np.array([[-1, -1, -1],
                              [-1,  9, -1],
                              [-1, -1, -1]])
            sharpened = cv2.filter2D(image, -1, kernel)
            logger.info("Applied sharpening filter")
            return sharpened
        except Exception as e:
            logger.warning(f"Sharpening failed: {e}. Returning original image.")
            return image
    
    def process_document(self, image_bytes: bytes, skip_deskew: bool = False) -> np.ndarray:
        """
        Optimized preprocessing pipeline for document images
        
        Steps:
        1. Load image from bytes
        2. Check and upscale resolution if needed
        3. (Optional) Deskew tilted documents - skip for faster processing
        4. Apply sharpening
        
        Args:
            image_bytes: Image data
            skip_deskew: If True, skip deskewing for faster processing (LLM handles slight tilts well)
        
        Returns: Processed image (still in BGR for LLM)
        """
        try:
            image = self.load_image_from_url(image_bytes)
            logger.info(f"Loaded image with shape {image.shape}")
            
            width, height = self.check_resolution(image)
            if width < self.min_resolution or height < self.min_resolution:
                image = self.upscale_image(image)
            
            # Skip deskewing for faster processing - Gemini handles slight tilts well
            if not skip_deskew:
                image = self.deskew_image(image)
            
            image = self.sharpen_image(image)
            
            logger.info("Document preprocessing completed successfully")
            return image
            
        except Exception as e:
            logger.error(f"Error in document processing pipeline: {e}")
            raise
    
    @staticmethod
    def image_to_bytes(image: np.ndarray, format: str = 'jpeg', quality: int = 90) -> bytes:
        """Convert OpenCV image to bytes (JPEG for faster processing)"""
        if format.lower() == 'jpeg':
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        else:
            _, buffer = cv2.imencode('.png', image)
        return buffer.tobytes()
    
    @staticmethod
    def image_to_base64(image: np.ndarray) -> str:
        """Convert OpenCV image to base64 string"""
        import base64
        image_bytes = ImageProcessor.image_to_bytes(image)
        return base64.b64encode(image_bytes).decode('utf-8')
