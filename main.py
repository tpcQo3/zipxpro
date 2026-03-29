import sys, subprocess, os, re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLineEdit, QLabel, QProgressBar, QComboBox, QMessageBox, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt

def get_command(fmt, output_file, file_paths, password, mode="a", output_folder=None):
    sevenzip_formats = [
        "7z","zip","tar","tar.gz","tar.bz2","tar.xz",
        "gz","bz2","xz","cab","arj","lzh","z","wim","bzip2","iso"
    ]
    if fmt == "rar":
        cmd = ["rar.exe", "a" if mode=="a" else "x", "-idp"]
        if mode=="a": cmd += [output_file] + file_paths
        else: cmd += [file_paths[0], output_folder]
        if password: cmd.append("-p"+password)
        return cmd
    elif fmt in sevenzip_formats:
        if fmt=="iso" and mode=="a": return None
        cmd = ["7z.exe", "a" if mode=="a" else "x"]
        if mode=="a": cmd += [output_file] + file_paths + ["-bsp1","-bso1"]
        else: cmd += [file_paths[0], f"-o{output_folder}", "-bsp1","-bso1"]
        if password: cmd.append("-p"+password)
        return cmd
    return None

class ZipXProUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZipX Pro")
        self.setGeometry(300,200,700,500)
        self.setWindowFlags(self.windowFlags()|Qt.WindowStaysOnTopHint)
        self.file_paths=None
        main=QVBoxLayout()

        fl=QHBoxLayout(); self.file_label=QLabel("No file"); b=QPushButton("Browse...")
        b.clicked.connect(self.choose_file); fl.addWidget(self.file_label); fl.addWidget(b)

        nl=QHBoxLayout(); nl.addWidget(QLabel("File name:")); self.output_name_input=QLineEdit(); self.output_name_input.setMaximumWidth(200); nl.addWidget(self.output_name_input)
        pl=QHBoxLayout(); pl.addWidget(QLabel("Password:")); self.password_input=QLineEdit(); self.password_input.setEchoMode(QLineEdit.Password); self.password_input.setMaximumWidth(200); pl.addWidget(self.password_input)

        fmtl=QHBoxLayout(); fmtl.addWidget(QLabel("Format:")); self.format_combo=QComboBox()
        self.format_combo.addItems(["7z","zip","rar","tar","tar.gz","tar.bz2","tar.xz","gz","bz2","xz","cab","wim","arj","lzh","iso","z","bzip2"])
        self.format_combo.currentTextChanged.connect(self.on_format_change); fmtl.addWidget(self.format_combo)

        al=QHBoxLayout(); self.btn_compress=QPushButton("Compress"); self.btn_extract=QPushButton("Extract"); self.btn_extract_multi=QPushButton("Extract Multiple")
        self.btn_compress.clicked.connect(self.compress_file); self.btn_extract.clicked.connect(self.extract_file); self.btn_extract_multi.clicked.connect(self.choose_files_to_extract)
        al.addWidget(self.btn_compress); al.addWidget(self.btn_extract); al.addWidget(self.btn_extract_multi)

        self.progress=QProgressBar(); self.progress.setValue(0)
        for l in [fl,nl,pl,fmtl,al]: main.addLayout(l)
        main.addWidget(self.progress); self.setLayout(main)

    def on_format_change(self, fmt):
        self.btn_compress.setEnabled(fmt.lower()!="iso")

    def choose_file(self):
        files,_=QFileDialog.getOpenFileNames(self,"Select files")
        if files:
            self.file_paths=files
            shown="; ".join(os.path.basename(f) for f in files[:3])
            if len(files)>3: shown+=" ..."
            self.file_label.setText(shown)
            self.output_name_input.setText("Archive" if len(files)>1 else os.path.splitext(os.path.basename(files[0]))[0])

    def compress_file(self):
        if not self.file_paths: return
        out=QFileDialog.getExistingDirectory(self,"Select output folder")
        if not out: return
        name=self.output_name_input.text().strip()
        if not name: return
        fmt=self.format_combo.currentText(); of=os.path.join(out,name+"."+fmt); pw=self.password_input.text().strip()
        cmd=get_command(fmt,of,self.file_paths,pw,"a")
        if not cmd: QMessageBox.warning(self,"Unsupported Format",f"Format {fmt} is not supported for compression."); return
        try:
            subprocess.run(cmd,check=True)
            self.progress.setValue(100); QMessageBox.information(self,"Compression Completed",f"Compressed completed!\nYour file: {of}")
        except: QMessageBox.warning(self,"Compression Failed","Compression failed!")

    def extract_file(self):
        if not self.file_paths: return
        out=QFileDialog.getExistingDirectory(self,"Select output folder")
        if not out: return
        fmt=self.format_combo.currentText(); pw=self.password_input.text().strip()
        cmd=get_command(fmt,None,self.file_paths,pw,"x",out)
        if not cmd: QMessageBox.warning(self,"Unsupported Format",f"Format {fmt} is not supported for extraction."); return
        try:
            subprocess.run(cmd,check=True)
            self.progress.setValue(100); QMessageBox.information(self,"Extraction Completed",f"Extracted completed!\nYour files are in: {out}")
        except: QMessageBox.warning(self,"Extraction Failed","Extraction failed!")

    def choose_files_to_extract(self):
        files,_=QFileDialog.getOpenFileNames(self,"Select archives")
        if files:
            self.extract_files=files
            self.show_password_table(files)

    def show_password_table(self, files):
        self.table=QTableWidget(len(files),2)
        self.table.setHorizontalHeaderLabels(["File","Password"])
        for i,f in enumerate(files):
            self.table.setItem(i,0,QTableWidgetItem(os.path.basename(f)))
            if self.is_password_protected(f):
                self.table.setItem(i,1,QTableWidgetItem(""))
            else:
                self.table.setItem(i,1,QTableWidgetItem("(none)"))
        self.layout().addWidget(self.table)
        btn=QPushButton("Extract All")
        btn.clicked.connect(self.extract_all_files)
        self.layout().addWidget(btn)

    def is_password_protected(self,file_path):
        try:
            result=subprocess.run(["7z.exe","l",file_path],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            return "Encrypted" in result.stdout or "Password" in result.stdout
        except: return False

    def extract_all_files(self):
        out=QFileDialog.getExistingDirectory(self,"Select output folder")
        if not out: return
        for i,f in enumerate(self.extract_files):
            pw_item=self.table.item(i,1)
            pw=pw_item.text() if pw_item else ""
            fmt=os.path.splitext(f)[1].lstrip(".").lower()
            cmd=get_command(fmt,None,[f],pw,"x",out)
            if cmd:
                try: subprocess.run(cmd,check=True)
                except: QMessageBox.warning(self,"Extraction Failed",f"Failed to extract {f}")
        QMessageBox.information(self,"Extraction Completed",f"All files extracted to: {out}")

if __name__=="__main__":
    app=QApplication(sys.argv); w=ZipXProUI(); w.show(); sys.exit(app.exec_())
