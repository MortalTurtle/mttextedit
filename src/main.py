import re
from mttext_app import MtTextEditApp
import sys
import argparse

def manage_permissions(username, access_rights):
    permissions_file = '/var/lib/mttext/permissions.txt'
    if access_rights not in ['rw', 'r', 'n']:
        return False
    try:
        permissions = {}
        try:
            with open(permissions_file, 'r') as f:
                for line in f:
                    if ':' in line:
                        user, rights = line.strip().split(':')
                        permissions[user] = rights
        except FileNotFoundError:
            pass
        permissions[username] = access_rights
        with open(permissions_file, 'w') as f:
            for user, rights in permissions.items():
                f.write(f"{user}:{rights}\n")
        return True
    except Exception as e:
        print(f"Error managing permissions: {e}")
        return False

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
        usage="%(prog)s [-D] (-H FILE_PATH USERNAME | -C CONN_IP USERNAME | -P USERNAME ACCESS_RIGHTS)"
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
    parser.add_argument('-P', nargs=2,
                   metavar=('USERNAME', 'ACCESS_RIGHTS'),
                   help='Manage user permissions (rw - read/write, r - read only, n - no access)')
    try:
        args = parser.parse_args()
        if args.P:
            manage_permissions(args.P[1], args.P[2])
        if args.C:
            connect_to_session(args.debug, args.C[0], args.C[1])
        if args.H:
            host_session(args.debug, args.H[0], args.H[1])
    except:
        parser.print_help()


if __name__ == '__main__':
    main()
