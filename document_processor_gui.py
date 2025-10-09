"""
Unified Document Processing GUI
Combines all document processing tools in one interface
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import sys
import os
from pathlib import Path
import json

# Import our unified processor
from document_processor import DocumentProcessor, process_contracts_simple, process_contracts_enhanced, sort_files_by_year

class RedirectText:
    """Redirect stdout/stderr to GUI text widget"""
    def __init__(self, text_widget):
        self.output = text_widget
    
    def write(self, string):
        self.output.insert(tk.END, string)
        self.output.see(tk.END)
        self.output.update()
    
    def flush(self):
        pass

class DocumentProcessorApp:
    """Main application class for document processing"""
    
    def __init__(self, root):
        self.root = root
        
        # Modern color scheme
        self.colors = {
            'primary': '#1E3A8A',      # Professional blue
            'secondary': '#3B82F6',    # Light blue
            'accent': '#10B981',       # Green
            'warning': '#F59E0B',      # Orange  
            'danger': '#EF4444',       # Red
            'background': '#F8FAFC',   # Light gray
            'card': '#FFFFFF',         # White
            'text_primary': '#1F2937', # Dark gray
            'text_secondary': '#6B7280', # Medium gray
            'border': '#E5E7EB',       # Light border
            'hover': '#F3F4F6'         # Hover state
        }
        
        # Configure main window
        self.root.title("Document Processing Suite v2.0")
        
        # Get screen dimensions for responsive sizing
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate optimal window size (80% of screen, min 1200x800)
        width = max(1200, int(screen_width * 0.8))
        height = max(800, int(screen_height * 0.8))
        
        # Center the window
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(1000, 700)
        self.root.configure(bg=self.colors['background'])
        
        # Configure modern style
        self.setup_styles()
        
        # Configuration storage
        self.config_file = Path.home() / "Documents" / "DocumentProcessorLogs" / "config.json"
        self.config = self.load_config()
        
        # Create the main interface
        self.create_header()
        self.create_notebook()
        self.create_log_area()
        
        # Redirect stdout to log area
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        sys.stdout = RedirectText(self.log_text)
        sys.stderr = RedirectText(self.log_text)
    
    def load_config(self):
        """Load saved configuration"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def save_config(self):
        """Save current configuration"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass
    
    def setup_styles(self):
        """Configure modern ttk styles"""
        style = ttk.Style()
        
        # Configure notebook style
        style.configure('Modern.TNotebook', 
                       background=self.colors['background'],
                       borderwidth=0)
        style.configure('Modern.TNotebook.Tab',
                       padding=[20, 12],
                       font=('Segoe UI', 10),
                       focuscolor='none')
        
        # Configure frame styles
        style.configure('Card.TFrame',
                       background=self.colors['card'],
                       relief='flat',
                       borderwidth=1)
        
        # Configure label frame styles
        style.configure('Modern.TLabelframe',
                       background=self.colors['card'],
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'])
        style.configure('Modern.TLabelframe.Label',
                       background=self.colors['card'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 10, 'bold'))
        
        # Configure button styles
        style.configure('Primary.TButton',
                       font=('Segoe UI', 10),
                       padding=[20, 10])
        style.configure('Secondary.TButton',
                       font=('Segoe UI', 10),
                       padding=[15, 8])
        style.configure('Accent.TButton',
                       font=('Segoe UI', 10, 'bold'),
                       padding=[25, 12])
        
        # Configure entry styles
        style.configure('Modern.TEntry',
                       padding=[8, 6],
                       font=('Segoe UI', 9))
    
    def create_modern_button(self, parent, text, command, style='primary', width=None):
        """Create a modern styled button"""
        if style == 'primary':
            btn = tk.Button(parent, text=text, command=command,
                           bg=self.colors['primary'], fg='white',
                           font=('Segoe UI', 10, 'bold'),
                           pady=12, padx=20,
                           relief='flat', cursor='hand2',
                           activebackground=self.colors['secondary'],
                           activeforeground='white')
        elif style == 'accent':
            btn = tk.Button(parent, text=text, command=command,
                           bg=self.colors['accent'], fg='white',
                           font=('Segoe UI', 10, 'bold'),
                           pady=12, padx=25,
                           relief='flat', cursor='hand2',
                           activebackground='#059669',
                           activeforeground='white')
        elif style == 'danger':
            btn = tk.Button(parent, text=text, command=command,
                           bg=self.colors['danger'], fg='white',
                           font=('Segoe UI', 10, 'bold'),
                           pady=12, padx=20,
                           relief='flat', cursor='hand2',
                           activebackground='#DC2626',
                           activeforeground='white')
        else:  # secondary
            btn = tk.Button(parent, text=text, command=command,
                           bg=self.colors['card'], fg=self.colors['text_primary'],
                           font=('Segoe UI', 10),
                           pady=10, padx=15,
                           relief='solid', bd=1, cursor='hand2',
                           activebackground=self.colors['hover'],
                           activeforeground=self.colors['text_primary'])
        
        if width:
            btn.configure(width=width)
        
        return btn
    
    def create_header(self):
        """Create modern application header"""
        # Main header container
        header_frame = tk.Frame(self.root, bg=self.colors['primary'], height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        
        # Inner container for content alignment
        header_content = tk.Frame(header_frame, bg=self.colors['primary'])
        header_content.pack(fill='both', expand=True, padx=30)
        
        # Left side - title and subtitle
        title_frame = tk.Frame(header_content, bg=self.colors['primary'])
        title_frame.pack(side='left', fill='y')
        
        title_label = tk.Label(
            title_frame, 
            text="Document Processing Suite", 
            font=("Segoe UI", 20, "bold"), 
            fg="white", 
            bg=self.colors['primary']
        )
        title_label.pack(anchor='w', pady=(12, 2))
        
        subtitle_label = tk.Label(
            title_frame,
            text="Intelligent contract organization with signature detection & expiration tracking",
            font=("Segoe UI", 9),
            fg="#A5B4FC",  # Light blue
            bg=self.colors['primary']
        )
        subtitle_label.pack(anchor='w')
        
        # Right side - version and status
        status_frame = tk.Frame(header_content, bg=self.colors['primary'])
        status_frame.pack(side='right', fill='y')
        
        version_label = tk.Label(
            status_frame,
            text="v2.0",
            font=("Segoe UI", 10, "bold"),
            fg="#A5B4FC",
            bg=self.colors['primary']
        )
        version_label.pack(anchor='e', pady=(15, 2))
        
        status_label = tk.Label(
            status_frame,
            text="Ready",
            font=("Segoe UI", 9),
            fg="#34D399",  # Green
            bg=self.colors['primary']
        )
        status_label.pack(anchor='e')
    
    def create_notebook(self):
        """Create modern tabbed interface"""
        # Container for notebook with padding and background
        notebook_container = tk.Frame(self.root, bg=self.colors['background'])
        notebook_container.pack(fill='both', expand=True, padx=20, pady=(15, 10))
        
        # Create notebook with modern style
        self.notebook = ttk.Notebook(notebook_container, style='Modern.TNotebook')
        self.notebook.pack(fill='both', expand=True)
        
        # Create tabs with icons and improved styling
        self.create_contract_renamer_tab()
        self.create_file_sorter_tab()
        self.create_settings_tab()
    
    def create_contract_renamer_tab(self):
        """Create modern contract renaming tab"""
        frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(frame, text="📋 Contract Processor")
        
        # Main container with modern scrolling
        canvas = tk.Canvas(frame, bg=self.colors['background'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['background'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Hero section with description
        hero_frame = tk.Frame(scrollable_frame, bg=self.colors['card'], relief='flat', bd=1)
        hero_frame.pack(fill='x', padx=25, pady=(20, 25))
        
        # Icon and title
        title_frame = tk.Frame(hero_frame, bg=self.colors['card'])
        title_frame.pack(fill='x', padx=25, pady=(20, 10))
        
        title_label = tk.Label(
            title_frame,
            text="🔄 Intelligent Contract Processing",
            font=("Segoe UI", 16, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['card']
        )
        title_label.pack(anchor='w')
        
        desc_label = tk.Label(
            hero_frame, 
            text="Transform your contract chaos into organized, searchable documents with signature detection, expiration tracking, and smart classification.",
            font=("Segoe UI", 11), 
            fg=self.colors['text_secondary'],
            bg=self.colors['card'],
            wraplength=900,
            justify='left'
        )
        desc_label.pack(padx=25, pady=(0, 20), anchor='w')
        
        # Input folder selection
        input_frame = tk.LabelFrame(scrollable_frame, text="Source Directory", font=("Arial", 10, "bold"))
        input_frame.pack(fill='x', padx=20, pady=5)
        
        self.input_var = tk.StringVar(value=self.config.get('input_folder', ''))
        input_entry_frame = tk.Frame(input_frame)
        input_entry_frame.pack(fill='x', padx=10, pady=10)
        
        input_entry = tk.Entry(input_entry_frame, textvariable=self.input_var, font=("Arial", 9))
        input_entry.pack(side='left', fill='x', expand=True)
        
        input_browse_btn = tk.Button(
            input_entry_frame, 
            text="Browse", 
            command=lambda: self.browse_folder(self.input_var),
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 9)
        )
        input_browse_btn.pack(side='right', padx=(5, 0))
        
        # Error folder selection
        error_frame = tk.LabelFrame(scrollable_frame, text="Error Files Directory", font=("Arial", 10, "bold"))
        error_frame.pack(fill='x', padx=20, pady=5)
        
        self.error_var = tk.StringVar(value=self.config.get('error_folder', ''))
        error_entry_frame = tk.Frame(error_frame)
        error_entry_frame.pack(fill='x', padx=10, pady=10)
        
        error_entry = tk.Entry(error_entry_frame, textvariable=self.error_var, font=("Arial", 9))
        error_entry.pack(side='left', fill='x', expand=True)
        
        error_browse_btn = tk.Button(
            error_entry_frame, 
            text="Browse", 
            command=lambda: self.browse_folder(self.error_var),
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 9)
        )
        error_browse_btn.pack(side='right', padx=(5, 0))
        
        # Vendor master list (optional)
        vendor_frame = tk.LabelFrame(scrollable_frame, text="Vendor Master List (Optional)", font=("Arial", 10, "bold"))
        vendor_frame.pack(fill='x', padx=20, pady=5)
        
        self.vendor_file_var = tk.StringVar(value=self.config.get('vendor_file', ''))
        vendor_entry_frame = tk.Frame(vendor_frame)
        vendor_entry_frame.pack(fill='x', padx=10, pady=10)
        
        vendor_entry = tk.Entry(vendor_entry_frame, textvariable=self.vendor_file_var, font=("Arial", 9))
        vendor_entry.pack(side='left', fill='x', expand=True)
        
        vendor_browse_btn = tk.Button(
            vendor_entry_frame, 
            text="Browse", 
            command=self.browse_vendor_file,
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 9)
        )
        vendor_browse_btn.pack(side='right', padx=(5, 0))
        
        # Processing options
        options_frame = tk.LabelFrame(scrollable_frame, text="Processing Options", font=("Arial", 10, "bold"))
        options_frame.pack(fill='x', padx=20, pady=5)
        
        options_inner = tk.Frame(options_frame)
        options_inner.pack(fill='x', padx=10, pady=10)
        
        # Processing mode
        mode_frame = tk.Frame(options_inner)
        mode_frame.pack(fill='x', pady=5)
        
        tk.Label(mode_frame, text="Processing Mode:", font=("Arial", 9, "bold")).pack(side='left')
        
        self.processing_mode = tk.StringVar(value=self.config.get('processing_mode', 'enhanced'))
        
        simple_radio = tk.Radiobutton(
            mode_frame, 
            text="Simple (YYYYMMDD_Vendor_File)", 
            variable=self.processing_mode, 
            value='simple',
            font=("Arial", 9)
        )
        simple_radio.pack(side='left', padx=(10, 0))
        
        enhanced_radio = tk.Radiobutton(
            mode_frame, 
            text="Enhanced (K_Vendor_type_001)", 
            variable=self.processing_mode, 
            value='enhanced',
            font=("Arial", 9)
        )
        enhanced_radio.pack(side='left', padx=(10, 0))
        
        # Additional options
        self.create_subfolders_var = tk.BooleanVar(value=self.config.get('create_subfolders', True))
        self.include_subfolders_var = tk.BooleanVar(value=self.config.get('include_subfolders', True))
        
        subfolder_check = tk.Checkbutton(
            options_inner, 
            text="Create organized subfolders (_final for signed documents, _supporting for all others)", 
            variable=self.create_subfolders_var,
            font=("Arial", 9)
        )
        subfolder_check.pack(anchor='w', pady=2)
        
        include_check = tk.Checkbutton(
            options_inner, 
            text="Include files in subfolders", 
            variable=self.include_subfolders_var,
            font=("Arial", 9)
        )
        include_check.pack(anchor='w', pady=2)
        
        # Information box
        info_text = (
            "Key Features:\n"
            "• Advanced signature detection (digital, physical, e-signature platforms)\n"
            "• Smart document classification: FINAL (signed) vs SUPPORTING (unsigned)\n"
            "• Document type detection (MSA, SOW, NDA, etc.)\n"
            "• Date extraction and expiration tracking\n"
            "• Vendor name normalization and matching\n"
            "• Automatic folder organization (_final and _supporting)\n"
            "• Comprehensive metadata generation for backend tracking\n"
            "• OCR support for scanned documents"
        )
        
        info_frame = tk.LabelFrame(scrollable_frame, text="Features", font=("Arial", 10, "bold"))
        info_frame.pack(fill='x', padx=20, pady=5)
        
        info_label = tk.Label(
            info_frame, 
            text=info_text, 
            justify="left", 
            fg="darkblue", 
            font=("Arial", 9),
            wraplength=750
        )
        info_label.pack(padx=10, pady=10)
        
        # Process button section
        action_frame = tk.Frame(scrollable_frame, bg=self.colors['background'])
        action_frame.pack(fill='x', padx=25, pady=30)
        
        # Create prominent process button
        process_btn = self.create_modern_button(
            action_frame,
            "🚀 Start Processing Contracts",
            self.start_contract_processing,
            style='accent'
        )
        process_btn.pack(pady=10)
        
        # Progress indicator (initially hidden)
        self.progress_frame = tk.Frame(action_frame, bg=self.colors['background'])
        
        progress_label = tk.Label(
            self.progress_frame,
            text="Processing documents...",
            font=("Segoe UI", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['background']
        )
        progress_label.pack()
        
        # Note about processing
        note_label = tk.Label(
            action_frame,
            text="💡 Processing may take a few minutes depending on document count and complexity",
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['background']
        )
        note_label.pack(pady=(5, 0))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_file_sorter_tab(self):
        """Create modern file sorting tab"""
        frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(frame, text="🗂️ Date Sorter")
        
        # Modern container for file sorter
        container = tk.Frame(frame, bg=self.colors['background'])
        container.pack(fill='both', expand=True, padx=25, pady=20)
        
        # Hero section
        hero_frame = tk.Frame(container, bg=self.colors['card'], relief='flat', bd=1)
        hero_frame.pack(fill='x', pady=(0, 25))
        
        title_label = tk.Label(
            hero_frame,
            text="🗓️ Smart Date-Based File Organization",
            font=("Segoe UI", 16, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['card']
        )
        title_label.pack(padx=25, pady=(20, 10), anchor='w')
        
        desc_label = tk.Label(
            hero_frame, 
            text="Archive older documents while preserving your folder structure. Perfect for compliance and storage management.",
            font=("Segoe UI", 11), 
            fg=self.colors['text_secondary'],
            bg=self.colors['card'],
            wraplength=900,
            justify='left'
        )
        desc_label.pack(padx=25, pady=(0, 20), anchor='w')
        
        # Source directory
        source_frame = tk.LabelFrame(container, text="Source Directory (to clean)", font=("Arial", 10, "bold"))
        source_frame.pack(fill='x', padx=20, pady=10)
        
        self.sort_source_var = tk.StringVar(value=self.config.get('sort_source', ''))
        source_entry_frame = tk.Frame(source_frame)
        source_entry_frame.pack(fill='x', padx=10, pady=10)
        
        source_entry = tk.Entry(source_entry_frame, textvariable=self.sort_source_var, font=("Arial", 9))
        source_entry.pack(side='left', fill='x', expand=True)
        
        source_browse_btn = tk.Button(
            source_entry_frame, 
            text="Browse", 
            command=lambda: self.browse_folder(self.sort_source_var),
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 9)
        )
        source_browse_btn.pack(side='right', padx=(5, 0))
        
        # Pre-2017 archive directory
        archive_frame = tk.LabelFrame(container, text="Pre-2017 Archive Directory", font=("Arial", 10, "bold"))
        archive_frame.pack(fill='x', padx=20, pady=10)
        
        self.archive_var = tk.StringVar(value=self.config.get('archive_folder', ''))
        archive_entry_frame = tk.Frame(archive_frame)
        archive_entry_frame.pack(fill='x', padx=10, pady=10)
        
        archive_entry = tk.Entry(archive_entry_frame, textvariable=self.archive_var, font=("Arial", 9))
        archive_entry.pack(side='left', fill='x', expand=True)
        
        archive_browse_btn = tk.Button(
            archive_entry_frame, 
            text="Browse", 
            command=lambda: self.browse_folder(self.archive_var),
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 9)
        )
        archive_browse_btn.pack(side='right', padx=(5, 0))
        
        # Error directory
        sort_error_frame = tk.LabelFrame(container, text="Error Files Directory", font=("Arial", 10, "bold"))
        sort_error_frame.pack(fill='x', padx=20, pady=10)
        
        self.sort_error_var = tk.StringVar(value=self.config.get('sort_error_folder', ''))
        sort_error_entry_frame = tk.Frame(sort_error_frame)
        sort_error_entry_frame.pack(fill='x', padx=10, pady=10)
        
        sort_error_entry = tk.Entry(sort_error_entry_frame, textvariable=self.sort_error_var, font=("Arial", 9))
        sort_error_entry.pack(side='left', fill='x', expand=True)
        
        sort_error_browse_btn = tk.Button(
            sort_error_entry_frame, 
            text="Browse", 
            command=lambda: self.browse_folder(self.sort_error_var),
            bg="#4CAF50", 
            fg="white",
            font=("Arial", 9)
        )
        sort_error_browse_btn.pack(side='right', padx=(5, 0))
        
        # Year threshold
        threshold_frame = tk.LabelFrame(container, text="Options", font=("Arial", 10, "bold"))
        threshold_frame.pack(fill='x', padx=20, pady=10)
        
        threshold_inner = tk.Frame(threshold_frame)
        threshold_inner.pack(fill='x', padx=10, pady=10)
        
        tk.Label(threshold_inner, text="Remove files older than year:", font=("Arial", 9)).pack(side='left')
        
        self.year_threshold = tk.StringVar(value=self.config.get('year_threshold', '2017'))
        year_entry = tk.Entry(threshold_inner, textvariable=self.year_threshold, width=8, font=("Arial", 9))
        year_entry.pack(side='left', padx=(10, 0))
        
        # Information section
        info_text = (
            "This tool will:\n"
            "• Extract dates from document content and filenames\n"
            "• Move old files to archive folder preserving structure\n"
            "• Keep newer files in original locations\n"
            "• Generate Excel summary of all operations\n"
            "• Move problematic files to error folder for review"
        )
        
        info_frame = tk.LabelFrame(container, text="Information", font=("Arial", 10, "bold"))
        info_frame.pack(fill='x', padx=20, pady=10)
        
        info_label = tk.Label(
            info_frame, 
            text=info_text, 
            justify="left", 
            fg="darkblue", 
            font=("Arial", 9),
            wraplength=750
        )
        info_label.pack(padx=10, pady=10)
        
        # Action section
        action_frame = tk.Frame(container, bg=self.colors['background'])
        action_frame.pack(fill='x', padx=20, pady=30)
        
        # Modern sort button
        sort_btn = self.create_modern_button(
            action_frame,
            "🗂️ Start Date-Based Sorting",
            self.start_file_sorting,
            style='danger'  # Using danger style for file removal operation
        )
        sort_btn.pack(pady=10)
        
        # Warning note
        warning_label = tk.Label(
            action_frame,
            text="⚠️ This operation will move files. Ensure you have backups before proceeding.",
            font=("Segoe UI", 9),
            fg=self.colors['danger'],
            bg=self.colors['background']
        )
        warning_label.pack(pady=(5, 0))
    
    def create_settings_tab(self):
        """Create modern settings and configuration tab"""
        frame = ttk.Frame(self.notebook, style='Card.TFrame')
        self.notebook.add(frame, text="⚙️ Settings")
        
        # OCR Settings
        ocr_frame = tk.LabelFrame(frame, text="OCR Configuration", font=("Arial", 10, "bold"))
        ocr_frame.pack(fill='x', padx=20, pady=10)
        
        # Check OCR availability
        try:
            from document_processor import OCR_AVAILABLE
            ocr_status = "Available" if OCR_AVAILABLE else "Not Available"
            ocr_color = "green" if OCR_AVAILABLE else "red"
        except:
            ocr_status = "Unknown"
            ocr_color = "orange"
        
        ocr_status_label = tk.Label(
            ocr_frame, 
            text=f"OCR Status: {ocr_status}", 
            font=("Arial", 10, "bold"),
            fg=ocr_color
        )
        ocr_status_label.pack(pady=10)
        
        if not OCR_AVAILABLE:
            ocr_info = tk.Label(
                ocr_frame,
                text="To enable OCR: pip install pytesseract pdf2image\nAlso install Tesseract-OCR from GitHub",
                font=("Arial", 9),
                fg="gray"
            )
            ocr_info.pack(pady=5)
        
        # Logging Settings
        log_frame = tk.LabelFrame(frame, text="Logging", font=("Arial", 10, "bold"))
        log_frame.pack(fill='x', padx=20, pady=10)
        
        log_dir = Path.home() / "Documents" / "DocumentProcessorLogs"
        log_info = tk.Label(
            log_frame,
            text=f"Log files saved to:\n{log_dir}",
            font=("Arial", 9),
            fg="darkblue"
        )
        log_info.pack(pady=10)
        
        # Clear logs button
        clear_logs_btn = tk.Button(
            log_frame,
            text="Clear Log Files",
            command=self.clear_log_files,
            bg="#ff9800",
            fg="white",
            font=("Arial", 9)
        )
        clear_logs_btn.pack(pady=5)
        
        # About
        about_frame = tk.LabelFrame(frame, text="About", font=("Arial", 10, "bold"))
        about_frame.pack(fill='x', padx=20, pady=10)
        
        about_text = (
            "Document Processing Suite v2.0\n\n"
            "This application provides comprehensive document processing capabilities:\n"
            "• Smart contract renaming and organization\n"
            "• Intelligent file sorting by date\n"
            "• OCR support for scanned documents\n"
            "• Vendor name standardization\n"
            "• Document type classification\n"
            "• Metadata generation and tracking\n\n"
            "Supports PDF, DOCX, DOC, and TXT files."
        )
        
        about_label = tk.Label(
            about_frame,
            text=about_text,
            justify="left",
            font=("Arial", 9),
            fg="darkblue",
            wraplength=750
        )
        about_label.pack(padx=10, pady=10)
    
    def create_log_area(self):
        """Create modern log output area"""
        # Log container with modern styling
        log_container = tk.Frame(self.root, bg=self.colors['background'])
        log_container.pack(fill='x', padx=20, pady=(0, 20))
        
        # Log header with title and controls
        log_header = tk.Frame(log_container, bg=self.colors['card'], height=45)
        log_header.pack(fill='x', pady=(0, 2))
        log_header.pack_propagate(False)
        
        # Log title
        log_title = tk.Label(
            log_header,
            text="📋 Processing Log",
            font=("Segoe UI", 11, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['card']
        )
        log_title.pack(side='left', padx=15, pady=12)
        
        # Log controls frame
        controls_frame = tk.Frame(log_header, bg=self.colors['card'])
        controls_frame.pack(side='right', padx=15, pady=8)
        
        # Clear log button (modern style)
        clear_btn = self.create_modern_button(
            controls_frame,
            "Clear Log",
            self.clear_log,
            style='secondary'
        )
        clear_btn.pack(side='right')
        
        # Auto-scroll toggle
        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_cb = tk.Checkbutton(
            controls_frame,
            text="Auto-scroll",
            variable=self.auto_scroll_var,
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['card'],
            activebackground=self.colors['card']
        )
        auto_scroll_cb.pack(side='right', padx=(0, 10))
        
        # Log content area
        log_content = tk.Frame(log_container, bg=self.colors['card'], relief='solid', bd=1)
        log_content.pack(fill='x')
        
        # Create modern scrolled text widget
        self.log_text = scrolledtext.ScrolledText(
            log_content,
            height=10,
            font=("Cascadia Code", 9),  # Modern monospace font
            wrap=tk.WORD,
            bg='#1E1E1E',  # Dark background for logs
            fg='#D4D4D4',  # Light text
            insertbackground='#D4D4D4',
            selectbackground='#264F78',
            relief='flat',
            bd=0
        )
        self.log_text.pack(fill='both', expand=True, padx=1, pady=1)
        
        # Configure text tags for colored log output
        self.log_text.tag_config('error', foreground='#F48771')    # Light red
        self.log_text.tag_config('warning', foreground='#DCDCAA')  # Yellow
        self.log_text.tag_config('success', foreground='#4EC9B0')  # Green
        self.log_text.tag_config('info', foreground='#9CDCFE')     # Light blue
    
    def browse_folder(self, var):
        """Browse for folder"""
        folder = filedialog.askdirectory(initialdir=var.get())
        if folder:
            var.set(folder)
    
    def browse_vendor_file(self):
        """Browse for vendor master list file"""
        file_path = filedialog.askopenfilename(
            title="Select Vendor Master List",
            filetypes=[
                ("Text files", "*.txt"),
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx"),
                ("All files", "*.*")
            ],
            initialdir=self.vendor_file_var.get()
        )
        if file_path:
            self.vendor_file_var.set(file_path)
    
    def load_vendor_list(self, file_path):
        """Load vendor master list from file"""
        if not file_path or not os.path.exists(file_path):
            return None
        
        try:
            if file_path.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return [line.strip() for line in f if line.strip()]
            elif file_path.endswith('.csv'):
                import pandas as pd
                df = pd.read_csv(file_path)
                # Try to find vendor column
                for col in ['vendor', 'vendors', 'company', 'name']:
                    if col in df.columns:
                        return df[col].dropna().tolist()
                return df.iloc[:, 0].dropna().tolist()  # Use first column
            elif file_path.endswith('.xlsx'):
                import pandas as pd
                df = pd.read_excel(file_path)
                for col in ['vendor', 'vendors', 'company', 'name']:
                    if col in df.columns:
                        return df[col].dropna().tolist()
                return df.iloc[:, 0].dropna().tolist()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load vendor list: {e}")
            return None
    
    def start_contract_processing(self):
        """Start contract processing in separate thread"""
        # Validate inputs
        input_folder = self.input_var.get().strip()
        error_folder = self.error_var.get().strip()
        
        if not input_folder:
            messagebox.showwarning("Missing Input", "Please select a source directory")
            return
        
        if not os.path.exists(input_folder):
            messagebox.showerror("Error", f"Source directory does not exist: {input_folder}")
            return
        
        # Save configuration
        self.config.update({
            'input_folder': input_folder,
            'error_folder': error_folder,
            'vendor_file': self.vendor_file_var.get(),
            'processing_mode': self.processing_mode.get(),
            'create_subfolders': self.create_subfolders_var.get(),
            'include_subfolders': self.include_subfolders_var.get()
        })
        self.save_config()
        
        # Confirm operation
        mode_desc = "Enhanced" if self.processing_mode.get() == 'enhanced' else "Simple"
        subfolders_desc = " with organized subfolders" if self.create_subfolders_var.get() else ""
        
        result = messagebox.askyesno(
            "Confirm Processing",
            f"Process contracts in {mode_desc} mode{subfolders_desc}?\n\n"
            f"Source: {input_folder}\n"
            f"Errors: {error_folder or 'Default (_errors folder)'}\n\n"
            f"Files will be renamed and organized. Continue?"
        )
        
        if result:
            self.clear_log()
            self.log_text.insert(tk.END, f"Starting {mode_desc.lower()} contract processing...\n")
            
            # Start processing in separate thread
            thread = threading.Thread(
                target=self.run_contract_processing,
                args=(input_folder, error_folder),
                daemon=True
            )
            thread.start()
    
    def run_contract_processing(self, input_folder, error_folder):
        """Run contract processing"""
        try:
            # Load vendor list if provided
            vendor_list = None
            vendor_file = self.vendor_file_var.get().strip()
            if vendor_file:
                vendor_list = self.load_vendor_list(vendor_file)
                if vendor_list:
                    print(f"Loaded {len(vendor_list)} vendors from master list")
            
            # Choose processing mode
            if self.processing_mode.get() == 'enhanced':
                processor = DocumentProcessor(input_folder, error_folder, vendor_list)
                processor.process_contracts_enhanced(
                    create_subfolders=self.create_subfolders_var.get(),
                    naming_format='enhanced'
                )
            else:
                processor = DocumentProcessor(input_folder, error_folder, vendor_list)
                processor.process_contracts_enhanced(
                    create_subfolders=False,
                    naming_format='simple'
                )
            
            processor.print_summary()
            print("\n✅ Contract processing completed!")
            
            messagebox.showinfo("Complete", "Contract processing completed! Check the log for details.")
            
        except Exception as e:
            print(f"\n❌ Error during processing: {e}")
            messagebox.showerror("Error", f"Processing failed: {e}")
    
    def start_file_sorting(self):
        """Start file sorting in separate thread"""
        # Validate inputs
        source_dir = self.sort_source_var.get().strip()
        archive_dir = self.archive_var.get().strip()
        error_dir = self.sort_error_var.get().strip()
        
        if not all([source_dir, archive_dir, error_dir]):
            messagebox.showwarning("Missing Input", "Please select all required directories")
            return
        
        if not os.path.exists(source_dir):
            messagebox.showerror("Error", f"Source directory does not exist: {source_dir}")
            return
        
        # Validate year threshold
        try:
            year_threshold = int(self.year_threshold.get())
            if year_threshold < 1990 or year_threshold > 2030:
                raise ValueError("Year must be between 1990 and 2030")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid year threshold: {e}")
            return
        
        # Save configuration
        self.config.update({
            'sort_source': source_dir,
            'archive_folder': archive_dir,
            'sort_error_folder': error_dir,
            'year_threshold': str(year_threshold)
        })
        self.save_config()
        
        # Confirm operation
        result = messagebox.askyesno(
            "Confirm File Sorting",
            f"Remove files older than {year_threshold}?\n\n"
            f"Source: {source_dir}\n"
            f"Archive: {archive_dir}\n"
            f"Errors: {error_dir}\n\n"
            f"Old files will be moved to archive. Continue?"
        )
        
        if result:
            self.clear_log()
            self.log_text.insert(tk.END, f"Starting file sorting (pre-{year_threshold} removal)...\n")
            
            # Start sorting in separate thread
            thread = threading.Thread(
                target=self.run_file_sorting,
                args=(source_dir, archive_dir, error_dir, year_threshold),
                daemon=True
            )
            thread.start()
    
    def run_file_sorting(self, source_dir, archive_dir, error_dir, year_threshold):
        """Run file sorting"""
        try:
            processor = DocumentProcessor(source_dir, error_dir)
            processor.sort_files_by_year(archive_dir, year_threshold)
            processor.print_summary()
            print(f"\n✅ File sorting completed!")
            
            messagebox.showinfo("Complete", "File sorting completed! Check the log for details.")
            
        except Exception as e:
            print(f"\n❌ Error during sorting: {e}")
            messagebox.showerror("Error", f"Sorting failed: {e}")
    
    def clear_log(self):
        """Clear the log display"""
        self.log_text.delete(1.0, tk.END)
    
    def clear_log_files(self):
        """Clear log files from disk"""
        try:
            log_dir = Path.home() / "Documents" / "DocumentProcessorLogs"
            if log_dir.exists():
                for log_file in log_dir.glob("*.log"):
                    log_file.unlink()
                for log_file in log_dir.glob("*.txt"):
                    log_file.unlink()
                messagebox.showinfo("Success", "Log files cleared")
            else:
                messagebox.showinfo("Info", "No log files found")
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear log files: {e}")
    
    def on_closing(self):
        """Handle application closing"""
        # Restore stdout/stderr
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        
        # Save configuration
        self.save_config()
        
        # Close application
        self.root.destroy()

def main():
    """Main application entry point"""
    root = tk.Tk()
    app = DocumentProcessorApp(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start the GUI
    root.mainloop()

if __name__ == "__main__":
    main()
