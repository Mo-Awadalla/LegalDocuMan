#!/usr/bin/env python3
"""
Document Processing Suite Launcher v2.1
Refactored with pluggable OCR backends.
"""
import sys
import os
import logging
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Configure logging — now called explicitly, not on import."""
    log_dir = Path.home() / "Documents" / "DocumentProcessorLogs"
    log_dir.mkdir(exist_ok=True, parents=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'document_processor.log'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"📁 Logs saved to: {log_dir}")


try:
    from legaldocuman import DocumentProcessor
    from legaldocuman.backends import NvidiaOCRBackend

    def main():
        setup_logging()
        print("🚀 Starting Document Processing Suite v2.1...")
        print("   OCR backends: tesseract (default) | nvidia")
        print("   Set OCR_BACKEND=nvidia to use NVIDIA OCR")
        print()

        # Example: use NVIDIA OCR if requested
        import os
        if os.environ.get('OCR_BACKEND', '').lower() == 'nvidia':
            ocr = NvidiaOCRBackend()
            if ocr.is_available():
                print("🔧 Using NVIDIA OCR backend")
            else:
                print("⚠️  NVIDIA OCR unavailable — falling back to Tesseract")
                ocr = None
        else:
            ocr = None

        # TODO: replace with your actual input folder
        # processor = DocumentProcessor("/path/to/contracts", ocr_backend=ocr)
        # processor.process_contracts_enhanced()
        # processor.print_summary()

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("\nPlease ensure you have installed all required dependencies:")
    print("pip install -r requirements.txt")
    sys.exit(1)
