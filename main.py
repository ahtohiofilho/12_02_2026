# main.py
import sys
from PySide6.QtWidgets import QApplication
from controller import Controller


def main():
    # 1. Cria aplicação Qt
    app = QApplication(sys.argv)

    # 2. Cria Controller (nosso novo ponto central)
    controller = Controller(app)

    # 3. Executa (Controller cuida da janela)
    controller.run()

    # 4. Loop Qt
    sys.exit(app.exec())


if __name__ == "__main__":
    main()