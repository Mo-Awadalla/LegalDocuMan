# Backend Tracking System for Record Management

## Overview
This system captures expiration dates and retention information for Sonja's backend record destruction scheduling.

## Key Features

### ✅ Expiration Date Handling (per Sonja's Requirements)
- **Expiration dates are captured in METADATA only**
- **NOT included in filenames** (keeps filenames clean)
- **Comprehensive extraction patterns** for various legal language
- **Centralized tracking registry** for backend processing

### Backend Files Generated
- `[filename].metadata.json` - Individual document metadata
- `_backend_tracking_registry.json` - Centralized tracking registry
- Retention categories: `long_term`, `short_term`, `indefinite`, `tied_to_parent`

## Usage

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

## Retention Categories

### Long Term
- MSA, CONTRACT, AGREEMENT documents with expiration dates
- Requires periodic review for destruction scheduling

### Short Term  
- PO, INVOICE documents
- Shorter retention periods

### Indefinite
- NDA, LICENSE documents
- No expiration, permanent retention

### Tied to Parent
- AMD (Amendment) documents
- Retention tied to parent contract

## Excel Report Features

The system generates comprehensive Excel reports with multiple sheets:
- **All_Documents** - Complete document inventory
- **Expiring_90_Days** - Documents requiring immediate attention
- **Category_[name]** - Documents grouped by retention category

## Integration with Document Processing

The backend tracking system automatically integrates with the main document processor:
1. Documents are processed and classified
2. Expiration dates are extracted and stored in metadata
3. Centralized registry is updated
4. Backend team can query and generate reports

This ensures compliance with record retention policies and efficient destruction scheduling.
