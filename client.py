"""
A primitive FTP (variant) server which supports Active Mode only
which can download multiple files concurrently.
"""

import socket
import threading
import os
import random
import logging
import time
import sys
import queue

from sty import fg

from utils import abk_recvmsg


if len(sys.argv) < 4:
    print("** FTP Variant **")
    print("Usage: python3 client.py [host] [port] [download_path]")
    sys.exit(-1)


DOWNLOAD_PATH = sys.argv[3]
if not os.path.exists(DOWNLOAD_PATH):
    print("{} does not exists".format(DOWNLOAD_PATH))
    sys.exit(-1)

logging.basicConfig(level=logging.INFO)

HOST = sys.argv[1]
PORT = int(sys.argv[2])

ADDRESS = (HOST, PORT)

COUNT = 0
MAX_COUNT = 0

COUNT_LOCK = threading.Lock()
COUNT_TO_MAXCOUNT = threading.Condition()


MSG_QUEUE = queue.Queue()
THREADS_LOC = {}
_x = 0
_y = 0


def print_there(x, y, text):
    sys.stdout.write("\x1b7\x1b[%d;%df%s\x1b8" % (x, y, text))
    sys.stdout.flush()


def save_cur_pos():
    sys.stdout.write("\x1bs")


def rest_cur_pos():
    sys.stdout.write("\x1bu")


class ProgressRenderingThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        global THREADS_LOC
        global _x, _y
        while True:

            tid, filename = MSG_QUEUE.get()

            if tid not in THREADS_LOC.keys():
                _x += 1
                THREADS_LOC[tid] = (_x, _y)
                print_there(THREADS_LOC[tid][0], THREADS_LOC[tid][1], filename)
                THREADS_LOC[tid] = (THREADS_LOC[tid][0],
                                    THREADS_LOC[tid][1] + len(filename) + 1)
            else:
                THREADS_LOC[tid] = (THREADS_LOC[tid][0],
                                    THREADS_LOC[tid][1] + 1)
            # print(progress)
            print_there(THREADS_LOC[tid][0], THREADS_LOC[tid][1],
                        fg.li_green + "◼" + fg.rs)
            MSG_QUEUE.task_done()


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
        global COUNT
        global MAX_COUNT
        global COUNT_LOCK
        global COUNT_TO_MAXCOUNT

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, self.port))
            s.listen()

            conn, _addr = s.accept()
            self.logger.debug("Data Handled Lock Acquired")

            if self.is_file_incoming:
                self.file_size = abk_recvmsg(conn).decode().strip("\r\n\x00")
                self.logger.debug("File Size: {}".format(self.file_size))
                self.file_size = int(self.file_size)

            content = ""
            recieved = 0
            old_progress = 0
            while True:
                if self.is_file_incoming:
                    if isinstance(content, str):
                        content = bytes()
                    response = abk_recvmsg(conn)
                    if not response:
                        break
                    content = content + response
                    recieved += len(response)
                    progress = int(100 * (recieved / self.file_size))
                    if progress > old_progress:
                        MSG_QUEUE.put(
                            (threading.get_ident(), self.filename))
                        old_progress = progress
                    if self.file_size - recieved == 0:
                        f = open(os.path.join(os.path.abspath(
                            DOWNLOAD_PATH), self.filename), "wb")
                        f.write(content)
                        f.close()
                        break
                    time.sleep(0.0005)
                    # print(self.file_size - recieved)
                else:
                    response = abk_recvmsg(conn)
                    if not response:
                        break
                    content = content + response.decode()
            print()
            if not self.is_file_incoming:
                print(content)

            with COUNT_LOCK:
                COUNT += 1
                if COUNT == MAX_COUNT:
                    COUNT_TO_MAXCOUNT.acquire()
                    COUNT_TO_MAXCOUNT.notify_all()
                    COUNT_TO_MAXCOUNT.release()
                    self.logger.debug("COUNT_TO_MAX notified")
            self.logger.debug("COUNT Locked released")


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
    ProgressRenderingThread().start()

    global COUNT
    global MAX_COUNT
    global COUNT_LOCK
    global COUNT_TO_MAXCOUNT
    main_logger = logging.getLogger("MAIN")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(ADDRESS)
        response = s.recv(1024).decode()
        print(fg.li_blue + response + fg.rs)

        while True:
            MAX_COUNT = 0
            COUNT = 0
            command = input(fg.green + ">> " + fg.rs)
            command = command.split()
            if not command:
                continue
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
                thread = HandleClientDataThread()
                thread.start()
                send_port(s, cmd, HOST, thread.port)
                well_formed_command = True

            elif cmd == 'RETR' and args:
                threads = []
                for filename in args:
                    threads.append(HandleClientDataThread(
                        is_file_incoming=True, filename=filename))
                    MAX_COUNT += 1
                os.system("clear")
                for thread in threads:
                    thread.start()
                    send_port(s, cmd, HOST, thread.port)
                main_logger.info("Max COUNT %d" % MAX_COUNT)
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
                elif cmd == 'LIST' and response[:3] != '530':
                    response = abk_recvmsg(s).decode()
                    print(response)

                elif cmd == 'RETR' and response[:3] != '530':
                    COUNT_TO_MAXCOUNT.acquire()
                    main_logger.debug("Waiting for COUNT_TO_MAX")

                    COUNT_TO_MAXCOUNT.wait()

                    main_logger.debug("Wait Ended for COUNT_TO_MAX")
                    for _i in range(MAX_COUNT):
                        response = abk_recvmsg(s).decode()
                        print(response)
                    THREADS_LOC.clear()
                    COUNT_TO_MAXCOUNT.release()
                elif cmd == 'SIZE' and response[:3] != '530':
                    file_size = abk_recvmsg(s).decode()
                    print("File Size:", file_size)


main()
