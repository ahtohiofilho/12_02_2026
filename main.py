# main.py
import sys
from PySide6.QtWidgets import QApplication
from controller import Controller
from ui.theme import APP_QSS

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)

    controller = Controller(app)
    controller.run()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
