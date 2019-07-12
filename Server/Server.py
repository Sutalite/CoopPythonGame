import socket
from threading import Thread
import select
import argparse
import curses
import os
import hashlib
import time
import sys
import struct
import json

class ClientThread(Thread):
    clients = []
    def __init__(self, ip, port, socket, drawer, server):
        Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.socket = socket
        self.running = True
        self.drawer = drawer
        self.server = server

        self.drawer.addstr("[+] New Thread for client {}:{}".format(self.ip, self.port))
        ClientThread.clients.append(self)
        self.drawer.addstr("[!] {} online clients".format(len(ClientThread.clients)))
        self.sendall("game_id {}".format(len(ClientThread.clients)))

    #TODO: Add listening to client message to detect when the game is finished, to load the next map
    def run(self):
        while self.running:
            ready = select.select([self.socket], [], [], 0.05)
            if ready[0]:
                r = self.socket.recv(2048).decode()
                if r.strip(' ') != "":
                    for client in ClientThread.clients:
                        if client is not self:
                            client.sendall(r)
                    self.player_message(r)
                else:
                    #WHEN 1 PLAYER IS DISCONNECTED, DISCONNECT ALL OTHER PLAYERS
                    self.drawer.addstr("[-] Client disconnect {}:{}".format(self.ip, self.port))
                    for client in ClientThread.clients:
                        ClientThread.clients.remove(client)
                        client.running = False

    def sendall(self, data):
        data = struct.pack('>I', len(data)) + data.encode()
        total_sent = 0
        while total_sent < len(data):
            sent = self.socket.send(data[total_sent:])
            total_sent += sent

    #ONLY HANDLES END GAME DETECTION FOR NOW BECAUSE ITS THE ONLY ONE NEEDED
    def player_message(self, message):
        if message == "end game":
            if not self.server.game_ended:
                self.drawer.addstr("Game ended")
                self.game_ended = True
                self.server.load_next_map()

        if message == "game started":
            self.game_ended = False

class ServerDrawer(Thread):
    def __init__(self, server):
        self.stdscr = curses.initscr()
        Thread.__init__(self)
        self.current_input = ""
        self.size = self.stdscr.getmaxyx()
        self.current_row = 0

        self.stdscr.scrollok(True)

        self.server = server
        self.running = True

    def addstr(self, text):
        self.clear_input()
        self.stdscr.addstr("{}\n".format(str(text)))
        self.current_row += 1

        if self.current_row >= self.size[0]:
            self.current_row = self.size[0] - 1

        self.draw_input()
        self.stdscr.refresh()

    def clear_input(self):
        self.stdscr.move(self.current_row,0)
        self.stdscr.clrtoeol()

    def draw_input(self):
        self.stdscr.addstr("-> {}".format(self.current_input))

    def send_command(self):
        self.addstr(self.current_input)
        self.server.command(self.current_input.lower())
        self.current_input = ""
        self.clear_input()
        self.stdscr.move(self.current_row, 0)
        self.draw_input()

    def clear_screen(self, *args):
        self.current_row = 0
        self.stdscr.move(0,0)
        self.stdscr.clrtobot()
        self.draw_input()

    def run(self):
        while self.running:
            key = self.stdscr.getkey()
            if key in ("", "\n"):
                self.send_command()
            else:
                if key in ('KEY_BACKSPACE', '^?', '\x7f'):
                    self.current_input = self.current_input[:-1]
                else:
                    self.current_input += str(key)[0]
                self.clear_input()
                self.draw_input()
        curses.endwin()

