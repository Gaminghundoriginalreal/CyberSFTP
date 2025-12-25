import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QSplitter
from sftp_panel import SFTPPanel
from ssh_terminal import SSHTerminal
from server_manager import load_servers

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python SFTP + SSH Client")
        self.resize(1200, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        for s in load_servers():
            self.open_server(s)

    def open_server(self, s):
        splitter = QSplitter()
        splitter.addWidget(SFTPPanel(s["host"], s["user"], s["password"]))
        splitter.addWidget(SSHTerminal(s["host"], s["user"], s["password"]))
        self.tabs.addTab(splitter, s["name"])

app = QApplication(sys.argv)
win = Main()
win.show()
sys.exit(app.exec())
