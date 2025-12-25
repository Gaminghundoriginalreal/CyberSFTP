import paramiko
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem

class SFTPPanel(QTreeWidget):
    def __init__(self, host, user, password):
        super().__init__()
        self.setHeaderLabels(["Name", "Size", "Type"])

        self.transport = paramiko.Transport((host, 22))
        self.transport.connect(username=user, password=password)
        self.sftp = paramiko.SFTPClient.from_transport(self.transport)

        self.load_dir(".")

    def load_dir(self, path):
        self.clear()
        for item in self.sftp.listdir_attr(path):
            row = QTreeWidgetItem([
                item.filename,
                str(item.st_size),
                "DIR" if paramiko.SFTPAttributes.from_stat(item).st_mode & 0o040000 else "FILE"
            ])
            self.addTopLevelItem(row)
