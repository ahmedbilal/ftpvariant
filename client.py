import socket
import threading
import os
import random
import logging

logging.basicConfig(level=logging.DEBUG)


HOST = '127.0.0.1'
PORT = 36

ADDRESS = (HOST, PORT)

p1 = random.randint(30, 50)
p2 = random.randint(96, 128)
p1_256_p2 = p1 * 256 + p2

logging.debug("P1:{}, P2:{}, P1*256 + P2:{}".format(p1, p2, p1_256_p2))

is_file_incoming = False

file_size = None

FILE_SIZE_LOCK = threading.Lock()
DATA_HANDLED_LOCK = threading.Lock()

def abk_recvmsg(sock):
    len = 256
    msg = b""
    while len > 0:
        received = sock.recv(256)
        len -= len(received)
        msg += received
    return msg


class HandleClientDataThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.logger = logging.getLogger("HandleClientDataThread")
    
    def run(self):
        global is_file_incoming
        global file_size
        global FILE_SIZE_LOCK
        global DATA_HANDLED_LOCK

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
                        self.logger.debug("FILE SIZE lock acquired")
                        print("File Size:", file_size)
                    self.logger.debug("FILE Size lock released")
                content = ""
                while True:
                    response = conn.recv(1024).decode()
                    if not response:
                        break
                    content += response
                print(content)
                DATA_HANDLED_LOCK.release()
                self.logger.debug("Data Handled Lock Released")


def send_port(s, cmd, host, p1, p2):
    # print("SENDING PORT")
    new_cmd = 'PORT'
    new_command = "{cmd} {host},{p1},{p2}".format(cmd=new_cmd,
                                                  host=HOST.replace(".", ","),
                                                  p1=p1, p2=p2)
    new_command = new_command.encode()
    s.sendall(new_command)
    response = s.recv(1024).decode()  # recv PORT's response
    # print(response)


def main():
    main_logger = logging.getLogger("MAIN")

    global is_file_incoming
    global file_size
    global FILE_SIZE_LOCK
    global DATA_HANDLED_LOCK

    HandleClientDataThread().start()


    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(ADDRESS)
        response = s.recv(1024).decode()
        print(response)

        while True:
            command = input(">> ")
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
                response = s.recv(1024).decode()
                print("SERVER RESPONSE:", response)

                if cmd == 'QUIT':
                    s.close()
                    return 0
                elif cmd == 'LIST':
                    response = s.recv(1024).decode()
                    print(response)
                elif cmd == 'RETR':
                    file_size = s.recv(1024).decode()
                    print("File Size", file_size)
                    FILE_SIZE_LOCK.release()
                    main_logger.debug("FILE Size lock released")
                    response = s.recv(1024).decode()
                    
                    with DATA_HANDLED_LOCK:
                        main_logger.debug("Acquired DATA Handled Lock")
                        print(response)
                        file_size = None
                        is_file_incoming = False

                elif cmd == 'SIZE':
                    file_size = s.recv(1024).decode()
                    print("File Size:",file_size)
            
main()