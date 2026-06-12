"""Generate pseudo-labelled training data for the small LM.

Walks a document corpus, runs the existing intake pipeline on each
document, and emits a JSONL file of {text, doc_type, vendor, confidence}
records.  The fine-tuning script (scripts/finetune_model.py) consumes
this file.

Filtering rules (configurable via flags):

  * --min-doc-type-score  Discard records whose doc-type regex scored
                          below the threshold (default 0).  A score of
                          0 means we accepted a "CONTRACT" default —
                          those rows are kept but flagged in a
                          `is_default` field so the fine-tuner can
                          downweight them.
  * --vendor-source       Only keep rows where the vendor came from one
                          of: text (LM), folder, filename.  Useful for
                          starting the model on text-only signal before
                          adding folder/filename-based noise.
  * --exclude-defaults    Drop the regex-CONTRACT default entirely.

Run:

    python scripts/generate_pseudo_labels.py \\
        --input ./uploads \\
        --output ./models/pseudo_labels.jsonl

The output is JSONL, one record per line, with this shape:

    {
      "text": "focused OCR snippet",
      "doc_type": "MSA",
      "vendor": "Acme Corp",
      "is_default": false,
      "source": "lm"  # or "regex"
    }
"""
import argparse
import json
import logging
import os
import sys
from typing import Iterable, List, Optional

# Ensure the repo root is on the path so we can import the package even
# when this script is run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from legaldocuman.intake import DocumentIntake

SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".txt"}


def iter_documents(input_dir: str) -> Iterable[str]:
    for root, _dirs, files in os.walk(input_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTS:
                yield os.path.join(root, f)


def generate(
    input_dir: str,
    output_path: str,
    use_lm: bool = False,
    exclude_defaults: bool = False,
    vendor_source: str = "any",
) -> int:
    intake = DocumentIntake()
    written = 0
    skipped = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for path in iter_documents(input_dir):
            filename = os.path.basename(path)
            folder = os.path.basename(os.path.dirname(path)) or ""

            try:
                if use_lm:
                    text, _region, _pages = intake.smart_reader.read(path)
                    if not text:
                        skipped += 1
                        continue
                    if intake.small_lm.is_available():
                        lm_result = intake.small_lm.analyze(text)
                        doc_type = (lm_result.get("doc_type") or "").upper().strip()
                        vendor = (lm_result.get("vendor") or "").strip()
                        is_default = not doc_type
                        source = "lm"
                    else:
                        skipped += 1
                        continue
                else:
                    text, _region, _pages = intake.smart_reader.read(path)
                    if not text:
                        skipped += 1
                        continue
                    doc_type = intake.doc_type_classifier.identify_type(text, filename)
                    is_default = doc_type == "CONTRACT"
                    vendor = (
                        intake.vendor_extractor.extract_vendor_from_folder(folder)
                        or intake.vendor_extractor.extract_vendor_from_filename(filename)
                        or ""
                    )
                    source = "regex"

                if not doc_type:
                    skipped += 1
                    continue
                if exclude_defaults and is_default:
                    skipped += 1
                    continue
                if vendor_source != "any" and not vendor:
                    # When filtering by vendor source, skip rows with no vendor.
                    skipped += 1
                    continue

                record = {
                    "text": text,
                    "doc_type": doc_type,
                    "vendor": vendor,
                    "is_default": is_default,
                    "source": source,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
            except Exception as exc:
                logging.debug(f"Skipped {path}: {exc}")
                skipped += 1
    logging.info(f"Pseudo-label generation complete: {written} written, {skipped} skipped")
    return written


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Document corpus root directory")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument(
        "--use-lm",
        action="store_true",
        help="Run the small LM (if available) instead of the regex pipeline to label rows",
    )
    parser.add_argument(
        "--exclude-defaults",
        action="store_true",
        help="Drop rows where the regex defaulted to CONTRACT",
    )
    parser.add_argument(
        "--vendor-source",
        default="any",
        choices=["any", "text", "folder", "filename"],
        help="Filter rows by where the vendor signal came from",
    )
    args = parser.parse_args(argv)
    return generate(
        input_dir=args.input,
        output_path=args.output,
        use_lm=args.use_lm,
        exclude_defaults=args.exclude_defaults,
        vendor_source=args.vendor_source,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
