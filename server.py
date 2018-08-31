"""
A primitive FTP (variant) server which supports Active Mode only
which can download multiple files concurrently.
"""

import socket
import threading
import os
import sys
from collections import namedtuple

from utils import abk_sendmsg

HOST = '127.0.0.1'

if len(sys.argv) < 2:
    print("** FTP Variant **")
    print("Usage: sudo python3 server.py [port]")
    sys.exit(-1)

PORT = int(sys.argv[1])

ADDRESS = (HOST, PORT)

ALLOWED_USERS = ['anonymous']
PRIVILEGED_COMMANDS = ['PWD', 'CWD', 'PORT', 'LIST', 'RETR', 'SIZE']

FileRetrRequest = namedtuple(
    "FileRetrRequest", "filename host port data_sock conn")


class FileSenderThread(threading.Thread):
    """Thread responsible for sending files
       which user requested through RETR command."""

    def __init__(self, file_retr_request):
        threading.Thread.__init__(self)
        self.filename = file_retr_request.filename
        self.host = file_retr_request.host
        self.port = file_retr_request.port
        self.data_sock = file_retr_request.data_sock
        self.conn = file_retr_request.conn

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
    """Thread responsible for getting and running user
       commands"""

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
                    file_retr_request = FileRetrRequest(file,
                                                        local_data.user_host,
                                                        local_data.user_data_ports.pop(
                                                            0), local_data.user_data_socks.pop(0), self.conn)

                    FileSenderThread(file_retr_request).start()

            elif cmd == 'QUIT':
                local_data.user_logged_in = False
                abk_sendmsg(self.conn, b"221 Logging out\r\n")
                self.conn.close()
                return

            elif cmd == 'SIZE':
                if args and args[0]:
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
    """Listen for connection and as soon as user connects create a WorkerThread
       to handle user's requests"""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(ADDRESS)

        sock.listen(10)
        while True:
            conn, addr = sock.accept()
            abk_sendmsg(conn, b"220 Ready to execute commands\r\n")
            WorkerThread(conn, addr).start()


main()
