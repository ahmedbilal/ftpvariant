# ftpvariant
A primitive FTP [Active Mode Only](https://winscp.net/eng/docs/ftp_modes) variant which can download multiple files concurrently.
It is written in Python3 and is less than 500 lines of code and easy to modify.

This ftp variant supports only **USER**,
**PWD**, **SYST**, **CWD**, **QUIT**, **LIST**, **RETR**, and **SIZE** command at the moment. Although it is born as fully
compliant FTP but have changed a lot so it may be not a fully compliant FTP now.

![screen record](https://image.ibb.co/mxkwxp/Peek_2018_08_31_10_24.gif)

## Installation
The easiest way is to clone/download the repository. Run the following command on your terminal to clone the repository.

```bash
   git clone https://github.com/ahmedbilal/ftpvariant.git
```
and you are **done**

## Usage
To run the server on privileged ports (ports less than 1024) you need sudo rights. If you want to run the server on port number
greater or equal to 1024 you would not need sudo in front of your command. Run the following command on your terminal.

```bash
   sudo python3 server.py [port]
```

To run the client enter the following command on your terminal.

```bash
   python3 client.py [host] [port]
```

*[host] is the ip address of machine on which the FTP server is running and [port] is the port of that server on which it
is listening. Port is the same you entered above when running the server*

## Contribution
I am happy to incorporate any contribution in this project. Just make sure your code is formatted according to PEP8 conventions.

## Some Useful Links
1. [PEP8](http://pep8.org)
