import socket
import threading
import json
import base64
import time
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

class LANChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Tkinter LAN Chatroom")
        self.root.geometry("750x550")

        self.sock = None
        self.username = ""
        self.pfp_base64 = ""
        self.pfp_images = {}  # Cache PhotoImage objects to prevent GC
        self.last_sent_time = 0

        self.setup_login_ui()

    def setup_login_ui(self):
        self.login_frame = tk.Frame(self.root, padx=20, pady=20)
        self.login_frame.pack(expand=True)

        tk.Label(self.login_frame, text="Server IP Address:").grid(row=0, column=0, sticky="w", pady=5)
        self.ip_entry = tk.Entry(self.login_frame, width=25)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.grid(row=0, column=1, pady=5)

        tk.Label(self.login_frame, text="Username:").grid(row=1, column=0, sticky="w", pady=5)
        self.user_entry = tk.Entry(self.login_frame, width=25)
        self.user_entry.grid(row=1, column=1, pady=5)

        tk.Label(self.login_frame, text="Profile Picture (PNG/GIF):").grid(row=2, column=0, sticky="w", pady=5)
        self.pfp_btn = tk.Button(self.login_frame, text="Select File...", command=self.load_pfp)
        self.pfp_btn.grid(row=2, column=1, sticky="w", pady=5)

        self.pfp_label = tk.Label(self.login_frame, text="No image selected", fg="gray")
        self.pfp_label.grid(row=3, column=0, columnspan=2)

        self.connect_btn = tk.Button(self.login_frame, text="Connect to Chat", command=self.connect_to_server, bg="#d0d0d0")
        self.connect_btn.grid(row=4, column=0, columnspan=2, pady=15)

    def load_pfp(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.gif")])
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    data = f.read()
                    self.pfp_base64 = base64.b64encode(data).decode('utf-8')
                self.pfp_label.config(text=os.path.basename(file_path), fg="green")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read image: {e}")

    def connect_to_server(self):
        self.username = self.user_entry.get().strip()
        server_ip = self.ip_entry.get().strip()

        if not self.username:
            messagebox.showwarning("Warning", "Username cannot be empty.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((server_ip, 5000))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Unable to connect: {e}")
            return

        # Send join frame
        join_payload = json.dumps({"type": "join", "username": self.username}) + "\n"
        self.sock.sendall(join_payload.encode('utf-8'))

        self.login_frame.destroy()
        self.setup_chat_ui()

        threading.Thread(target=self.receive_messages, daemon=True).start()

    def setup_chat_ui(self):
        # Main Layout Frames
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Column: Chat log
        self.chat_frame = tk.Frame(self.main_frame)
        self.chat_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.chat_display = tk.Text(self.chat_frame, state=tk.DISABLED, wrap=tk.WORD)
        self.chat_display.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Bottom Input Controls
        self.input_frame = tk.Frame(self.chat_frame, pady=5)
        self.input_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.msg_entry = tk.Entry(self.input_frame)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.msg_entry.bind("<Return>", lambda e: self.send_chat_message())

        self.send_btn = tk.Button(self.input_frame, text="Send", command=self.send_chat_message)
        self.send_btn.pack(side=tk.LEFT, padx=2)

        self.file_btn = tk.Button(self.input_frame, text="Send File", command=self.send_file)
        self.file_btn.pack(side=tk.LEFT, padx=2)

        # Right Column: User list & Admin panel
        self.right_frame = tk.Frame(self.main_frame, width=180, padx=5)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(self.right_frame, text="Connected Users", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        self.user_listbox = tk.Listbox(self.right_frame, width=20)
        self.user_listbox.pack(fill=tk.BOTH, expand=True)

        # Admin Controls (Shown only for "Mitche")
        if self.username == "Mitche":
            admin_label = tk.Label(self.right_frame, text="Mitche Controls", font=("TkDefaultFont", 9, "bold"), fg="red")
            admin_label.pack(anchor="w", pady=(10, 2))

            self.block_btn = tk.Button(self.right_frame, text="Block Member", command=self.block_selected_user)
            self.block_btn.pack(fill=tk.X, pady=2)

            self.unblock_btn = tk.Button(self.right_frame, text="Unblock Member", command=self.unblock_selected_user)
            self.unblock_btn.pack(fill=tk.X, pady=2)

    def send_chat_message(self):
        now = time.time()
        # Rate-limiting check (10 seconds per message unless username is Mitche)
        if self.username != "Mitche" and (now - self.last_sent_time) < 10:
            remaining = int(10 - (now - self.last_sent_time))
            self.append_system_message(f"[System] Rate limit active. Please wait {remaining} seconds.")
            return

        content = self.msg_entry.get().strip()
        if not content:
            return

        payload = {
            "type": "chat",
            "content": content,
            "pfp": self.pfp_base64
        }
        try:
            self.sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))
            self.last_sent_time = now
            self.msg_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send message: {e}")

    def send_file(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return

        filename = os.path.basename(file_path)
        try:
            with open(file_path, "rb") as f:
                encoded_data = base64.b64encode(f.read()).decode('utf-8')

            payload = {
                "type": "file",
                "filename": filename,
                "filedata": encoded_data
            }
            self.sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read/send file: {e}")

    def block_selected_user(self):
        selected = self.user_listbox.curselection()
        if selected:
            target = self.user_listbox.get(selected[0])
            payload = {"type": "admin_block", "target": target}
            self.sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))

    def unblock_selected_user(self):
        selected = self.user_listbox.curselection()
        if selected:
            target = self.user_listbox.get(selected[0])
            payload = {"type": "admin_unblock", "target": target}
            self.sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))

    def receive_messages(self):
        buffer = ""
        while True:
            try:
                data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    self.root.after(0, self.handle_incoming_message, msg)
            except Exception:
                break

    def handle_incoming_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "system":
            self.append_system_message(f"[System] {msg.get('content')}")

        elif msg_type == "user_list":
            self.user_listbox.delete(0, tk.END)
            for user in msg.get("users", []):
                self.user_listbox.insert(tk.END, user)

        elif msg_type == "chat":
            sender = msg.get("sender")
            content = msg.get("content")
            pfp_data = msg.get("pfp")
            timestamp = msg.get("timestamp", "")

            self.chat_display.config(state=tk.NORMAL)
            
            # Display PFP image if available
            if pfp_data:
                try:
                    raw_bytes = base64.b64decode(pfp_data)
                    img = tk.PhotoImage(data=raw_bytes)
                    width, height = img.width(), img.height()
                    if width > 32 or height > 32:
                        factor = max(width // 32, height // 32)
                        if factor > 0:
                            img = img.subsample(factor, factor)

                    img_key = f"{sender}_{time.time()}"
                    self.pfp_images[img_key] = img
                    self.chat_display.image_create(tk.END, image=img)
                    self.chat_display.insert(tk.END, " ")
                except Exception:
                    pass

            time_prefix = f"[{timestamp}] " if timestamp else ""
            self.chat_display.insert(tk.END, f"{time_prefix}{sender}: {content}\n")
            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)

        elif msg_type == "file":
            sender = msg.get("sender")
            filename = msg.get("filename")
            filedata = msg.get("filedata")

            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.insert(tk.END, f"[File from {sender}]: {filename} ")

            # Unique tag for save link
            tag_name = f"file_{time.time()}"
            self.chat_display.insert(tk.END, "[Save File]\n", tag_name)
            self.chat_display.tag_config(tag_name, foreground="blue", underline=1)
            self.chat_display.tag_bind(tag_name, "<Button-1>", lambda e, fn=filename, fd=filedata: self.save_received_file(fn, fd))

            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)

    def save_received_file(self, default_filename, filedata_b64):
        save_path = filedialog.asksaveasfilename(initialfile=default_filename)
        if save_path:
            try:
                file_bytes = base64.b64decode(filedata_b64)
                with open(save_path, "wb") as f:
                    f.write(file_bytes)
                messagebox.showinfo("Success", f"Saved to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")

    def append_system_message(self, text):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{text}\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = LANChatClient(root)
    root.mainloop()