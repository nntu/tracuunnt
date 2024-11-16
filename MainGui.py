# -*- coding: utf8 -*-
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                            QTableWidget, QTableWidgetItem, QProgressBar, 
                            QFileDialog, QMessageBox, QHeaderView, QTextEdit,
                            QSplitter, QDialog, QStatusBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QProcess, QTimer
from PyQt6.QtGui import QAction, QIcon, QTextCursor
import subprocess
import sys
import json
import logging
import os
from pathlib import Path
import pandas as pd
from typing import Optional, List, Dict, Any, Union
import threading
from queue import Queue
from datetime import date, datetime
from PyQt6.QtGui import QAction , QIcon,QPixmap


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedSize(568, 700)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Add logo/image
        logo_label = QLabel()
        # Replace 'logo.png' with your image path
        pixmap = QPixmap('tkbidv.png')
        scaled_pixmap = pixmap.scaled(345, 617, Qt.AspectRatioMode.KeepAspectRatio, 
                                    Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add text information
        info_label = QLabel(
            """<h2>Kiểm tra Thông Tin hóa đơn</h2>
        <p>Version 1.1</p> 
        <p>Copyright (C) 2024 by Nguyen Ngoc Tu</p>                
        <p>Email: ngoctuct@gmail.com</p>"""
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        
        # Add widgets to layout
       
        layout.addWidget(info_label)
        layout.addWidget(logo_label)
        layout.addStretch()
        
        self.setLayout(layout)    
class EnhancedReportDialog(QDialog):
    """Enhanced dialog for handling multiple report formats"""
    def __init__(self, excel_path: Union[str, Path], docx_path: Optional[Union[str, Path]], 
                report_dir: Union[str, Path], parent=None):
        super().__init__(parent)
        self.excel_path = Path(excel_path) if excel_path else None
        self.docx_path = Path(docx_path) if docx_path else None
        self.report_dir = Path(report_dir)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Reports Generated")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Report directory info
        dir_label = QLabel("Reports saved to:")
        dir_path = QLabel(str(self.report_dir))
        dir_path.setWordWrap(True)
        dir_path.setStyleSheet("font-weight: bold;")
        
        layout.addWidget(dir_label)
        layout.addWidget(dir_path)
        layout.addSpacing(10)
        
        # Available reports section
        reports_group = QWidget()
        reports_layout = QVBoxLayout(reports_group)
        
        # Excel report
        if self.excel_path and self.excel_path.exists():
            excel_btn = QPushButton("Open Excel Report")
            excel_btn.clicked.connect(lambda: self.open_file(self.excel_path))
            reports_layout.addWidget(excel_btn)
        
        # Word report
        if self.docx_path and self.docx_path.exists():
            word_btn = QPushButton("Open Word Report")
            word_btn.clicked.connect(lambda: self.open_file(self.docx_path))
            reports_layout.addWidget(word_btn)
        
        layout.addWidget(reports_group)
        layout.addSpacing(10)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        open_folder_btn = QPushButton("Open Reports Folder")
        open_folder_btn.clicked.connect(self.open_folder)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(open_folder_btn)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)

    def open_folder(self):
        """Open folder containing the reports"""
        try:
            if sys.platform == 'win32':
                os.startfile(self.report_dir)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(self.report_dir)])
            else:  # linux
                subprocess.run(['xdg-open', str(self.report_dir)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open folder: {str(e)}")

    def open_file(self, file_path: Path):
        """Open a specific report file"""
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(file_path)])
            else:  # linux
                subprocess.run(['xdg-open', str(file_path)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open file: {str(e)}")   

class SignalHandler:
    """Handler to bridge logging to GUI signals"""
    def __init__(self, signal):
        self.signal = signal

    def emit(self, message):
        self.signal.emit(message)

    def write(self, message):
        if message.strip():  # Ignore empty messages
            self.signal.emit(message.strip())

    def flush(self):
        pass

class LogHandler(logging.Handler):
    """Custom logging handler emitting signals"""
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)

class ReportManager:
    """Manages report generation and organization"""
    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.report_dir = self.base_path / 'reports'
        self.report_dir.mkdir(exist_ok=True)
        
    def create_report(self, 
                     result_df: pd.DataFrame,
                     screenshots: Dict[str, str],
                     prefix: str = "") -> Path:
        """Creates a comprehensive report package"""
        try:
            timestamp = date.today().strftime('%d%m%Y_%H%M%S')
            report_name = f"{prefix}_report_{timestamp}" if prefix else f"report_{timestamp}"
            report_path = self.report_dir / f"{report_name}.xlsx"
            
            # Create a copy of the DataFrame to avoid modifying the original
            report_df = result_df.copy()
            
            # Add screenshot paths to DataFrame if they exist
            if screenshots:
                # Create a new column for screenshot paths, match by MST if it exists
                if 'MST' in report_df.columns:
                    report_df['screenshot_path'] = report_df['MST'].map(screenshots)
                else:
                    # If no MST column, add screenshots as a separate sheet
                    screenshot_df = pd.DataFrame(list(screenshots.items()), 
                                              columns=['MST', 'screenshot_path'])
            
            # Prepare summary data
            summary_data = {
                'Total Records': len(report_df),
                'Processing Date': timestamp,
            }
            
            # Add status distribution if status column exists
            if 'status' in report_df.columns:
                status_counts = report_df['status'].value_counts().to_dict()
                summary_data.update({f'Status - {k}': v for k, v in status_counts.items()})
            
            # Save to Excel with multiple sheets
            with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
                # Write main results
                report_df.to_excel(writer, sheet_name='Results', index=False)
                
                # Write summary sheet
                pd.DataFrame([summary_data]).to_excel(writer, sheet_name='Summary', index=False)
                
                # Write screenshots to separate sheet if they exist and weren't added to main df
                if screenshots and 'MST' not in report_df.columns:
                    screenshot_df.to_excel(writer, sheet_name='Screenshots', index=False)
            
            logging.info(f"Report created successfully at {report_path}")
            return report_path
            
        except Exception as e:
            logging.error(f"Failed to create report: {str(e)}")
            raise

class InvoiceProcessThread(QThread):
    """Worker thread for processing invoices"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)  # Changed to emit dict instead of DataFrame
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, mst_list: List[str], path: Union[str, Path], config: Dict[str, Any]):
        super().__init__()
        self.mst_list = mst_list
        self.path = Path(path)
        self.config = config
        self.signal_handler = SignalHandler(self.log)
        
        # Set up logging for this thread
        self.logger = logging.getLogger(f'InvoiceProcessThread_{id(self)}')
        self.logger.setLevel(logging.INFO)
        
        # Add signal handler
        handler = LogHandler(self.log)
        formatter = logging.Formatter('%(levelname)s | %(asctime)s | %(message)s',
                                    datefmt='%m/%d/%Y %I:%M:%S %p')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def run(self):
        try:
            from app.InvoiceChecker import InvoiceChecker
            
            # Create data directory with current date
            current_date = date.today()
            data_dir = self.path.joinpath('reports', current_date.strftime('%d_%m_%Y'))
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize checker with logger
            checker = InvoiceChecker(
                self.path, 
                data_dir, 
                self.config,
                self.signal_handler
            )
            
            # Process invoices
            self.logger.info("Starting invoice processing...")
            results = checker.process_invoices(self.mst_list)  # Now expects list of MSTs directly
            self.logger.info("Invoice processing completed")
            
            self.finished.emit(results)
            
        except Exception as e:
            self.logger.error(f"Error occurred: {str(e)}")
            self.error.emit(str(e))

    def cleanup(self):
        """Clean up logging handlers"""
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()

class ReportDialog(QDialog):
    """Dialog showing report details with open folder option"""
    def __init__(self, report_path: Path, parent=None):
        super().__init__(parent)
        self.report_path = Path(report_path)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Report Generated")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Report path
        path_label = QLabel(f"Report saved to:\n{self.report_path}")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self.open_folder)
        
        open_file_btn = QPushButton("Open Report")
        open_file_btn.clicked.connect(self.open_file)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(open_folder_btn)
        button_layout.addWidget(open_file_btn)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)

    def open_folder(self):
        """Open folder containing the report"""
        try:
            if sys.platform == 'win32':
                os.startfile(self.report_path.parent)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(self.report_path.parent)])
            else:  # linux
                subprocess.run(['xdg-open', str(self.report_path.parent)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open folder: {str(e)}")

    def open_file(self):
        """Open the report file"""
        try:
            if sys.platform == 'win32':
                os.startfile(self.report_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(self.report_path)])
            else:  # linux
                subprocess.run(['xdg-open', str(self.report_path)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open report: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Invoice Checker")
        self.setMinimumSize(1000, 800)
        
        # Initialize variables
        self.path = Path(os.getcwd())
        self.mst_list: List[str] = []
        self.screenshots: Dict[str, str] = {}
        self.report_manager = ReportManager(self.path)
        self.setup_config()
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Create splitter for main layout and log
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Create upper widget for main content
        upper_widget = QWidget()
        layout = QVBoxLayout(upper_widget)
        
        # Create UI components
        self.create_input_section(layout)
        self.create_table(layout)
        self.create_buttons(layout)
        self.create_progress_section(layout)
        
        # Create log section
        self.create_log_section()
        
        # Add widgets to splitter
        splitter.addWidget(upper_widget)
        splitter.addWidget(self.log_widget)
        splitter.setSizes([700, 300])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Create menu bar and status bar
        self.create_menu()
        self.statusBar().showMessage("Ready")
        
        # Initialize processing thread
        self.process_thread = None

    def setup_config(self):
        """Load configuration from config.json"""
        config_path = self.path.joinpath('config.json')
        try:
            with open(config_path, 'r', encoding='UTF-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "headless": "True",
                "use_proxy": "False"
            }
            with open(config_path, 'w', encoding='UTF-8') as f:
                json.dump(self.config, f, indent=4)

    def create_input_section(self, layout: QVBoxLayout):
        """Create MST input section"""
        input_layout = QHBoxLayout()
        
        self.mst_input = QLineEdit()
        self.mst_input.setPlaceholderText("Enter MST...")
        self.mst_input.returnPressed.connect(self.add_mst)
        
        add_button = QPushButton("Add")
        add_button.clicked.connect(self.add_mst)
        
        import_button = QPushButton("Import Excel")
        import_button.clicked.connect(self.import_excel)
        
        input_layout.addWidget(self.mst_input)
        input_layout.addWidget(add_button)
        input_layout.addWidget(import_button)
        
        layout.addLayout(input_layout)

    def create_table(self, layout: QVBoxLayout):
        """Create MST list table"""
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["MST"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def create_buttons(self, layout: QVBoxLayout):
        """Create action buttons"""
        button_layout = QHBoxLayout()
        
        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self.clear_list)
        
        export_button = QPushButton("Export Excel")
        export_button.clicked.connect(self.export_excel)
        
        process_button = QPushButton("Start Processing")
        process_button.clicked.connect(self.start_processing)
        
        button_layout.addWidget(clear_button)
        button_layout.addWidget(export_button)
        button_layout.addWidget(process_button)
        
        layout.addLayout(button_layout)

    def create_progress_section(self, layout: QVBoxLayout):
        """Create progress section"""
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

    def create_log_section(self):
        """Create log display section"""
        self.log_widget = QWidget()
        log_layout = QVBoxLayout(self.log_widget)
        
        # Log header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Log Output")
        title_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(clear_log_btn)
        
        save_log_btn = QPushButton("Save Log")
        save_log_btn.clicked.connect(self.save_log)
        header_layout.addWidget(save_log_btn)
        
        log_layout.addLayout(header_layout)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #F8F9FA;
                font-family: Consolas, Monaco, monospace;
                font-size: 9pt;
            }
        """)
        log_layout.addWidget(self.log_text)

    def append_log(self, message: str):
        """Append message to log display"""
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        self.log_text.insertPlainText(message + '\n')
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_log(self):
        """Clear log display"""
        self.log_text.clear()

    def save_log(self):
        """Save log contents to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log File",
            "",
            "Log Files (*.log);;Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Success", "Log saved successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save log: {str(e)}")

    def create_menu(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        import_action = QAction("Import Excel", self)
        import_action.triggered.connect(self.import_excel)
        file_menu.addAction(import_action)
        
        export_action = QAction("Export Excel", self)
        export_action.triggered.connect(self.export_excel)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def add_mst(self):
        """Add MST to the list"""
        mst = self.mst_input.text().strip()
        if mst and mst not in self.mst_list:
            self.mst_list.append(mst)
            self.update_table()
            self.mst_input.clear()
            self.statusBar().showMessage(f"Added MST: {mst}")

    def update_table(self):
        """Update table with current MST list"""
        self.table.setRowCount(len(self.mst_list))
        for i, mst in enumerate(self.mst_list):
            item = QTableWidgetItem(mst)
            self.table.setItem(i, 0, item)

    def clear_list(self):
        """Clear MST list and table"""
        reply = QMessageBox.question(
            self, 
            'Confirm Clear',
            'Are you sure you want to clear all entries?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.mst_list.clear()
            self.screenshots.clear()
            self.table.setRowCount(0)
            self.statusBar().showMessage("Cleared all entries")

    def import_excel(self):
        """Import MST list from Excel file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Excel File",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        
        if file_path:
            try:
                df = pd.read_excel(file_path)
                if 'MST' not in df.columns:
                    raise ValueError("Excel file must contain 'MST' column")
                
                # Convert MST values to strings and remove duplicates
                new_mst_list = df['MST'].astype(str).unique().tolist()
                
                # Add only new MST values
                added_count = 0
                for mst in new_mst_list:
                    if mst not in self.mst_list:
                        self.mst_list.append(mst)
                        added_count += 1
                
                self.update_table()
                self.statusBar().showMessage(f"Imported {added_count} new MST entries")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import Excel: {str(e)}")

    def export_excel(self):
        """Export MST list to Excel file"""
        if not self.mst_list:
            QMessageBox.warning(self, "Warning", "No MST entries to export")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel File",
            "",
            "Excel Files (*.xlsx);;All Files (*.*)"
        )
        
        if file_path:
            try:
                df = pd.DataFrame({'MST': self.mst_list})
                df.to_excel(file_path, index=False)
                self.statusBar().showMessage(f"Exported {len(self.mst_list)} MST entries")
                
                reply = QMessageBox.question(
                    self,
                    "Success",
                    "MST list exported successfully. Would you like to open the file?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.open_file(Path(file_path))
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export Excel: {str(e)}")

    def start_processing(self):
        """Start processing MST list"""
        if not self.mst_list:
            QMessageBox.warning(self, "Warning", "No MST entries to process")
            return
            
        if self.process_thread and self.process_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Processing already in progress")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Processing",
            f"Start processing {len(self.mst_list)} MST entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Clear previous results
            self.clear_log()
            self.screenshots.clear()
            
            # Initialize and start processing thread
            self.process_thread = InvoiceProcessThread(self.mst_list, self.path, self.config)
            self.process_thread.progress.connect(self.update_progress)
            self.process_thread.status.connect(self.update_status)
            self.process_thread.finished.connect(self.processing_finished)
            self.process_thread.error.connect(self.processing_error)
            self.process_thread.log.connect(self.append_log)
            
            self.process_thread.start()
            self.status_label.setText("Processing...")
            self.progress_bar.setMaximum(len(self.mst_list))
            self.append_log(f"Started processing {len(self.mst_list)} MST entries...")
            self.statusBar().showMessage("Processing in progress...")

    def update_progress(self, value: int):
        """Update progress bar value"""
        self.progress_bar.setValue(value)

    def update_status(self, message: str):
        """Update status label and status bar"""
        self.status_label.setText(message)
        self.statusBar().showMessage(message)

    def processing_finished(self, results: Dict[str, Any]):
        """Handle processing completion with Excel and Word reports"""
        try:
            # Extract results from the dictionary
            result_df = results.get('result_df', pd.DataFrame())
            screenshots = results.get('screenshots', {})
            
            if result_df.empty:
                raise ValueError("No results received from processing")
            
            # Create timestamp directory for reports
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_dir = self.path.joinpath('reports', timestamp)
            report_dir.mkdir(parents=True, exist_ok=True)
            
            # Save Excel report
            excel_path = report_dir.joinpath(f'report_{timestamp}.xlsx')
            result_df.to_excel(excel_path, index=False)
            
            # Initialize DocxReportGenerator and create Word report
            from app.DocxReportGenerator import DocxReportGenerator
            docx_generator = DocxReportGenerator(report_dir)
            
            try:
                # Pass result_df and screenshots separately
                docx_path = docx_generator.create_docx_report(
                    result_df=result_df,
                    screenshots=screenshots,
                    title="Invoice Check Report"
                )
                self.append_log(f"Created Word report at: {docx_path}")
            except Exception as e:
                self.append_log(f"Warning: Failed to create Word report: {str(e)}")
                docx_path = None
            
            self.status_label.setText("Processing completed")
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.statusBar().showMessage("Processing completed successfully")
            
            # Log results summary
            self.append_log(f"Processing completed. Total records: {len(result_df)}")
            self.append_log(f"Reports directory: {report_dir}")
            
            # Show enhanced report dialog
            dialog = EnhancedReportDialog(excel_path, docx_path, report_dir, self)
            dialog.exec()
            
        except Exception as e:
            error_msg = f"Failed to create reports: {str(e)}"
            logging.error(error_msg)
            self.processing_error(error_msg)
            
    def update_screenshots(self, mst: str, screenshot_path: str):
        """Update screenshots dictionary"""
        if screenshot_path and Path(screenshot_path).exists():
            self.screenshots[mst] = screenshot_path
            logging.info(f"Added screenshot for MST {mst}: {screenshot_path}")

    def processing_error(self, error_message: str):
        """Handle processing error"""
        self.status_label.setText("Error occurred")
        self.statusBar().showMessage("Processing failed")
        QMessageBox.critical(self, "Error", f"Processing failed: {error_message}")

    def show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()   
         

    @staticmethod
    def open_file(file_path: Path):
        """Open a file using the system default application"""
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(file_path)])
            else:  # linux
                subprocess.run(['xdg-open', str(file_path)])
        except Exception as e:
            logging.error(f"Failed to open file: {str(e)}")
            raise

def main():
    """Application entry point"""
    try:
        # Setup logging
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s | %(asctime)s | %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p',
            handlers=[
                logging.FileHandler(log_dir / f"app_{date.today().strftime('%Y_%m_%d')}.log"),
                logging.StreamHandler()
            ]
        )
        
        # Create and run application
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        logging.error(f"Application error: {str(e)}")
        raise

if __name__ == '__main__':
    main()