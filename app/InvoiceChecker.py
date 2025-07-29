# -*- coding: utf8 -*-
from __future__ import annotations
import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from PIL import Image
from Screenshot import Screenshot
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    StaleElementReferenceException
)

from app.DocxReportGenerator import DocxReportGenerator
from app.ChromeDriverManager import ChromeDriverManager
from check_re import CaptchaPredictor

class InvoiceChecker:
    """Optimized system for checking and processing invoices."""
    
    def __init__(
        self, 
        path: str | Path, 
        data_dir: str | Path, 
        config: dict,
        signal_handler: Optional[Any] = None,
        wait_timeout: int = 20,
        max_retries: int = 3,
        max_captcha_attempts: int = 5
    ):
        self.path = Path(path)
        self.data_dir = Path(data_dir)
        self.config = config
        self.wait_timeout = wait_timeout
        self.max_retries = max_retries
        self.max_captcha_attempts = max_captcha_attempts
        self.predictor = CaptchaPredictor('captcha.keras')
        self.signal_handler = signal_handler
        self.driver_manager = ChromeDriverManager(
            is_headless=config.get('headless', True),
            path=self.path,
            download_dir=self.data_dir
        )
    
    

    def _wait_for_element(
        self, 
        by: By, 
        value: str, 
        timeout: Optional[int] = None,
        condition: Any = EC.presence_of_element_located
    ) -> Any:
        """Wait for element with explicit wait and proper error handling."""
        return self.driver_manager.wait_for_element(by, value, timeout, condition)

    def process_invoice_row(self, mst: str) -> Dict:
        """Process a single invoice row with improved error handling."""
        try:
            self._fill_form_safely('mst', mst)
            self._handle_captcha()
            
            # Wait for and get result
            """Wait for and parse result table."""
        
            result_element = self._wait_for_element(
                By.CLASS_NAME, 
                "ta_border",
                timeout=5
            )
            result_html = result_element.get_attribute("outerHTML")
            
            if "<table class" in result_html:
                df = pd.read_html(io.StringIO(result_html))[0]
              
                post_scr = """
                var table_html = ''
                $.post('tcnnt/nganhkinhdoanh.jsp', {tin: %s}, function(result){
                    table_html = result;
                });
                return table_html
                """ % (mst)                
                
                nganhnghe = self.driver_manager.execute_script(post_scr)
                
                logging.info(nganhnghe)
                 
                result =  df.iloc[:-1, :]  # Remove last row
                
        
            
            # Take screenshot
            screenshot_path = self._take_screenshot(mst)
            
            return {
                'result': result,
                'screenshot': screenshot_path
            }
            
        except Exception as e:
            logging.error(f"Error processing invoice {mst}: {str(e)}")
            return {'error': str(e)}

    def _fill_form_safely(self, element_id: str, value: str, clear_first: bool = True) -> None:
        """Safely fill a form field with retry logic."""
        for attempt in range(self.max_retries):
            try:
                element = self._wait_for_element(By.NAME, element_id)
                if clear_first:
                    element.clear()
                    element.send_keys(Keys.CONTROL, 'a')
                    element.send_keys(Keys.DELETE)
                element.send_keys(str(value))
                return
            except StaleElementReferenceException:
                if attempt == self.max_retries - 1:
                    raise

    def _handle_captcha(self) -> None:
        """Handle captcha solving with improved retry logic and error handling."""
        captcha_xpath = '/html/body/div/div[1]/div[4]/div[2]/div[2]/div/div/div[1]/form/table/tbody/tr[5]/td[2]/table/tbody/tr/td[2]/img'
        capcha_dir = self.path.joinpath("captcha")
        capcha_dir.mkdir(parents=True, exist_ok=True)
        
        for attempt in range(self.max_captcha_attempts):
            try:
                img_element = self._wait_for_element(By.XPATH, captcha_xpath)
                capfile = str(capcha_dir.joinpath(f"captcha_{attempt}.png"))
                
                # Save captcha image
                image_binary = img_element.screenshot_as_png
                img = Image.open(io.BytesIO(image_binary))
                img.save(capfile)
                
                # Predict captcha
                solved_captcha = self.predictor.predict(capfile)
                logging.info(f"Predicted captcha: {solved_captcha}")
                
                # Fill captcha
                captcha_input = self._wait_for_element(By.ID, 'captcha')
                captcha_input.clear()
                captcha_input.send_keys(solved_captcha)
                
                # Submit form
                submit_btn = self._wait_for_element(By.CLASS_NAME, "subBtn")
                submit_btn.click()
                
                # Check for error message
                try:
                    error_xpath = "/html/body/div/div[1]/div[4]/div[2]/div[2]/div/div/div/p"
                    error_element = self._wait_for_element(By.XPATH, error_xpath, timeout=5)
                    
                    if error_element.text == "Vui lòng nhập đúng mã xác nhận!":
                        self._move_failed_captcha(capfile, solved_captcha)
                        continue
                    
                except TimeoutException:
                    self._move_successful_captcha(capfile, solved_captcha)
                    return
                    
            except Exception as e:
                logging.error(f"Captcha attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_captcha_attempts - 1:
                    raise Exception(f"Failed to solve captcha after {self.max_captcha_attempts} attempts")

    def _move_failed_captcha(self, capfile: str, solved_captcha: str) -> None:
        """Move failed captcha to error directory."""
        capcha_error = self.path.joinpath("captcha", "capcha_error")
        capcha_error.mkdir(parents=True, exist_ok=True)
        new_path = capcha_error.joinpath(f'{solved_captcha}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
        os.replace(capfile, str(new_path))

    def _move_successful_captcha(self, capfile: str, solved_captcha: str) -> None:
        """Move successful captcha to success directory."""
        capcha_ok = self.path.joinpath("captcha", "capcha_ok")
        capcha_ok.mkdir(parents=True, exist_ok=True)
        new_path = capcha_ok.joinpath(f"{solved_captcha}.png")
        os.replace(capfile, str(new_path))

 

    def _take_screenshot(self, mst: str) -> str:
        """Take and save full page screenshot."""
        screenshot = Screenshot.Screenshot()
        screenshot_dir = self.data_dir.joinpath("screenshot")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%d%m%Y')
        filename = f"{mst}_{timestamp}.png"
        
        return str(screenshot.full_screenshot(
            self.driver_manager.driver,
            save_path=str(screenshot_dir),
            image_name=filename,
            is_load_at_runtime=True,
            load_wait_time=3
        ))

    def process_invoices(self, mst_list: List[str]) -> Dict[str, Any]:
        """Process multiple MST numbers with improved error handling and reporting."""
        results = []
        screenshots = {}
        total = len(mst_list)
        
        with self.driver_manager as driver:
            driver.get('https://tracuunnt.gdt.gov.vn/tcnnt/mstdn.jsp')
            self._wait_for_element(By.NAME, 'mst')  # Wait for page load
            
            for idx, mst in enumerate(mst_list, 1):
                try:
                    result = self.process_invoice_row(mst)
                    
                    if 'error' in result:
                        logging.error(f"Error processing MST {mst}: {result['error']}")
                    else:
                        results.append(result['result'])
                        screenshots[mst] = result['screenshot']
                        
                    logging.info(f"Processed {idx}/{total} MSTs")
                    
                except Exception as e:
                    logging.error(f"Failed to process MST {mst}: {str(e)}")
        
        # Combine results
        result_df = pd.concat(results, ignore_index=True, sort=False) if results else pd.DataFrame()
        
        # Add MST column if not present
        if 'MST' not in result_df.columns and not result_df.empty:
            result_df['MST'] = mst_list[:len(result_df)]
        
        return {
            'result_df': result_df,
            'screenshots': screenshots
        }

    def create_docx_report(self, df: pd.DataFrame) -> Path:
        """Create Word document report with screenshots."""
        try:
            docx_generator = DocxReportGenerator(str(self.data_dir))
            logging.info("Creating Word report...") 
            logging.info(f"DataFrame shape: {df.shape}")
            logging.info(f"DataFrame columns: {df.columns}")
            logging.info(f"DataFrame head:\n{df.head()}")
            return docx_generator.create_docx_report(
                df,
                title="Invoice Check Report"
            )
        except Exception as e:
            logging.error(f"Failed to create Word report: {str(e)}")
            raise

    def run(self, list_mst: List[str]) -> None:
        """Main execution method with improved error handling."""
        try:
            results = self.process_invoices(list_mst)
            self.create_docx_report(results['result_df'])
            logging.info("Invoice processing completed successfully")
            
        except Exception as e:
            logging.error(f"Error during execution: {str(e)}")
            raise