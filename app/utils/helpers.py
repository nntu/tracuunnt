from pathlib import Path
from typing import Optional, Union
import pickle
from datetime import date
import os

class DataStateManager:
    """Manages the state of data processing."""
    
    def __init__(self, state_file: Union[str, Path]):
        self.state_file = Path(state_file)
    
    def save_state(self, date_run: date) -> None:
        """Save the processing state."""
        with open(self.state_file, 'wb') as f:
            pickle.dump(date_run, f)
    
    def get_last_run_date(self) -> Optional[date]:
        """Get the date of last successful run."""
        if not self.state_file.exists():
            return None
            
        try:
            with open(self.state_file, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return None
    
    def should_run_today(self) -> bool:
        """Check if processing should run today."""
        last_run = self.get_last_run_date()
        return last_run != date.today()
    
