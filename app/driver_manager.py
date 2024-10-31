from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from pathlib import Path
import logging
from typing import Optional, Union
import time

class ChromeDriverManager:
    def __init__(self, isHeadless: True, path: Path, download_dir: Union[str, Path]):
        self.isHeadless = isHeadless
        self.path = path
        self.download_dir = str(Path(download_dir))
        self.driver: Optional[webdriver.Chrome] = None
        
    def __enter__(self) -> webdriver.Chrome:
        self.driver = self.create_driver()
        return self.driver
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
            
    def create_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver."""
        try:
             
            driver_path = self.path / 'bin' / 'driver' / 'chromedriver.exe'
            chrome_binary = self.path / 'bin' / 'chromium' / 'chrome.exe'
            
            options = self._configure_chrome_options(chrome_binary)
            driver = webdriver.Chrome(
                service=Service(executable_path=str(driver_path)),
                options=options
            )
            
            self._configure_download_behavior(driver)
            return driver
            
        except Exception as e:
            logging.error(f"Failed to create WebDriver: {str(e)}")
            raise
    
    def _configure_chrome_options(self, chrome_binary: Path) -> Options:
        """Configure Chrome options."""
        options = Options()
        options.binary_location = str(chrome_binary)
        
        if self.isHeadless:
            options.add_argument("--headless")
            options.add_argument("--headless=new")
        
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControllered")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "download_restrictions": 0,
            'safebrowsing.enabled': False,
            'safebrowsing.disable_download_protection': True
        }
        
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        return options
    
    def _configure_download_behavior(self, driver: webdriver.Chrome):
        """Configure download behavior for Chrome."""
        driver.command_executor._commands["send_command"] = (
            "POST", '/session/$sessionId/chromium/send_command'
        )
        params = {
            'cmd': 'Page.setDownloadBehavior',
            'params': {'behavior': 'allow', 'downloadPath': self.download_dir}
        }
        driver.execute("send_command", params)
        driver.implicitly_wait(10)

    @staticmethod
    def wait_for_downloads(directory: Union[str, Path], timeout: int = 300) -> bool:
        """Wait for downloads to complete."""
        directory = Path(directory)
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            if any(f.suffix == '.crdownload' for f in directory.glob('*')):
                time.sleep(1)
                continue
            return True
            
        return False