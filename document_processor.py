"""
Unified Document Processing System
Combines contract renaming, file sorting, and vendor matching functionality
"""
import os
import re
import shutil
import json
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from difflib import SequenceMatcher
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

# Document processing libraries
import pdfplumber
import docx
import pandas as pd
import dateparser
from dateparser.search import search_dates

# OCR libraries (optional)
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
    # Set Tesseract path (update as needed) - try common locations
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'tesseract'  # If in PATH
    ]
    
    for path in tesseract_paths:
        try:
            pytesseract.pytesseract.tesseract_cmd = path
            break
        except:
            continue
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None
    convert_from_path = None

# Setup logging
def setup_logging():
    # Use Documents folder for logs - no C: drive access needed
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

setup_logging()

# =====================================================================
# UTILITY FUNCTIONS
# =====================================================================

def normalize_vendor_name(name):
    """Normalize vendor name for comparison"""
    if not name:
        return ""
    
    normalized = name.lower()
    
    # Remove common legal suffixes
    suffixes = [
        r'\bllc\b', r'\bl\.l\.c\.\b', r'\binc\b', r'\binc\.\b', r'\bincorporated\b',
        r'\bcorp\b', r'\bcorp\.\b', r'\bcorporation\b', r'\bltd\b', r'\bltd\.\b',
        r'\blimited\b', r'\bco\b', r'\bco\.\b', r'\bcompany\b', r'\bllp\b', r'\bl\.l\.p\.\b',
        r'\bplc\b'
    ]
    
    for suffix in suffixes:
        normalized = re.sub(suffix, '', normalized)
    
    # Remove punctuation and extra whitespace
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def clean_vendor_for_filename(vendor_name):
    """Clean vendor name for use in filename (camelCase style)"""
    if not vendor_name:
        return 'UnknownVendor'
    
    # Remove special characters and spaces
    clean_name = re.sub(r'[^\w\s-]', '', vendor_name)
    # Replace spaces and hyphens with nothing (camelCase style)
    clean_name = re.sub(r'[\s-]+', '', clean_name)
    # Ensure it starts with capital letter
    if clean_name:
        clean_name = clean_name[0].upper() + clean_name[1:]
    return clean_name or 'UnknownVendor'

# =====================================================================
# TEXT EXTRACTION CLASSES
# =====================================================================

