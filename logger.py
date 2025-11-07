# -----------------------------------------------------------------------------
# Authors: Arash Sheikhlar and Kristinn Thorisson
# Project: Research Expenditure Allocation (REA)
# -----------------------------------------------------------------------------
# Copyright (c) 2025, Arash Sheikhlar and Kristinn Thorisson. All rights reserved.
#
# This software is provided "as is", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose, and noninfringement. In no event shall
# the authors be liable for any claim, damages, or other liability, whether
# in an action of contract, tort, or otherwise, arising from, out of, or in
# connection with the software or the use or other dealings in the software.
#
# Unauthorized copying, distribution, or modification of this code, via any
# medium, is strictly prohibited unless prior written permission is obtained
# from the authors.
# -----------------------------------------------------------------------------

"""
Logging framework for the REA application.
Provides structured logging with different severity levels and output destinations.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from config import AppConfig


class REALogger:
    """
    Centralized logging for the REA application.
    
    Provides methods for logging at different severity levels and handles
    output to both console and file.
    """
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(REALogger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """
        Initialize the logging system with handlers for console and file output.
        """
        self._logger = logging.getLogger('REA')
        self._logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        if not any(isinstance(h, logging.StreamHandler) for h in self._logger.handlers):
            self._logger.addHandler(console_handler)
    
    def add_file_handler(self, filename: str, level: int = logging.DEBUG):
        """
        Add a file handler to write logs to a specific file.
        
        Args:
            filename: Path to log file
            level: Logging level for this handler
        """
        file_handler = logging.FileHandler(filename, mode='w')
        file_handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(Path(filename).absolute()) 
                  for h in self._logger.handlers):
            self._logger.addHandler(file_handler)
    
    def debug(self, message: str):
        """Log a debug message."""
        self._logger.debug(message)
    
    def info(self, message: str):
        """Log an info message."""
        self._logger.info(message)
    
    def warning(self, message: str):
        """Log a warning message."""
        self._logger.warning(message)
    
    def error(self, message: str):
        """Log an error message."""
        self._logger.error(message)
    
    def critical(self, message: str):
        """Log a critical message."""
        self._logger.critical(message)


class AlgorithmLogger:
    """
    Specialized logger for algorithm execution with buffer capture.
    
    Captures detailed algorithm output for diagnostics while also
    writing to standard log files.
    """
    
    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize algorithm logger.
        
        Args:
            log_file: Optional file path for algorithm-specific logs
        """
        self.messages = []
        self.log_file = log_file or AppConfig.DEBUG_LOG_FILE
        self.logger = REALogger()
        self.logger.add_file_handler(self.log_file)
    
    def log(self, message: str, level: str = 'INFO'):
        """
        Log a message and store it in the buffer.
        
        Args:
            message: Message to log
            level: Severity level (INFO, WARNING, ERROR, DEBUG)
        """
        self.messages.append(message)
        
        if level == 'DEBUG':
            self.logger.debug(message)
        elif level == 'INFO':
            self.logger.info(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        elif level == 'ERROR':
            self.logger.error(message)
        else:
            self.logger.info(message)
    
    def get_buffered_output(self) -> str:
        """
        Get all buffered log messages as a single string.
        
        Returns:
            Concatenated log messages
        """
        return '\n'.join(self.messages)
    
    def clear_buffer(self):
        """Clear the message buffer."""
        self.messages.clear()


def get_logger() -> REALogger:
    """
    Get the singleton logger instance.
    
    Returns:
        REALogger instance
    """
    return REALogger()

