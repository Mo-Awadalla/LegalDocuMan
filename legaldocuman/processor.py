"""Main document processor orchestrating extraction, classification, and organization."""
import json
import logging
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .config import Config
from .extractors import TextExtractor
from .classifiers import DocumentTypeClassifier, DocumentStatusClassifier
from .dates import DateExtractor
from .vendors import VendorExtractor
from .utils import clean_vendor_for_filename, get_unique_filename, setup_directories


class DocumentProcessor:
    """Unified document processing system."""

    def __init__(self, input_folder, error_folder=None, vendor_master_list=None,
                 ocr_backend=None):
        self.cfg = Config.get()
        self.input_folder = input_folder
        self.error_folder = error_folder or os.path.join(input_folder, self.cfg.ERROR_SUBDIR)
        setup_directories(self.error_folder)

        # Initialize components
        self.text_extractor = TextExtractor(ocr_backend=ocr_backend)
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
        self.contract_counters = defaultdict(lambda: defaultdict(int))

    def process_contracts_enhanced(self, create_subfolders=True, naming_format='enhanced'):
        """Process contracts with enhanced organization."""
        if not os.path.exists(self.input_folder):
            logging.error(f"Input folder does not exist: {self.input_folder}")
            return

        for vendor_folder in os.listdir(self.input_folder):
            vendor_path = os.path.join(self.input_folder, vendor_folder)
            if not os.path.isdir(vendor_path) or vendor_folder.startswith(('.', '_')):
                continue

            logging.info(f"Processing vendor folder: {vendor_folder}")
            if create_subfolders:
                self._create_vendor_subfolders(vendor_path, vendor_folder)

            for root, dirs, files in os.walk(vendor_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in self.cfg.SUPPORTED_EXTENSIONS:
                        try:
                            self._process_single_file(
                                file_path, vendor_folder, vendor_path,
                                create_subfolders, naming_format
                            )
                        except Exception as e:
                            logging.error(f"Error processing {file_path}: {e}")
                            self._move_to_error_folder(file_path, str(e))

    def _create_vendor_subfolders(self, vendor_path, vendor_name):
        """Create organized subfolders for vendor."""
        for subfolder in ('_final', '_supporting'):
            subfolder_path = os.path.join(vendor_path, f"{vendor_name}{subfolder}")
            os.makedirs(subfolder_path, exist_ok=True)

    def _process_single_file(self, file_path, folder_name, vendor_base_path,
                             create_subfolders, naming_format):
        """Process a single document file."""
        filename = os.path.basename(file_path)
        logging.info(f"Processing: {filename}")

        text_content = self.text_extractor.extract_text(file_path)
        vendor_name = self.vendor_extractor.extract_vendor_from_folder(folder_name)
        if self.vendor_extractor.vendor_master_list:
            vendor_name, _ = self.vendor_extractor.match_vendor_against_master_list(vendor_name)

        clean_vendor = clean_vendor_for_filename(vendor_name)
        doc_type = self.doc_type_classifier.identify_type(text_content, filename)
        sig_analysis = self.status_classifier.get_signature_analysis(text_content)
        doc_status = self.status_classifier.classify_status(filename, text_content)

        date_str = self.date_extractor.extract_date_from_text(text_content, filename)
        date_metadata = self.date_extractor.extract_dates_with_metadata(text_content)

        if naming_format == 'enhanced':
            unique_id = self._get_unique_id(clean_vendor, doc_type)
            new_filename = self._generate_enhanced_filename(
                clean_vendor, doc_type, filename, date_str, unique_id
            )
        else:
            new_filename = self._generate_simple_filename(clean_vendor, filename, date_str)

        if create_subfolders:
            target_folder = os.path.join(vendor_base_path, f"{folder_name}_{doc_status}")
            os.makedirs(target_folder, exist_ok=True)
        else:
            target_folder = vendor_base_path

        target_path = os.path.join(target_folder, new_filename)
        target_path = self._handle_filename_conflict(target_path)
        shutil.move(file_path, target_path)

        metadata = self._create_metadata(target_path, {
            'original_filename': filename,
            'vendor': vendor_name,
            'clean_vendor': clean_vendor,
            'document_type': doc_type,
            'status': doc_status,
            'date_str': date_str,
            'signature_analysis': sig_analysis,
            'date_metadata': date_metadata,
            'new_filename': new_filename,
        })

        with self.results_lock:
            self.results['successful'].append({
                'original': file_path,
                'new_path': target_path,
                'vendor': clean_vendor,
                'type': doc_type,
                'status': doc_status,
                'metadata': metadata
            })
            self.results['summary'][(clean_vendor, doc_type)] += 1

        self._update_backend_tracking_registry(metadata)

    def _generate_enhanced_filename(self, clean_vendor, doc_type, original_filename, date_str, unique_id):
        """Generate enhanced filename: K_Vendor_type_001.ext"""
        abbreviation = self.cfg.TYPE_ABBREVIATIONS.get(doc_type, 'K')
        type_desc = self.cfg.TYPE_DESCRIPTIONS.get(doc_type, 'document')
        file_ext = os.path.splitext(original_filename)[1]
        return f"{abbreviation}_{clean_vendor}_{type_desc}_{unique_id:03d}{file_ext}"

    def _generate_simple_filename(self, clean_vendor, original_filename, date_str):
        """Generate simple filename: YYYYMMDD_Vendor_OriginalFile.ext"""
        prefix = f"{date_str}_{clean_vendor}_" if date_str else f"{clean_vendor}_"
        return f"{prefix}{original_filename}"

    def _get_unique_id(self, vendor_name, doc_type):
        """Get unique sequential ID."""
        with self.counter_lock:
            self.contract_counters[vendor_name][doc_type] += 1
            return self.contract_counters[vendor_name][doc_type]

    def _handle_filename_conflict(self, target_path):
        """Handle filename conflicts."""
        if not os.path.exists(target_path):
            return target_path
        base_path, ext = os.path.splitext(target_path)
        counter = 1
        while os.path.exists(target_path):
            target_path = f"{base_path}_conflict{counter:02d}{ext}"
            counter += 1
        return target_path

    def _create_metadata(self, file_path, metadata):
        """Create comprehensive metadata JSON file for backend tracking."""
        try:
            metadata_file = f"{os.path.splitext(file_path)[0]}.metadata.json"
            metadata_dir = os.path.dirname(metadata_file)
            if not os.path.exists(metadata_dir):
                os.makedirs(metadata_dir, exist_ok=True)

            file_stat = os.stat(file_path)
            metadata.update({
                'file_created_timestamp': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'file_modified_timestamp': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                'metadata_created_timestamp': datetime.now().isoformat(),
                'metadata_location': metadata_file,
                'tracking_id': f"{metadata.get('vendor', 'unknown')}_{metadata.get('document_type', 'doc')}_{hash(file_path) % 10000:04d}",
                'processing_date': datetime.now().isoformat(),
            })

            retention = self.cfg.get_retention_category(
                metadata.get('document_type', ''),
                metadata.get('date_metadata', {}).get('expiration_date') is not None
            )
            metadata['retention_category'] = retention

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

            logging.info(f"📋 Metadata saved: {metadata_file}")
            return metadata
        except Exception as e:
            logging.error(f"❌ Error creating metadata: {e}")
            return metadata

    def _update_backend_tracking_registry(self, document_metadata):
        """Update centralized registry for backend record tracking."""
        try:
            registry_file = os.path.join(self.input_folder, self.cfg.REGISTRY_FILE_NAME)
            if not os.path.exists(self.input_folder):
                os.makedirs(self.input_folder, exist_ok=True)

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

            registry['last_updated'] = datetime.now().isoformat()
            registry['total_documents'] += 1

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

            retention_cat = document_metadata.get('retention_category', 'unknown')
            registry['retention_categories'][retention_cat] = registry['retention_categories'].get(retention_cat, 0) + 1
            registry['expiration_tracking'].sort(key=lambda x: x.get('expiration_date') or '9999-12-31')

            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False, default=str)

            logging.info(f"📊 Updated backend tracking registry: {registry_file}")
        except Exception as e:
            logging.error(f"❌ Error updating backend tracking registry: {e}")

    def _move_to_error_folder(self, file_path, error_reason):
        """Move problematic files to error folder."""
        try:
            filename = os.path.basename(file_path)
            error_file_path = os.path.join(self.error_folder, filename)
            if os.path.exists(error_file_path):
                error_file_path = self._handle_filename_conflict(error_file_path)
            shutil.move(file_path, error_file_path)
            with open(f"{error_file_path}.error.txt", 'w') as f:
                f.write(f"Error: {error_reason}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            with self.results_lock:
                self.results['errors'].append({
                    'original_path': file_path,
                    'reason': error_reason
                })
        except Exception as e:
            logging.error(f"Error moving file to error folder: {e}")

    def sort_files_by_year(self, pre_2017_dir, year_threshold=None):
        """Sort files by year, archiving old files."""
        year_threshold = year_threshold or self.cfg.YEAR_SORT_THRESHOLD
        if not os.path.exists(self.input_folder):
            logging.error(f"Input folder does not exist: {self.input_folder}")
            return

        os.makedirs(pre_2017_dir, exist_ok=True)
        file_summary = []

        files_to_process = []
        for root, dirs, files in os.walk(self.input_folder):
            for file in files:
                if file.lower().endswith(tuple(self.cfg.SORT_SUPPORTED_EXTENSIONS)):
                    files_to_process.append(os.path.join(root, file))

        logging.info(f"Found {len(files_to_process)} files to process")

        for file_path in files_to_process:
            filename = os.path.basename(file_path)
            relative_path = os.path.relpath(file_path, self.input_folder)
            try:
                text_content = self.text_extractor.extract_text(file_path)
                date_str = self.date_extractor.extract_date_from_text(text_content, filename)
                if not date_str:
                    raise ValueError("No dates found")
                year = int(date_str[:4])
                if year < year_threshold:
                    rel_dir = os.path.dirname(relative_path)
                    dest_dir = os.path.join(pre_2017_dir, rel_dir) if rel_dir else pre_2017_dir
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_path = os.path.join(dest_dir, filename)
                    dest_path = self._handle_filename_conflict(dest_path)
                    shutil.move(file_path, dest_path)
                    file_summary.append({'file': filename, 'year': year,
                                         'action': f'Moved to pre-{year_threshold}',
                                         'new_path': dest_path})
                    logging.info(f"Archived: {filename} (year: {year})")
                else:
                    file_summary.append({'file': filename, 'year': year,
                                         'action': 'Kept in place',
                                         'new_path': file_path})
                    logging.info(f"Kept: {filename} (year: {year})")
            except Exception as e:
                self._move_to_error_folder(file_path, str(e))
                file_summary.append({'file': filename, 'year': 'ERROR',
                                     'action': 'Moved to error folder',
                                     'error': str(e)})

        if file_summary:
            try:
                import pandas as pd
                df = pd.DataFrame(file_summary)
                summary_path = os.path.join(os.path.dirname(self.error_folder), 'file_sorting_summary.xlsx')
                os.makedirs(os.path.dirname(summary_path), exist_ok=True)
                df.to_excel(summary_path, index=False)
                logging.info(f"Summary saved to: {summary_path}")
            except ImportError:
                logging.warning("pandas not installed — skipping Excel summary")

    def print_summary(self):
        """Print processing summary."""
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
                vendor_stats[result['vendor']] += 1
                status = result['status']
                if status == 'final':
                    signature_stats['final_with_sigs'] += 1
                elif status == 'supporting':
                    signature_stats['supporting'] += 1
                else:
                    signature_stats['draft_no_sigs'] += 1
            for vendor, count in sorted(vendor_stats.items(), key=lambda x: -x[1]):
                print(f"  {vendor}: {count} files")
            print(f"\n🖋️  SIGNATURE-BASED CLASSIFICATION RESULTS:")
            print(f"  Final documents (with signatures): {signature_stats['final_with_sigs']}")
            print(f"  Draft documents (no signatures): {signature_stats['draft_no_sigs']}")
            print(f"  Supporting documents: {signature_stats['supporting']}")
            if successful_count > 0:
                sig_percentage = (signature_stats['final_with_sigs'] / successful_count) * 100
                print(f"  Signature detection rate: {sig_percentage:.1f}% of main documents have signatures")
        if error_count > 0:
            print(f"\nError files moved to: {self.error_folder}")
            for i, error in enumerate(self.results['errors'][:5]):
                print(f"  {os.path.basename(error['original_path'])}: {error['reason']}")
            if error_count > 5:
                print(f"  ... and {error_count - 5} more errors")
        print("="*60)

        # Backend tracking summary
        registry_file = os.path.join(self.input_folder, self.cfg.REGISTRY_FILE_NAME)
        if os.path.exists(registry_file):
            try:
                with open(registry_file, 'r', encoding='utf-8') as f:
                    registry = json.load(f)
                print("\n📋 BACKEND TRACKING SUMMARY")
                print("─" * 50)
                print(f"Total documents processed: {registry.get('total_documents', 0)}")
                print(f"Documents with expiration dates: {registry.get('documents_with_expiration', 0)}")
                retention_cats = registry.get('retention_categories', {})
                if retention_cats:
                    print(f"\nRetention categories:")
                    for category, count in retention_cats.items():
                        print(f"  {category}: {count} documents")
                upcoming_expirations = []
                for doc in registry.get('expiration_tracking', []):
                    exp_date_str = doc.get('expiration_date')
                    if exp_date_str:
                        try:
                            exp_date = datetime.fromisoformat(exp_date_str)
                            days_until = (exp_date - datetime.now()).days
                            if 0 <= days_until <= 365:
                                upcoming_expirations.append((exp_date_str, doc.get('vendor', 'Unknown'), doc.get('document_type', 'Unknown')))
                        except ValueError:
                            continue
                if upcoming_expirations:
                    print(f"\n⚠️  EXPIRING WITHIN 12 MONTHS ({len(upcoming_expirations)} documents):")
                    for exp_date, vendor, doc_type in upcoming_expirations[:5]:
                        print(f"  {exp_date} - {vendor} ({doc_type})")
                    if len(upcoming_expirations) > 5:
                        print(f"  ... and {len(upcoming_expirations) - 5} more")
                else:
                    print(f"\n✅ No documents expiring in next 12 months")
                print(f"\n📁 Backend Tracking Files Created:")
                print(f"  Registry: {self.cfg.REGISTRY_FILE_NAME}")
            except Exception as e:
                logging.error(f"Error reading backend tracking registry: {e}")
        else:
            print("\n📋 BACKEND TRACKING SUMMARY")
            print("No expiration tracking data available")
