import sys, subprocess, os, tempfile, random, string
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QTreeWidget, QTreeWidgetItem,
    QFileIconProvider, QInputDialog, QLineEdit, QMessageBox, QMenu, QStyle,
    QDialog, QVBoxLayout, QLineEdit, QPushButton, QHeaderView
)
from PyQt5.QtCore import QFileInfo, Qt, pyqtSignal, QThread

class SevenZipThread(QThread):
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            result = subprocess.run(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10
            )
            self.result_ready.emit(result.stdout)
        except subprocess.TimeoutExpired:
            self.error_occurred.emit("Timeout")
        except Exception as e:
            self.error_occurred.emit(str(e))

class ArchiveExplorer(QWidget):
    def rename_dialog(self, old_name):
        dialog = QDialog(self)
        dialog.setWindowTitle("Rename")
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.resize(400, 120)  # 🔥 to hơn cho đẹp
        layout = QVBoxLayout()

        edit = QLineEdit(old_name)
        edit.setMinimumWidth(350)

        # chọn phần name (không chọn extension)
        if "." in old_name:
            base = old_name.rsplit(".", 1)[0]
            edit.setSelection(0, len(base))
        else:
            edit.selectAll()

        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")

        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        layout.addWidget(edit)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            return edit.text(), True

        return None, False
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZXG Archive Explorer")
        self.setGeometry(200, 100, 1200, 700)
        self.setAcceptDrops(True)

        self.current_archive = None
        self.current_password = None
        self.clipboard_item = None
        self.loading = False

        # 🔥 Pending operations
        self.operations = []

        main = QHBoxLayout()

        # ===== LEFT SIDE =====
        left = QVBoxLayout()

        fl = QHBoxLayout()
        self.file_label = QLabel("No archive selected")
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.browse_btn.setFixedWidth(120)  # chỉnh tuỳ bạn
        self.browse_btn.clicked.connect(self.on_browse_click)
        fl.addWidget(self.file_label)
        fl.addWidget(self.browse_btn)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name","Size","Modified"])
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)          # Name auto giãn
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Size fit nội dung
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Date fit nội dung
        self.tree.itemDoubleClicked.connect(self.open_file)

        left.addLayout(fl)
        left.addWidget(self.tree)

        # ===== RIGHT SIDE (HISTORY) =====
        right = QVBoxLayout()

        self.history_label = QLabel("Pending Operations")

        self.history_list = QTreeWidget()
        self.history_list.setHeaderLabels(["Action", "Target"])

        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.apply_operations)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_operations)

        right.addWidget(self.history_label)
        right.addWidget(self.history_list)
        right.addWidget(self.apply_btn)
        right.addWidget(self.clear_btn)

        main.addLayout(left, 3)
        main.addLayout(right, 1)

        self.setLayout(main)

    def password_dialog(self, archive_name):
        dialog = QDialog(self)
        dialog.setWindowTitle("Password Required")

        # 🔥 bỏ dấu ?
        dialog.setWindowFlags(
            dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        dialog.resize(400, 140)

        layout = QVBoxLayout()

        label = QLabel(f"Archive '{archive_name}' requires a password:")

        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setMinimumWidth(350)
        edit.setFocus()

        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")

        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        layout.addWidget(label)
        layout.addWidget(edit)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            return edit.text(), True

        return None, False

    # ===== FILE HANDLING =====
    def on_browse_click(self):
        if self.loading:
            return
        f, _ = QFileDialog.getOpenFileName(self, "Select archive file")
        if f:
            self.open_archive(f)

    def choose_archive(self):
        self.on_browse_click()

    def open_archive(self, file_path):
        self.file_label.setText(file_path)
        self.current_archive = file_path
        self.current_password = None
        self.show_archive_contents(file_path)

    def is_archive_encrypted(self, output):
        return "Encrypted = +" in output

    def ensure_password(self):
        if not self.current_archive:
            QMessageBox.warning(self, "Error", "No archive selected.")
            return False

        if self.current_password:
            return True

        while True:
            pw, ok = self.password_dialog(os.path.basename(self.current_archive))

            if not ok:
                return False

            cmd = ["7z.exe", "t", self.current_archive, "-p" + pw]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            output = result.stdout.lower()

            if "wrong password" in output:
                QMessageBox.critical(self, "Error", "Incorrect password.")
                continue

            self.current_password = pw
            return True

    def show_archive_contents(self, file_path):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

        self.current_archive = file_path
        self.current_password = None

        cmd = ["7z.exe", "l", "-slt", "-sccUTF-8", file_path]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6
            )
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Error", "Archive loading timeout.")
            QApplication.restoreOverrideCursor()
            return

        # 🔥 luôn parse luôn (không check password nữa)
        self.parse_and_show(result.stdout)

        QApplication.restoreOverrideCursor()

    # ===== PARSE =====
    def parse_and_show(self, output):
        self.tree.clear()
        icon_provider = QFileIconProvider()

        items_map = {}
        current = {}
        archive_name = os.path.basename(self.current_archive)

        for line in output.splitlines():
            line = line.strip()

            if line.startswith("Path = "):
                current["path"] = line[7:]

            elif line.startswith("Size = "):
                current["size"] = line[7:]

            elif line.startswith("Modified = "):
                current["date"] = line[11:]

            elif line == "":
                if "path" in current:
                    full_path = current.get("path", "")

                    # 🔥 filter
                    if full_path == archive_name or ":" in full_path or not full_path:
                        current = {}
                        continue

                    size = current.get("size", "")
                    date = current.get("date", "")

                    parts = full_path.replace("\\", "/").split("/")

                    parent = self.tree
                    built_path = ""

                    for i, part in enumerate(parts):
                        if not part:
                            continue

                        built_path = built_path + "/" + part if built_path else part

                        if built_path not in items_map:
                            if i == len(parts) - 1:
                                item = QTreeWidgetItem([part, size, date])
                                fi = QFileInfo(part)
                                item.setIcon(0, icon_provider.icon(fi))
                                item.setData(0, Qt.UserRole, full_path)
                            else:
                                item = QTreeWidgetItem([part, "", ""])
                                item.setIcon(0, icon_provider.icon(QFileIconProvider.Folder))

                            if isinstance(parent, QTreeWidget):
                                parent.addTopLevelItem(item)
                            else:
                                parent.addChild(item)

                            items_map[built_path] = item

                        parent = items_map[built_path]

                current = {}

        self.tree.expandAll()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)

    def is_locked(self):
        return self.current_password is None
    
    # ===== OPERATIONS QUEUE =====
    def add_operation(self, action, target):
        self.operations.append(action)
        item = QTreeWidgetItem([action[0].capitalize(), target])
        self.history_list.addTopLevelItem(item)

    def rename_in_archive(self, oldname, newname):
        if not self.ensure_password():
            return
        self.add_operation(("rename", oldname, newname), f"{oldname} → {newname}")

    def delete_in_archive(self, item):
        if not self.ensure_password():
            return
        target = item.data(0, Qt.UserRole)
        if target:
            self.add_operation(("delete", target), target)

    def add_files_to_archive(self, files):
        if not self.ensure_password():
            return
        for f in files:
            self.add_operation(("add", f), f)

    # ===== APPLY =====
    def apply_operations(self):
        if not self.current_archive:
            QMessageBox.warning(self, "Error", "No archive loaded.")
            return
        if not self.ensure_password():
            return
        if not self.operations:
            QMessageBox.information(self, "Info", "No pending operations.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm",
            "Apply all pending operations?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        for op in self.operations:
            if op[0] == "rename":
                cmd = ["7z.exe", "rn", self.current_archive, op[1], op[2]]
            elif op[0] == "delete":
                cmd = ["7z.exe", "d", self.current_archive, op[1], "-y"]
            elif op[0] == "add":
                cmd = ["7z.exe", "a", self.current_archive, op[1]]
            else:
                continue

            if self.current_password:
                cmd.append("-p" + self.current_password)

            subprocess.run(cmd, timeout=10)

        self.operations.clear()
        self.history_list.clear()
        self.show_archive_contents(self.current_archive)

    def clear_operations(self):
        self.operations.clear()
        self.history_list.clear()

    # ===== FILE OPEN =====
    def open_file(self, item):
        target = item.data(0, Qt.UserRole)
        if not target:
            return

        # 🔐 yêu cầu password nếu cần
        if not self.ensure_password():
            return

        tmp = tempfile.mkdtemp()
        cmd = ["7z.exe", "x", self.current_archive, target, "-o" + tmp]

        if self.current_password:
            cmd.append("-p" + self.current_password)

        subprocess.run(cmd)

        full = os.path.join(tmp, target)
        if os.path.exists(full):
            os.startfile(full)

    # ===== CONTEXT MENU =====
    
    def open_file(self, item):
        if self.is_locked():
            QMessageBox.warning(self, "Locked", "Enter correct password first.")
            return
    
    def contextMenuEvent(self, event):
        item = self.tree.currentItem()
        if not item or not self.current_archive:
            return
        if self.is_locked():
            QMessageBox.warning(self, "Locked", "Enter correct password first.")
            return

        menu = QMenu(self)

        open_action = menu.addAction("Open")
        copy_action = menu.addAction("Copy")
        paste_action = menu.addAction("Paste")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == open_action:
            self.open_file(item)

        elif action == copy_action:
            self.clipboard_item = item.data(0, Qt.UserRole)

        elif action == paste_action:
            if self.clipboard_item:
                self.add_files_to_archive([self.clipboard_item])

        elif action == rename_action:
            
            oldname = item.data(0, Qt.UserRole)
            # 🔥 chỉ lấy tên file cuối cùng (không lấy path)
            display_name = os.path.basename(oldname)

            newname, ok = self.rename_dialog(display_name)

            if ok and newname:
                # giữ nguyên path
                path = os.path.dirname(oldname)
                full_new = os.path.join(path, newname).replace("\\", "/") if path else newname

                self.rename_in_archive(oldname, full_new)

        elif action == delete_action:
            self.delete_in_archive(item)

    # ===== DRAG DROP =====
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            f = url.toLocalFile()
            if f:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".zip", ".7z", ".rar", ".iso"]:
                    self.open_archive(f)
                else:
                    if self.current_archive:
                        self.add_files_to_archive([f])
                break
        


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    w = ArchiveExplorer()
    w.show()
    sys.exit(app.exec_())