class TextExtractor:
    """Extract text from various document formats"""
    
    def __init__(self):
        self.ocr_available = OCR_AVAILABLE
    
    def extract_from_pdf(self, file_path, max_pages=5):
        """Extract text from PDF using pdfplumber with OCR fallback"""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                num_pages = min(len(pdf.pages), max_pages)
                
                for page_num in range(num_pages):
                    try:
                        page = pdf.pages[page_num]
                        page_text = page.extract_text()
                        
                        if page_text and len(page_text.strip()) > 10:
                            text += page_text + "\n"
                    except Exception as e:
                        logging.debug(f"Error extracting from page {page_num}: {e}")
                        continue
                
                # If no meaningful text found, try OCR
                if len(text.strip()) < 50 and self.ocr_available:
                    logging.info(f"Attempting OCR for {os.path.basename(file_path)}")
                    text = self._extract_with_ocr(file_path, max_pages)
                
        except Exception as e:
            logging.error(f"Error processing PDF {file_path}: {e}")
            # If pdfplumber fails, try OCR as fallback
            if self.ocr_available:
                logging.info(f"PDF processing failed, trying OCR for {os.path.basename(file_path)}")
                return self._extract_with_ocr(file_path, max_pages)
            return ""
        
        return text[:5000]  # Limit to first 5000 characters
    
    def _extract_with_ocr(self, file_path, max_pages):
        """Extract text using OCR as fallback"""
        if not self.ocr_available:
            return ""
        
        try:
            # Try different poppler paths - use Documents folder
            poppler_paths = [
                os.path.expanduser(r"~/Documents/poppler-24.08.0/Library/bin"),
                os.path.expanduser(r"~/poppler-24.08.0/Library/bin"),
                None  # Let pdf2image find it automatically
            ]
            
            images = None
            for poppler_path in poppler_paths:
                try:
                    images = convert_from_path(
                        file_path, 
                        poppler_path=poppler_path, 
                        first_page=1, 
                        last_page=min(max_pages, 3)
                    )
                    break
                except Exception:
                    continue
            
            if images is None:
                logging.error("Could not convert PDF to images - check poppler installation")
                return ""
            
            ocr_text = ""
            for img in images:
                try:
                    page_text = pytesseract.image_to_string(img)
                    ocr_text += page_text + "\n"
                except Exception as e:
                    logging.debug(f"OCR error on page: {e}")
                    continue
            
            return ocr_text
        except Exception as e:
            logging.error(f"OCR failed for {file_path}: {e}")
            return ""
    
    def extract_from_docx(self, file_path):
        """Extract text from DOCX files"""
        try:
            doc = docx.Document(file_path)
            text = ""
            
            # Get text from first 10 paragraphs
            for paragraph in doc.paragraphs[:10]:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            
            return text[:3000]  # Limit to first 3000 characters
            
        except Exception as e:
            logging.error(f"Error reading DOCX {file_path}: {e}")
            return ""
    
    def extract_text(self, file_path, max_pages=5):
        """Universal text extraction method"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            return self.extract_from_pdf(file_path, max_pages)
        elif file_ext in ['.docx', '.doc']:
            return self.extract_from_docx(file_path)
        elif file_ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()[:3000]
            except Exception as e:
                logging.error(f"Error reading text file {file_path}: {e}")
                return ""
        else:
            return ""

# =====================================================================
# DOCUMENT CLASSIFICATION CLASSES
# =====================================================================

class DocumentTypeClassifier:
    """Classify document types (MSA, SOW, NDA, etc.)"""
    
    def __init__(self):
        self.type_patterns = {
            'MSA': [
                r'\bmaster\s+service\s+agreement\b',
                r'\bmsa\b',
                r'\bmaster\s+agreement\b'
            ],
            'SOW': [
                r'\bstatement\s+of\s+work\b',
                r'\bsow\b',
                r'\bwork\s+statement\b'
            ],
            'NDA': [
                r'\bnon-disclosure\s+agreement\b',
                r'\bnda\b',
                r'\bconfidentiality\s+agreement\b',
                r'\bnon\s+disclosure\b'
            ],
            'PO': [
                r'\bpurchase\s+order\b',
                r'\bp\.o\.\b',
                r'\bpo\s+\d+\b'
            ],
            'AMD': [
                r'\bamendment\b',
                r'\bamend\b',
                r'\bmodification\b'
            ],
            'LICENSE': [
                r'\blicense\s+agreement\b',
                r'\blicensing\b',
                r'\bsoftware\s+license\b'
            ]
        }
    
    def identify_type(self, text, filename=""):
        """Identify document type from text and filename"""
        # Combine filename and text for analysis
        combined_text = f"{filename} {text}".lower()
        
        # Score each type
        type_scores = {}
        for doc_type, patterns in self.type_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, combined_text, re.IGNORECASE))
                # Give higher weight to filename matches
                if re.search(pattern, filename.lower(), re.IGNORECASE):
                    score += matches * 3
                else:
                    score += matches
            type_scores[doc_type] = score
        
        # Return the type with highest score, or default to 'CONTRACT'
        if type_scores and max(type_scores.values()) > 0:
            best_type = max(type_scores, key=type_scores.get)
            logging.info(f"Document classified as {best_type} (score: {type_scores[best_type]})")
            return best_type
        
        return 'CONTRACT'

class DocumentStatusClassifier:
    """Classify documents as final, supporting, or draft based on signatures and content"""
    
    def __init__(self):
        # Enhanced signature detection patterns (PRIMARY indicator for final vs draft)
        self.signature_patterns = [
            # Digital/electronic signatures (most common)
            r'digitally\s+signed\s+by\s+[A-Za-z\s\.]+',
            r'electronic(?:ally)?\s+signed\s+by\s+[A-Za-z\s\.]+',
            r'/s/\s*[A-Za-z\s\.]+',  # /s/ format like "/s/ John Smith"
            r'signature:\s*[A-Za-z\s\.]+',
            r'signed\s+by:\s*[A-Za-z\s\.]+',
            r'e-?signature:\s*[A-Za-z\s\.]+',
            
            # Physical signature indicators
            r'signature\s+of\s+[A-Za-z\s\.]+',
            r'authorized\s+signature\s*:?\s*[A-Za-z\s\.]*',
            r'signature\s+page',
            r'signature\s+block',
            r'signatory\s*:?\s*[A-Za-z\s\.]+',
            
            # Execution language (strong indicators of final documents)
            r'executed\s+(?:on\s+)?(?:this\s+)?\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+[A-Za-z]+',
            r'executed\s+on\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}',
            r'signed\s+(?:on\s+)?(?:this\s+)?\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+[A-Za-z]+',
            r'signed\s+on\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}',
            r'executed\s+(?:as\s+of\s+)?[A-Za-z]+\s+\d{1,2},?\s+\d{4}',
            r'signed\s+(?:as\s+of\s+)?[A-Za-z]+\s+\d{1,2},?\s+\d{4}',
            r'executed\s+and\s+delivered\s+on',
            r'date\s+of\s+execution:\s*\d',
            
            # Legal execution phrases
            r'in\s+witness\s+whereof',
            r'have\s+executed\s+this\s+agreement',
            r'duly\s+executed\s+and\s+delivered',
            r'executed\s+in\s+duplicate',
            r'executed\s+in\s+counterparts',
            r'parties\s+have\s+executed\s+this',
            r'binding\s+agreement\s+executed',
            
            # Witness signatures  
            r'witness(?:ed)?\s+by\s*:?\s*[A-Za-z\s\.]*',
            r'in\s+the\s+presence\s+of\s*:?\s*[A-Za-z\s\.]*',
            r'notarized\s+by',
            r'notary\s+public',
            r'attested\s+by',
            
            # Company signature blocks (enhanced patterns)
            r'by:\s*[_\-\s]*\s*name:\s*[A-Za-z\s\.]+\s*title:',
            r'name:\s*[A-Za-z\s\.]+\s*title:\s*[A-Za-z\s\.]+\s*date:',
            r'print\s+name:\s*[A-Za-z\s\.]+',
            r'title:\s*[A-Za-z\s\.]+\s*signature:',
            r'authorized\s+representative:\s*[A-Za-z\s\.]+',
            r'company\s+representative:\s*[A-Za-z\s\.]+',
            
            # Signature lines and blocks (more variations)
            r'_+\s*signature',
            r'signature\s*_+',
            r'x\s*_+\s*(?:date|signature)',
            r'by:\s*_+\s*date:\s*_+',
            r'signature\s+line',
            r'please\s+sign\s+here',
            
            # E-signature platforms (comprehensive list)
            r'docusign\s+envelope\s+id',
            r'adobe\s+(?:e)?sign',
            r'hellosign',
            r'signnow',
            r'pandadoc',
            r'echosign',
            r'rightsignature',
            r'signrequest',
            r'signable',
            r'eversign',
            r'signeasily',
            r'onespan\s+sign',
            
            # Mobile signature apps and timestamps
            r'signed\s+on\s+(?:iphone|android|mobile)',
            r'sent\s+from\s+docusign',
            r'e-signed\s+document',
            r'digitally\s+executed',
            r'electronically\s+executed',
            
            # Legal terminology indicating execution
            r'this\s+agreement\s+(?:is\s+)?(?:fully\s+)?executed',
            r'parties\s+hereby\s+execute',
            r'executed\s+copy',
            r'original\s+signature',
            r'wet\s+signature',
            r'ink\s+signature'
        ]
        
        self.draft_keywords = {
            'filename': [
                'draft', 'dft', 'temp', 'temporary', 'working', 'wip', 'review',
                'preliminary', 'version', 'v1', 'v2', 'v3', 'revision', 'rev',
                'redline', 'markup', 'comments', 'tracked', 'changes', 'edit'
            ],
            'content': [
                'draft agreement', 'preliminary version', 'for review only',
                'subject to revision', 'not final', 'working draft',
                'confidential draft', 'review copy', 'draft contract',
                'pending signature', 'awaiting execution', 'unsigned'
            ]
        }
        
        self.supporting_keywords = {
            'filename': [
                'exhibit', 'exh', 'appendix', 'schedule', 'attachment', 'annex',
                'rider', 'supplement', 'addendum', 'enclosure', 'tab', 'sow',
                'statement', 'work', 'order', 'invoice', 'receipt', 'quote',
                'proposal', 'estimate', 'specification', 'spec', 'requirements'
            ],
            'content': [
                'exhibit', 'appendix', 'schedule', 'attachment', 'statement of work',
                'work order', 'purchase order', 'invoice', 'receipt', 'quotation'
            ]
        }
        
        self.final_keywords = {
            'filename': [
                'final', 'executed', 'signed', 'fully', 'complete', 'master',
                'agreement', 'contract', 'msa', 'nda', 'license'
            ],
            'content': [
                'fully executed', 'signed agreement', 'executed contract',
                'final version', 'master service agreement', 'binding agreement'
            ]
        }
    
    def classify_status(self, filename, text_content=""):
        """Classify document status with signature detection as primary indicator"""
        filename_lower = filename.lower()
        content_lower = text_content.lower() if text_content else ""
        
        # PRIORITY 1: Check for signatures (ONLY indicator for FINAL classification)
        signatures_found = self._detect_signatures(content_lower)
        
        if signatures_found:
            logging.info(f"🖋️  SIGNATURES DETECTED - classifying as FINAL: {signatures_found}")
            return 'final'
        
        # PRIORITY 2: NO SIGNATURES = SUPPORTING (simplified classification)
        # All unsigned documents, regardless of type, go to supporting folder
        main_contract_indicators = ['agreement', 'contract', 'msa', 'nda', 'license']
        if any(indicator in filename_lower for indicator in main_contract_indicators):
            logging.warning(f"⚠️  Main contract file but NO SIGNATURES FOUND - classifying as SUPPORTING")
            return 'supporting'  # Changed: No signatures = supporting (not draft)
        else:
            logging.info(f"📎 Document without signatures - classifying as SUPPORTING")
            return 'supporting'
    
    def _detect_signatures(self, content):
        """Detect signatures using targeted keyword-based approach"""
        if not content:
            return []
        
        # Step 1: Define signature section keywords
        signature_keywords = [
            'signature', 'signed', 'execute', 'executed', 'witness', 'notary',
            'by:', 'date:', 'title:', 'name:', 'signatory', 'authorized',
            'signature page', 'execution page', 'signature block',
            'in witness whereof', 'parties hereby', 'duly executed',
            'docusign', 'adobe sign', 'hellosign', 'esign', 'e-sign',
            'digitally signed', 'electronically signed',
            'parties have executed', 'binding agreement executed'
        ]
        
        # Step 2: Find signature-related sections (extract text around keywords)
        signature_sections = []
        
        for keyword in signature_keywords:
            # Find all occurrences of the keyword
            for match in re.finditer(re.escape(keyword), content, re.IGNORECASE):
                start_pos = max(0, match.start() - 200)  # 200 chars before
                end_pos = min(len(content), match.end() + 200)  # 200 chars after
                section_text = content[start_pos:end_pos]
                signature_sections.append(section_text)
        
        # Step 3: Search for signature patterns only within these sections
        signatures_found = []
        signature_types = []
        
        # Define pattern categories for better reporting  
        pattern_categories = {
            'digital_signature': self.signature_patterns[:6],
            'execution_language': self.signature_patterns[8:14], 
            'legal_execution': self.signature_patterns[14:21],
            'witness_notary': self.signature_patterns[21:25],
            'signature_blocks': self.signature_patterns[25:31],
            'esignature_platform': self.signature_patterns[31:45],
            'execution_terminology': self.signature_patterns[45:]
        }
        
        # Search patterns within signature sections only
        for section in signature_sections:
            for category, patterns in pattern_categories.items():
                for pattern in patterns:
                    matches = re.findall(pattern, section, re.IGNORECASE | re.MULTILINE)
                    if matches:
                        signatures_found.extend(matches)
                        signature_types.append(category)
        
        # Remove duplicates while preserving order
        unique_signatures = []
        seen = set()
        for sig in signatures_found:
            # Clean up the signature text
            sig_clean = ' '.join(sig.split())  # Remove extra whitespace
            if sig_clean and sig_clean.lower() not in seen:
                unique_signatures.append(sig_clean)
                seen.add(sig_clean.lower())
        
        if unique_signatures:
            logging.info(f"🎯 Found {len(signature_sections)} signature sections, detected {len(unique_signatures)} signatures")
        
        return unique_signatures
    
    def get_signature_analysis(self, content):
        """Get detailed signature analysis for debugging"""
        if not content:
            return {
                'has_signatures': False,
                'signature_count': 0,
                'signature_types': [],
                'signatures_found': [],
                'confidence': 'none'
            }
        
        signatures = self._detect_signatures(content.lower())
        
        # Analyze signature confidence
        confidence = 'none'
        if len(signatures) >= 3:
            confidence = 'high'
        elif len(signatures) >= 1:
            confidence = 'medium'
        
        # Check for high-confidence patterns
        high_confidence_patterns = [
            'in witness whereof',
            'executed in duplicate',
            'docusign envelope',
            'digitally signed by'
        ]
        
        for pattern in high_confidence_patterns:
            if pattern in content.lower():
                confidence = 'high'
                break
        
        return {
            'has_signatures': len(signatures) > 0,
            'signature_count': len(signatures),
            'signatures_found': signatures[:5],  # Limit to first 5 for logging
            'confidence': confidence,
            'is_final': len(signatures) > 0
        }
    
    def _calculate_score(self, filename, content, keywords_dict):
        """Calculate keyword match score"""
        score = 0
        
        # Filename keywords (higher weight)
        for keyword in keywords_dict['filename']:
            if keyword in filename:
                score += 3
        
        # Content keywords (lower weight)
        if content:
            for keyword in keywords_dict['content']:
                if keyword in content:
                    score += 1
        
        return score

# =====================================================================
# DATE EXTRACTION CLASS
# =====================================================================

class DateExtractor:
    """Extract dates from documents and filenames"""
    
    def __init__(self):
        self.date_patterns = [
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',
            r'\beffective\s+(?:date\s+)?(?:of\s+)?(?:as\s+of\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
            r'\b(20[0-3][0-9]|19[9][0-9])\b'  # Years 1990-2039
        ]
    
    def extract_date_from_text(self, text, filename=None):
        """Extract date using dateparser for better accuracy"""
        candidates = []
        
        # Extract from text content
        if text:
            results = search_dates(text, settings={'PREFER_DAY_OF_MONTH': 'first'})
            if results:
                candidates.extend([dt for _, dt in results])
        
        # Extract from filename
        if filename:
            results = search_dates(filename, settings={'PREFER_DAY_OF_MONTH': 'first'})
            if results:
                candidates.extend([dt for _, dt in results])
        
        # Filter and find best date
        candidates = [dt.replace(tzinfo=None) if dt.tzinfo else dt for dt in candidates]
        candidates = [dt for dt in candidates if 1990 <= dt.year <= 2035]
        
        if candidates:
            # Use the most recent date found
            best_date = max(candidates)
            return best_date.strftime('%Y%m%d')
        
        return None
    
    def extract_dates_with_metadata(self, text):
        """Extract dates with additional metadata (expiration, effective, etc.) for backend record keeping"""
        metadata = {
            'effective_date': None,
            'expiration_date': None,
            'signature_date': None,
            'renewal_date': None,
            'termination_date': None,
            'review_date': None
        }
        
        # Enhanced patterns for effective dates
        effective_patterns = [
            r'effective\s+(?:date\s+)?(?:of\s+)?(?:as\s+of\s+)?([^\.;\n]+)',
            r'commencing\s+(?:on\s+)?([^\.;\n]+)',
            r'beginning\s+(?:on\s+)?([^\.;\n]+)',
            r'starts?\s+(?:on\s+)?([^\.;\n]+)',
            r'in\s+effect\s+(?:as\s+of\s+)?([^\.;\n]+)'
        ]
        
        # Enhanced patterns for expiration dates (CRITICAL for backend tracking)
        expiration_patterns = [
            r'expir(?:es|ation)\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'terminat(?:es|ion)\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'end(?:s|ing)\s+(?:on\s+)?([^\.;\n]+)',
            r'shall\s+(?:expire|terminate)\s+(?:on\s+)?([^\.;\n]+)',
            r'valid\s+(?:through|until)\s+([^\.;\n]+)',
            r'term\s+(?:expires|ends)\s+(?:on\s+)?([^\.;\n]+)',
            r'contract\s+(?:expires|terminates)\s+(?:on\s+)?([^\.;\n]+)',
            r'agreement\s+(?:expires|terminates)\s+(?:on\s+)?([^\.;\n]+)',
            r'this\s+agreement\s+shall\s+remain\s+in\s+effect\s+until\s+([^\.;\n]+)'
        ]
        
        # Patterns for renewal dates
        renewal_patterns = [
            r'renew(?:al|s)?\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'automatically\s+renew(?:s|ed)?\s+(?:on\s+)?([^\.;\n]+)',
            r'renewal\s+period\s+(?:begins|starts)\s+([^\.;\n]+)'
        ]
        
        # Patterns for review dates  
        review_patterns = [
            r'review\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'shall\s+be\s+reviewed\s+(?:on\s+)?([^\.;\n]+)',
            r'subject\s+to\s+review\s+(?:on\s+)?([^\.;\n]+)'
        ]
        
        # Extract effective dates
        for pattern in effective_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:3]:  # Check first 3 matches
                parsed_date = dateparser.parse(match.strip())
                if parsed_date and 1990 <= parsed_date.year <= 2040:
                    metadata['effective_date'] = parsed_date.strftime('%Y-%m-%d')
                    logging.info(f"Found effective date: {metadata['effective_date']}")
                    break
            if metadata['effective_date']:
                break
        
        # Extract expiration dates (PRIORITY for backend tracking)
        for pattern in expiration_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:3]:  # Check first 3 matches
                parsed_date = dateparser.parse(match.strip())
                if parsed_date and 1990 <= parsed_date.year <= 2040:
                    metadata['expiration_date'] = parsed_date.strftime('%Y-%m-%d')
                    logging.info(f"🗓️  EXPIRATION DATE FOUND for backend tracking: {metadata['expiration_date']}")
                    break
            if metadata['expiration_date']:
                break
        
        # Extract renewal dates
        for pattern in renewal_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:2]:
                parsed_date = dateparser.parse(match.strip())
                if parsed_date and 1990 <= parsed_date.year <= 2040:
                    metadata['renewal_date'] = parsed_date.strftime('%Y-%m-%d')
                    logging.info(f"Found renewal date: {metadata['renewal_date']}")
                    break
            if metadata['renewal_date']:
                break
        
        # Extract review dates
        for pattern in review_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:2]:
                parsed_date = dateparser.parse(match.strip())
                if parsed_date and 1990 <= parsed_date.year <= 2040:
                    metadata['review_date'] = parsed_date.strftime('%Y-%m-%d')
                    logging.info(f"Found review date: {metadata['review_date']}")
                    break
            if metadata['review_date']:
                break
        
        # Log summary for backend tracking
        dates_found = [k for k, v in metadata.items() if v is not None]
        if dates_found:
            logging.info(f"📋 Backend tracking dates captured: {', '.join(dates_found)}")
        else:
            logging.warning("⚠️  No dates found for backend tracking")
        
        return metadata

# =====================================================================
# VENDOR EXTRACTION CLASS
# =====================================================================

class VendorExtractor:
    """Extract and normalize vendor names"""
    
    def __init__(self, vendor_master_list=None):
        self.vendor_master_list = vendor_master_list or []
    
    def extract_vendor_from_folder(self, folder_name):
        """Extract vendor name from folder name"""
        if not folder_name:
            return None
        
        folder_lower = folder_name.lower().strip()
        
        # Skip generic folders
        generic_folders = [
            'contracts', 'agreements', 'documents', 'files', 'scans', 'pdfs',
            'archive', 'backup', 'temp', 'old', 'new', 'draft', 'final'
        ]
        
        if folder_lower in generic_folders:
            return None
        
        # Remove common suffixes
        suffixes = [
            'contract', 'contracts', 'agreement', 'agreements', 'folder', 'folders',
            'documents', 'docs', 'files', 'archive', 'backup'
        ]
        
        words = re.split(r'[\s_-]+', folder_lower)
        vendor_words = [word for word in words if word not in suffixes and word.strip()]
        
        if vendor_words:
            vendor_name = ' '.join(vendor_words)
            logging.info(f"Extracted vendor '{vendor_name}' from folder '{folder_name}'")
            return vendor_name
        
        return folder_name
    
    def match_vendor_against_master_list(self, vendor_name, threshold=80):
        """Match vendor against master list using fuzzy matching"""
        if not vendor_name or not self.vendor_master_list:
            return vendor_name, 0
        
        normalized_vendor = normalize_vendor_name(vendor_name)
        best_match = vendor_name
        best_score = 0
        
        for master_vendor in self.vendor_master_list:
            normalized_master = normalize_vendor_name(master_vendor)
            score = SequenceMatcher(None, normalized_vendor, normalized_master).ratio() * 100
            
            if normalized_vendor == normalized_master:
                return master_vendor, 100
            
            if score > best_score and score >= threshold:
                best_match = master_vendor
                best_score = score
        
        return best_match, best_score

# =====================================================================
# MAIN DOCUMENT PROCESSOR CLASS
# =====================================================================

class DocumentProcessor:
    """Unified document processing system"""
    
    def __init__(self, input_folder, error_folder=None, vendor_master_list=None):
        self.input_folder = input_folder
        self.error_folder = error_folder or os.path.join(input_folder, '_errors')
        
        # Create error folder
        os.makedirs(self.error_folder, exist_ok=True)
        
        # Initialize components
        self.text_extractor = TextExtractor()
        self.date_extractor = DateExtractor()
        self.doc_type_classifier = DocumentTypeClassifier()
        self.status_classifier = DocumentStatusClassifier()
        self.vendor_extractor = VendorExtractor(vendor_master_list)
        
        # Processing results
        self.results = {
            'successful': [],
            'errors': [],
            'summary': defaultdict(int)
        }
        
        # Thread safety
        self.results_lock = Lock()
        self.counter_lock = Lock()
        
        # Contract counters per vendor
        self.contract_counters = defaultdict(lambda: defaultdict(int))
        
        # Document type abbreviations
        self.type_abbreviations = {
            'MSA': 'AGMT', 'SOW': 'AGMT', 'NDA': 'AGMT', 'PO': 'K',
            'AMD': 'AMD', 'LICENSE': 'K', 'CONTRACT': 'K', 'AGREEMENT': 'AGMT'
        }
        
        # Type descriptions for filenames
        self.type_descriptions = {
            'MSA': 'masterServiceAgreement', 'SOW': 'statementOfWork',
            'NDA': 'nonDisclosureAgreement', 'PO': 'purchaseOrder',
            'AMD': 'amendment', 'LICENSE': 'licenseAgreement',
            'CONTRACT': 'serviceAgreement', 'AGREEMENT': 'serviceAgreement'
        }
    
    def process_contracts_enhanced(self, create_subfolders=True, naming_format='enhanced'):
        """
        Process contracts with enhanced organization
        
        Args:
            create_subfolders: Create _final, _supporting subfolders
            naming_format: 'enhanced' (K_Vendor_type_001) or 'simple' (YYYYMMDD_Vendor_file)
        """
        if not os.path.exists(self.input_folder):
            logging.error(f"Input folder does not exist: {self.input_folder}")
            return
        
        supported_extensions = ['.pdf', '.docx', '.doc', '.txt']
        
        # Process vendor folders
        for vendor_folder in os.listdir(self.input_folder):
            vendor_path = os.path.join(self.input_folder, vendor_folder)
            
            if not os.path.isdir(vendor_path) or vendor_folder.startswith('.') or vendor_folder.startswith('_'):
                continue
            
            logging.info(f"Processing vendor folder: {vendor_folder}")
            
            # Create subfolders if requested
            if create_subfolders:
                self._create_vendor_subfolders(vendor_path, vendor_folder)
            
            # Process all files
            for root, dirs, files in os.walk(vendor_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    
                    if file_ext in supported_extensions:
                        try:
                            self._process_single_file(
                                file_path, vendor_folder, vendor_path,
                                create_subfolders, naming_format
                            )
                        except Exception as e:
                            logging.error(f"Error processing {file_path}: {e}")
                            self._move_to_error_folder(file_path, str(e))
    
    def _create_vendor_subfolders(self, vendor_path, vendor_name):
        """Create organized subfolders for vendor"""
        # Only create _final and _supporting folders (simplified structure)
        subfolders = ['_final', '_supporting']
        for subfolder in subfolders:
            subfolder_path = os.path.join(vendor_path, f"{vendor_name}{subfolder}")
            os.makedirs(subfolder_path, exist_ok=True)
    
    def _process_single_file(self, file_path, folder_name, vendor_base_path, create_subfolders, naming_format):
        """Process a single document file"""
        filename = os.path.basename(file_path)
        logging.info(f"Processing: {filename}")
        
        # Extract text content
        text_content = self.text_extractor.extract_text(file_path)
        
        # Extract vendor name from folder
        vendor_name = self.vendor_extractor.extract_vendor_from_folder(folder_name)
        if self.vendor_extractor.vendor_master_list:
            vendor_name, score = self.vendor_extractor.match_vendor_against_master_list(vendor_name)
        
        # Clean vendor name for filename use
        clean_vendor = clean_vendor_for_filename(vendor_name)
        
        # Classify document
        doc_type = self.doc_type_classifier.identify_type(text_content, filename)
        
        # Get detailed signature analysis for logging
        sig_analysis = self.status_classifier.get_signature_analysis(text_content)
        if sig_analysis['has_signatures']:
            logging.info(f"🖋️  Signature Analysis - Count: {sig_analysis['signature_count']}, Confidence: {sig_analysis['confidence']}")
            logging.info(f"   Signatures found: {sig_analysis['signatures_found']}")
        else:
            logging.info(f"❌ No signatures detected in document content")
        
        doc_status = self.status_classifier.classify_status(filename, text_content)
        
        # Extract dates
        date_str = self.date_extractor.extract_date_from_text(text_content, filename)
        date_metadata = self.date_extractor.extract_dates_with_metadata(text_content)
        
        # Generate new filename
        if naming_format == 'enhanced':
            unique_id = self._get_unique_id(clean_vendor, doc_type)
            new_filename = self._generate_enhanced_filename(
                clean_vendor, doc_type, filename, date_str, unique_id
            )
        else:
            unique_id = None
            new_filename = self._generate_simple_filename(
                clean_vendor, filename, date_str
            )
        
        # Determine target location
        if create_subfolders:
            target_folder = os.path.join(vendor_base_path, f"{folder_name}_{doc_status}")
            os.makedirs(target_folder, exist_ok=True)
        else:
            target_folder = vendor_base_path
        
        target_path = os.path.join(target_folder, new_filename)
        
        # Handle filename conflicts
        target_path = self._handle_filename_conflict(target_path)
        
        # Move and rename file
        shutil.move(file_path, target_path)
        
        # Create comprehensive metadata for ALL documents (for backend tracking)
        self._create_metadata(target_path, {
            'original_filename': filename,
            'original_path': file_path,
            'new_filename': os.path.basename(target_path),
            'new_path': target_path,
            'vendor': clean_vendor,
            'folder_source': folder_name,
            'document_type': doc_type,
            'document_status': doc_status,
            'processing_date': datetime.now().isoformat(),
            'file_size_bytes': os.path.getsize(target_path),
            'file_extension': os.path.splitext(target_path)[1].lower(),
            'unique_id': unique_id if naming_format == 'enhanced' else None,
            'naming_format_used': naming_format,
            'created_subfolders': create_subfolders,
            # Date metadata for backend record keeping (expiration tracking)
            **date_metadata,
            # Backend tracking fields for record destruction
            'requires_retention_review': date_metadata.get('expiration_date') is not None,
            'backend_notes': f"Expiration tracking: {'Yes' if date_metadata.get('expiration_date') else 'No'}"
        })
        
        # Record results
        with self.results_lock:
            self.results['successful'].append({
                'original_path': file_path,
                'new_path': target_path,
                'vendor': vendor_name,
                'doc_type': doc_type,
                'doc_status': doc_status,
                'filename': new_filename,
                'has_signatures': sig_analysis['has_signatures'],
                'signature_count': sig_analysis['signature_count'],
                'signature_confidence': sig_analysis['confidence']
            })
            self.results['summary'][f'{vendor_name}_{doc_type}'] += 1
        
        logging.info(f"Successfully processed: {filename} -> {new_filename}")
    
    def _generate_enhanced_filename(self, clean_vendor, doc_type, original_filename, date_str, unique_id):
        """Generate enhanced filename: K_Vendor_type_001.ext"""
        abbreviation = self.type_abbreviations.get(doc_type, 'K')
        type_desc = self.type_descriptions.get(doc_type, 'document')
        
        file_ext = os.path.splitext(original_filename)[1]
        return f"{abbreviation}_{clean_vendor}_{type_desc}_{unique_id:03d}{file_ext}"
    
    def _generate_simple_filename(self, clean_vendor, original_filename, date_str):
        """Generate simple filename: YYYYMMDD_Vendor_OriginalFile.ext"""
        if date_str:
            prefix = f"{date_str}_{clean_vendor}_"
        else:
            prefix = f"{clean_vendor}_"
        
        return f"{prefix}{original_filename}"
    
    def _get_unique_id(self, vendor_name, doc_type):
        """Get unique sequential ID"""
        with self.counter_lock:
            self.contract_counters[vendor_name][doc_type] += 1
            return self.contract_counters[vendor_name][doc_type]
    
    def _handle_filename_conflict(self, target_path):
        """Handle filename conflicts"""
        if not os.path.exists(target_path):
            return target_path
        
        base_path, ext = os.path.splitext(target_path)
        counter = 1
        
        while os.path.exists(target_path):
            target_path = f"{base_path}_conflict{counter:02d}{ext}"
            counter += 1
        
        return target_path
    
    def _create_metadata(self, file_path, metadata):
        """Create comprehensive metadata JSON file for backend tracking"""
        try:
            # Metadata file goes right next to the document (same folder)
            metadata_file = f"{os.path.splitext(file_path)[0]}.metadata.json"
            
            # Ensure the directory exists and is writable
            metadata_dir = os.path.dirname(metadata_file)
            if not os.path.exists(metadata_dir):
                os.makedirs(metadata_dir, exist_ok=True)
                logging.info(f"📁 Created metadata directory: {metadata_dir}")
            
            # Add file timestamps for backend tracking
            file_stat = os.stat(file_path)
            metadata.update({
                'file_created_timestamp': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'file_modified_timestamp': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                'metadata_created_timestamp': datetime.now().isoformat(),
                'metadata_location': metadata_file,
                # Backend tracking identifiers
                'tracking_id': f"{metadata.get('vendor', 'unknown')}_{metadata.get('document_type', 'doc')}_{hash(file_path) % 10000:04d}",
                'destruction_review_required': metadata.get('expiration_date') is not None,
                'last_reviewed': None,  # For backend to update
                'destruction_scheduled': None,  # For backend to update
                'retention_category': self._determine_retention_category(metadata)
            })
            
            # Write metadata file in the same folder as the document
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
            
            logging.info(f"✅ Created metadata: {metadata_file}")
            
            # Update centralized tracking for backend
            self._update_backend_tracking_registry(metadata)
            
        except PermissionError as e:
            logging.error(f"❌ Permission denied creating metadata for {file_path}: {e}")
            logging.error(f"   Try running as administrator or check folder permissions")
        except Exception as e:
            logging.error(f"❌ Error creating metadata for {file_path}: {e}")
            logging.error(f"   Attempted location: {metadata_file if 'metadata_file' in locals() else 'unknown'}")
    
    def _determine_retention_category(self, metadata):
        """Determine retention category for backend record management"""
        doc_type = metadata.get('document_type', '').upper()
        has_expiration = metadata.get('expiration_date') is not None
        
        # Categorize for retention purposes
        if doc_type in ['MSA', 'CONTRACT', 'AGREEMENT']:
            return 'long_term' if has_expiration else 'indefinite'
        elif doc_type in ['NDA', 'LICENSE']:
            return 'indefinite'
        elif doc_type in ['PO', 'INVOICE']:
            return 'short_term'
        elif doc_type == 'AMD':
            return 'tied_to_parent'
        else:
            return 'review_required'
    
    def _update_backend_tracking_registry(self, document_metadata):
        """Update centralized registry for backend record tracking"""
        try:
            # Save registry in input folder
            registry_file = os.path.join(self.input_folder, '_backend_tracking_registry.json')
            
            # Ensure the input folder is accessible
            if not os.path.exists(self.input_folder):
                os.makedirs(self.input_folder, exist_ok=True)
                logging.info(f"📁 Created input directory: {self.input_folder}")
            
            # Load existing registry or create new one
            if os.path.exists(registry_file):
                with open(registry_file, 'r', encoding='utf-8') as f:
                    registry = json.load(f)
            else:
                registry = {
                    'registry_created': datetime.now().isoformat(),
                    'registry_location': registry_file,
                    'last_updated': None,
                    'total_documents': 0,
                    'documents_with_expiration': 0,
                    'retention_categories': {},
                    'expiration_tracking': [],
                    'backend_processing_notes': 'Created for backend - expiration dates in metadata only, NOT in filenames'
                }
                logging.info(f"📋 Created new backend tracking registry: {registry_file}")
            
            # Update registry statistics
            registry['last_updated'] = datetime.now().isoformat()
            registry['total_documents'] += 1
            
            # Track expiration dates
            if document_metadata.get('expiration_date'):
                registry['documents_with_expiration'] += 1
                registry['expiration_tracking'].append({
                    'tracking_id': document_metadata.get('tracking_id'),
                    'vendor': document_metadata.get('vendor'),
                    'document_type': document_metadata.get('document_type'),
                    'filename': document_metadata.get('new_filename'),
                    'file_path': document_metadata.get('new_path'),
                    'expiration_date': document_metadata.get('expiration_date'),
                    'renewal_date': document_metadata.get('renewal_date'),
                    'review_date': document_metadata.get('review_date'),
                    'retention_category': document_metadata.get('retention_category'),
                    'destruction_review_required': True,
                    'processing_date': document_metadata.get('processing_date')
                })
            
            # Track retention categories
            retention_cat = document_metadata.get('retention_category', 'unknown')
            registry['retention_categories'][retention_cat] = registry['retention_categories'].get(retention_cat, 0) + 1
            
            # Sort expiration tracking by date for easy backend review
            registry['expiration_tracking'].sort(key=lambda x: x.get('expiration_date') or '9999-12-31')
            
            # Write updated registry
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False, default=str)
            
            logging.info(f"📊 Updated backend tracking registry: {registry_file}")
            
        except Exception as e:
            logging.error(f"❌ Error updating backend tracking registry: {e}")
    
    def _move_to_error_folder(self, file_path, error_reason):
        """Move problematic files to error folder"""
        try:
            filename = os.path.basename(file_path)
            error_file_path = os.path.join(self.error_folder, filename)
            
            if os.path.exists(error_file_path):
                error_file_path = self._handle_filename_conflict(error_file_path)
            
            shutil.move(file_path, error_file_path)
            
            # Create error log
            with open(f"{error_file_path}.error.txt", 'w') as f:
                f.write(f"Error: {error_reason}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            
            with self.results_lock:
                self.results['errors'].append({
                    'original_path': file_path,
                    'error_path': error_file_path,
                    'reason': error_reason
                })
            
            logging.error(f"Moved to error folder: {filename} - {error_reason}")
        except Exception as e:
            logging.error(f"Failed to move error file: {e}")
    
    def sort_files_by_year(self, pre_2017_dir, year_threshold=2017):
        """Sort files by year, removing old files"""
        if not os.path.exists(self.input_folder):
            logging.error(f"Input folder does not exist: {self.input_folder}")
            return
        
        os.makedirs(pre_2017_dir, exist_ok=True)
        
        file_summary = []
        supported_extensions = ['.pdf', '.docx', '.doc']
        
        # Get all files to process
        files_to_process = []
        for root, dirs, files in os.walk(self.input_folder):
            for file in files:
                if file.lower().endswith(tuple(supported_extensions)):
                    files_to_process.append(os.path.join(root, file))
        
        logging.info(f"Found {len(files_to_process)} files to process")
        
        for file_path in files_to_process:
            filename = os.path.basename(file_path)
            relative_path = os.path.relpath(file_path, self.input_folder)
            
            try:
                # Extract text and determine year
                text_content = self.text_extractor.extract_text(file_path)
                date_str = self.date_extractor.extract_date_from_text(text_content, filename)
                
                if not date_str:
                    raise ValueError("No dates found")
                
                year = int(date_str[:4])
                
                if year < year_threshold:
                    # Move to pre-2017 folder
                    rel_dir = os.path.dirname(relative_path)
                    dest_dir = os.path.join(pre_2017_dir, rel_dir) if rel_dir else pre_2017_dir
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    dest_path = os.path.join(dest_dir, filename)
                    dest_path = self._handle_filename_conflict(dest_path)
                    
                    shutil.move(file_path, dest_path)
                    
                    file_summary.append({
                        'file': filename,
                        'year': year,
                        'action': f'Moved to pre-{year_threshold}',
                        'new_path': dest_path
                    })
                    
                    logging.info(f"Archived: {filename} (year: {year})")
                else:
                    file_summary.append({
                        'file': filename,
                        'year': year,
                        'action': 'Kept in place',
                        'new_path': file_path
                    })
                    
                    logging.info(f"Kept: {filename} (year: {year})")
            
            except Exception as e:
                self._move_to_error_folder(file_path, str(e))
                file_summary.append({
                    'file': filename,
                    'year': 'ERROR',
                    'action': 'Moved to error folder',
                    'error': str(e)
                })
        
        # Save summary
        if file_summary:
            df = pd.DataFrame(file_summary)
            summary_path = os.path.join(os.path.dirname(self.error_folder), 'file_sorting_summary.xlsx')
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            df.to_excel(summary_path, index=False)
            logging.info(f"Summary saved to: {summary_path}")
    
    def print_summary(self):
        """Print processing summary"""
        print("\n" + "="*60)
        print("DOCUMENT PROCESSING SUMMARY")
        print("="*60)
        
        successful_count = len(self.results['successful'])
        error_count = len(self.results['errors'])
        
        print(f"Successfully processed: {successful_count}")
        print(f"Errors: {error_count}")
        print(f"Total files: {successful_count + error_count}")
        
        if self.results['successful']:
            print("\nProcessed by vendor and type:")
            vendor_stats = defaultdict(int)
            signature_stats = {'final_with_sigs': 0, 'draft_no_sigs': 0, 'supporting': 0}
            
            for result in self.results['successful']:
                vendor = result['vendor']
                vendor_stats[vendor] += 1
                
                # Track signature-based classification
                if result.get('doc_status') == 'final' and result.get('has_signatures', False):
                    signature_stats['final_with_sigs'] += 1
                elif result.get('doc_status') == 'draft':
                    signature_stats['draft_no_sigs'] += 1
                elif result.get('doc_status') == 'supporting':
                    signature_stats['supporting'] += 1
            
            for vendor, count in sorted(vendor_stats.items()):
                print(f"  {vendor}: {count} files")
            
            # Show signature detection results
            print(f"\n🖋️  SIGNATURE-BASED CLASSIFICATION RESULTS:")
            print(f"  Final documents (with signatures): {signature_stats['final_with_sigs']}")
            print(f"  Draft documents (no signatures): {signature_stats['draft_no_sigs']}")  
            print(f"  Supporting documents: {signature_stats['supporting']}")
            
            total_main_docs = signature_stats['final_with_sigs'] + signature_stats['draft_no_sigs']
            if total_main_docs > 0:
                sig_percentage = (signature_stats['final_with_sigs'] / total_main_docs) * 100
                print(f"  Signature detection rate: {sig_percentage:.1f}% of main documents have signatures")
        
        if self.results['errors']:
            print(f"\nError files moved to: {self.error_folder}")
            for error in self.results['errors'][:5]:
                print(f"  {os.path.basename(error['original_path'])}: {error['reason']}")
            if error_count > 5:
                print(f"  ... and {error_count - 5} more errors")
        
        # Generate backend tracking summary
        self._generate_backend_tracking_summary()
        print("="*60)
    
    def _generate_backend_tracking_summary(self):
        """Generate summary for backend record tracking and destruction scheduling"""
        try:
            registry_file = os.path.join(self.input_folder, '_backend_tracking_registry.json')
            
            if not os.path.exists(registry_file):
                print("\n📋 BACKEND TRACKING SUMMARY")
                print("No expiration tracking data available")
                return
            
            with open(registry_file, 'r', encoding='utf-8') as f:
                registry = json.load(f)
            
            print("\n📋 BACKEND TRACKING SUMMARY")
            print("─" * 50)
            print(f"Total documents processed: {registry.get('total_documents', 0)}")
            print(f"Documents with expiration dates: {registry.get('documents_with_expiration', 0)}")
            
            # Show retention categories
            retention_cats = registry.get('retention_categories', {})
            if retention_cats:
                print(f"\nRetention categories:")
                for category, count in retention_cats.items():
                    print(f"  {category}: {count} documents")
            
            # Show upcoming expirations (next 12 months)
            expiration_list = registry.get('expiration_tracking', [])
            if expiration_list:
                from datetime import datetime, timedelta
                today = datetime.now()
                next_year = today + timedelta(days=365)
                
                upcoming_expirations = [
                    doc for doc in expiration_list 
                    if doc.get('expiration_date') and 
                    today <= datetime.fromisoformat(doc['expiration_date']) <= next_year
                ]
                
                if upcoming_expirations:
                    print(f"\n⚠️  EXPIRING WITHIN 12 MONTHS ({len(upcoming_expirations)} documents):")
                    for doc in upcoming_expirations[:5]:  # Show first 5
                        exp_date = doc.get('expiration_date', 'Unknown')
                        vendor = doc.get('vendor', 'Unknown')
                        doc_type = doc.get('document_type', 'Unknown')
                        print(f"  {exp_date} - {vendor} ({doc_type})")
                    
                    if len(upcoming_expirations) > 5:
                        print(f"  ... and {len(upcoming_expirations) - 5} more")
                else:
                    print(f"\n✅ No documents expiring in next 12 months")
            
            # Backend tracking files summary
            print(f"\n📁 Backend Tracking Files Created:")
            print(f"  Registry: _backend_tracking_registry.json")
            print(f"  Individual metadata: [filename].metadata.json (for each document)")
            print(f"  Note: Expiration dates are in METADATA only, NOT in filenames")
            
        except Exception as e:
            print(f"\n❌ Error generating backend summary: {e}")

# =====================================================================
# CONVENIENCE FUNCTIONS
# =====================================================================

def process_contracts_simple(input_folder, error_folder=None):
    """Simple contract processing with basic renaming"""
    processor = DocumentProcessor(input_folder, error_folder)
    processor.process_contracts_enhanced(create_subfolders=False, naming_format='simple')
    processor.print_summary()
    return processor

def process_contracts_enhanced(input_folder, error_folder=None, vendor_master_list=None):
    """Enhanced contract processing with full organization"""
    processor = DocumentProcessor(input_folder, error_folder, vendor_master_list)
    processor.process_contracts_enhanced(create_subfolders=True, naming_format='enhanced')
    processor.print_summary()
    return processor

def sort_files_by_year(input_folder, pre_2017_folder, error_folder=None):
    """Sort files by year, moving old files to archive"""
    processor = DocumentProcessor(input_folder, error_folder)
    processor.sort_files_by_year(pre_2017_folder)
    processor.print_summary()
    return processor

if __name__ == "__main__":
    # Example usage
    input_folder = input("Enter input folder path: ").strip()
    
    choice = input("Choose processing type (1=Simple, 2=Enhanced, 3=Sort by year): ").strip()
    
    if choice == "1":
        process_contracts_simple(input_folder)
    elif choice == "2":
        process_contracts_enhanced(input_folder)
    elif choice == "3":
        pre_2017_folder = input("Enter pre-2017 archive folder: ").strip()
        sort_files_by_year(input_folder, pre_2017_folder)
    else:
        print("Invalid choice")
