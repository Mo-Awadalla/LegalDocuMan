# Document Processing Suite

A unified Python application for intelligent document processing with **advanced signature detection**, contract renaming, and file organization.

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

## 🎯 Key Features

### ✨ **Advanced Signature Detection**
- **Targeted keyword-based approach** - First identifies signature sections, then searches within those areas
- **Comprehensive signature patterns** - Digital, physical, e-signature platforms, legal execution language
- **Smart classification** - Only truly signed documents go to `_final`, everything else to `_supporting`
- **10-50x faster processing** compared to scanning entire documents

### 📄 **Contract Processing**
- **Smart document classification** (MSA, SOW, NDA, Purchase Orders, etc.)
- **Intelligent naming conventions**:
  - Simple: `YYYYMMDD_Vendor_OriginalFile.pdf`
  - Enhanced: `K_AcmeCorp_serviceAgreement_001.pdf`
- **Simplified folder organization** with `_final` (signed only) and `_supporting` (everything else)
- **Vendor name standardization** and master list matching
- **Date extraction** from document content and filenames
- **OCR support** for scanned documents
- **Metadata generation** for contract tracking

### 🗂️ **File Sorter**
- **Intelligent date detection** from document content
- **Archive old files** while preserving folder structure
- **Configurable year thresholds**
- **Excel reporting** of all operations

### ⚙️ **Additional Features**
- **Multi-format support**: PDF, DOCX, DOC, TXT files
- **Error handling** with dedicated error folders
- **Progress tracking** and detailed logging
- **Configuration persistence**
- **Threaded processing** for responsive GUI
- **Backend tracking system** for record management and destruction scheduling
- **Expiration date tracking** in metadata (NOT in filenames)

## 🚀 Quick Start

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/DocumentProcessingSuite.git
   cd DocumentProcessingSuite
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Optional: Install OCR support** (for scanned documents):
   ```bash
   pip install pytesseract pdf2image Pillow
   ```
   
   Then install [Tesseract-OCR](https://github.com/UB-Mannheim/tesseract/wiki) on your system.

### Usage

**Run the GUI application**:
```bash
python run.py
```

**Command line usage**:
```python
from document_processor import process_contracts_enhanced, sort_files_by_year

# Enhanced contract processing
process_contracts_enhanced("C:/path/to/contracts", vendor_master_list=["Vendor1", "Vendor2"])

# Simple contract processing  
process_contracts_simple("C:/path/to/contracts")

# Sort files by year
sort_files_by_year("C:/source", "C:/pre2017_archive")
```

## 📁 Project Structure

```
DocumentProcessingSuite/
├── document_processor.py          # Main processing engine
├── document_processor_gui.py      # Unified GUI application
├── backend_tracking_query.py     # Backend tracking tool
├── test_signature_detection.py   # Test suite
├── utils.py                       # Helper utilities
├── run.py                         # Application launcher
├── requirements.txt               # Dependencies
├── README.md                      # This file
└── docs/                          # Documentation
    └── BACKEND_TRACKING.md        # Backend tracking documentation
```

## 🎯 Document Types Supported

The system automatically detects and classifies:
- **MSA** - Master Service Agreements
- **SOW** - Statements of Work  
- **NDA** - Non-Disclosure Agreements
- **PO** - Purchase Orders
- **AMD** - Amendments
- **LICENSE** - License Agreements
- **CONTRACT** - General Contracts

## 📂 Folder Organization

### Enhanced Mode
Creates organized structure:
```
VendorName/
├── VendorName_final/          # Signed, executed contracts only
└── VendorName_supporting/     # All unsigned documents (drafts, exhibits, etc.)
```

### Naming Conventions
- **Enhanced**: `K_VendorName_documentType_001.pdf`
- **Simple**: `20231201_VendorName_OriginalFile.pdf`

## 🔧 Configuration

The application saves your settings automatically in:
- Windows: `%USERPROFILE%/Documents/DocumentProcessorLogs/config.json`
- Logs saved to: `%USERPROFILE%/Documents/DocumentProcessorLogs/`

## 📊 Backend Tracking System

### Query Backend Tracking Data
```bash
# Show summary of all tracked documents
python backend_tracking_query.py "C:/processed_contracts" --summary

# Show documents expiring in next 6 months  
python backend_tracking_query.py "C:/processed_contracts" --expiring 6

# Generate Excel report for backend processing
python backend_tracking_query.py "C:/processed_contracts" --excel tracking_report.xlsx

# Query by retention category
python backend_tracking_query.py "C:/processed_contracts" --category long_term
```

### Metadata Fields Captured
- `expiration_date` - Contract expiration
- `effective_date` - When contract starts
- `renewal_date` - Auto-renewal dates
- `review_date` - Required review dates
- `retention_category` - For destruction scheduling
- `destruction_review_required` - Boolean flag
- `tracking_id` - Unique identifier for backend

## 🧪 Testing

Run the signature detection test suite:
```bash
python test_signature_detection.py
```

This will test the advanced signature detection system with various document types and signature patterns.

## 🛠️ Troubleshooting

### OCR Not Working
1. Install Tesseract-OCR system package
2. Install Python packages: `pip install pytesseract pdf2image`
3. Update Tesseract path in `document_processor.py` if needed

### PDF Processing Errors
- Some PDFs may be password-protected or corrupted
- Check error folder for problematic files
- OCR fallback will attempt to process scanned documents
- Using pdfplumber for superior text extraction accuracy

### Memory Issues
- Large PDF files may consume significant memory
- Processing is limited to first few pages for performance
- Consider processing in smaller batches

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 Support

- Check the application logs in `%USERPROFILE%/Documents/DocumentProcessorLogs/` for detailed error information
- Create an issue on GitHub for bug reports or feature requests
- See [docs/BACKEND_TRACKING.md](docs/BACKEND_TRACKING.md) for backend tracking documentation

## 🏆 Acknowledgments

- Built with Python and modern GUI frameworks
- Advanced signature detection algorithms
- OCR support via Tesseract
- PDF processing via pdfplumber
- Date parsing via dateparser

---

**Made with ❤️ for intelligent document processing**