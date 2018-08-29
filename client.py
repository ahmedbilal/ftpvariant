import socket
import threading
import os
import random
import logging
import time
import sys
from sty import fg, bg, ef, rs

logging.basicConfig(level=logging.INFO)


def random_color():
    colors = [fg.li_blue, fg.li_cyan, fg.li_green, fg.li_magenta, fg.li_red,
              fg.li_white, fg.li_yellow]
    return random.choice(colors)

HOST = '127.0.0.1'
PORT = 20

ADDRESS = (HOST, PORT)

p1 = random.randint(30, 50)
p2 = random.randint(96, 128)
p1_256_p2 = p1 * 256 + p2

logging.debug("P1:{}, P2:{}, P1*256 + P2:{}".format(p1, p2, p1_256_p2))

is_file_incoming = False
filename = None
file_size = None

FILE_SIZE_LOCK = threading.Lock()
DATA_HANDLED_LOCK = threading.Lock()


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
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.logger = logging.getLogger("HandleClientDataThread")
        self.file_size = 0
        self.is_file_incoming = False

    def run(self):
        global is_file_incoming
        global file_size
        global FILE_SIZE_LOCK
        global DATA_HANDLED_LOCK
        global filename
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, p1_256_p2))
            s.listen()

            while True:
                conn, addr = s.accept()
                DATA_HANDLED_LOCK.acquire()
                self.logger.debug("Data Handled Lock Acquired")

                # print("FTP Server link with me on data port")
                

                if is_file_incoming:
                    with FILE_SIZE_LOCK:
                        self.file_size = file_size
                        self.logger.debug("FILE SIZE lock acquired")
                        self.logger.debug("File Size: {}".format(file_size))
                    self.logger.debug("FILE Size lock released")
                content = ""
                recieved = 0
                old_progress = 0
                if is_file_incoming:
                    print("Progress: ", end='')

                while True:                    
                    if is_file_incoming:
                        if type(content) == str:
                            content = bytes()
                        response = abk_recvmsg(conn)
                        if not response:
                            break
                        content = content + response
                        recieved += len(response)
                        progress = int(100 * (recieved / file_size))
                        if progress > old_progress:
                            if progress % 2 == 0:
                                print(fg.li_green + "◼" + fg.rs, end="")
                            else:
                                print("", end="")
                            sys.stdout.flush()

                            old_progress = progress

                        if file_size - recieved == 0:
                            f = open("/home/bilal/Desktop/" + filename, "wb")
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
                if not is_file_incoming:
                    print(content)
                DATA_HANDLED_LOCK.release()
                self.logger.debug("Data Handled Lock Released")


def send_port(s, cmd, host, p1, p2):
    new_cmd = 'PORT'
    new_command = "{cmd} {host},{p1},{p2}".format(cmd=new_cmd,
                                                  host=HOST.replace(".", ","),
                                                  p1=p1, p2=p2)
    new_command = new_command.encode()
    s.sendall(new_command)
    response = abk_recvmsg(s).decode()  # recv PORT's response
    print(response)


def main():
    main_logger = logging.getLogger("MAIN")

    global is_file_incoming
    global file_size
    global FILE_SIZE_LOCK
    global DATA_HANDLED_LOCK
    global filename

    HandleClientDataThread().start()


    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(ADDRESS)
        response = s.recv(1024).decode()
        print(fg.li_blue + response + fg.rs)

        while True:
            command = input(fg.green + ">> " + fg.rs)
            command = command.split()
            command[0] = command[0].upper()
            command = " ".join(command)

            splitted_command = command.split()
            command = command.encode()

            cmd = splitted_command[0]
            args = splitted_command[1:]

            well_formed_command = False
            
            if cmd == 'USER' and args and args[0]:
                well_formed_command = True
            
            elif cmd == 'PWD':
                well_formed_command = True
            
            elif cmd == 'SYST':
                well_formed_command = True
            
            elif cmd == 'CWD':
                if args and len(args) == 1:
                    well_formed_command = True
            
            elif cmd == 'QUIT' and not args:
                well_formed_command = True

            elif cmd == 'LIST':
                send_port(s, cmd, HOST, p1, p2)
                well_formed_command = True

            elif cmd == 'RETR' and args and len(args) == 1:
                is_file_incoming = True
                FILE_SIZE_LOCK.acquire()
                main_logger.debug("FILE Size lock acquired")

                send_port(s, cmd, HOST, p1, p2)
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
                    file_size = int(abk_recvmsg(s).decode().strip("\r\n\x00"))
                    filename = args[0]
                    print("File Size", file_size)
                    FILE_SIZE_LOCK.release()
                    main_logger.debug("FILE Size lock released")
                    response = abk_recvmsg(s).decode()
                    
                    with DATA_HANDLED_LOCK:
                        main_logger.debug("Acquired DATA Handled Lock")
                        print(response)
                        file_size = None
                        is_file_incoming = False
                        filename = None
                    main_logger.debug("Released DATA Handled Lock")


                elif cmd == 'SIZE':
                    file_size = abk_recvmsg(s).decode()
                    print("File Size:",file_size)
            
main()