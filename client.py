import socket
import threading
import os
import random
import logging
import time
import sys
from sty import fg, rs

logging.basicConfig(level=logging.DEBUG)

HOST = '127.0.0.1'
PORT = 24

ADDRESS = (HOST, PORT)

count = 0
max_count = 0

COUNT_LOCK = threading.Lock()
COUNT_TO_MAXCOUNT = threading.Condition()


def abk_sendmsg(sock, msg):
    modded_msg = msg[:256]  # only first 256 chars
    if type(modded_msg) == bytes:
        modded_msg = modded_msg.decode()
        modded_msg = modded_msg.ljust(256, chr(0))  # padd with \0 upto 256 len
        modded_msg = modded_msg.encode()
    else:
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


class HandleClientDataThread(threading.Thread):
    def __init__(self, is_file_incoming=False, filename=None):
        threading.Thread.__init__(self)
        self.daemon = True

        self.logger = logging.getLogger("HandleClientDataThread")

        self.filename = filename
        self.file_size = None
        self.is_file_incoming = is_file_incoming

        self.port = random.randint(10000, 15000)

    def run(self):
        global count
        global max_count
        global COUNT_LOCK
        global COUNT_TO_MAXCOUNT

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, self.port))
            s.listen()

            conn, addr = s.accept()
            self.logger.debug("Data Handled Lock Acquired")

            if self.is_file_incoming:
                self.file_size = abk_recvmsg(conn).decode().strip("\r\n\x00")
                self.logger.debug("File Size: {}".format(self.file_size))
                self.file_size = int(self.file_size)
                print("Progress: ", end='')

            content = ""
            recieved = 0
            old_progress = 0

            while True:
                if self.is_file_incoming:
                    if type(content) == str:
                        content = bytes()
                    response = abk_recvmsg(conn)
                    if not response:
                        break
                    content = content + response
                    recieved += len(response)
                    progress = int(100 * (recieved / self.file_size))
                    if progress > old_progress:
                        if progress % 2 == 0:
                            print(fg.li_green + "◼" + fg.rs, end="")
                        else:
                            print("", end="")
                        sys.stdout.flush()

                        old_progress = progress

                    if self.file_size - recieved == 0:
                        f = open("/home/bilal/Desktop/" + self.filename, "wb")
                        f.write(content)
                        f.close()
                        break
                    # time.sleep(0.005)
                else:
                    response = abk_recvmsg(conn)
                    if not response:
                        break
                    content = content + response.decode()
            print()
            if not self.is_file_incoming:
                print(content)
            
            with COUNT_LOCK:
                count += 1
                if count == max_count:
                    COUNT_TO_MAXCOUNT.acquire()
                    COUNT_TO_MAXCOUNT.notify()
                    COUNT_TO_MAXCOUNT.release()

            self.logger.debug("COUNT Locked released and COUNT_TO_MAX notified")


def send_port(s, cmd, host, port):
    new_cmd = 'PORT'
    new_command = "{cmd} {host} {port}".format(cmd=new_cmd,
                                               host=host,
                                               port=port)
    new_command = new_command.encode()
    s.sendall(new_command)
    response = abk_recvmsg(s).decode()  # recv PORT's response
    print(response)


def main():
    global count
    global max_count
    global COUNT_LOCK
    global COUNT_TO_MAXCOUNT
    main_logger = logging.getLogger("MAIN")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(ADDRESS)
        response = s.recv(1024).decode()
        print(fg.li_blue + response + fg.rs)

        while True:
            max_count = 0
            count = 0
            command = input(fg.green + ">> " + fg.rs)
            command = command.split()
            command[0] = command[0].upper()
            command = " ".join(command)

            splitted_command = command.split()
            command = command.encode()

            cmd = splitted_command[0]
            args = splitted_command[1:]

            well_formed_command = False

            if cmd == 'USER' and args and len(args) == 1:
                well_formed_command = True

            elif cmd == 'PWD':
                well_formed_command = True

            elif cmd == 'SYST':
                well_formed_command = True

            elif cmd == 'CWD' and args and len(args) == 1:
                    well_formed_command = True

            elif cmd == 'QUIT' and not args:
                well_formed_command = True

            elif cmd == 'LIST':
                t = HandleClientDataThread()
                t.start()
                send_port(s, cmd, HOST, t.port)
                well_formed_command = True

            elif cmd == 'RETR' and args:
                threads = []
                for filename in args:
                    threads.append(HandleClientDataThread(is_file_incoming=True,
                                               filename=filename))
                    max_count += 1
                
                for t in threads:
                    t.start()
                    send_port(s, cmd, HOST, t.port)

                well_formed_command = True

            elif cmd == 'SIZE' and args and len(args) == 1:
                well_formed_command = True

            if well_formed_command:
                s.sendall(command)
                response = abk_recvmsg(s).decode()
                print("SERVER RESPONSE:", response)

                if cmd == 'QUIT':
                    s.close()
                    return 0
                elif cmd == 'LIST':
                    response = abk_recvmsg(s).decode()
                    print(response)
                elif cmd == 'RETR':
                    COUNT_TO_MAXCOUNT.acquire()
                    main_logger.debug("Waiting for COUNT_TO_MAX")
                    COUNT_TO_MAXCOUNT.wait()
                    main_logger.debug("Wait Ended for COUNT_TO_MAX")
                    for i in range(max_count):
                        response = abk_recvmsg(s).decode()
                        print(response)
                    COUNT_TO_MAXCOUNT.release()
                elif cmd == 'SIZE':
                    file_size = abk_recvmsg(s).decode()
                    print("File Size:", file_size)

main()
