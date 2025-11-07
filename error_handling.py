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
Error handling and user notification system.
Provides consistent error dialogs and exception handling.
"""

from PyQt5.QtWidgets import QMessageBox, QWidget
from typing import Optional, Callable, Any
from logger import get_logger


class ErrorHandler:
    """
    Centralized error handling with user notifications.
    """
    
    @staticmethod
    def show_error(parent: Optional[QWidget], title: str, message: str, 
                   detailed_message: Optional[str] = None):
        """
        Display an error dialog to the user.
        
        Args:
            parent: Parent widget for the dialog
            title: Dialog title
            message: Main error message
            detailed_message: Optional detailed error information
        """
        logger = get_logger()
        logger.error(f"{title}: {message}")
        
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if detailed_message:
            msg_box.setDetailedText(detailed_message)
        
        msg_box.exec_()
    
    @staticmethod
    def show_warning(parent: Optional[QWidget], title: str, message: str,
                    detailed_message: Optional[str] = None):
        """
        Display a warning dialog to the user.
        
        Args:
            parent: Parent widget for the dialog
            title: Dialog title
            message: Main warning message
            detailed_message: Optional detailed warning information
        """
        logger = get_logger()
        logger.warning(f"{title}: {message}")
        
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if detailed_message:
            msg_box.setDetailedText(detailed_message)
        
        msg_box.exec_()
    
    @staticmethod
    def show_info(parent: Optional[QWidget], title: str, message: str):
        """
        Display an informational dialog to the user.
        
        Args:
            parent: Parent widget for the dialog
            title: Dialog title
            message: Informational message
        """
        logger = get_logger()
        logger.info(f"{title}: {message}")
        
        QMessageBox.information(parent, title, message)
    
    @staticmethod
    def ask_confirmation(parent: Optional[QWidget], title: str, 
                        message: str) -> bool:
        """
        Ask user for confirmation with Yes/No dialog.
        
        Args:
            parent: Parent widget for the dialog
            title: Dialog title
            message: Question to ask
            
        Returns:
            True if user clicked Yes, False otherwise
        """
        reply = QMessageBox.question(
            parent, 
            title, 
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes


def handle_exceptions(default_return=None, show_dialog: bool = True):
    """
    Decorator to handle exceptions in functions with optional UI notification.
    
    Args:
        default_return: Value to return if exception occurs
        show_dialog: Whether to show error dialog to user
        
    Returns:
        Decorated function that handles exceptions
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = get_logger()
                error_msg = f"Error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                
                if show_dialog:
                    parent = None
                    if args and hasattr(args[0], 'view'):
                        parent = args[0].view
                    elif args and isinstance(args[0], QWidget):
                        parent = args[0]
                    
                    ErrorHandler.show_error(
                        parent,
                        "Operation Failed",
                        f"An error occurred: {str(e)}",
                        error_msg
                    )
                
                return default_return
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


class ValidationError(Exception):
    """
    Custom exception for validation failures.
    """
    pass


class FileOperationError(Exception):
    """
    Custom exception for file operation failures.
    """
    pass


class AlgorithmError(Exception):
    """
    Custom exception for algorithm execution failures.
    """
    pass

