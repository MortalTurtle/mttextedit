import collections
import re
from mttext_app import MtTextEditApp
import sys
import argparse
import os

PERMISSION_FILE = "/tmp/lib/mttext/permissions"
HISTORY_FILE_PATH = "/tmp/lib/mttext/history/"

# TODO: implement correct division for files with same filename


def list_all_saved_history(file_path):
    file_name = file_path[file_path.rfind("/") :]
    os.makedirs(
        os.path.dirname(HISTORY_FILE_PATH + file_name + "/"), exist_ok=True
    )
    files = os.listdir(HISTORY_FILE_PATH + file_name + "/")
    files.sort()
    i = 1
    for hist_file in filter(lambda x: ".o.cache" in x, files):
        print(hist_file[: hist_file.rfind(".o.cache")] + f"\t{i}")
        i += 1


def show_changes(file_path, changes_index):
    file_name = file_path[file_path.rfind("/") :]
    file_list = os.listdir(HISTORY_FILE_PATH + file_name + "/")
    file_list.sort()
    files = list(filter(lambda x: ".o.cache" in x, file_list))
    try:
        with open(
            HISTORY_FILE_PATH
            + file_name
            + "/"
            + files[int(changes_index) - 1],
            "r",
        ) as f:
            filetext = f.read()
    except:
        print("no such changes file found, :(")
        return
    app = MtTextEditApp("view_changes", filetext)
    app.show_changes(file_name, files[int(changes_index) - 1])


def get_permissions():
    permissions = {}
    try:
        with open(PERMISSION_FILE, "r") as f:
            for line in f:
                if ":" in line:
                    user, rights = line.strip().split(":")
                    permissions[user] = rights
    except FileNotFoundError:
        os.makedirs(os.path.dirname(PERMISSION_FILE), exist_ok=True)
    return permissions


def list_permissions():
    permissions = get_permissions()
    for user, rights in permissions.items():
        print(f"{user}:{rights}")


def manage_permissions(username, access_rights):
    sign = access_rights[0]
    access_rights = access_rights[1:]
    if access_rights not in ["rw", "r"] or (sign != "+" and sign != "-"):
        return False
    try:
        permissions = get_permissions()
        if sign == "+":
            if (
                access_rights == "rw"
                or access_rights == "r"
                and permissions.get(username, "") != "rw"
            ):
                permissions[username] = access_rights
        elif username in permissions:
            permissions.pop(username)
        with open(PERMISSION_FILE, "w") as f:
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
        with open(file_path, "r") as f:
            filetext = f.read()
    except IOError:
        print("File does not exist :(")
        return
    socket = MtTextEditApp(
        username, filetext, debug=debug, file_path=file_path
    )
    socket.run()


def main():
    offset = 0
    debug = False
    parser = argparse.ArgumentParser(
        prog="mtrtext",
        description="multi-user text editor",
        epilog=":)",
        usage="%(prog)s [-D] (-H FILE_PATH USERNAME | -C CONN_IP USERNAME | \
        -P USERNAME ACCESS_RIGHTS | -Pl | -CHH FILE_PATH | -CH FILE_PATH INDEX)",
    )
    parser.add_argument(
        "-D",
        action="store_true",
        default=False,
        dest="debug",
        help="Print some debug messages",
    )
    parser.add_argument(
        "-H",
        nargs=2,
        metavar=("FILE_PATH", "USERNAME"),
        help="Host edit session",
    )
    parser.add_argument(
        "-C",
        nargs=2,
        metavar=("CONN_IP", "USERNAME"),
        help="Connect to session",
    )
    parser.add_argument(
        "-P",
        nargs=2,
        metavar=("USERNAME", "ACCESS_RIGHTS"),
        help="Manage user permissions + to add, - to remove (rw - read/write, r - read only)",
    )
    parser.add_argument(
        "-Pl", action="store_true", default=False, help="List all permissions"
    )
    parser.add_argument(
        "-CHH",
        nargs=1,
        metavar=("FILE_PATH"),
        help="List all availible history changes for file",
    )
    parser.add_argument(
        "-CH",
        nargs=2,
        metavar=("FILE_PATH", "INDEX"),
        help="Show history for file from i-th session",
    )
    try:
        args = parser.parse_args()
        if args.Pl:
            list_permissions()
        if args.P:
            manage_permissions(args.P[0], args.P[1])
        if args.C:
            connect_to_session(args.debug, args.C[0], args.C[1])
        if args.H:
            host_session(args.debug, args.H[0], args.H[1])
        if args.CHH:
            list_all_saved_history(args.CHH[0])
        if args.CH:
            show_changes(args.CH[0], args.CH[1])
    except:
        parser.print_help()


if __name__ == "__main__":
    main()
