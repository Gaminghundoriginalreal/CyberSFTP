import paramiko
import customtkinter as ctk
from customtkinter import CTkInputDialog, CTkToplevel, CTkTextbox, CTkComboBox
from tkinter import filedialog, messagebox, Menu
import tkinter as tk
from tkinter import ttk
import os
import json
import threading
import time
import stat as py_stat
from tkinterdnd2 import DND_FILES, TkinterDnD
import random

# Speicherort für Sessions
APP_DATA_DIR = os.path.join(os.getenv('APPDATA') or os.path.expanduser("~"), 'CyberSFTP')
os.makedirs(APP_DATA_DIR, exist_ok=True)
SESSIONS_FILE = os.path.join(APP_DATA_DIR, 'sessions.json')

# Verfügbare Encodings
ENCODINGS = ["utf-8", "latin-1", "cp1252", "windows-1252", "iso-8859-1", "utf-16", "ascii"]

class CyberEditor(CTkToplevel):
    def __init__(self, parent, remote_path, local_temp_path, sftp_client, on_save_callback):
        super().__init__(parent)
        self.title(f"CyberSFTP Editor – {os.path.basename(remote_path)}")
        self.geometry("1200x800")
        self.minsize(900, 600)
        ctk.set_appearance_mode("Dark")

        self.remote_path = remote_path
        self.local_temp_path = local_temp_path
        self.sftp = sftp_client
        self.on_save_callback = on_save_callback

        # Toolbar
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(toolbar, text="Encoding:").pack(side="left", padx=5)
        self.encoding_var = ctk.StringVar(value="utf-8")
        self.encoding_combo = CTkComboBox(toolbar, values=ENCODINGS, variable=self.encoding_var, command=self.reload_with_encoding)
        self.encoding_combo.pack(side="left", padx=5)

        ctk.CTkButton(toolbar, text="Speichern (Ctrl+S)", fg_color="green", command=self.save_file).pack(side="right", padx=5)
        ctk.CTkButton(toolbar, text="Schließen", fg_color="gray", command=self.on_close).pack(side="right", padx=5)

        # Textbox
        self.textbox = CTkTextbox(self, font=("Consolas", 14), wrap="none")
        self.textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Scrollbars
        v_scroll = ctk.CTkScrollbar(self, command=self.textbox.yview)
        v_scroll.pack(side="right", fill="y")
        self.textbox.configure(yscrollcommand=v_scroll.set)

        h_scroll = ctk.CTkScrollbar(self, orientation="horizontal", command=self.textbox.xview)
        h_scroll.pack(side="bottom", fill="x")
        self.textbox.configure(xscrollcommand=h_scroll.set)

        # Datei laden
        self.load_file()

        # Shortcuts
        self.bind("<Control-s>", lambda e: self.save_file())
        self.bind("<Control-w>", lambda e: self.on_close())

    def reload_with_encoding(self):
        self.load_file()

    def load_file(self):
        encoding = self.encoding_var.get()
        try:
            with open(self.local_temp_path, "r", encoding=encoding, errors="replace") as f:
                content = f.read()
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", content)
        except Exception as e:
            messagebox.showwarning("Ladefehler", f"Konnte nicht mit {encoding} laden:\n{e}")

    def save_file(self):
        encoding = self.encoding_var.get()
        try:
            content = self.textbox.get("1.0", "end-1c")
            with open(self.local_temp_path, "w", encoding=encoding) as f:
                f.write(content)
            self.sftp.put(self.local_temp_path, self.remote_path)
            messagebox.showinfo("Gespeichert", f"Datei mit {encoding} erfolgreich hochgeladen!")
            self.on_save_callback()
        except Exception as e:
            messagebox.showerror("Fehler", f"Speichern fehlgeschlagen:\n{e}")

    def on_close(self):
        if messagebox.askyesno("Schließen", "Editor schließen? Ungespeicherte Änderungen gehen verloren!"):
            try:
                os.remove(self.local_temp_path)
            except:
                pass
            self.destroy()


