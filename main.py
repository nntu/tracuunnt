# -*- coding: utf8 -*-
import json
import logging
import os
from datetime import date
from pathlib import Path
from contextlib import contextmanager
 
from app.InvoiceChecker import InvoiceChecker
from app.utils.logging_config import setup_logging
def main():
    """Main entry point."""
    try:
        # Get current working directory and date
        path = os.getcwd()
        current_date = date.today()
        
        config_path = Path(path) / 'config.json'
        with open(config_path, 'r', encoding='UTF-8') as f:
            config = json.load(f)
        
        setup_logging(Path(path) /"logs")
        # Create data directory
        data_dir = Path(path) / 'reports' / current_date.strftime('%d_%m_%Y')
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize and run invoice checker
        checker = InvoiceChecker(path, str(data_dir), config)
        list_mst = {'0100150619-041','0100150619-052'}
        
        checker.run(list_mst)
        
    except Exception as e:
        logging.error(f"Critical error in main: {str(e)}")
        raise

if __name__ == '__main__':
    main()