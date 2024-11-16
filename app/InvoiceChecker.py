# -*- coding: utf8 -*-
from __future__ import annotations
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

import pandas as pd
from PIL import Image
from Screenshot import Screenshot
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    StaleElementReferenceException,
    WebDriverException
)

from app.DocxReportGenerator import DocxReportGenerator
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
        self._setup_logging()

    def _setup_logging(self, level: int = logging.INFO) -> None:
        """Configure logging with proper format and file handling."""
        log_dir = self.path.joinpath('logs')
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir.joinpath(f'log_{datetime.now().strftime("%Y_%m_%d")}.log')
        formatter = logging.Formatter(
            '%(levelname)s | %(asctime)s | %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p'
        )
        
        logger = logging.getLogger()
        logger.setLevel(level)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Add handlers with proper formatting
        handlers = [
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler()
        ]
        
        if self.signal_handler:
            handlers.append(logging.StreamHandler(self.signal_handler))
        
        for handler in handlers:
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    def log_info(self, message: str) -> None:
        """Helper method to log info messages with signal handling."""
        logging.info(message)
        if self.signal_handler:
            timestamp = datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')
            self.signal_handler.emit(f"INFO | {timestamp} | {message}")

    def _init_chrome_options(self) -> Options:
        """Initialize Chrome options with optimal settings."""
        chrome_options = Options()
        chrome_binary = self.path.joinpath('bin', 'chromium', 'chrome.exe')
        chrome_options.binary_location = str(chrome_binary)
        
        if self.config.get('use_proxy') == "True":
            ext_path = self.path.joinpath('bin', 'chromium', 'Extensions')
            self._setup_proxy_extension(ext_path)
            chrome_options.add_argument(f"--load-extension={ext_path}")
        
        # Standard options
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument("--disable-blink-features=AutomationControllered")
        chrome_options.add_argument('--disable-gpu')
        
        if self.config.get('headless') == "True":
            chrome_options.add_argument("--headless=new")
        
        # Experimental options
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "download.default_directory": str(self.data_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "download_restrictions": 0,
            'safebrowsing.enabled': False,
            'safebrowsing.disable_download_protection': True
        })
        
        return chrome_options

    def _setup_proxy_extension(self, ext_path: Path) -> None:
        """Setup proxy extension if enabled."""
        if ext_path.exists():
            for f in ext_path.glob("*"):
                if f.is_file():
                    f.unlink()
        
        proxy_config = {
            'username': self.config.get('proxy_username'),
            'password': self.config.get('proxy_password'),
            'host': self.config.get('proxy_address'),
            'port': self.config.get('proxy_port')
        }
        
        self._create_proxy_extension(ext_path, proxy_config)

    @staticmethod
    def _create_proxy_extension(ext_path: Path, proxy_config: dict) -> None:
        """Create proxy extension files."""
        manifest = {
            "version": "1.0.0",
            "manifest_version": 3,
            "name": "Chrome Proxy",
            "permissions": ["proxy", "webRequest", "webRequestAuthProvider"],
            "host_permissions": ["<all_urls>"],
            "background": {"service_worker": "service-worker.js"},
            "minimum_chrome_version": "108"
        }
        
        worker_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{proxy_config['host']}",
                    port: {proxy_config['port']}
                }},
                bypassList: ["localhost"]
            }}
        }};
        
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        
        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{proxy_config['username']}",
                    password: "{proxy_config['password']}"
                }}
            }};
        }}
        
        chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """
        
        ext_path.mkdir(parents=True, exist_ok=True)
        with open(ext_path.joinpath("manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        with open(ext_path.joinpath("service-worker.js"), "w") as f:
            f.write(worker_js)

    @contextmanager
    def _browser_context(self):
        """Context manager for browser initialization and cleanup."""
        browser = None
        try:
            chrome_options = self._init_chrome_options()
            driver_path = self.path.joinpath('bin', 'driver', 'chromedriver.exe')
            
            browser = webdriver.Chrome(
                service=Service(executable_path=str(driver_path)),
                options=chrome_options
            )
            
            # Configure download behavior
            browser.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
            params = {
                'cmd': 'Page.setDownloadBehavior',
                'params': {'behavior': 'allow', 'downloadPath': str(self.data_dir)}
            }
            browser.execute("send_command", params)
            browser.implicitly_wait(10)
            
            yield browser
            
        finally:
            if browser:
                try:
                    browser.quit()
                except WebDriverException:
                    pass

    def _wait_for_element(
        self, 
        by: By, 
        value: str, 
        timeout: Optional[int] = None,
        condition: Any = EC.presence_of_element_located
    ) -> Any:
        """Wait for element with explicit wait and proper error handling."""
        timeout = timeout or self.wait_timeout
        try:
            return WebDriverWait(self.browser, timeout).until(
                condition((by, value))
            )
        except TimeoutException as e:
            raise TimeoutException(f"Element {value} not found after {timeout} seconds") from e

    def process_invoice_row(self, mst: str) -> Dict:
        """Process a single invoice row with improved error handling."""
        try:
            self._fill_form_safely('mst', mst)
            self._handle_captcha()
            
            # Wait for and get result
            result = self._wait_for_result()
            
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
        captcha_xpath = '//*[@id="tcmst"]/form/table/tbody/tr[6]/td[2]/table/tbody/tr/td[2]/div/img'
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

    def _wait_for_result(self) -> pd.DataFrame:
        """Wait for and parse result table."""
        try:
            result_element = self._wait_for_element(
                By.CLASS_NAME, 
                "ta_border",
                timeout=5
            )
            result_html = result_element.get_attribute("outerHTML")
            
            if "<table class" in result_html:
                df = pd.read_html(io.StringIO(result_html))[0]
                return df.iloc[:-1, :]  # Remove last row
                
        except TimeoutException as e:
            raise TimeoutException("Timeout waiting for result table") from e
        except Exception as e:
            raise Exception(f"Error parsing result table: {str(e)}") from e

    def _take_screenshot(self, mst: str) -> str:
        """Take and save full page screenshot."""
        screenshot = Screenshot.Screenshot()
        screenshot_dir = self.data_dir.joinpath("screenshot")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%d%m%Y')
        filename = f"{mst}_{timestamp}.png"
        
        return str(screenshot.full_screenshot(
            self.browser,
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
        
        with self._browser_context() as browser:
            self.browser = browser
            self.browser.get('https://tracuunnt.gdt.gov.vn/tcnnt/mstdn.jsp')
            self._wait_for_element(By.NAME, 'mst')  # Wait for page load
            
            for idx, mst in enumerate(mst_list, 1):
                try:
                    result = self.process_invoice_row(mst)
                    
                    if 'error' in result:
                        logging.error(f"Error processing MST {mst}: {result['error']}")
                    else:
                        results.append(result['result'])
                        screenshots[mst] = result['screenshot']
                        
                    self.log_info(f"Processed {idx}/{total} MSTs")
                    
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
                result_data=df,
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
            self.log_info("Invoice processing completed successfully")
            
        except Exception as e:
            logging.error(f"Error during execution: {str(e)}")
            raise