import os
from datetime import datetime
from typing import Tuple


class ImageStorage:
    def __init__(self, base_dir: str = "generated_images"):
        self.base_dir = base_dir
        self.raw_dir = os.path.join(base_dir, "raw")
        self.overlay_dir = os.path.join(base_dir, "overlay")
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create directories if they don't exist."""
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.overlay_dir, exist_ok=True)
    
    def generate_filenames(self, quote_id: int) -> Tuple[str, str]:
        """Generate unique filenames for raw and overlay images."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_filename = f"quote_{quote_id}_{timestamp}_raw.png"
        overlay_filename = f"quote_{quote_id}_{timestamp}_overlay.png"
        return raw_filename, overlay_filename
    
    def get_full_paths(self, raw_filename: str, overlay_filename: str) -> Tuple[str, str]:
        """Get full paths for the image files."""
        raw_path = os.path.join(self.raw_dir, raw_filename)
        overlay_path = os.path.join(self.overlay_dir, overlay_filename)
        return raw_path, overlay_path
    
    def save_images(self, raw_image_bytes: bytes, overlay_image_bytes: bytes, 
                   raw_filename: str, overlay_filename: str):
        """Save both raw and overlay images to filesystem."""
        raw_path, overlay_path = self.get_full_paths(raw_filename, overlay_filename)
        
        with open(raw_path, 'wb') as f:
            f.write(raw_image_bytes)
        
        with open(overlay_path, 'wb') as f:
            f.write(overlay_image_bytes)