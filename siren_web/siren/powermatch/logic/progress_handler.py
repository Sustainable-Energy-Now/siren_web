class ProgressHandler:
    """Abstract interface for handling progress updates and logs."""
    def update_progress(self, value: int):
        """Handle progress updates (e.g., update a progress bar)."""
        raise NotImplementedError

    def log_message(self, message: str):
        """Handle log messages."""
        raise NotImplementedError
    
    def on_status_update(self, message: str):
        """Called when there is a status update."""
        raise NotImplementedError

    def on_progress_update(self, progress: int):
        """Called when progress changes."""
        raise NotImplementedError