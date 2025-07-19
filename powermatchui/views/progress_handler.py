import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from queue import Queue

@dataclass
class ProgressUpdate:
    """Container for progress update information"""
    current_step: int
    total_steps: int
    percentage: float
    message: str
    elapsed_time: float
    estimated_remaining: Optional[float] = None

class ProgressChannel:
    """Progress Channel for real-time updates"""
    def __init__(self, session_id):
        self.session_id = session_id
        self.queue = Queue()
        self.active = True
    
    def send_update(self, data):
        """Send update to stream"""
        if self.active:
            self.queue.put(data)
    
    def close(self):
        """Close the channel and signal completion"""
        self.active = False
        self.queue.put(None)  # Signal to close connection

class ProgressHandler:
    """Enhanced progress handler with detailed tracking for SSE"""
    
    def __init__(self, total_steps: int = 100, callback: Optional[Callable] = None):
        self.total_steps = total_steps
        self.current_step = 0
        self.callback = callback
        self.start_time = time.time()
        self.step_times = []
        self.current_message = "Initializing..."
        
        # Create a mock progress bar for compatibility with existing code
        self.progress_bar = MockProgressBar()
    
    def update(self, step: Optional[int] = None, message: Optional[str] = None, 
               increment: bool = True):
        """Update progress with optional step and message"""
        if step is not None:
            self.current_step = step
        elif increment:
            self.current_step += 1
            
        if message:
            self.current_message = message
            
        # Record timing
        current_time = time.time()
        self.step_times.append(current_time)
        
        # Calculate progress
        percentage = min(100.0, (self.current_step / self.total_steps) * 100)
        elapsed_time = current_time - self.start_time
        
        # Estimate remaining time
        estimated_remaining = None
        if self.current_step > 0 and self.current_step < self.total_steps:
            avg_step_time = elapsed_time / self.current_step
            remaining_steps = self.total_steps - self.current_step
            estimated_remaining = avg_step_time * remaining_steps
        
        # Create progress update
        progress_update = ProgressUpdate(
            current_step=self.current_step,
            total_steps=self.total_steps,
            percentage=percentage,
            message=self.current_message,
            elapsed_time=elapsed_time,
            estimated_remaining=estimated_remaining
        )
        
        # Update mock progress bar for compatibility
        self.progress_bar.setValue(int(percentage))
        
        # Call callback if provided (this is where SSE updates happen)
        if self.callback:
            try:
                self.callback(progress_update)
            except Exception as e:
                print(f"Error in progress callback: {e}")
            
        return progress_update
    
    def finish(self, message: str = "Complete"):
        """Mark progress as finished"""
        self.update(step=self.total_steps, message=message, increment=False)
        self.progress_bar.setHidden(True)

class MockProgressBar:
    """Mock progress bar for compatibility with existing code"""
    def __init__(self):
        self.value = 0
        self.hidden = False
        
    def setValue(self, value: int):
        self.value = value
        
    def setHidden(self, hidden: bool):
        self.hidden = hidden

def create_sse_progress_callback(sse_channel):
    """Create a specialized callback for real-time updates"""
    
    def sse_callback(progress_update: ProgressUpdate):
        """Callback that sends updates to the progress channel"""
        
        try:
            update_data = {
                'type': 'progress',
                'percentage': progress_update.percentage,
                'message': progress_update.message,
                'elapsed_time': progress_update.elapsed_time,
                'estimated_remaining': progress_update.estimated_remaining
            }
            
            if sse_channel and hasattr(sse_channel, 'send_update'):
                sse_channel.send_update(update_data)
                
            # Debug logging
            print(f"Progress Update: {progress_update.percentage:.1f}% - {progress_update.message}")
            
        except Exception as e:
            print(f"Error in progress callback: {e}")
    
    return sse_callback

def enhance_powermatch_progress(processor_instance, progress_handler=None):
    """Enhanced version that accepts external progress handler"""
    
    # Store original method
    if hasattr(processor_instance, 'matchSupplytoLoad'):
        original_match = processor_instance.matchSupplytoLoad
    else:
        print("Warning: matchSupplytoLoad method not found on processor instance")
        return processor_instance
    
    def enhanced_matchSupplytoLoad(year, option, sender_name, technology_attributes, load_and_supply):
        
        # Use provided progress handler or create/get existing one
        if progress_handler:
            current_handler = progress_handler
        elif hasattr(processor_instance, 'listener') and processor_instance.listener:
            current_handler = processor_instance.listener
        else:
            current_handler = ProgressHandler(total_steps=100)
            processor_instance.listener = current_handler
        
        # Define progress steps for real PowerMatch execution
        progress_steps = [
            (15, "Initializing dispatch configuration..."),
            (25, "Processing technology attributes..."),
            (35, "Setting up energy balance calculations..."),
            (45, "Processing hourly dispatch..."),
            (55, "Calculating storage operations..."),
            (65, "Computing economic metrics..."),
            (75, "Generating summary statistics..."),
            (85, "Creating output arrays..."),
            (95, "Finalizing results...")
        ]
        
        # Track progress through each major step
        for step_pct, message in progress_steps:
            current_handler.update(step=step_pct, message=message, increment=False)
            time.sleep(0.02)  # Small delay to make progress visible
        
        # Call the original PowerMatch method
        current_handler.update(step=50, message="Executing core PowerMatch algorithm...", increment=False)
        result = original_match(year, option, sender_name, technology_attributes, load_and_supply)
        
        # Finish progress
        current_handler.finish("PowerMatch calculation complete")
        
        return result
    
    # Replace the method
    processor_instance.matchSupplytoLoad = enhanced_matchSupplytoLoad
    return processor_instance

# Django view integration helpers
def create_progress_callback(request=None, channel=None):
    """Create a progress callback for Django views with optional channel"""
    
    def progress_callback(progress_update: ProgressUpdate):
        """Callback function that handles both session storage and real-time updates"""
        
        # Format time remaining
        time_remaining = ""
        if progress_update.estimated_remaining:
            if progress_update.estimated_remaining < 60:
                time_remaining = f" (Est. {progress_update.estimated_remaining:.0f}s remaining)"
            else:
                time_remaining = f" (Est. {progress_update.estimated_remaining/60:.1f}m remaining)"
        
        # Create status message
        status_msg = f"{progress_update.message} - {progress_update.percentage:.1f}%{time_remaining}"
        
        # For Django session storage (backwards compatibility)
        if request and hasattr(request, 'session'):
            request.session['powermatch_progress'] = {
                'percentage': progress_update.percentage,
                'message': progress_update.message,
                'elapsed_time': progress_update.elapsed_time,
                'estimated_remaining': progress_update.estimated_remaining
            }
        
        # For real-time channel updates
        if channel and hasattr(channel, 'send_update'):
            update_data = {
                'type': 'progress',
                'percentage': progress_update.percentage,
                'message': progress_update.message,
                'elapsed_time': progress_update.elapsed_time,
                'estimated_remaining': progress_update.estimated_remaining
            }
            channel.send_update(update_data)
        
        # Print to console for debugging
        print(f"PowerMatch Progress: {status_msg}")
        
        return status_msg
    
    return progress_callback