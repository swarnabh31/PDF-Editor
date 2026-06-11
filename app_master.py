# --- CRITICAL ISOLATION DIRECTORIES ---
# Ensure this executes BEFORE importing PySide6/PyQt6 modules
import os
import sys

if sys.platform == "win32":
    # Get the directory where the application code/executable is currently running
    if getattr(sys, 'frozen', False):
        # Running as compiled PyInstaller executable
        base_dir = sys._MEIPASS
    else:
        # Running as standard Python script
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Calculate the exact internal path to your bundled Qt plugins folder
    plugin_path = os.path.join(base_dir, "PySide6", "plugins")

    if os.path.exists(plugin_path):
        # Force Windows to ignore global registry overrides and look here first
        os.environ["QT_PLUGIN_PATH"] = plugin_path

        # Explicitly configure the platform plugin directory hook
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(plugin_path, "platforms")

# Now it is completely safe to load your UI modules
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ui_main import MainWindow


def main():
    # High DPI scaling for modern Windows displays
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