class Server:
    def get_map_folder_path(self):
        parent_folder = os.path.join(os.path.dirname(__file__), "..")
        asset_folder = os.path.join(parent_folder, "assets")
        map_folder = os.path.join(asset_folder, "maps")
        abs_map_folder = os.path.abspath(map_folder)
        return abs_map_folder

    def initialize_socket(self):
        s= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', self.port))
        self.drawer.addstr("[!] Listening")
        return s

    def __init__(self, port):
        self.drawer = ServerDrawer(self)
        self.drawer.start()
        self.port = port
        self.socket = self.initialize_socket()
        self.running = True

        self.map_folder = self.get_map_folder_path()
        self.start_time = time.time()
        self.loaded_map_name = []
        self.game_ended = False

        self.aliases_file_path = self.get_aliases_file_path()
        self.aliases = self.load_aliases()

    def run(self):
        while self.running:
            self.socket.listen(5)
            connexions, wlist, xlist = select.select([self.socket], [], [], 0.05)

            for connexion in connexions:
                (socket, (ip,port)) = self.socket.accept()
                newthread = ClientThread(ip, port, socket, self.drawer, self)
                newthread.start()
                self.drawer.addstr("[!] Listening")

                if len(ClientThread.clients) > 2:
                    for client in ClientThread.clients[2:]: #from 3rd to last client in the list
                        client.socket.send("disconnect There is already 2 player in the game".encode())
                        client.socket.close()

    def CloseServer(self, *args):
        self.drawer.addstr("[!] Closing server")
        self.drawer.running = False
        self.running = False
        for client in ClientThread.clients:
            client.sendall("disconnect Server closing")
            client.running = False
        self.socket.close()

    def player_count(self, *args):
        self.drawer.addstr("{} players conncted".format(len(ClientThread.clients)))

    def uptime(self, *args):
        now = time.time()
        elapse_time = now - self.start_time
        time_format = time.strftime("%M:%S", time.gmtime(elapse_time))
        self.drawer.addstr("{}".format(time_format))

    def get_aliases_file_path(self):
        file_name = "aliases.json"
        self_file_path = os.path.dirname(__file__)
        file_path = os.path.join(self_file_path, file_name)
        return file_path

    def print_alias(self, args):
        alias = self.get_alias(args[0])
        alias_name = alias[0]
        alias_args = " ".join(str(x[0]) for x in alias[1:])
        if alias:
            self.drawer.addstr("{} {}".format(alias_name, alias_args))

    def get_alias(self, alias):
        if alias in self.aliases:
            return self.aliases[alias]
        return None

    def save_aliases(self):
        json_data = json.dumps(self.aliases)
        with open(self.aliases_file_path, 'w') as f:
            f.write(json_data)

    def add_aliases(self, args):
        name = args[0]
        alias = args[1]
        alias_args = args[2:]
        self.aliases[name] = alias + " " + " ".join(alias_args)
        self.save_aliases()

    def get_alias(self, args):
        if args[0] in self.aliases:
            alias = self.aliases[args[0]].split(' ')
            alias_name = alias[0]
            alias_args = alias[1:] if len(alias) > 1 else None
            return (alias_name, alias_args)
        return (None, None)

    def load_aliases(self):
        if os.path.exists(self.aliases_file_path):
            with open(self.aliases_file_path, 'r') as f:
                json_data = f.read()
                data = json.loads(json_data)
                return data
        else:
            self.addstr("No aliases file")

    def list_aliases(self, args):
        self.drawer.addstr("Loaded aliases :")
        for alias in  self.aliases:
            alias_name, alias_args = self.get_alias(alias)
            msg = "    - {} : {} {}".format(alias, alias_name, *alias_args)
            self.drawer.addstr(msg)

    def command(self, command):
        commands = {
                "quit": self.CloseServer,
                "exit": self.CloseServer,
                "load_map": self.load_map,
                "reload_map": self.reload_map,
                "clear": self.drawer.clear_screen,
                "list": self.player_count,
                "uptime": self.uptime,
                "set_alias": self.add_aliases,
                "get_alias": self.print_alias,
                "list_aliases": self.list_aliases,
        }

        command_name = command.split(' ')[0]
        args = command.split(' ')[1:]
        alias_name,alias_args = self.get_alias(command_name)

        if alias_name:
            if alias_args:
                commands[alias_name](alias_args)
            else:
                commands[alias_name](args)
        elif command_name in commands:
            commands[command_name](args)
        elif command != "":
            self.drawer.addstr("Invalid command")

    #ONLY RELOADS FOR NOW
    def load_next_map(self):
        self.reload_map()

    def hash_map(self, map_path):
        with open(map_path, 'r') as f:
            map_hash = hashlib.sha256(f.read().encode()).hexdigest()
            return map_hash

    def load_map(self, args):
        if len(ClientThread.clients) != 2:
            self.drawer.addstr("You need to be 2 players in order to play and load a map")
            return

        map_name = args[0]
        map_path = os.path.join(self.map_folder, map_name)
        self.drawer.addstr(map_path)
        if os.path.exists(map_path):
            map_hash = self.hash_map(map_path)
            self.drawer.addstr("Map hash: {}".format(map_hash))
            self.send_message_to_all_client("map_hash {} {}".format(map_name, map_hash))
            self.loaded_map_name.clear()
            self.loaded_map_name.append(map_name)
        else:
            self.drawer.addstr("The map {} does not exist".format(map_name))
            self.loaded_map_path = None

    def reload_map(self, *args):
        if self.loaded_map_name:
            self.load_map(self.loaded_map_name)
        else:
            self.drawer.addstr("No map is currently loaded")

    def send_message_to_all_client(self, message):
        for client in ClientThread.clients:
            client.sendall(message)


parser = argparse.ArgumentParser(description="Server")
parser.add_argument('--port', type=int,default=25565,help='the port you want to use for the server')
args = parser.parse_args()

server = Server(args.port)
server.run()
