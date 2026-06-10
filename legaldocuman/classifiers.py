"""Document type and status classifiers."""
import logging
import os
import re
from typing import Any, Dict, List, Optional

from .config import Config


class DocumentTypeClassifier:
    """Classify document types (MSA, SOW, NDA, etc.)."""

    def __init__(self):
        self.type_patterns = {
            'MSA': [
                r'(?<!\w)master\s+service\s+agreement(?!\w)',
                r'(?<!\w)msa(?!\w)',
                r'(?<!\w)master\s+agreement(?!\w)'
            ],
            'SOW': [
                r'(?<!\w)statement\s+of\s+work(?!\w)',
                r'(?<!\w)sow(?!\w)',
                r'(?<!\w)work\s+statement(?!\w)'
            ],
            'NDA': [
                r'(?<!\w)non-disclosure\s+agreement(?!\w)',
                r'(?<!\w)nda(?!\w)',
                r'(?<!\w)confidentiality\s+agreement(?!\w)',
                r'(?<!\w)non\s+disclosure(?!\w)'
            ],
            'PO': [
                r'(?<!\w)purchase\s+order(?!\w)',
                r'(?<!\w)p\.o\.(?!\w)',
                r'(?<!\w)po\s+\d+(?!\w)'
            ],
            'AMD': [
                r'(?<!\w)amendment(?!\w)',
                r'(?<!\w)amend(?!\w)',
                r'(?<!\w)modification(?!\w)'
            ],
            'LICENSE': [
                r'(?<!\w)license\s+agreement(?!\w)',
                r'(?<!\w)licensing(?!\w)',
                r'(?<!\w)software\s+license(?!\w)'
            ]
        }

    def identify_type(self, text, filename=""):
        """Identify document type from text and filename."""
        combined_text = f"{filename} {text}".lower()
        filename_lower = filename.lower()

        type_scores = {}
        for doc_type, patterns in self.type_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, combined_text, re.IGNORECASE))
                # Higher weight for filename matches (fixed regex for underscores)
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    score += matches * 3
                else:
                    score += matches
            type_scores[doc_type] = score

        if type_scores and max(type_scores.values()) > 0:
            best_type = max(type_scores, key=type_scores.get)
            logging.info(f"Document classified as {best_type} (score: {type_scores[best_type]})")
            return best_type

        return 'CONTRACT'


