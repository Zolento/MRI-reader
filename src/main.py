"""
MRI Reader - Main Entry Point
A Qt-based MRI image viewing and processing tool
"""

import sys

from PyQt5.QtWidgets import QApplication

from . import __version__
from .main_window import MainWindow


def main():
    """Main entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("MRI Reader")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MRI Reader Project")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
