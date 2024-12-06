from PyQt5.QtWidgets import QApplication
from utilities.settings import load_settings
import sys
from ui.main_window import powerMatchUI

def main():
    app = QApplication(sys.argv)
    # Check for command-line argument
    if len(sys.argv) < 2:
        print("Usage: main.py <config_file>")
        sys.exit(1)

    config, settings = load_settings()

    # Load configuration
    ui = powerMatchUI(config, settings)
    ui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
