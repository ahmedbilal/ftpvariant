def abk_sendmsg(sock, msg):
    modded_msg = msg[:256]  # only first 256 chars
    if isinstance(modded_msg, bytes):
        modded_msg = modded_msg.decode()
        modded_msg = modded_msg.ljust(256, chr(0))  # padd with \0 upto 256 len
        modded_msg = modded_msg.encode()
    elif isinstance(modded_msg, str):
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
