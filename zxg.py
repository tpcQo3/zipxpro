import sys, subprocess, os, tempfile
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTreeWidget, QTreeWidgetItem,
    QFileIconProvider, QInputDialog, QLineEdit, QMessageBox, QMenu
)
from PyQt5.QtCore import QFileInfo, Qt

class ArchiveExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZXG Archive Explorer")
        self.setGeometry(300,200,800,600)
        self.setAcceptDrops(True)
        self.current_archive = None
        self.current_password = None
        self.clipboard_item = None
        self.undo_stack = []

        main=QVBoxLayout()
        fl=QHBoxLayout()
        self.file_label=QLabel("No archive selected")
        b=QPushButton("Browse Archive")
        b.clicked.connect(self.choose_archive)
        fl.addWidget(self.file_label); fl.addWidget(b)

        self.tree=QTreeWidget()
        self.tree.setHeaderLabels(["Name","Size","Modified"])
        main.addLayout(fl); main.addWidget(self.tree)
        self.setLayout(main)

    def choose_archive(self):
        f,_=QFileDialog.getOpenFileName(self,"Select archive file")
        if f: self.open_archive(f)

    def open_archive(self, file_path):
        self.file_label.setText(file_path)
        self.current_archive = file_path
        self.current_password = None
        self.show_archive_contents(file_path)

    def show_archive_contents(self, file_path):
        cmd=["7z.exe","l",file_path]
        if self.current_password: cmd.append("-p"+self.current_password)
        result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,encoding="utf-8",errors="ignore")
        output=result.stdout
        if "Encrypted" in output and not self.current_password:
            pw, ok = QInputDialog.getText(self, "Password Required",
                                          f"Archive {os.path.basename(file_path)} requires a password:",
                                          QLineEdit.Password)
            if not ok or not pw: return
            self.current_password = pw
            return self.show_archive_contents(file_path)
        self.parse_and_show(output)

    def parse_and_show(self, output):
        self.tree.clear()
        icon_provider = QFileIconProvider()
        root_items = {}
        start = False
        for line in output.splitlines():
            if line.startswith("----"):
                if not start:
                    start = True
                else:
                    break
                continue
            # parse theo cột cố định, giữ nguyên Unicode và khoảng trắng
            if start and len(line) > 59:
                date = line[0:10].strip()
                size = line[33:45].strip()
                attr = line[19:32].strip()
                name = line[59:].rstrip()   # lấy nguyên tên file, không split
                ftype = "Folder" if "D" in attr else "File"
                parts = name.replace("\\", "/").split("/")
                parent = self.tree
                path = ""
                for i, p in enumerate(parts):
                    path = os.path.join(path, p)
                    if i == len(parts) - 1:
                        item = QTreeWidgetItem([p, size, date])
                        if ftype == "Folder":
                            item.setIcon(0, icon_provider.icon(QFileIconProvider.Folder))
                        else:
                            fi = QFileInfo(p)
                            item.setIcon(0, icon_provider.icon(fi))
                        parent.addTopLevelItem(item) if isinstance(parent, QTreeWidget) else parent.addChild(item)
                        # lưu nguyên tên nội bộ để Delete dùng đúng
                        item.setData(0, Qt.UserRole, name)
                    else:
                        if path not in root_items:
                            folder_item = QTreeWidgetItem([p, "", ""])
                            folder_item.setIcon(0, icon_provider.icon(QFileIconProvider.Folder))
                            parent.addTopLevelItem(folder_item) if isinstance(parent, QTreeWidget) else parent.addChild(folder_item)
                            root_items[path] = folder_item
                        parent = root_items[path]

    def add_files_to_archive(self, files):
        cmd = ["7z.exe","a",self.current_archive] + files
        if self.current_password: cmd.append("-p"+self.current_password)
        subprocess.run(cmd)
        self.show_archive_contents(self.current_archive)

    def rename_in_archive(self, oldname, newname):
        cmd=["7z.exe","rn",self.current_archive,oldname,newname]
        if self.current_password: cmd.append("-p"+self.current_password)
        subprocess.run(cmd)
        self.undo_stack.append(("rename",oldname,newname))
        self.show_archive_contents(self.current_archive)

    def delete_in_archive(self, item):
        target=item.data(0, Qt.UserRole)
        if not target: return
        cmd=["7z.exe","d",self.current_archive,target,"-y"]
        if self.current_password: cmd.append("-p"+self.current_password)
        subprocess.run(cmd)
        self.undo_stack.append(("delete",target))
        self.show_archive_contents(self.current_archive)

    def undo_last_action(self):
        if not self.undo_stack: return
        action=self.undo_stack.pop()
        if action[0]=="rename": self.rename_in_archive(action[2],action[1])
        elif action[0]=="delete": QMessageBox.information(self,"Undo","Cannot undo delete directly.")

    def open_file(self,item):
        target=item.data(0, Qt.UserRole)
        if not target: return
        tmp=tempfile.mkdtemp()
        cmd=["7z.exe","x",self.current_archive,target,"-o"+tmp]
        if self.current_password: cmd.append("-p"+self.current_password)
        subprocess.run(cmd)
        full=os.path.join(tmp,target)
        if os.path.exists(full): os.startfile(full)

    def contextMenuEvent(self, event):
        item = self.tree.currentItem()
        if not item or not self.current_archive: return
        menu = QMenu(self)
        open_action = menu.addAction("Open")
        copy_action = menu.addAction("Copy")
        paste_action = menu.addAction("Paste")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        prop_action = menu.addAction("Properties")
        undo_action = menu.addAction("Undo")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == open_action: self.open_file(item)
        elif action == copy_action: self.clipboard_item=item.data(0, Qt.UserRole)
        elif action == paste_action:
            if self.clipboard_item: self.add_files_to_archive([self.clipboard_item])
        elif action == rename_action:
            oldname=item.data(0, Qt.UserRole)
            newname, ok = QInputDialog.getText(self,"Rename","Enter new name:",text=item.text(0))
            if ok and newname: self.rename_in_archive(oldname,newname)
        elif action == delete_action: self.delete_in_archive(item)
        elif action == prop_action:
            QMessageBox.information(self,"Properties",
                f"Name: {item.text(0)}\nSize: {item.text(1)}\nModified: {item.text(2)}")
        elif action == undo_action: self.undo_last_action()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            f = url.toLocalFile()
            if f:
                ext=os.path.splitext(f)[1].lower()
                if ext in [".zip",".7z",".rar",".iso"]: self.open_archive(f)
                else:
                    if self.current_archive and os.path.exists(self.current_archive):
                        self.add_files_to_archive([f])
                break

if __name__=="__main__":
    app=QApplication(sys.argv); w=ArchiveExplorer(); w.show(); sys.exit(app.exec_())
