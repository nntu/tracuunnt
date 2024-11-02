import logging
from pathlib import Path
from datetime import date

def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    """Configure logging for the application."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f'log_{date.today().strftime("%Y_%m_%d")}.log'
    
    logging.basicConfig(
        filename=str(log_file),
        format='%(levelname)s | %(asctime)s | %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        level=level,
        encoding="utf-8"
    )
    
    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(message)s')
    )
    logging.getLogger().addHandler(console_handler)