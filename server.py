import socket
import threading
import json
import time
import datetime

HOST = '0.0.0.0'
PORT = 5000

class ChatServer:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((HOST, PORT))
        self.server.listen()
        
        self.clients = {}  # socket: username
        self.muted_users = set()
        self.last_msg_time = {}  # username: timestamp
        self.lock = threading.Lock()
        
        print(f"[*] Server running on port {PORT}...")

    def broadcast(self, message_dict, exclude_sock=None):
        payload = json.dumps(message_dict).encode('utf-8')
        with self.lock:
            for client_sock in list(self.clients.keys()):
                if client_sock != exclude_sock:
                    try:
                        client_sock.sendall(payload + b'\n')
                    except Exception:
                        self.remove_client(client_sock)

    def remove_client(self, client_sock):
        with self.lock:
            if client_sock in self.clients:
                username = self.clients[client_sock]
                del self.clients[client_sock]
                client_sock.close()
                self.broadcast({"type": "system", "content": f"{username} left the chat."})
                self.broadcast_user_list()

    def broadcast_user_list(self):
        users = list(self.clients.values())
        self.broadcast({"type": "user_list", "users": users})

    def handle_client(self, client_sock, addr):
        buffer = ""
        try:
            while True:
                data = client_sock.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    self.process_message(client_sock, msg)
        except Exception as e:
            print(f"[!] Error handling client {addr}: {e}")
        finally:
            self.remove_client(client_sock)

    def process_message(self, client_sock, msg):
        msg_type = msg.get("type")
        
        if msg_type == "join":
            username = msg.get("username", "Anonymous")
            with self.lock:
                self.clients[client_sock] = username
            self.broadcast({"type": "system", "content": f"{username} joined the chat."})
            self.broadcast_user_list()
            
        elif msg_type == "chat":
            username = self.clients.get(client_sock, "Unknown")
            
            # Check Mute Status (Mitche blocks)
            if username in self.muted_users:
                self.send_direct(client_sock, {"type": "system", "content": "You are currently blocked from speaking by Mitche."})
                return

            # Check 10-second rate limit server-side
            now = time.time()
            last_time = self.last_msg_time.get(username, 0)
            if now - last_time < 10 and username != "Mitche":
                remaining = int(10 - (now - last_time))
                self.send_direct(client_sock, {"type": "system", "content": f"Rate limit active. Wait {remaining}s."})
                return

            self.last_msg_time[username] = now
            timestamp = datetime.datetime.now().strftime("%H:%M")

            self.broadcast({
                "type": "chat",
                "sender": username,
                "content": msg.get("content"),
                "pfp": msg.get("pfp"),
                "timestamp": timestamp
            })

        elif msg_type == "file":
            username = self.clients.get(client_sock, "Unknown")
            if username in self.muted_users:
                self.send_direct(client_sock, {"type": "system", "content": "You are blocked from sending files."})
                return
                
            self.broadcast({
                "type": "file",
                "sender": username,
                "filename": msg.get("filename"),
                "filedata": msg.get("filedata")
            })

        elif msg_type == "admin_block":
            sender = self.clients.get(client_sock, "")
            if sender == "Mitche":
                target = msg.get("target")
                if target:
                    self.muted_users.add(target)
                    self.broadcast({"type": "system", "content": f"Admin Mitche blocked {target} from speaking."})

        elif msg_type == "admin_unblock":
            sender = self.clients.get(client_sock, "")
            if sender == "Mitche":
                target = msg.get("target")
                if target in self.muted_users:
                    self.muted_users.remove(target)
                    self.broadcast({"type": "system", "content": f"Admin Mitche unblocked {target}."})

    def send_direct(self, client_sock, message_dict):
        try:
            payload = json.dumps(message_dict).encode('utf-8') + b'\n'
            client_sock.sendall(payload)
        except Exception:
            pass

    def start(self):
        while True:
            client_sock, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(client_sock, addr), daemon=True).start()

if __name__ == "__main__":
    server = ChatServer()
    server.start()