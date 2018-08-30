import socket
import threading
import os
import random
import logging
import time
import sys
import queue
from sty import fg, rs

logging.basicConfig(level=logging.INFO)

HOST = '127.0.0.1'
PORT = 24

ADDRESS = (HOST, PORT)

count = 0
max_count = 0

COUNT_LOCK = threading.Lock()
COUNT_TO_MAXCOUNT = threading.Condition()


MSG_QUEUE = queue.Queue()
threads_loc = {}
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
        global threads_loc
        global _x, _y
        while True:

            tid, filename = MSG_QUEUE.get()

            if tid not in threads_loc.keys():
                _x += 1
                threads_loc[tid] = (_x, _y)
                print_there(threads_loc[tid][0], threads_loc[tid][1], filename)
                threads_loc[tid] = (threads_loc[tid][0],
                                    threads_loc[tid][1] + len(filename) + 1)
            else:
                threads_loc[tid] = (threads_loc[tid][0],
                                    threads_loc[tid][1] + 1)
            # print(progress)
            print_there(threads_loc[tid][0], threads_loc[tid][1],
                        fg.li_green + "◼" + fg.rs)
            MSG_QUEUE.task_done()


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
                    if type(content) == str:
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
                        f = open("/home/bilal/Desktop/" + self.filename, "wb")
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
                count += 1
                if count == max_count:
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
            if len(command) == 0:
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
                t = HandleClientDataThread()
                t.start()
                send_port(s, cmd, HOST, t.port)
                well_formed_command = True

            elif cmd == 'RETR' and args:
                threads = []
                for filename in args:
                    threads.append(HandleClientDataThread(
                        is_file_incoming=True, filename=filename)
                    )
                    max_count += 1
                os.system("clear")
                for t in threads:
                    t.start()
                    send_port(s, cmd, HOST, t.port)
                main_logger.info("Max Count {}".format(max_count))
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
                    for _i in range(max_count):
                        response = abk_recvmsg(s).decode()
                        print(response)
                    threads_loc.clear()
                    COUNT_TO_MAXCOUNT.release()
                elif cmd == 'SIZE' and response[:3] != '530':
                    file_size = abk_recvmsg(s).decode()
                    print("File Size:", file_size)


main()
