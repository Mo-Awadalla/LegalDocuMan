# Installation Guide

This guide will help you install and set up the Document Processing Suite on your system.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Windows 10/11 (primary), macOS, or Linux
- **Python**: Version 3.8 or higher
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 500MB free space for installation
- **Internet**: Required for downloading dependencies

### Python Installation
If you don't have Python installed:

1. **Download Python** from [python.org](https://www.python.org/downloads/)
2. **Install Python** with "Add to PATH" option checked
3. **Verify installation**:
   ```bash
   python --version
   pip --version
   ```

## 🚀 Quick Installation

### Method 1: Direct Installation

1. **Clone or download** the repository:
   ```bash
   git clone https://github.com/yourusername/DocumentProcessingSuite.git
   cd DocumentProcessingSuite
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python run.py
   ```

### Method 2: Virtual Environment (Recommended)

1. **Create virtual environment**:
   ```bash
   python -m venv document_processor_env
   ```

2. **Activate virtual environment**:
   - **Windows**:
     ```bash
     document_processor_env\Scripts\activate
     ```
   - **macOS/Linux**:
     ```bash
     source document_processor_env/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python run.py
   ```

## 🔧 Advanced Installation

### OCR Support (Optional but Recommended)

For processing scanned documents, install OCR support:

#### Windows
1. **Install Tesseract-OCR**:
   - Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
   - Install to default location: `C:\Program Files\Tesseract-OCR\`

2. **Install Python OCR packages**:
   ```bash
   pip install pytesseract pdf2image Pillow
   ```

#### macOS
1. **Install Tesseract**:
   ```bash
   brew install tesseract
   ```

2. **Install Python packages**:
   ```bash
   pip install pytesseract pdf2image Pillow
   ```

#### Linux (Ubuntu/Debian)
1. **Install Tesseract**:
   ```bash
   sudo apt-get install tesseract-ocr
   ```

2. **Install Python packages**:
   ```bash
   pip install pytesseract pdf2image Pillow
   ```

### Additional Dependencies

For enhanced functionality:

```bash
# For Excel file support
pip install openpyxl

# For advanced PDF processing
pip install PyMuPDF

# For better date parsing
pip install dateparser

# For fuzzy string matching
pip install fuzzywuzzy python-Levenshtein
```

## 🧪 Testing Installation

### Verify Core Installation
```bash
python -c "import document_processor; print('Core modules imported successfully')"
```

### Test Signature Detection
```bash
python test_signature_detection.py
```

### Test GUI
```bash
python run.py
```

## 🛠️ Troubleshooting

### Common Issues

#### Python Not Found
- **Error**: `'python' is not recognized as an internal or external command`
- **Solution**: Add Python to your system PATH or use `py` instead of `python`

#### Permission Errors
- **Error**: `Permission denied` when installing packages
- **Solution**: Run as administrator or use virtual environment

#### OCR Not Working
- **Error**: `TesseractNotFoundError`
- **Solution**: 
  1. Install Tesseract-OCR system package
  2. Update path in `document_processor.py` if needed
  3. Verify installation: `tesseract --version`

#### PDF Processing Errors
- **Error**: `PDF processing failed`
- **Solution**: 
  1. Check if PDF is password-protected
  2. Verify file is not corrupted
  3. Try with different PDF file

#### Memory Issues
- **Error**: `MemoryError` or slow processing
- **Solution**: 
  1. Process smaller batches
  2. Close other applications
  3. Increase system RAM

### Platform-Specific Issues

#### Windows
- **Path issues**: Use forward slashes or raw strings
- **Long paths**: Enable long path support in Windows
- **Antivirus**: May block file operations - add exception

#### macOS
- **Permission issues**: Grant full disk access to Terminal
- **Python version**: Use `python3` instead of `python`
- **Tesseract**: May need to install via Homebrew

#### Linux
- **Dependencies**: Install system packages for PDF processing
- **Permissions**: Ensure write access to target directories
- **Python version**: Use `python3` instead of `python`

## 📁 Configuration

### Default Settings
The application creates configuration files in:
- **Windows**: `%USERPROFILE%/Documents/DocumentProcessorLogs/`
- **macOS**: `~/Documents/DocumentProcessorLogs/`
- **Linux**: `~/Documents/DocumentProcessorLogs/`

### Custom Configuration
Edit `config.json` to customize:
- Default input/output directories
- Processing preferences
- OCR settings
- Logging levels

## 🔄 Updates

### Updating the Application
1. **Backup your data** (if any)
2. **Pull latest changes**:
   ```bash
   git pull origin main
   ```
3. **Update dependencies**:
   ```bash
   pip install -r requirements.txt --upgrade
   ```

### Version Compatibility
- **Python 3.8+**: Fully supported
- **Python 3.7**: May work with some limitations
- **Python 3.6 and below**: Not supported

## 🚨 Uninstallation

### Remove Application
1. **Delete the folder**:
   ```bash
   rm -rf DocumentProcessingSuite
   ```

2. **Remove virtual environment** (if used):
   ```bash
   rm -rf document_processor_env
   ```

3. **Remove configuration** (optional):
   ```bash
   rm -rf ~/Documents/DocumentProcessorLogs
   ```

### Remove Dependencies
```bash
pip uninstall -r requirements.txt
```

## 📞 Support

### Getting Help
- **GitHub Issues**: Report bugs and request features
- **Documentation**: Check README.md and docs/ folder
- **Community**: Join discussions for help

### System Information
When reporting issues, include:
- Operating system and version
- Python version (`python --version`)
- Application version
- Error messages
- Steps to reproduce

## ✅ Installation Checklist

- [ ] Python 3.8+ installed
- [ ] Repository cloned/downloaded
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Application runs (`python run.py`)
- [ ] GUI opens successfully
- [ ] Test signature detection works
- [ ] OCR support installed (optional)
- [ ] Configuration saved
- [ ] Logs directory created

## 🎯 Next Steps

After successful installation:

1. **Read the README** for usage instructions
2. **Try the test suite** to verify functionality
3. **Process sample documents** to get familiar
4. **Configure settings** for your workflow
5. **Set up vendor master lists** (if needed)
6. **Explore backend tracking** features

---

**Need help?** Check the [GitHub Issues](https://github.com/yourusername/DocumentProcessingSuite/issues) or create a new issue with your system information.
