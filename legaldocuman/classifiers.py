"""Document type and status classifiers."""
import logging
import re
from typing import List

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
    """Classify documents as final, supporting, or draft based on signatures and content."""

    def __init__(self):
        cfg = Config.get()
        self.signature_patterns = [
            # Digital/electronic signatures
            r'digitally\s+signed\s+by\s+[A-Za-z\s\.]+',
            r'electronic(?:ally)?\s+signed\s+by\s+[A-Za-z\s\.]+',
            r'/s/\s*[A-Za-z\s\.]+',
            r'signature:\s*[A-Za-z\s\.]+',
            r'signed\s+by:\s*[A-Za-z\s\.]+',
            r'e-?signature:\s*[A-Za-z\s\.]+',
            # Physical signature indicators
            r'signature\s+of\s+[A-Za-z\s\.]+',
            r'authorized\s+signature\s*:?\s*[A-Za-z\s\.]*',
            r'signature\s+page',
            r'signature\s+block',
            r'signatory\s*:?\s*[A-Za-z\s\.]+',
            # Execution language
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
            # Company signature blocks
            r'by:\s*[_\-\s]*\s*name:\s*[A-Za-z\s\.]+\s*title:',
            r'name:\s*[A-Za-z\s\.]+\s*title:\s*[A-Za-z\s\.]+\s*date:',
            r'print\s+name:\s*[A-Za-z\s\.]+',
            r'title:\s*[A-Za-z\s\.]+\s*signature:',
            r'authorized\s+representative:\s*[A-Za-z\s\.]+',
            r'company\s+representative:\s*[A-Za-z\s\.]+',
            # Signature lines and blocks
            r'_+\s*signature',
            r'signature\s*_+',
            r'x\s*_+\s*(?:date|signature)',
            r'by:\s*_+\s*date:\s*_+',
            r'signature\s+line',
            r'please\s+sign\s+here',
            # E-signature platforms
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
            # Mobile signature apps
            r'signed\s+on\s+(?:iphone|android|mobile)',
            r'sent\s+from\s+docusign',
            r'e-signed\s+document',
            r'digitally\s+executed',
            r'electronically\s+executed',
            # Legal terminology
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
        """Classify document status with signature detection as primary indicator."""
        filename_lower = filename.lower()
        content_lower = text_content.lower() if text_content else ""

        signatures_found = self._detect_signatures(content_lower)

        if signatures_found:
            logging.info(f"🖋️  SIGNATURES DETECTED - classifying as FINAL: {signatures_found}")
            return 'final'

        main_contract_indicators = ['agreement', 'contract', 'msa', 'nda', 'license']
        if any(indicator in filename_lower for indicator in main_contract_indicators):
            logging.warning(f"⚠️  Main contract file but NO SIGNATURES FOUND - classifying as SUPPORTING")
            return 'supporting'
        else:
            logging.info(f"📎 Document without signatures - classifying as SUPPORTING")
            return 'supporting'

    def _detect_signatures(self, content):
        """Detect signatures using targeted keyword-based approach."""
        if not content:
            return []

        signature_keywords = [
            'signature', 'signed', 'execute', 'executed', 'witness', 'notary',
            'by:', 'date:', 'title:', 'name:', 'signatory', 'authorized',
            'signature page', 'execution page', 'signature block',
            'in witness whereof', 'parties hereby', 'duly executed',
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

        pattern_categories = {
            'digital_signature': self.signature_patterns[:6],
            'execution_language': self.signature_patterns[8:14],
            'legal_execution': self.signature_patterns[14:21],
            'witness_notary': self.signature_patterns[21:25],
            'signature_blocks': self.signature_patterns[25:31],
            'esignature_platform': self.signature_patterns[31:45],
            'execution_terminology': self.signature_patterns[45:]
        }

        for section in signature_sections:
            for category, patterns in pattern_categories.items():
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

    def get_signature_analysis(self, content):
        """Get detailed signature analysis for debugging."""
        if not content:
            return {
                'has_signatures': False,
                'signature_count': 0,
                'signature_types': [],
                'signatures_found': [],
                'confidence': 'none',
                'is_final': False
            }

        cfg = Config.get()
        signatures = self._detect_signatures(content.lower())

        confidence = 'none'
        if len(signatures) >= cfg.HIGH_CONFIDENCE_SIGNATURE_THRESHOLD:
            confidence = 'high'
        elif len(signatures) >= cfg.MEDIUM_CONFIDENCE_SIGNATURE_THRESHOLD:
            confidence = 'medium'

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
            'signatures_found': signatures[:cfg.MAX_SIGNATURES_LOGGED],
            'confidence': confidence,
            'is_final': len(signatures) > 0
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
