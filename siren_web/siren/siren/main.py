
# main.py
import sys
from ui.ui import ApplicationUI

def main():
    ui = ApplicationUI()
    ui.setup()
    try:
        return ui.run()
    finally:
        ui.cleanup()

if __name__ == '__main__':
    sys.exit(main())