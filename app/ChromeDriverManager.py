from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException
from pathlib import Path
import logging
import time
import json
from typing import Optional, Union, Any, Dict

class ChromeDriverManager:
    """Manages Chrome WebDriver instances with configurable options."""
    
    DEFAULT_WINDOW_SIZE = "1920,1080"
    DEFAULT_TIMEOUT = 10
    
    def __init__(self, 
                 is_headless: bool = True, 
                 path: Path = None, 
                 download_dir: Union[str, Path] = None,
                 config: Dict = None):
        """
        Initialize ChromeDriverManager with configuration options.
        
        Args:
            is_headless: Whether to run Chrome in headless mode
            path: Base path for Chrome binary and driver
            download_dir: Directory for downloaded files
            config: Additional configuration options
        """
        self.is_headless = is_headless
        self.path = Path(path) if path else Path.cwd()
        self.download_dir = str(Path(download_dir)) if download_dir else str(self.path / 'downloads')
        self.config = config or {}
        self.driver: Optional[webdriver.Chrome] = None
        self.wait_timeout = self.config.get('wait_timeout', self.DEFAULT_TIMEOUT)

    def __enter__(self) -> webdriver.Chrome:
        """Context manager entry point."""
        self.driver = self.create_driver()
        return self.driver

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point with proper cleanup."""
        self._cleanup_driver()

    def _cleanup_driver(self):
        """Safely quit the driver instance."""
        try:
            if self.driver:
                self.driver.quit()
        except WebDriverException as e:
            logging.warning(f"Error while closing driver: {e}")
        finally:
            self.driver = None

    def create_driver(self) -> webdriver.Chrome:
        """Create and configure a new Chrome WebDriver instance."""
        try:
            driver_path = self.path / 'bin' / 'driver' / 'chromedriver.exe'
            chrome_binary = self.path / 'bin' / 'chromium' / 'chrome.exe'
            
            options = self._configure_chrome_options(chrome_binary)
            service = Service(executable_path=str(driver_path))
            
            driver = webdriver.Chrome(service=service, options=options)
            self._configure_download_behavior(driver)
            
            return driver
            
        except Exception as e:
            logging.error(f"Failed to create WebDriver: {e}")
            raise

    def _configure_chrome_options(self, chrome_binary: Path) -> Options:
        """Configure Chrome options with optimal settings."""
        options = Options()
        options.binary_location = str(chrome_binary)

        # Headless configuration
        if self.is_headless:
            options.add_argument("--headless=new")

        # Standard arguments
        options.add_argument(f"--window-size={self.DEFAULT_WINDOW_SIZE}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControllered")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")

        # Download preferences
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
        
        # Add proxy if configured
        if self.config.get('use_proxy') == "True":
            self._setup_proxy(options)

        return options

    def _configure_download_behavior(self, driver: webdriver.Chrome):
        """Configure Chrome download behavior."""
        try:
            driver.command_executor._commands["send_command"] = (
                "POST", '/session/$sessionId/chromium/send_command'
            )
            params = {
                'cmd': 'Page.setDownloadBehavior',
                'params': {'behavior': 'allow', 'downloadPath': self.download_dir}
            }
            driver.execute("send_command", params)
            driver.implicitly_wait(self.wait_timeout)
        except Exception as e:
            logging.error(f"Failed to configure download behavior: {e}")
            raise

    def _setup_proxy(self, options: Options):
        """Setup proxy configuration if enabled."""
        ext_path = self.path / 'bin' / 'chromium' / 'Extensions'
        proxy_config = {
            'username': self.config.get('proxy_username'),
            'password': self.config.get('proxy_password'),
            'host': self.config.get('proxy_address'),
            'port': self.config.get('proxy_port')
        }
        
        self._create_proxy_extension(ext_path, proxy_config)
        options.add_argument(f"--load-extension={ext_path}")

    @staticmethod
    def _create_proxy_extension(ext_path: Path, proxy_config: dict):
        """Create proxy extension files with proper configuration."""
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

    @staticmethod
    def wait_for_downloads(directory: Union[str, Path], timeout: int = 300) -> bool:
        """
        Wait for downloads to complete in the specified directory.
        
        Args:
            directory: Download directory path
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if downloads completed, False if timeout reached
        """
        directory = Path(directory)
        end_time = time.time() + timeout

        while time.time() < end_time:
            if not any(f.suffix == '.crdownload' for f in directory.glob('*')):
                return True
            time.sleep(1)

        return False

    def wait_for_element(
        self, 
        by: By, 
        value: str, 
        timeout: Optional[int] = None,
        condition: Any = EC.presence_of_element_located
    ) -> Any:
        """
        Wait for element with explicit wait and proper error handling.
        
        Args:
            by: Selenium By locator
            value: Element identifier
            timeout: Wait timeout in seconds
            condition: Expected condition to wait for
            
        Returns:
            The found element
            
        Raises:
            TimeoutException: If element is not found within timeout
        """
        timeout = timeout or self.wait_timeout
        try:
            return WebDriverWait(self.driver, timeout).until(
                condition((by, value))
            )
        except TimeoutException as e:
            raise TimeoutException(
                f"Element {value} not found after {timeout} seconds"
            ) from e