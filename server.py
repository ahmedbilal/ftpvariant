import socket
import threading
import os

HOST = '127.0.0.1'
PORT = 24

ADDRESS = (HOST, PORT)

ALLOWED_USERS = ['anonymous']
PRIVILEGED_COMMANDS = ['PWD', 'CWD', 'PORT', 'LIST', 'RETR', 'SIZE']


def abk_sendmsg(sock, msg):
    modded_msg = msg[:256]  # only first 256 chars
    if type(modded_msg) == bytes:
        modded_msg = modded_msg.decode()
        modded_msg = modded_msg.ljust(256, chr(0))  # padd with \0 upto 256 len
        modded_msg = modded_msg.encode()
    elif type(modded_msg) == str:
        modded_msg = modded_msg.ljust(256, chr(0))
    sock.sendall(modded_msg)


def abk_recvmsg(sock):
    length = 256
    msg = b""
    while length > 0:
        received = sock.recv(256)
        length -= len(received)
        msg += received

        if len(received) < 256:
            return msg
    return msg


class FileSenderThread(threading.Thread):
    def __init__(self, filename, host, port, data_sock, conn):
        threading.Thread.__init__(self)
        self.filename = filename
        self.host = host
        self.port = port
        self.data_sock = data_sock
        self.conn = conn

    def run(self):
        try:
            with open(self.filename, 'rb') as output_file:
                size = os.path.getsize(self.filename)

                with self.data_sock as user_data_sock:
                    user_data_sock.connect((self.host, self.port))
                    abk_sendmsg(user_data_sock,
                                ("{}\r\n".format(size)).encode())
                    user_data_sock.sendall(output_file.read())
                    abk_sendmsg(self.conn,
                                b"250 File Succesfully transmitted\r\n")

        except FileNotFoundError:
            with self.data_sock as user_data_sock:
                user_data_sock.connect((self.host, self.port))
                abk_sendmsg(user_data_sock, b"-1\r\n")
            abk_sendmsg(self.conn, b"550 File Not Found\r\n")


class WorkerThread(threading.Thread):
    def __init__(self, conn, addr):
        threading.Thread.__init__(self)

        self.conn = conn
        self.addr = addr

    def run(self):
        local_data = threading.local()
        local_data.user_logged_in = False
        local_data.cwd = os.getcwd()

        local_data.user_data_ports = []
        local_data.user_host = None
        local_data.user_data_socks = []

        while True:
            command = self.conn.recv(1024).decode("utf-8")

            command = command.split()
            if command == []:
                self.conn.close()
                return
            cmd = command[0]
            args = command[1:]
            print(command)

            if cmd in PRIVILEGED_COMMANDS:
                if not local_data.user_logged_in:
                    abk_sendmsg(self.conn, b"530 User not logged in\r\n")
                    continue

            if cmd == 'USER':
                if args[0] in ALLOWED_USERS:
                    print("Lo and Behold. User have arrived.")
                    local_data.user_logged_in = True
                    abk_sendmsg(self.conn, b"230 User logged in\r\n")
                else:
                    abk_sendmsg(self.conn, b"530 Wrong Credentials\r\n")

            elif cmd == 'PWD':
                output = "257 {}\r\n".format(local_data.cwd)
                abk_sendmsg(self.conn, output.encode())

            elif cmd == 'SYST':
                abk_sendmsg(self.conn, b"215 Linux\r\n")

            elif cmd == 'CWD':
                try:
                    os.chdir(args[0])
                    local_data.cwd = os.getcwd()
                    output = "250 CWD = {}\r\n".format(local_data.cwd)
                    abk_sendmsg(self.conn, output.encode())

                except FileNotFoundError:
                    abk_sendmsg(self.conn, b"550 No Such path exists\r\n")

            elif cmd == 'PORT':
                local_data.user_host = args[0]
                for port in args[1:]:
                    local_data.user_data_ports.append(int(port))
                    local_data.user_data_socks.append(
                        socket.socket(socket.AF_INET, socket.SOCK_STREAM))
                print(local_data.user_host, local_data.user_data_ports)
                abk_sendmsg(self.conn, b"200 OK\r\n")

            elif cmd == 'LIST':
                ls_output = os.listdir(local_data.cwd)
                abk_sendmsg(self.conn, b"125 Transfer started\r\n")

                with local_data.user_data_socks.pop() as user_data_sock:
                    user_data_sock.connect(
                        (
                            local_data.user_host,
                            local_data.user_data_ports.pop()
                        )
                    )

                    for entry in ls_output:
                        _entry = "{}\r\n".format(entry)
                        abk_sendmsg(user_data_sock, _entry.encode())
                    abk_sendmsg(self.conn, b"226 Transfer Complete\r\n")

            elif cmd == 'RETR' and args[0]:
                abk_sendmsg(self.conn, b"125\r\n")
                for file in args:
                    FileSenderThread(filename=file,
                                     data_sock=local_data.user_data_socks.pop(
                                         0),
                                     host=local_data.user_host,
                                     port=local_data.user_data_ports.pop(
                                         0),
                                     conn=self.conn
                                     ).start()

            elif cmd == 'QUIT':
                local_data.user_logged_in = False
                abk_sendmsg(self.conn, b"221 Logging out\r\n")
                self.conn.close()
                return

            elif cmd == 'SIZE':
                if len(args) > 0 and args[0]:
                    abk_sendmsg(self.conn, b"125\r\n")
                    try:
                        size = os.path.getsize(args[0])

                        abk_sendmsg(
                            self.conn, ("{}\r\n".format(size)).encode())

                        abk_sendmsg(
                            self.conn,
                            b"250 File Size Succesfully transmitted\r\n")

                    except FileNotFoundError:
                        abk_sendmsg(self.conn, b"-1\r\n")
                        abk_sendmsg(self.conn, b"550 File Not Found\r\n")


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(ADDRESS)

        sock.listen(10)
        while True:
            conn, addr = sock.accept()
            abk_sendmsg(conn, b"220 Ready to execute commands\r\n")
            WorkerThread(conn, addr).start()


main()
