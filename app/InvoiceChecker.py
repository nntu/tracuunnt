# -*- coding: utf8 -*-
import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from typing import Dict
import base64
import re
import time
 
 
from PIL import Image
import urllib

from app.utils.downloadCaptcha import downloadCaptcha
class InvoiceChecker:
    """Optimized system for checking and processing invoices."""
    
    def __init__(self, path: str, data_dir: str, config: dict):
        self.path = path
        self.data_dir = data_dir
        self.config = config
        self.wait_timeout = 20
        self.max_retries = 3
        self.browser = None
        
        # Configure logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging with proper format and file handling."""
        log_dir = Path(self.path) / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'log_{datetime.now().strftime("%Y_%m_%d")}.log'
        logging.basicConfig(
            filename=log_file,
            format='%(levelname)s | %(asctime)s | %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p',
            level=logging.INFO,
            encoding="utf-8"
        )
    
    def _init_chrome_options(self) -> Options:
        """Initialize Chrome options with optimal settings."""
        chrome_options = Options()
        chrome_options.binary_location = str(Path(self.path) / 'bin' / 'chromium' / 'chrome.exe')
        
        # Clear and setup extensions if using proxy
        if self.config.get('use_proxy') == "True":
            ext_path = Path(self.path) / 'bin' / 'chromium' / 'Extensions'
            self._setup_proxy_extension(ext_path)
            chrome_options.add_argument(f"--load-extension={ext_path}")
        
        # Add standard options
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument("--disable-blink-features=AutomationControllered")
        chrome_options.add_argument('--disable-gpu')
        
        if self.config.get('headless') == "True":
            chrome_options.add_argument("--headless=new")
        
        # Add experimental options
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("prefs", self._get_chrome_prefs())
        
        return chrome_options
    
    def _get_chrome_prefs(self) -> dict:
        """Get Chrome preferences configuration."""
        return {
            "profile.default_content_setting_values.notifications": 2,
            "download.default_directory": self.data_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "download_restrictions": 0,
            'safebrowsing.enabled': False,
            'safebrowsing.disable_download_protection': True
        }
    
    def _setup_proxy_extension(self, ext_path: Path) -> None:
        """Setup proxy extension if enabled."""
        # Clear existing extension files
        for f in ext_path.glob("*"):
            if f.is_file():
                f.unlink()
        
        # Create new proxy extension
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
        with open(ext_path / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        with open(ext_path / "service-worker.js", "w") as f:
            f.write(worker_js)
    
    def init_driver(self) -> webdriver.Chrome:
        """Initialize and configure Chrome WebDriver."""
        chrome_options = self._init_chrome_options()
        driver_path = Path(self.path) / 'bin' / 'driver' / 'chromedriver.exe'
        
        driver = webdriver.Chrome(
            service=Service(executable_path=str(driver_path)),
            options=chrome_options
        )
        
        # Configure download behavior
        driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
        params = {
            'cmd': 'Page.setDownloadBehavior',
            'params': {'behavior': 'allow', 'downloadPath': self.data_dir}
        }
        driver.execute("send_command", params)
        driver.implicitly_wait(10)
        
        return driver
    
    def process_invoice_row(self, row: pd.Series) -> Dict:
        """Process a single invoice row."""
        try:
            # Prepare invoice data
            mst = row['MST']
            
            
            # Fill form fields
            self._fill_form_safely('mst', mst)
             
            
            # Handle captcha and get result
            self._handle_captcha()
            time.sleep(5)
            
            result = self._wait_for_result()
            
            # Take screenshot
            screenshot_path = self._take_screenshot(row)
            
            return {
                'result': result,
                'analysis': self._parse_invoice_data(result),
                'screenshot': screenshot_path
            }
            
        except Exception as e:
            logging.error(f"Error processing invoice {row['MST']}: {str(e)}")
            return {'error': str(e)}
    
    def _fill_form_safely(self, element_id: str, value: str, clear_first: bool = True) -> None:
        """Safely fill a form field with retry logic."""
        for attempt in range(self.max_retries):
            try:
                element = WebDriverWait(self.browser, self.wait_timeout).until(
                    EC.presence_of_element_located((By.NAME, element_id))
                )
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
        """Handle captcha solving with retry logic."""
        captcha_xpath = '//*[@id="tcmst"]/form/table/tbody/tr[6]/td[2]/table/tbody/tr/td[2]/div/img'
        capcha_dir = Path(self.path) / "captcha"
        capcha_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(self.max_retries):
            try:
                img_element = WebDriverWait(self.browser, self.wait_timeout).until(
                    EC.presence_of_element_located((By.XPATH, captcha_xpath))
                )
                
                img_file = img_element.get_attribute("src") 
                
                logging.info(img_file)
                capfile =  downloadCaptcha(capcha_dir,img_file)
                logging.info(capfile)
    
                
                # solved_captcha = solve_captcha(base64.b64decode(base64_svg))
                
                # captcha_input = WebDriverWait(self.browser, self.wait_timeout).until(
                #     EC.presence_of_element_located((By.ID, 'captcha'))
                # )
                # captcha_input.clear()
                # captcha_input.send_keys(solved_captcha)
                # captcha_input.send_keys(Keys.RETURN)
                return
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise Exception(f"Failed to solve captcha: {str(e)}")
    
    def _wait_for_result(self) -> str:
        """Wait for and return the result text."""
        try:
            result_xpath = '//*[@id="__next"]/section/main/section/div/div/div/div/div[3]/div[1]/div[2]/div[2]/section'
            result_element = WebDriverWait(self.browser, self.wait_timeout).until(
                EC.presence_of_element_located((By.XPATH, result_xpath))
            )
            return result_element.text
        except TimeoutException:
            raise Exception("Timeout waiting for result")
    
    def _take_screenshot(self, row: pd.Series) -> str:
        """Take and save screenshot."""
        screenshot_path = Path(self.data_dir) / f"{row['Mã số thuế NCC']}_{row['Số hóa đơn']}_{datetime.now().strftime('%d%m%Y')}.png"
        self.browser.save_screenshot(str(screenshot_path))
        return str(screenshot_path)
    
    @staticmethod
    def _parse_invoice_data(text: str) -> Dict:
        """Parse invoice result text into structured data."""
        if not text.strip():
            return {}
            
        invoice = {}
        invoice['Tồn tại hóa đơn'] = "Tồn tại hóa đơn" in text
        
        patterns = {
            'Trạng thái xử lý hoá đơn': r"Trạng thái xử lý hoá đơn: (.+)",
            'Trạng thái hóa đơn': r"Trạng thái hóa đơn: (.+)",
            'Thay thế cho hóa đơn': r"Thay thế cho hóa đơn (.+)"
        }
        
        for key, pattern in patterns.items():
            if match := re.search(pattern, text):
                invoice[key] = match.group(1).strip()
                
        return invoice
    
    def process_invoices(self, excel_path: str) -> pd.DataFrame:
        """Process all invoices from Excel file."""
        try:
            # Initialize browser
            self.browser = self.init_driver()
            self.browser.get('https://tracuunnt.gdt.gov.vn/tcnnt/mstdn.jsp')
            time.sleep(5)
            # Handle initial popup if present
            
            
            # Read and process Excel file
            df = pd.read_excel(
                excel_path,
                dtype={'MST': str} 
            )
           
            
            # Process each row
            for idx, row in df.iterrows():
                result = self.process_invoice_row(row)
                
                if 'error' in result:
                    df.loc[idx, 'noidung'] = f"Error: {result['error']}"
                else:
                    df.loc[idx, 'noidung'] = result['result']
                    for key, value in result['analysis'].items():
                        df.loc[idx, key] = value
                    df.loc[idx, 'screenshot'] = result['screenshot']
            
            return df
            
        finally:
            if self.browser:
                self.browser.quit()
    
    def create_report(self, df: pd.DataFrame ) -> Path:
        """Create Excel and Word reports from processed data."""
        timestamp = datetime.now().strftime('%d%m%Y_%H%M%S')
        report_dir = Path(self.path) / 'reports'
        report_dir.mkdir(exist_ok=True)
        
        return report_dir
    
    def run(self,filename = "template.xlsx") -> None:
        """Main execution method."""
        try:
            template_path = Path(filename)  
            if not template_path.exists():
                raise FileNotFoundError("Template Excel file not found")
            
            # Process invoices and generate reports
            df = self.process_invoices(str(template_path))
            self.create_report(df)
            
            logging.info("Invoice processing completed successfully")
            
        except Exception as e:
            logging.error(f"Error during execution: {str(e)}")
            raise