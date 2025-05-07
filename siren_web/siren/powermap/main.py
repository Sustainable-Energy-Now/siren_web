
from ui.main_window import MainWindow
from powermap.api.api import PowermapAPI
from PyQt5.QtWidgets import QApplication
import sys
from utilities.settings import load_settings
from siren_web.siren.powermap.ui.wascene import WAScene

def main():
    app = QApplication(sys.argv)

    # Check for command-line argument
    if len(sys.argv) < 2:
        print("Usage: main.py <config_file>")
        sys.exit(1)

    config_path = sys.argv[1]  # Get the first argument (path to preferences file)

    # Load configuration
    config, settings = load_settings()

    # Initialize API
    api = PowermapAPI(config, settings)
    scene = WAScene()
    # Launch the main window
    main_window = MainWindow(scene)
    main_window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()