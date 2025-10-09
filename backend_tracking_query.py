#!/usr/bin/env python3
"""
Backend Tracking Query Tool for Sonja
Query expiration dates and retention information for record destruction scheduling
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

def load_tracking_registry(folder_path):
    """Load the backend tracking registry"""
    registry_file = os.path.join(folder_path, '_backend_tracking_registry.json')
    
    if not os.path.exists(registry_file):
        print(f"❌ No tracking registry found at: {registry_file}")
        print("Run the document processor first to generate tracking data.")
        return None
    
    try:
        with open(registry_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading registry: {e}")
        return None

def query_expiring_documents(registry, months_ahead=12):
    """Query documents expiring within specified months"""
    if not registry or 'expiration_tracking' not in registry:
        return []
    
    today = datetime.now()
    future_date = today + timedelta(days=30 * months_ahead)
    
    expiring_docs = []
    for doc in registry['expiration_tracking']:
        exp_date_str = doc.get('expiration_date')
        if exp_date_str:
            try:
                exp_date = datetime.fromisoformat(exp_date_str)
                if today <= exp_date <= future_date:
                    # Calculate days until expiration
                    days_until = (exp_date - today).days
                    doc_copy = doc.copy()
                    doc_copy['days_until_expiration'] = days_until
                    expiring_docs.append(doc_copy)
            except ValueError:
                continue
    
    # Sort by expiration date
    expiring_docs.sort(key=lambda x: x.get('expiration_date', ''))
    return expiring_docs

def query_by_retention_category(registry, category=None):
    """Query documents by retention category"""
    if not registry or 'expiration_tracking' not in registry:
        return []
    
    if category:
        return [doc for doc in registry['expiration_tracking'] 
                if doc.get('retention_category', '').lower() == category.lower()]
    else:
        # Return all with their categories
        return registry['expiration_tracking']

def generate_excel_report(registry, output_path=None):
    """Generate Excel report for Sonja's backend tracking"""
    if not registry:
        return None
    
    try:
        # Prepare data for Excel
        all_docs = registry.get('expiration_tracking', [])
        
        if not all_docs:
            print("No documents with expiration dates to export")
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(all_docs)
        
        # Add helpful columns for backend processing
        today = datetime.now()
        df['days_until_expiration'] = df['expiration_date'].apply(
            lambda x: (datetime.fromisoformat(x) - today).days if x else None
        )
        
        df['expiration_status'] = df['days_until_expiration'].apply(
            lambda days: 'EXPIRED' if days and days < 0 
                         else 'EXPIRING_SOON' if days and days <= 90
                         else 'ACTIVE' if days and days > 90
                         else 'NO_EXPIRATION'
        )
        
        # Reorder columns for Sonja's use
        column_order = [
            'tracking_id', 'vendor', 'document_type', 'filename', 
            'expiration_date', 'days_until_expiration', 'expiration_status',
            'retention_category', 'renewal_date', 'review_date',
            'destruction_review_required', 'file_path', 'processing_date'
        ]
        
        # Only include columns that exist
        available_columns = [col for col in column_order if col in df.columns]
        df_ordered = df[available_columns]
        
        # Set output path
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'backend_tracking_report_{timestamp}.xlsx'
        
        # Write to Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # All documents
            df_ordered.to_excel(writer, sheet_name='All_Documents', index=False)
            
            # Expiring soon (next 90 days)
            expiring_soon = df_ordered[df_ordered['expiration_status'] == 'EXPIRING_SOON']
            if not expiring_soon.empty:
                expiring_soon.to_excel(writer, sheet_name='Expiring_90_Days', index=False)
            
            # By retention category
            for category in df['retention_category'].unique():
                if pd.notna(category):
                    cat_data = df_ordered[df_ordered['retention_category'] == category]
                    sheet_name = f'Category_{category}'.replace('/', '_')[:31]  # Excel limit
                    cat_data.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"✅ Excel report generated: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Error generating Excel report: {e}")
        return None

def print_summary(registry):
    """Print summary of tracking data"""
    if not registry:
        return
    
    print("\n📊 BACKEND TRACKING SUMMARY")
    print("=" * 50)
    print(f"Last updated: {registry.get('last_updated', 'Unknown')}")
    print(f"Total documents: {registry.get('total_documents', 0)}")
    print(f"Documents with expiration dates: {registry.get('documents_with_expiration', 0)}")
    
    # Retention categories
    retention_cats = registry.get('retention_categories', {})
    if retention_cats:
        print(f"\nRetention categories:")
        for category, count in retention_cats.items():
            print(f"  {category}: {count}")

def main():
    """Main function for command-line usage"""
    if len(sys.argv) < 2:
        print("Backend Tracking Query Tool for Sonja")
        print("Usage: python backend_tracking_query.py <folder_path> [options]")
        print("\nOptions:")
        print("  --summary                Show summary information")
        print("  --expiring <months>      Show documents expiring in N months (default: 12)")
        print("  --category <name>        Show documents by retention category")
        print("  --excel [path]          Generate Excel report")
        print("\nExamples:")
        print("  python backend_tracking_query.py C:/contracts --summary")
        print("  python backend_tracking_query.py C:/contracts --expiring 6")
        print("  python backend_tracking_query.py C:/contracts --excel report.xlsx")
        return
    
    folder_path = sys.argv[1]
    
    # Load tracking registry
    registry = load_tracking_registry(folder_path)
    if not registry:
        return
    
    # Process commands
    if '--summary' in sys.argv:
        print_summary(registry)
    
    if '--expiring' in sys.argv:
        try:
            idx = sys.argv.index('--expiring')
            months = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 12
        except (ValueError, IndexError):
            months = 12
        
        expiring = query_expiring_documents(registry, months)
        print(f"\n🗓️  DOCUMENTS EXPIRING IN NEXT {months} MONTHS:")
        print("-" * 60)
        
        if expiring:
            for doc in expiring:
                exp_date = doc.get('expiration_date', 'Unknown')
                days = doc.get('days_until_expiration', 0)
                vendor = doc.get('vendor', 'Unknown')
                doc_type = doc.get('document_type', 'Unknown')
                filename = doc.get('filename', 'Unknown')
                print(f"{exp_date} ({days} days) - {vendor} - {doc_type}")
                print(f"  File: {filename}")
        else:
            print(f"No documents expiring in next {months} months")
    
    if '--category' in sys.argv:
        try:
            idx = sys.argv.index('--category')
            category = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        except IndexError:
            category = None
        
        docs = query_by_retention_category(registry, category)
        if category:
            print(f"\n📂 DOCUMENTS IN CATEGORY: {category}")
        else:
            print(f"\n📂 ALL DOCUMENTS BY CATEGORY:")
        print("-" * 60)
        
        for doc in docs:
            vendor = doc.get('vendor', 'Unknown')
            doc_type = doc.get('document_type', 'Unknown')
            ret_cat = doc.get('retention_category', 'Unknown')
            exp_date = doc.get('expiration_date', 'No expiration')
            print(f"{vendor} - {doc_type} - {ret_cat} - Expires: {exp_date}")
    
    if '--excel' in sys.argv:
        try:
            idx = sys.argv.index('--excel')
            output_path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        except IndexError:
            output_path = None
        
        generate_excel_report(registry, output_path)

if __name__ == "__main__":
    main()
