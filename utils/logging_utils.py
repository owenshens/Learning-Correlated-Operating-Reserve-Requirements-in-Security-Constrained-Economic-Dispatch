"""
Logging Utilities for Experiments
==================================

Provides structured logging for experiments with:
- Experiment tracking (start/end times, parameters, results)
- Progress monitoring (iteration counters, time estimates)
- Result formatting (tables, summaries)
- File logging (JSON, CSV, text logs)
"""

import time
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np


class ExperimentLogger:
    """
    Logger for experiment tracking and reporting.

    Features:
    - Hierarchical logging (experiment > category > run)
    - Automatic timestamping
    - JSON/CSV output
    - Console pretty-printing
    - Progress tracking
    """

    def __init__(
        self,
        experiment_name: str,
        log_dir: Optional[Path] = None,
        console_output: bool = True,
        file_output: bool = True,
    ):
        """
        Initialize experiment logger.

        Args:
            experiment_name: Name of experiment (e.g., "I.1_envelope_verification")
            log_dir: Directory for log files (default: results/<category>/)
            console_output: Print to console
            file_output: Write to log file
        """
        self.experiment_name = experiment_name
        self.console_output = console_output
        self.file_output = file_output

        # Create log directory
        if log_dir is None:
            category = experiment_name.split('_')[0]  # e.g., "I.1" -> "I"
            log_dir = Path(__file__).parent.parent / "results" / f"category_{category}"
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{experiment_name}_{timestamp}.log"
        self.json_file = self.log_dir / f"{experiment_name}_{timestamp}.json"

        # Experiment metadata
        self.metadata = {
            'experiment_name': experiment_name,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': None,
            'parameters': {},
            'results': {},
            'runs': [],
        }

        self.start_time = time.time()
        self._log_header()

    def _log_header(self):
        """Print experiment header."""
        header = f"\n{'='*70}\n{self.experiment_name.upper()}\n{'='*70}"
        self._write(header)
        self._write(f"Started: {self.metadata['start_time']}")
        self._write(f"Log file: {self.log_file}")

    def _write(self, message: str, level: str = "INFO"):
        """Write message to console and/or file."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {level:5s} | {message}"

        if self.console_output:
            print(formatted)

        if self.file_output:
            with open(self.log_file, 'a') as f:
                f.write(formatted + '\n')

    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        self._write(message, level)

    def info(self, message: str):
        """Log info message."""
        self._write(message, "INFO")

    def warning(self, message: str):
        """Log warning message."""
        self._write(message, "WARN")

    def error(self, message: str):
        """Log error message."""
        self._write(message, "ERROR")

    def set_parameters(self, params: Dict[str, Any]):
        """Record experiment parameters."""
        self.metadata['parameters'] = params
        self._write(f"Parameters: {json.dumps(params, indent=2)}")

    def log_run(self, run_id: int, params: Dict, results: Dict, duration: float):
        """
        Log a single experiment run.

        Args:
            run_id: Run identifier
            params: Run-specific parameters
            results: Run results
            duration: Runtime in seconds
        """
        run_data = {
            'run_id': run_id,
            'parameters': params,
            'results': results,
            'duration_seconds': duration,
        }
        self.metadata['runs'].append(run_data)

        self._write(f"\n  Run {run_id}: {duration:.2f}s")
        for key, val in results.items():
            if isinstance(val, (int, float)):
                self._write(f"    {key}: {val:.6f}")
            else:
                self._write(f"    {key}: {val}")

    def log_progress(self, current: int, total: int, extra_info: str = ""):
        """
        Log progress (e.g., iteration count).

        Args:
            current: Current iteration
            total: Total iterations
            extra_info: Additional info to display
        """
        pct = 100.0 * current / total if total > 0 else 0
        elapsed = time.time() - self.start_time
        eta = elapsed / current * (total - current) if current > 0 else 0

        msg = f"Progress: {current}/{total} ({pct:.1f}%) | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s"
        if extra_info:
            msg += f" | {extra_info}"

        self._write(msg, "PROG")

    def log_table(self, title: str, data: List[Dict], headers: Optional[List[str]] = None):
        """
        Log a formatted table.

        Args:
            title: Table title
            data: List of dictionaries (rows)
            headers: Column headers (default: keys from first row)
        """
        if not data:
            self._write(f"{title}: (empty)")
            return

        if headers is None:
            headers = list(data[0].keys())

        # Calculate column widths
        col_widths = {h: len(h) for h in headers}
        for row in data:
            for h in headers:
                val_str = str(row.get(h, ''))
                col_widths[h] = max(col_widths[h], len(val_str))

        # Header
        self._write(f"\n{title}")
        header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
        self._write(header_line)
        self._write("-" * len(header_line))

        # Rows
        for row in data:
            row_line = " | ".join(str(row.get(h, '')).ljust(col_widths[h]) for h in headers)
            self._write(row_line)

    def set_results(self, results: Dict[str, Any]):
        """Record final experiment results."""
        self.metadata['results'] = results
        self._write(f"\nResults: {json.dumps(results, default=str, indent=2)}")

    def finalize(self):
        """Finalize experiment logging."""
        end_time = time.time()
        duration = end_time - self.start_time

        self.metadata['end_time'] = datetime.now().isoformat()
        self.metadata['duration_seconds'] = duration

        self._write(f"\n{'='*70}")
        self._write(f"Experiment completed in {duration:.2f}s")
        self._write(f"{'='*70}\n")

        # Save JSON metadata
        if self.file_output:
            with open(self.json_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
            self._write(f"Metadata saved: {self.json_file}")


class ProgressBar:
    """Simple progress bar for long-running operations."""

    def __init__(self, total: int, desc: str = "", width: int = 50):
        """
        Initialize progress bar.

        Args:
            total: Total number of steps
            desc: Description
            width: Bar width in characters
        """
        self.total = total
        self.desc = desc
        self.width = width
        self.current = 0
        self.start_time = time.time()

    def update(self, n: int = 1):
        """Update progress by n steps."""
        self.current = min(self.current + n, self.total)
        self._display()

    def _display(self):
        """Display progress bar."""
        pct = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * pct)
        bar = '█' * filled + '░' * (self.width - filled)

        elapsed = time.time() - self.start_time
        eta = elapsed / self.current * (self.total - self.current) if self.current > 0 else 0

        sys.stdout.write(f'\r{self.desc}: |{bar}| {self.current}/{self.total} '
                        f'({pct*100:.1f}%) [{elapsed:.1f}s<{eta:.1f}s]')
        sys.stdout.flush()

        if self.current >= self.total:
            sys.stdout.write('\n')
            sys.stdout.flush()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.current < self.total:
            self.current = self.total
            self._display()


def format_number(x: float, precision: int = 4) -> str:
    """
    Format number for display.

    Args:
        x: Number to format
        precision: Decimal places

    Returns:
        Formatted string
    """
    if np.isnan(x):
        return "NaN"
    elif np.isinf(x):
        return "∞" if x > 0 else "-∞"
    elif abs(x) < 10**(-precision):
        return f"{x:.2e}"
    else:
        return f"{x:.{precision}f}"


def format_time(seconds: float) -> str:
    """
    Format time duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable time string
    """
    if seconds < 1:
        return f"{seconds*1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"
