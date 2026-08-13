import logging
from datetime import datetime

class SarlaLogger:
    """
    Unified logging for Sarala AI.
    Handles console output with timestamps and severity levels.
    """
    def __init__(self, name="SARLA"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            
            # Simple format: [TIME] [LEVEL] [NAME] MESSAGE
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] %(message)s', 
                                        datefmt='%H:%M:%S')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(f"❌ {msg}")

    def debug(self, msg):
        self.logger.debug(f"🔍 {msg}")

    def warning(self, msg):
        self.logger.warning(f"⚠️ {msg}")

# Global logger instance
logger = SarlaLogger()
