import sys
import json
import logging
import pandas as pd
from pathlib import Path
from datetime import date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QLineEdit, QPushButton, QTextEdit, 
    QFileDialog, QMessageBox, QPlainTextEdit, QGroupBox,
    QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from app.InvoiceChecker import InvoiceChecker

class QTextEditLogger(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.setReadOnly(True)
        
        # Create a formatter
        formatter = logging.Formatter(
            '%(levelname)s | %(asctime)s | %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p'
        )
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.appendPlainText(msg)
    
    def write(self, message):
        if message and not message.isspace():
            self.text_widget.appendPlainText(message)
    
    def flush(self):
        pass

class InvoiceCheckerThread(QThread):
    finished = pyqtSignal(bool)
    log_message = pyqtSignal(str)

    def __init__(self, checker, mst_list):
        super().__init__()
        self.checker = checker
        self.mst_list = mst_list

    def run(self):
        try:
            self.checker.run(self.mst_list)
            self.finished.emit(True)
        except Exception as e:
            self.log_message.emit(f"Error: {str(e)}")
            self.finished.emit(False)

class InvoiceCheckerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Invoice Checker")
        self.setMinimumSize(800, 600)
        
        # Initialize main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Add tabs
        tabs.addTab(self.create_input_tab(), "Input")
        tabs.addTab(self.create_config_tab(), "Configuration")
        
        # Initialize variables
        self.current_path = Path.cwd()
        self.load_config()
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration."""
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        # Create file handler
        log_dir = self.current_path / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f'log_{date.today().strftime("%Y_%m_%d")}.log'
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_formatter = logging.Formatter(
            '%(levelname)s | %(asctime)s | %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Add GUI handler
        text_handler = QTextEditLogger(self.log_view)
        logger.addHandler(text_handler)
        
    def create_input_tab(self):
        """Create the input tab with MST input options and log view."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # MST Input Group
        input_group = QGroupBox("MST Input")
        input_layout = QVBoxLayout()
        
        # Single MST input
        single_input_layout = QHBoxLayout()
        self.mst_input = QLineEdit()
        add_button = QPushButton("Add MST")
        add_button.clicked.connect(self.add_mst)
        single_input_layout.addWidget(QLabel("MST:"))
        single_input_layout.addWidget(self.mst_input)
        single_input_layout.addWidget(add_button)
        input_layout.addLayout(single_input_layout)
        
        # Excel import
        excel_layout = QHBoxLayout()
        self.excel_path = QLineEdit()
        self.excel_path.setReadOnly(True)
        browse_button = QPushButton("Browse Excel")
        browse_button.clicked.connect(self.browse_excel)
        import_button = QPushButton("Import")
        import_button.clicked.connect(self.import_excel)
        excel_layout.addWidget(self.excel_path)
        excel_layout.addWidget(browse_button)
        excel_layout.addWidget(import_button)
        input_layout.addLayout(excel_layout)
        
        # MST List
        self.mst_list = QTextEdit()
        self.mst_list.setPlaceholderText("MST numbers will appear here...")
        input_layout.addWidget(self.mst_list)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        clear_button = QPushButton("Clear List")
        clear_button.clicked.connect(self.clear_list)
        start_button = QPushButton("Start Processing")
        start_button.clicked.connect(self.start_processing)
        open_reports_button = QPushButton("Open Reports Folder")
        open_reports_button.clicked.connect(self.open_reports_folder)
        button_layout.addWidget(clear_button)
        button_layout.addWidget(start_button)
        button_layout.addWidget(open_reports_button)
        layout.addLayout(button_layout)
        
        # Log view
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        return tab
        
    def create_config_tab(self):
        """Create the configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Proxy settings
        proxy_group = QGroupBox("Proxy Settings")
        proxy_layout = QVBoxLayout()
        
        self.use_proxy = QCheckBox("Use Proxy")
        self.use_proxy.stateChanged.connect(self.save_config)
        proxy_layout.addWidget(self.use_proxy)
        
        proxy_fields = [
            ("Proxy Address:", "proxy_address"),
            ("Proxy Port:", "proxy_port"),
            ("Username:", "proxy_username"),
            ("Password:", "proxy_password")
        ]
        
        self.proxy_inputs = {}
        for label_text, field_name in proxy_fields:
            field_layout = QHBoxLayout()
            field_layout.addWidget(QLabel(label_text))
            line_edit = QLineEdit()
            line_edit.textChanged.connect(self.save_config)
            self.proxy_inputs[field_name] = line_edit
            field_layout.addWidget(line_edit)
            proxy_layout.addLayout(field_layout)
            
        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)
        
        # Browser settings
        browser_group = QGroupBox("Browser Settings")
        browser_layout = QVBoxLayout()
        
        self.headless = QCheckBox("Headless Mode")
        self.headless.stateChanged.connect(self.save_config)
        browser_layout.addWidget(self.headless)
        
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Wait Timeout (seconds):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 60)
        self.timeout_spin.valueChanged.connect(self.save_config)
        timeout_layout.addWidget(self.timeout_spin)
        browser_layout.addLayout(timeout_layout)
        
        browser_group.setLayout(browser_layout)
        layout.addWidget(browser_group)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
        return tab
    
    def load_config(self):
        """Load configuration from file."""
        config_path = self.current_path / 'config.json'
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='UTF-8') as f:
                    config = json.load(f)
                    
                self.use_proxy.setChecked(config.get('use_proxy') == "True")
                self.headless.setChecked(config.get('headless') == "True")
                self.timeout_spin.setValue(int(config.get('wait_timeout', 20)))
                
                for field, value in config.items():
                    if field in self.proxy_inputs:
                        self.proxy_inputs[field].setText(str(value))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load configuration: {str(e)}")
    
    def save_config(self):
        """Save configuration to file."""
        config = {
            'use_proxy': str(self.use_proxy.isChecked()),
            'headless': str(self.headless.isChecked()),
            'wait_timeout': str(self.timeout_spin.value())
        }
        
        for field, input_widget in self.proxy_inputs.items():
            config[field] = input_widget.text()
        
        try:
            config_path = self.current_path / 'config.json'
            with open(config_path, 'w', encoding='UTF-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {str(e)}")
    
    def add_mst(self):
        """Add single MST to the list."""
        mst = self.mst_input.text().strip()
        if mst:
            current_text = self.mst_list.toPlainText()
            if current_text:
                self.mst_list.setText(f"{current_text}\n{mst}")
            else:
                self.mst_list.setText(mst)
            self.mst_input.clear()
    
    def browse_excel(self):
        """Open file dialog to select Excel file."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Excel File",
            str(self.current_path),
            "Excel Files (*.xlsx *.xls)"
        )
        if file_name:
            self.excel_path.setText(file_name)
    
    def import_excel(self):
        """Import MST numbers from Excel file."""
        if not self.excel_path.text():
            QMessageBox.warning(self, "Error", "Please select an Excel file first")
            return
            
        try:
            df = pd.read_excel(self.excel_path.text())
            if 'MST' in df.columns:
                mst_numbers = df['MST'].astype(str).tolist()
                self.mst_list.setText("\n".join(mst_numbers))
            else:
                QMessageBox.warning(self, "Error", "Excel file must contain a 'MST' column")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to import Excel file: {str(e)}")
    
    def clear_list(self):
        """Clear the MST list."""
        self.mst_list.clear()
    
    def start_processing(self):
        """Start processing the MST list."""
        mst_text = self.mst_list.toPlainText().strip()
        if not mst_text:
            QMessageBox.warning(self, "Error", "Please add MST numbers first")
            return
            
        mst_list = [mst.strip() for mst in mst_text.split('\n') if mst.strip()]
        
        # Create data directory
        current_date = date.today()
        data_dir = self.current_path / 'reports' / current_date.strftime('%d_%m_%Y')
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize checker with log handler
        checker = InvoiceChecker(
            str(self.current_path),
            str(data_dir),
            self.get_config()
        )
        
        # Start processing thread
        self.worker = InvoiceCheckerThread(checker, mst_list)
        self.worker.finished.connect(self.processing_finished)
        self.worker.log_message.connect(lambda msg: logging.info(msg))
        self.worker.start()
        
        # Disable input while processing
        self.setEnabled(False)
    
    def processing_finished(self, success):
        """Handle processing completion."""
        self.setEnabled(True)
        if success:
            QMessageBox.information(self, "Success", "Processing completed successfully")
            self.open_reports_folder()
        else:
            QMessageBox.warning(self, "Error", "Processing failed. Check the log for details.")
    
    def open_reports_folder(self):
        """Open the reports folder in file explorer."""
        current_date = date.today()
        reports_dir = self.current_path / 'reports' / current_date.strftime('%d_%m_%Y')
        if reports_dir.exists():
            import os
            os.startfile(str(reports_dir))
    
    def get_config(self):
        """Get current configuration."""
        return {
            'use_proxy': str(self.use_proxy.isChecked()),
            'headless': str(self.headless.isChecked()),
            'wait_timeout': str(self.timeout_spin.value()),
            **{field: input_widget.text() 
               for field, input_widget in self.proxy_inputs.items()}
        }

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = InvoiceCheckerGUI()
    window.show()
    sys.exit(app.exec())