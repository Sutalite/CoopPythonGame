import pygame
import Tiles
import os
import hashlib

#IT MAY BE BETTHER TO CACHE THE GAME INSTEAD OF GIVINT IT AS AN ARG
class Map:
    def create_board(self):
        offset = self.offset / self.cell_size
        return [[Tiles.Tile(x + offset,y + offset, self.cell_size) for x in range(self.map_size)] for y in range(self.map_size)]

    def draw(self, game):
        if self.map_data:
            for i in range(self.map_size):
                for j in range(self.map_size):
                    self.map_data.board[i][j].draw(game, self.offset)

    def load_map(self, args):
        map_name = args[0]
        map_hash = args[1]
        map_path = os.path.join(self.map_folder, map_name)

        if os.path.exists(map_path):
            with open(map_path, 'r') as f:
                local_map_hash = hashlib.sha256(f.read().encode()).hexdigest()
                if local_map_hash == map_hash:
                    self.map_data = MapData.from_file(map_path)
                else:
                    print("You don't have this map or your map is incompatible")

    def __init__(self, map_folder):
        self.map_size = 16
        self.cell_size = 48
        self.offset = (800 - self.cell_size * self.map_size) / 2 #OFFSET ON EACH SIDE OF THE MAP
        self.map_folder = map_folder
        self.map_data = None

class MapData:
    def __init__(self, author, board):
        self.author = author
        self.board = board

    def from_file(path):
        import json
        with open(path, 'r') as f:
            json_data = f.read()
            data = json.loads(json_data)
            
            author = data["author"]
            board_data = data["board"]
            
            board = [[0 for _ in range(16)] for _ in range(16)]

            for i in range(16): #x
                for j in range(16): #y
                    board[i][j] = Tiles.from_json_data(board_data[i][j])

            print("Map loaded")
            
            return MapData(author, board)

    def save_map(self):
        import json
        tiles_data = [[0 for _ in range(16)] for _ in range(16)]
        for i in range(16):
            for j in range(16):
                tiles_data[i][j] = self.board[i][j].to_json_data()

        json_data = json.dumps({"author":self.author, "board":tiles_data})
        with open("assets/maps/md", 'w') as f:
            f.write(json_data)
