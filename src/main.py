import re
from mttext_app import MtTextEditApp
import sys
import argparse


def connect_to_session(debug, conn_ip, username):
    r = re.compile(r"(\d{1,3}\.){3}\d{1,3}")
    if not r.match(conn_ip):
        print("Wrong connection ip address")
        return 0
    socket = MtTextEditApp(username, debug=debug)
    socket.connect(conn_ip)


def host_session(debug, file_path, username):
    try:
        with open(file_path, 'r') as f:
            filetext = f.read()
    except IOError:
        print("File does not exist :(")
        return
    socket = MtTextEditApp(username, filetext,
                           debug=debug, file_path=file_path)
    socket.run()


def main():
    offset = 0
    debug = False
    parser = argparse.ArgumentParser(
        prog="mtrtext",
        description="multi-user text editor",
        epilog=":)",
        usage="%(prog)s [-D] (-H FILE_PATH USERNAME | -C CONN_IP USERNAME)"
    )
    parser.add_argument('-D', action='store_true', default=False,
                        dest='debug',
                        help="Print some debug messages")
    parser.add_argument('-H', nargs=2,
                        metavar=('FILE_PATH', 'USERNAME'),
                        help='Host edit session')
    parser.add_argument('-C', nargs=2,
                        metavar=('CONN_IP', 'USERNAME'),
                        help='Connect to session')
    try:
        args = parser.parse_args()
        if args.C:
            connect_to_session(args.debug, args.C[0], args.C[1])
        if args.H:
            host_session(args.debug, args.H[0], args.H[1])
    except:
        parser.print_help()


if __name__ == '__main__':
    main()