class DocumentStatusClassifier:
    """Classify documents as final or supporting based on signatures.

    Detection order:
      1. RF-DETR visual model on the last SIGNATURE_PAGES pages (primary)
      2. Regex patterns on the last SIGNATURE_PAGES pages text (fallback)

    RF-DETR is optional; if the model file is absent the system falls back
    to regex-only, preserving the existing behaviour unchanged.
    """

    def __init__(self):
        cfg = Config.get()
        # Keyed by category so _detect_signatures can iterate directly — no
        # fragile positional slices.  Patterns that match *unfilled* template
        # blanks (underscores, "please sign here", "signature page/block/line")
        # and boilerplate that appears in every unsigned contract template
        # ("in witness whereof") are intentionally excluded to prevent false
        # positives on blank contracts.
        self.signature_patterns = {
            'digital_signature': [
                r'digitally\s+signed\s+by\s+[A-Za-z\s\.]+',
                r'electronic(?:ally)?\s+signed\s+by\s+[A-Za-z\s\.]+',
                r'/s/\s*[A-Za-z\s\.]+',
                r'signature:\s*[A-Za-z\s\.]+',
                r'signed\s+by:\s*[A-Za-z\s\.]+',
                r'e-?signature:\s*[A-Za-z\s\.]+',
                r'signature\s+of\s+[A-Za-z\s\.]+',
                r'authorized\s+signature\s*:?\s*[A-Za-z\s\.]+',
            ],
            'execution_language': [
                r'signatory\s*:?\s*[A-Za-z\s\.]+',
                r'executed\s+(?:on\s+)?(?:this\s+)?\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+[A-Za-z]+',
                r'executed\s+on\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}',
                r'signed\s+(?:on\s+)?(?:this\s+)?\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+[A-Za-z]+',
                r'signed\s+on\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}',
                r'executed\s+(?:as\s+of\s+)?[A-Za-z]+\s+\d{1,2},?\s+\d{4}',
                r'signed\s+(?:as\s+of\s+)?[A-Za-z]+\s+\d{1,2},?\s+\d{4}',
                r'executed\s+and\s+delivered\s+on',
                r'date\s+of\s+execution:\s*\d',
                r'have\s+executed\s+this\s+agreement',
            ],
            'legal_execution': [
                r'duly\s+executed\s+and\s+delivered',
                r'executed\s+in\s+duplicate',
                r'executed\s+in\s+counterparts',
                r'parties\s+have\s+executed\s+this',
                r'binding\s+agreement\s+executed',
            ],
            'witness_notary': [
                r'witness(?:ed)?\s+by\s*:?\s*[A-Za-z\s\.]+',
                r'in\s+the\s+presence\s+of\s*:?\s*[A-Za-z\s\.]+',
                r'notarized\s+by',
                r'notary\s+public',
                r'attested\s+by',
            ],
            'signature_blocks': [
                r'by:\s*[_\-\s]*\s*name:\s*[A-Za-z\s\.]+\s*title:',
                r'name:\s*[A-Za-z\s\.]+\s*title:\s*[A-Za-z\s\.]+\s*date:',
                r'print\s+name:\s*[A-Za-z\s\.]+',
                r'title:\s*[A-Za-z\s\.]+\s*signature:',
                r'authorized\s+representative:\s*[A-Za-z\s\.]+',
                r'company\s+representative:\s*[A-Za-z\s\.]+',
            ],
            'esignature_platform': [
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
                r'signed\s+on\s+(?:iphone|android|mobile)',
                r'sent\s+from\s+docusign',
                r'e-signed\s+document',
                r'digitally\s+executed',
                r'electronically\s+executed',
            ],
            'execution_terminology': [
                r'this\s+agreement\s+(?:is\s+)?(?:fully\s+)?executed',
                r'parties\s+hereby\s+execute',
                r'executed\s+copy',
                r'original\s+signature',
                r'wet\s+signature',
                r'ink\s+signature',
            ],
        }

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

        # Visual signature detector — loaded once, reused for every document
        self.signature_detector = None
        model_path = cfg.RFDETR_MODEL_PATH
        if model_path and os.path.exists(model_path):
            from .backends.rfdetr_signature import RFDETRSignatureBackend
            backend = RFDETRSignatureBackend(
                model_path=model_path,
                detection_threshold=cfg.RFDETR_DETECTION_THRESHOLD,
            )
            if backend.is_available():
                self.signature_detector = backend
            else:
                logging.warning("RF-DETR backend initialised but not available — using regex only")
        else:
            logging.info("RF-DETR model not found — using regex-only signature detection")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render_pdf_pages(self, file_path: str, n_pages: int, dpi: int):
        """Render the last n_pages of a PDF as PIL Images.

        Returns (images, page_offset) where page_offset is the 0-indexed
        page number of images[0] within the document.
        """
        try:
            import pdfplumber
            from pdf2image import convert_from_path

            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)

            first_page = max(1, total_pages - n_pages + 1)  # pdf2image is 1-indexed
            page_offset = first_page - 1                     # callers use 0-indexed

            images = convert_from_path(
                file_path,
                dpi=dpi,
                first_page=first_page,
                last_page=total_pages,
                poppler_path=Config.get().POPLER_PATH,
            )
            return images, page_offset
        except Exception as exc:
            logging.warning(f"PDF page rendering failed for {file_path}: {exc}")
            return [], 0

    def _extract_last_n_pages_text(self, file_path: str, n_pages: int) -> str:
        """Extract text from the last n_pages of a PDF using pdfplumber."""
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(file_path) as pdf:
                total = len(pdf.pages)
                start = max(0, total - n_pages)  # 0-indexed
                for page in pdf.pages[start:]:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
            return text
        except Exception as exc:
            logging.warning(f"Last-{n_pages}-pages text extraction failed for {file_path}: {exc}")
            return ""

    def _detect_signatures_visual(self, file_path: str) -> List[Dict[str, Any]]:
        """Run RF-DETR on the last SIGNATURE_PAGES pages of a PDF."""
        if not self.signature_detector:
            return []
        cfg = Config.get()
        images, page_offset = self._render_pdf_pages(
            file_path, cfg.SIGNATURE_PAGES, cfg.PDF_RENDER_DPI
        )
        if not images:
            return []
        return self.signature_detector.detect(images, page_offset=page_offset)

    def classify_status(self, filename, text_content="", file_path=None):
        """Classify document status. RF-DETR runs first; regex is the fallback."""
        filename_lower = filename.lower()
        is_pdf = file_path and file_path.lower().endswith('.pdf')

        # 1. Visual detection (RF-DETR on last N pages)
        if is_pdf and self.signature_detector:
            cfg = Config.get()
            visual = self._detect_signatures_visual(file_path)
            if len(visual) >= cfg.MIN_VISUAL_SIGNATURES_FOR_FINAL:
                logging.info(f"RF-DETR detected {len(visual)} signature(s) — classifying as FINAL")
                return 'final'
            elif visual:
                logging.info(
                    f"RF-DETR detected {len(visual)} signature(s) — below "
                    f"minimum {cfg.MIN_VISUAL_SIGNATURES_FOR_FINAL}, classifying as SUPPORTING"
                )

        # 2. Regex fallback — restrict to last N pages text when file is available
        if is_pdf:
            search_text = self._extract_last_n_pages_text(file_path, Config.get().SIGNATURE_PAGES)
        else:
            search_text = text_content or ""

        signatures_found = self._detect_signatures(search_text.lower())

        if signatures_found:
            logging.info(f"Regex detected signatures — classifying as FINAL: {signatures_found}")
            return 'final'

        main_contract_indicators = ['agreement', 'contract', 'msa', 'nda', 'license']
        if any(indicator in filename_lower for indicator in main_contract_indicators):
            logging.warning("Main contract file but NO SIGNATURES FOUND — classifying as SUPPORTING")
            return 'supporting'

        logging.info("Document without signatures — classifying as SUPPORTING")
        return 'supporting'

    def _detect_signatures(self, content):
        """Detect signatures using targeted keyword-based approach."""
        if not content:
            return []

        signature_keywords = [
            'signature', 'signed', 'execute', 'executed', 'witness', 'notary',
            'by:', 'date:', 'title:', 'name:', 'signatory', 'authorized',
            'execution page', 'parties hereby', 'duly executed',
            'docusign', 'adobe sign', 'hellosign', 'esign', 'e-sign',
            'digitally signed', 'electronically signed',
            'parties have executed', 'binding agreement executed'
        ]

        signature_sections = []
        for keyword in signature_keywords:
            for match in re.finditer(re.escape(keyword), content, re.IGNORECASE):
                start_pos = max(0, match.start() - Config.get().SIGNATURE_CONTEXT_WINDOW)
                end_pos = min(len(content), match.end() + Config.get().SIGNATURE_CONTEXT_WINDOW)
                section_text = content[start_pos:end_pos]
                signature_sections.append(section_text)

        signatures_found = []
        signature_types = []

        for section in signature_sections:
            for category, patterns in self.signature_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, section, re.IGNORECASE | re.MULTILINE)
                    if matches:
                        signatures_found.extend(matches)
                        signature_types.append(category)

        unique_signatures = []
        seen = set()
        for sig in signatures_found:
            sig_clean = ' '.join(sig.split())
            if sig_clean and sig_clean.lower() not in seen:
                unique_signatures.append(sig_clean)
                seen.add(sig_clean.lower())

        if unique_signatures:
            logging.info(
                f"🎯 Found {len(signature_sections)} signature sections, "
                f"detected {len(unique_signatures)} signatures"
            )

        return unique_signatures

    def get_signature_analysis(self, content, file_path=None) -> Dict[str, Any]:
        """Return detailed signature analysis for a document.

        Detection order:
          1. RF-DETR visual detection on the last SIGNATURE_PAGES pages (PDF only).
          2. Regex on the last SIGNATURE_PAGES pages text (fallback).

        The returned dict is backward-compatible with the existing schema; new
        fields (detections, review_required, detection_source) are additive.
        """
        cfg = Config.get()
        is_pdf = file_path and file_path.lower().endswith('.pdf')

        # --- 1. RF-DETR visual detection ---
        if is_pdf and self.signature_detector:
            visual = self._detect_signatures_visual(file_path)
            if visual:
                high = [d for d in visual if d['confidence'] >= cfg.RFDETR_HIGH_CONFIDENCE_THRESHOLD]
                medium = [d for d in visual if d['confidence'] < cfg.RFDETR_HIGH_CONFIDENCE_THRESHOLD]
                confidence = 'high' if high else 'medium'
                return {
                    'has_signatures': True,
                    'signature_count': len(visual),
                    'signatures_found': [],
                    'detections': visual[:cfg.MAX_SIGNATURES_LOGGED],
                    'confidence': confidence,
                    'review_required': bool(medium) and not bool(high),
                    'is_final': True,
                    'detection_source': 'rfdetr',
                }

        # --- 2. Regex fallback ---
        if is_pdf:
            search_text = self._extract_last_n_pages_text(file_path, cfg.SIGNATURE_PAGES)
        else:
            search_text = content or ""

        if not search_text:
            return {
                'has_signatures': False,
                'signature_count': 0,
                'signatures_found': [],
                'detections': [],
                'confidence': 'none',
                'review_required': False,
                'is_final': False,
                'detection_source': 'none',
            }

        signatures = self._detect_signatures(search_text.lower())

        confidence = 'none'
        if len(signatures) >= cfg.HIGH_CONFIDENCE_SIGNATURE_THRESHOLD:
            confidence = 'high'
        elif len(signatures) >= cfg.MEDIUM_CONFIDENCE_SIGNATURE_THRESHOLD:
            confidence = 'medium'

        high_confidence_patterns = [
            'executed in duplicate',
            'executed this in duplicate',
            'docusign envelope',
            'digitally signed by',
        ]
        if any(p in search_text.lower() for p in high_confidence_patterns):
            confidence = 'high'

        return {
            'has_signatures': bool(signatures),
            'signature_count': len(signatures),
            'signatures_found': signatures[:cfg.MAX_SIGNATURES_LOGGED],
            'detections': [],
            'confidence': confidence,
            'review_required': False,
            'is_final': bool(signatures),
            'detection_source': 'regex' if signatures else 'none',
        }

    def _calculate_score(self, filename, content, keywords_dict):
        """Calculate keyword match score."""
        score = 0
        for keyword in keywords_dict['filename']:
            if keyword in filename:
                score += 3
        if content:
            for keyword in keywords_dict['content']:
                if keyword in content:
                    score += 1
        return score
