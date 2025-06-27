import os
import time
import logging
from pathlib import Path
from datetime import datetime
import cv2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RTSP_URL = os.getenv("RTSP_URL", "rtsp://admin:password@192.168.1.100:554/stream")
SNAPSHOT_INTERVAL = int(os.getenv("SNAPSHOT_INTERVAL", "5"))
MAX_SNAPSHOTS = int(os.getenv("MAX_SNAPSHOTS", "100"))
RANDOMNESS_SOURCE = Path("/randomness-source")

class SnapshotCapture:
    def __init__(self):
        self.rtsp_url = RTSP_URL
        self.interval = SNAPSHOT_INTERVAL
        self.max_snapshots = MAX_SNAPSHOTS
        self.output_dir = RANDOMNESS_SOURCE
        self.cap = None
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def initialize_camera(self):
        """Initialize camera connection."""
        try:
            logger.info(f"Connecting to RTSP stream: {self.rtsp_url}")
            self.cap = cv2.VideoCapture(self.rtsp_url)
            
            # Set buffer size to reduce latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not self.cap.isOpened():
                raise Exception("Failed to open RTSP stream")
                
            logger.info("Successfully connected to RTSP stream")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            return False
    
    def capture_frame(self) -> bool:
        """Capture a single frame and save it."""
        try:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Failed to read frame from stream")
                return False
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"snapshot_{timestamp}.jpg"
            filepath = self.output_dir / filename
            
            # Save frame as JPEG
            success = cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            if success:
                logger.info(f"Captured snapshot: {filename}")
                return True
            else:
                logger.error("Failed to save snapshot")
                return False
                
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return False
    
    def cleanup_old_snapshots(self):
        """Remove oldest snapshots if we exceed max_snapshots."""
        try:
            snapshots = list(self.output_dir.glob("snapshot_*.jpg"))
            
            if len(snapshots) > self.max_snapshots:
                # Sort by modification time (oldest first)
                snapshots.sort(key=lambda x: x.stat().st_mtime)
                
                # Remove oldest files
                files_to_remove = len(snapshots) - self.max_snapshots
                for i in range(files_to_remove):
                    snapshots[i].unlink()
                    logger.info(f"Removed old snapshot: {snapshots[i].name}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up snapshots: {e}")
    
    def run(self):
        """Main capture loop."""
        logger.info("Starting snapshot capture service")
        logger.info(f"RTSP URL: {self.rtsp_url}")
        logger.info(f"Capture interval: {self.interval} seconds")
        logger.info(f"Max snapshots: {self.max_snapshots}")
        logger.info(f"Output directory: {self.output_dir}")
        
        while True:
            try:
                if not self.initialize_camera():
                    logger.error("Failed to initialize camera, retrying in 30 seconds...")
                    time.sleep(30)
                    continue
                    
                while True:
                    # Capture frame
                    if not self.capture_frame():
                        logger.warning("Failed to capture frame, reconnecting...")
                        break
                    
                    # Clean up old snapshots
                    self.cleanup_old_snapshots()
                    
                    # Wait for next capture
                    time.sleep(self.interval)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(10)
            finally:
                if self.cap:
                    self.cap.release()
                    self.cap = None
        
        logger.info("Snapshot capture service stopped")

def main():
    """Main entry point."""
    if not RTSP_URL or RTSP_URL == "rtsp://admin:password@192.168.1.100:554/stream":
        logger.error("RTSP_URL not configured properly in environment")
        logger.error("Please set RTSP_URL in .env file")
        return
    
    capture = SnapshotCapture()
    capture.run()

if __name__ == "__main__":
    main()