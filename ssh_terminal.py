import paramiko
from PyQt6.QtWidgets import QPlainTextEdit
from threading import Thread

class SSHTerminal(QPlainTextEdit):
    def __init__(self, host, user, password):
        super().__init__()
        self.setReadOnly(False)
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.client.connect(
            hostname=host,
            username=user,
            password=password,
            look_for_keys=False,
            allow_agent=False
        )

        self.channel = self.client.invoke_shell()
        Thread(target=self.read_loop, daemon=True).start()

    def read_loop(self):
        while True:
            if self.channel.recv_ready():
                data = self.channel.recv(4096).decode(errors="ignore")
                self.appendPlainText(data)

    def keyPressEvent(self, event):
        text = event.text()
        if text:
            self.channel.send(text)
