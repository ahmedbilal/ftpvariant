import socket
import threading
import os

HOST = '127.0.0.1'
PORT = 36

ADDRESS = (HOST, PORT)

allowed_users = ['anonymous', 'bilal']

def abk_sendmsg(sock, msg):
    modded_msg = msg[:256]  # only first 256 chars
    modded_msg = modded_msg.ljust(256, chr(0))  # padd with \0 upto 256 len
    sock.sendall(modded_msg)

class WorkerThread(threading.Thread):
    def __init__(self, conn, addr):
        threading.Thread.__init__(self)

        self.conn = conn
        self.addr = addr
    
    def run(self):
        local_data = threading.local()
        local_data.user_logged_in = False
        local_data.cwd = os.getcwd()

        local_data.user_data_port = None
        local_data.user_host = None
        local_data.user_data_sock = None

        while True:
            command =  self.conn.recv(1024).decode("utf-8")
            
            command = command.split()
            if command == []:
                self.conn.close()
                return
            cmd = command[0]
            args = command[1:]
            print(command)
            if cmd == 'USER':
                if args[0] in allowed_users:
                    print("Lo and Behold. User have arrived.")
                    local_data.user_logged_in = True
                    self.conn.sendall(b"230 User logged in\r\n")
                else:
                    self.conn.sendall(b"530 Wrong Credentials\r\n")

            elif cmd == 'PWD':
                output = "257 {}\r\n".format(local_data.cwd)
                self.conn.sendall(output.encode())

            elif cmd == 'SYST':
                self.conn.sendall(b"215 Linux\r\n")            

            elif cmd == 'CWD':
                try:
                    os.chdir(args[0])
                    local_data.cwd = os.getcwd()
                    output = "250 CWD = {}\r\n".format(local_data.cwd)
                    self.conn.sendall(output.encode())
                
                except FileNotFoundError:
                    self.conn.sendall(b"550 No Such path exists\r\n")
            
            elif cmd == 'RETR' and args[0]:
                self.conn.sendall(b"125\r\n")
                try:
                    with open(args[0], 'r') as output_file:
                        size = os.path.getsize(args[0])
                        self.conn.sendall(("{}\r\n".format(size)).encode())
    
                        with local_data.user_data_sock as user_data_sock:
                            user_data_sock.connect((local_data.user_host, local_data.user_data_port))
                            for c in output_file.read():
                                user_data_sock.sendall(c.encode())
                            self.conn.sendall(b"250 File Succesfully transmitted\r\n")
                
                except FileNotFoundError:
                    self.conn.sendall(b"550 File Not Found\r\n")

            elif cmd == 'QUIT':
                local_data.user_logged_in = False
                self.conn.sendall(b"221 Logging out\r\n")
                self.conn.close()
                return
            
            elif cmd == 'PORT':
                address = args[0].split(",")
                print(args)
                local_data.user_host = ".".join(address[:-2])
                local_data.user_data_port = int(address[-2]) * 256 + int(address[-1])
                local_data.user_data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print(local_data.user_host, local_data.user_data_port)
                self.conn.sendall(b"200 OK\r\n")

            elif cmd == 'LIST':
                ls_output = os.listdir(local_data.cwd)
                self.conn.sendall(b"125 Transfer started\r\n")
                # print(local_data.user_data_sock)
                with local_data.user_data_sock as user_data_sock:
                    user_data_sock.connect((local_data.user_host, local_data.user_data_port))
                    for entry in ls_output:
                        _entry = "{}\r\n".format(entry)
                        user_data_sock.sendall(_entry.encode())
                    self.conn.sendall(b"226 Transfer Complete\r\n")
            
            elif cmd == 'SIZE':

                if args and len(args[0]):
                    self.conn.sendall(b"125\r\n")
                    try:
                        size = os.path.getsize(args[0])
                        self.conn.sendall(("{}\r\n".format(size)).encode())                            
                        self.conn.sendall(b"250 File Size Succesfully transmitted\r\n")

                    except FileNotFoundError:
                        self.conn.sendall(b"550 File Not Found\r\n")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(ADDRESS)

        s.listen(10)
        while True:
            conn, addr = s.accept()
            conn.sendall(b"220 Ready to execute commands\r\n")
            WorkerThread(conn, addr).start()


main()