class CyberSFTP(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("CyberSFTP – Der geilste SFTP-Client 2025 🔥")
        self.geometry("1600x900")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.host = ctk.StringVar()
        self.port = ctk.StringVar(value="22")
        self.username = ctk.StringVar()
        self.password = ctk.StringVar()
        self.key_file = ctk.StringVar()

        self.ssh = None
        self.sftp = None
        self.channel = None
        self.connected = False

        self.local_dir = os.getcwd()
        self.remote_dir = "/"

        self.local_history = [self.local_dir]
        self.local_history_index = 0
        self.remote_history = ["/"]
        self.remote_history_index = 0

        self.sessions = self.load_sessions()

        self.create_widgets()
        self.refresh_local()
        self.update_session_list()
        self.refresh_remote_navigation_buttons()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if messagebox.askokcancel("Beenden", "CyberSFTP beenden?"):
            self.disconnect()
            self.destroy()

    def load_sessions(self):
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_sessions(self):
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.sessions, f, indent=2)

    def update_session_list(self):
        display_list = []
        for name, data in self.sessions.items():
            key_info = f" (Key: {os.path.basename(data.get('key_file', ''))})" if data.get("key_file") else ""
            display_list.append(f"{name}{key_info}")
        self.session_combo.configure(values=display_list)

    def create_widgets(self):
        conn_frame = ctk.CTkFrame(self)
        conn_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(conn_frame, text="Session:").grid(row=0, column=0, padx=5, pady=5)
        self.session_combo = ctk.CTkComboBox(conn_frame, values=[], command=self.load_session_from_display)
        self.session_combo.grid(row=0, column=1, padx=5, sticky="ew")

        ctk.CTkLabel(conn_frame, text="Host:").grid(row=0, column=2, padx=5)
        ctk.CTkEntry(conn_frame, textvariable=self.host, width=200).grid(row=0, column=3, padx=5)

        ctk.CTkLabel(conn_frame, text="Port:").grid(row=0, column=4, padx=5)
        ctk.CTkEntry(conn_frame, textvariable=self.port, width=80).grid(row=0, column=5, padx=5)

        ctk.CTkLabel(conn_frame, text="User:").grid(row=0, column=6, padx=5)
        ctk.CTkEntry(conn_frame, textvariable=self.username, width=150).grid(row=0, column=7, padx=5)

        ctk.CTkLabel(conn_frame, text="Pass:").grid(row=0, column=8, padx=5)
        ctk.CTkEntry(conn_frame, textvariable=self.password, show="*", width=150).grid(row=0, column=9, padx=5)

        ctk.CTkButton(conn_frame, text="Key wählen", command=self.choose_key).grid(row=0, column=10, padx=5)
        ctk.CTkButton(conn_frame, text="Session speichern", fg_color="#0066CC", command=self.save_current_session).grid(row=0, column=11, padx=5)
        ctk.CTkButton(conn_frame, text="Connect", fg_color="green", command=self.connect).grid(row=0, column=12, padx=10)
        ctk.CTkButton(conn_frame, text="Disconnect", fg_color="red", command=self.disconnect).grid(row=0, column=13, padx=10)

        conn_frame.columnconfigure(1, weight=1)

        main_pane = ttk.PanedWindow(self, orient="horizontal")
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        left_frame = ctk.CTkFrame(main_pane)
        main_pane.add(left_frame, weight=1)

        local_nav = ctk.CTkFrame(left_frame)
        local_nav.pack(fill="x", pady=5)
        self.local_back_btn = ctk.CTkButton(local_nav, text="←", width=40, command=self.local_go_back)
        self.local_back_btn.pack(side="left", padx=5)
        self.local_forward_btn = ctk.CTkButton(local_nav, text="→", width=40, command=self.local_go_forward)
        self.local_forward_btn.pack(side="left", padx=5)
        ctk.CTkLabel(local_nav, text="Lokaler Ordner", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=10)

        self.local_list = ctk.CTkScrollableFrame(left_frame)
        self.local_list.pack(fill="both", expand=True, padx=10, pady=5)

        terminal_frame = ctk.CTkFrame(left_frame, height=220)
        terminal_frame.pack(fill="x", pady=10)
        terminal_frame.pack_propagate(False)
        ctk.CTkLabel(terminal_frame, text="SSH Terminal", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10)
        self.terminal = CTkTextbox(terminal_frame, height=150)
        self.terminal.pack(fill="both", expand=True, padx=10, pady=5)
        self.terminal.insert("end", "Terminal bereit nach Connect...\n")
        self.terminal.configure(state="disabled")

        self.cmd_entry = ctk.CTkEntry(terminal_frame, placeholder_text="Befehl eingeben...")
        self.cmd_entry.pack(fill="x", padx=10, pady=5)
        self.cmd_entry.bind("<Return>", self.execute_ssh_command)

        remote_frame = ctk.CTkFrame(main_pane)
        main_pane.add(remote_frame, weight=1)

        remote_nav = ctk.CTkFrame(remote_frame)
        remote_nav.pack(fill="x", pady=5)
        self.remote_back_btn = ctk.CTkButton(remote_nav, text="←", width=40, command=self.remote_go_back)
        self.remote_back_btn.pack(side="left", padx=5)
        self.remote_forward_btn = ctk.CTkButton(remote_nav, text="→", width=40, command=self.remote_go_forward)
        self.remote_forward_btn.pack(side="left", padx=5)
        ctk.CTkLabel(remote_nav, text="Remote Server", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=10)

        self.remote_list = ctk.CTkScrollableFrame(remote_frame)
        self.remote_list.pack(fill="both", expand=True, padx=10, pady=5)

        self.remote_list.drop_target_register(DND_FILES)
        self.remote_list.dnd_bind('<<Drop>>', self.on_drop_upload)

        remote_btns = ctk.CTkFrame(remote_frame)
        remote_btns.pack(fill="x", pady=5)
        ctk.CTkButton(remote_btns, text="Refresh", command=self.refresh_remote).pack(side="left", padx=5)
        ctk.CTkButton(remote_btns, text="Neuer Ordner", command=self.remote_mkdir).pack(side="left", padx=5)
        ctk.CTkButton(remote_btns, text="Löschen", fg_color="darkred", command=self.remote_delete).pack(side="left", padx=5)

        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(fill="x", padx=20, pady=5)
        self.progress.set(0)

        self.status = ctk.CTkLabel(self, text="CyberSFTP bereit – Editor, Keys & Drag&Drop aktiv! 🔥")
        self.status.pack(pady=5)

        self.remote_menu = Menu(self, tearoff=0)
        self.remote_menu.add_command(label="Bearbeiten (CyberEditor)", command=self.edit_remote_file)
        self.remote_menu.add_command(label="Umbenennen", command=self.remote_rename)
        self.remote_menu.add_command(label="Löschen", command=self.remote_delete)

        self.bind_all("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        widget = event.widget
        if isinstance(widget, ctk.CTkLabel) and widget.master == self.remote_list:
            self.highlight_label(widget, self.remote_list)
            self.remote_menu.tk_popup(event.x_root, event.y_root)

    def on_drop_upload(self, event):
        if not self.connected:
            messagebox.showwarning("Nicht verbunden", "Zuerst verbinden!")
            return
        files = self.tk.splitlist(event.data)
        for file_path in files:
            if os.path.isfile(file_path):
                name = os.path.basename(file_path)
                remote_path = os.path.normpath(f"{self.remote_dir}/{name}").replace("\\", "/")
                threading.Thread(target=self.transfer, args=(file_path, remote_path, "upload")).start()

    def choose_key(self):
        file = filedialog.askopenfilename(title="Private Key auswählen")
        if file:
            self.key_file.set(file)
            self.status.configure(text=f"Key gewählt: {os.path.basename(file)} – wird automatisch gespeichert!")

    def save_current_session(self):
        name = CTkInputDialog(text="Sessionsname:", title="Session speichern").get_input()
        if not name or not self.host.get():
            return
        self.sessions[name] = {
            "host": self.host.get(),
            "port": self.port.get(),
            "username": self.username.get(),
            "password": self.password.get(),
            "key_file": self.key_file.get()  # AUTOMATISCH!
        }
        self.save_sessions()
        self.update_session_list()
        self.status.configure(text=f"Session '{name}' gespeichert (inkl. Key)!")

    def load_session_from_display(self, display_name):
        if not display_name:
            return
        real_name = display_name.split(" (Key:")[0]
        if real_name in self.sessions:
            data = self.sessions[real_name]
            self.host.set(data.get("host", ""))
            self.port.set(data.get("port", "22"))
            self.username.set(data.get("username", ""))
            self.password.set(data.get("password", ""))
            self.key_file.set(data.get("key_file", ""))
            key_text = f" (Key: {os.path.basename(self.key_file.get())})" if self.key_file.get() else ""
            self.status.configure(text=f"Session '{real_name}' geladen{key_text}")

    def connect(self):
        if self.connected:
            return
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if self.key_file.get() and os.path.exists(self.key_file.get()):
                pkey = paramiko.RSAKey.from_private_key_file(self.key_file.get())
                self.ssh.connect(self.host.get(), port=int(self.port.get()), username=self.username.get(), pkey=pkey)
            else:
                self.ssh.connect(self.host.get(), port=int(self.port.get()), username=self.username.get(), password=self.password.get())

            self.sftp = self.ssh.open_sftp()
            self.channel = self.ssh.invoke_shell(width=120, height=30)
            self.connected = True

            self.remote_history = ["/"]
            self.remote_history_index = 0

            threading.Thread(target=self.read_ssh_output, daemon=True).start()

            self.status.configure(text=f"Verbunden mit {self.host.get()}")
            self.refresh_remote()
            self.refresh_remote_navigation_buttons()
            self.terminal_insert("Verbunden! Terminal aktiv.\n$ ")
        except Exception as e:
            messagebox.showerror("Fehler", f"Verbindung fehlgeschlagen:\n{str(e)}")

    def disconnect(self):
        if self.sftp: self.sftp.close()
        if self.channel: self.channel.close()
        if self.ssh: self.ssh.close()
        self.connected = False
        self.clear_list(self.remote_list)
        self.status.configure(text="Getrennt")
        self.refresh_remote_navigation_buttons()
        self.terminal_insert("Verbindung getrennt.\n")

    def terminal_insert(self, text):
        self.terminal.configure(state="normal")
        self.terminal.insert("end", text)
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    def read_ssh_output(self):
        while self.connected:
            if self.channel.recv_ready():
                data = self.channel.recv(1024).decode('utf-8', errors='ignore')
                if data:
                    self.terminal_insert(data)
            time.sleep(0.05)

    def execute_ssh_command(self, event=None):
        if not self.connected: return "break"
        cmd = self.cmd_entry.get().strip()
        if cmd:
            self.terminal_insert(f"$ {cmd}\n")
            self.channel.send(cmd + "\n")
            self.cmd_entry.delete(0, "end")
        return "break"

    def clear_list(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def highlight_label(self, label, parent):
        for child in parent.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                child.configure(fg_color="transparent")
        label.configure(fg_color=("#2b2b2b", "#1f6aa5"))

    def refresh_local(self):
        self.clear_list(self.local_list)
        try:
            for item in sorted(os.listdir(self.local_dir)):
                path = os.path.join(self.local_dir, item)
                is_dir = os.path.isdir(path)
                size = os.path.getsize(path) if not is_dir else ""
                mod = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
                icon = "📁" if is_dir else "📄"
                label = ctk.CTkLabel(self.local_list, text=f"{icon} {item:<30} {str(size):>12}  {mod}", anchor="w", cursor="hand2")
                label.pack(fill="x", pady=1, padx=5)
                label.bind("<Double-1>", lambda e, p=path: self.local_navigate(p))
                label.bind("<Button-1>", lambda e, l=label: self.highlight_label(l, self.local_list))
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def local_navigate(self, path):
        if os.path.isdir(path):
            self.local_history = self.local_history[:self.local_history_index + 1]
            self.local_history.append(path)
            self.local_history_index += 1
            self.local_dir = path
            self.refresh_local()

    def local_go_back(self):
        if self.local_history_index > 0:
            self.local_history_index -= 1
            self.local_dir = self.local_history[self.local_history_index]
            self.refresh_local()

    def local_go_forward(self):
        if self.local_history_index < len(self.local_history) - 1:
            self.local_history_index += 1
            self.local_dir = self.local_history[self.local_history_index]
            self.refresh_local()

    def refresh_remote(self):
        if not self.connected: return
        self.clear_list(self.remote_list)
        try:
            current_dir = self.remote_dir.rstrip("/") or "/"
            if current_dir != "/":
                up = ctk.CTkLabel(self.remote_list, text="📁 .. (nach oben)", anchor="w", cursor="hand2")
                up.pack(fill="x", pady=1, padx=5)
                up.bind("<Double-1>", lambda e: self.remote_navigate_parent())
                up.bind("<Button-1>", lambda e, l=up: self.highlight_label(l, self.remote_list))

            for attr in sorted(self.sftp.listdir_attr(current_dir), key=lambda a: a.filename.lower()):
                is_dir = py_stat.S_ISDIR(attr.st_mode)
                size = attr.st_size if not is_dir else ""
                mod = time.strftime("%Y-%m-%d %H:%M", time.localtime(attr.st_mtime))
                perm = oct(attr.st_mode)[-4:]
                icon = "📁" if is_dir else "📄"
                full_path = (current_dir + "/" + attr.filename).replace("//", "/")
                label = ctk.CTkLabel(self.remote_list, text=f"{icon} {attr.filename:<30} {str(size):>12}  {perm}  {mod}", anchor="w", cursor="hand2")
                label.pack(fill="x", pady=1, padx=5)
                label.bind("<Double-1>", lambda e, p=full_path, d=is_dir: self.remote_navigate(p, d))
                label.bind("<Button-1>", lambda e, l=label: self.highlight_label(l, self.remote_list))
        except Exception as e:
            messagebox.showerror("Fehler", f"Ordner nicht lesbar:\n{str(e)}")

    def remote_navigate_parent(self):
        if self.remote_dir != "/":
            new_dir = os.path.dirname(self.remote_dir.rstrip("/")) or "/"
            self.remote_history = self.remote_history[:self.remote_history_index + 1]
            self.remote_history.append(new_dir)
            self.remote_history_index += 1
            self.remote_dir = new_dir
            self.refresh_remote()
            self.refresh_remote_navigation_buttons()

    def remote_navigate(self, path, is_dir):
        if is_dir:
            normalized = os.path.normpath(path).replace("\\", "/")
            if not normalized.startswith("/"): normalized = "/" + normalized
            self.remote_history = self.remote_history[:self.remote_history_index + 1]
            self.remote_history.append(normalized)
            self.remote_history_index += 1
            self.remote_dir = normalized
            self.refresh_remote()
            self.refresh_remote_navigation_buttons()

    def refresh_remote_navigation_buttons(self):
        self.remote_back_btn.configure(state="normal" if self.remote_history_index > 0 else "disabled")
        self.remote_forward_btn.configure(state="normal" if self.remote_history_index < len(self.remote_history) - 1 else "disabled")

    def remote_go_back(self):
        if self.remote_history_index > 0:
            self.remote_history_index -= 1
            self.remote_dir = self.remote_history[self.remote_history_index]
            self.refresh_remote()
            self.refresh_remote_navigation_buttons()

    def remote_go_forward(self):
        if self.remote_history_index < len(self.remote_history) - 1:
            self.remote_history_index += 1
            self.remote_dir = self.remote_history[self.remote_history_index]
            self.refresh_remote()
            self.refresh_remote_navigation_buttons()

    def get_selected_name(self, frame):
        for child in frame.winfo_children():
            if isinstance(child, ctk.CTkLabel) and child.cget("fg_color") != "transparent":
                text = child.cget("text").strip()
                return text[2:].split()[0]
        return None

    def edit_remote_file(self):
        name = self.get_selected_name(self.remote_list)
        if not name or name == ".." or not self.connected: return
        remote_path = os.path.normpath(f"{self.remote_dir}/{name}").replace("\\", "/")
        try:
            attr = self.sftp.stat(remote_path)
            if py_stat.S_ISDIR(attr.st_mode):
                messagebox.showinfo("Info", "Ordner können nicht bearbeitet werden.")
                return

            temp_path = os.path.join(os.getenv("TEMP"), f"cybersftp_{random.randint(1000,9999)}_{name}")
            self.sftp.get(remote_path, temp_path)

            CyberEditor(
                parent=self,
                remote_path=remote_path,
                local_temp_path=temp_path,
                sftp_client=self.sftp,
                on_save_callback=self.refresh_remote
            )
        except Exception as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht geöffnet werden:\n{e}")

    def remote_mkdir(self):
        name = CTkInputDialog(text="Ordnername:", title="Neuer Ordner").get_input()
        if name and self.connected:
            try:
                self.sftp.mkdir(os.path.normpath(f"{self.remote_dir}/{name}").replace("\\", "/"))
                self.refresh_remote()
            except Exception as e:
                messagebox.showerror("Fehler", str(e))

    def remote_delete(self):
        name = self.get_selected_name(self.remote_list)
        if not name or name == ".." or not self.connected: return
        if messagebox.askyesno("Löschen", f"{name} wirklich löschen?"):
            try:
                path = os.path.normpath(f"{self.remote_dir}/{name}").replace("\\", "/")
                if py_stat.S_ISDIR(self.sftp.stat(path).st_mode):
                    self.sftp.rmdir(path)
                else:
                    self.sftp.remove(path)
                self.refresh_remote()
            except Exception as e:
                messagebox.showerror("Fehler", str(e))

    def remote_rename(self):
        old = self.get_selected_name(self.remote_list)
        if not old or old == ".." or not self.connected: return
        new = CTkInputDialog(text="Neuer Name:", title="Umbenennen").get_input()
        if new:
            try:
                old_path = os.path.normpath(f"{self.remote_dir}/{old}").replace("\\", "/")
                new_path = os.path.normpath(f"{self.remote_dir}/{new}").replace("\\", "/")
                self.sftp.rename(old_path, new_path)
                self.refresh_remote()
            except Exception as e:
                messagebox.showerror("Fehler", str(e))

    def transfer(self, src, dst, direction):
        self.progress.set(0)
        def callback(t, total):
            if total > 0:
                self.progress.set(t / total)
        try:
            if direction == "upload":
                self.sftp.put(src, dst, callback=callback)
            else:
                self.sftp.get(src, dst, callback=callback)
            self.progress.set(1)
            self.status.configure(text="Transfer erfolgreich!")
            self.refresh_local()
            self.refresh_remote()
        except Exception as e:
            messagebox.showerror("Fehler", str(e))
            self.progress.set(0)


if __name__ == "__main__":
    app = CyberSFTP()
    app.mainloop()
