# -*- coding: utf8 -*-
import json
import logging
import os
from datetime import date
from pathlib import Path
from contextlib import contextmanager
 
from app.InvoiceChecker_CN import InvoiceChecker_CN
from app.utils.logging_config import setup_logging

import pandas as pd



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
        checker = InvoiceChecker_CN(path, str(data_dir), config)
                
        df = pd.read_excel(  'cccd.xlsx', sheet_name='Sheet1',converters={'CCCD':str})

        list_mst = df['CCCD'].astype('str').values.tolist()
 
        
        results = checker.process_invoices_cccd(list_mst)
        print(results['result_df']) 
        # Save results to Excel file
        results['result_df'].to_excel(data_dir / 'results.xlsx', index=False)
        
        
        checker.create_docx_report(results['result_df'])
        
    except Exception as e:
        logging.error(f"Critical error in main: {str(e)}")
        raise

if __name__ == '__main__':
    main()