from docx import Document
from docx.shared import Inches, Cm
from docx.enum.section import WD_ORIENTATION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List
from PIL import Image

class DocxReportGenerator:
    """Generates Word document reports with screenshots"""
    
    def __init__(self, save_dir: Path):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
    def create_docx_report(self, 
                          result_data: Dict[str, any],                          
                          title: str = "Invoice Check Report") -> Dict[str, Path]:
        """
        Creates a Word document with results and screenshots
        
        Args:
            result_data: Dictionary containing result_df and screenshots
            title: Title for the report
            
        Returns:
            Dictionary containing paths to generated reports
        """
        try:
            # Extract data from result dictionary
            result_df = result_data.get('result_df', pd.DataFrame())
            screenshots = result_data.get('screenshots', {})
            
            # Create new document
            doc = Document()
            
            # Set landscape orientation for all sections
            section = doc.sections[0]
            section.orientation = WD_ORIENTATION.LANDSCAPE
            section.page_width, section.page_height = section.page_height, section.page_width
            
            # Add title
            title_paragraph = doc.add_paragraph()
            title_run = title_paragraph.add_run(title)
            title_run.font.size = Pt(16)
            title_run.font.bold = True
            title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Add datetime
            date_paragraph = doc.add_paragraph()
            date_run = date_paragraph.add_run(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            date_run.font.size = Pt(10)
            date_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Add summary table if available
            if not result_df.empty:
                doc.add_paragraph("\nSummary:", style='Heading 1')
                summary_table = doc.add_table(rows=1, cols=2)
                summary_table.style = 'Table Grid'
                header_cells = summary_table.rows[0].cells
                header_cells[0].text = 'Metric'
                header_cells[1].text = 'Value'
                
                # Add summary rows
                summary_data = {
                    'Total Records': len(result_df),
                    'Total Screenshots': len(screenshots),
                    'Processing Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                for key, value in summary_data.items():
                    row_cells = summary_table.add_row().cells
                    row_cells[0].text = key
                    row_cells[1].text = str(value)
            
            # Add each MST's info and screenshot
            for mst, screenshot_path in screenshots.items():
                if Path(screenshot_path).exists():
                    # Add MST header
                    doc.add_paragraph()  # Add spacing
                    mst_paragraph = doc.add_paragraph()
                    mst_run = mst_paragraph.add_run(f"MST: {mst}")
                    mst_run.font.bold = True
                    mst_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    
                    # Add MST information from result_df
                    if not result_df.empty and 'MST' in result_df.columns:
                        mst_info = result_df[result_df['MST'] == mst]
                        if not mst_info.empty:
                            info_table = doc.add_table(rows=1, cols=2)
                            info_table.style = 'Table Grid'
                            
                            # Add each column as a row in the table
                            for col in mst_info.columns:
                                if col != 'MST':  # Skip MST since we already show it in header
                                    row_cells = info_table.add_row().cells
                                    row_cells[0].text = str(col)
                                    row_cells[1].text = str(mst_info[col].iloc[0])
                            
                            # Add spacing after table
                            doc.add_paragraph()
                    
                    # Get image dimensions
                    with Image.open(screenshot_path) as img:
                        width, height = img.size
                    
                    # Calculate scaled dimensions to fit page
                    max_width = Inches(9)  # Landscape A4 width margin
                    max_height = Inches(6)  # Landscape A4 height margin
                    
                    # Calculate scaling factor
                    width_scale = max_width / width
                    height_scale = max_height / height
                    scale = min(width_scale, height_scale)
                    
                    # Add image paragraph
                    image_paragraph = doc.add_paragraph()
                    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    image_run = image_paragraph.add_run()
                    image_run.add_picture(
                        screenshot_path,
                        width=int(width * scale),
                        height=int(height * scale)
                    )
                    
                    # Add page break
                    doc.add_page_break()
            
            # Save documents
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save Word document
            docx_path = self.save_dir / f"report_{timestamp}.docx"
            doc.save(str(docx_path))
            
           
            
            logging.info(f"Created reports at: {self.save_dir}")
            
            return {
                'docx_path': docx_path,
               
                'screenshots': screenshots,
                'result_df': result_df
            }
            
        except Exception as e:
            logging.error(f"Failed to create reports: {str(e)}")
            raise

    def create_combined_report(self, result_data: Dict[str, any]) -> Dict[str, Path]:
        """
        Creates both Word and Excel reports in one go
        
        Args:
            result_data: Dictionary containing result_df and screenshots
            
        Returns:
            Dictionary containing paths to all generated reports
        """
        try:
            return self.create_docx_report(result_data)
        except Exception as e:
            logging.error(f"Failed to create combined reports: {str(e)}")
            raise