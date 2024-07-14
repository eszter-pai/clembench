import random

class Dungeon:
    def __init__(self):
        self.grid = [['' for _ in range(5)] for _ in range(5)]
        self.player_a_position = None #these all should be none, for now this is for testing.
        self.player_b_position = None
        self.player_dm_position = None
        self.cells_blocked = []

    def generate_positions(self):

        #player a and b need to spawned together and in a corner
        corners = [(0, 0), (0, 1), (4, 4), (4, 3)]
        corner = random.choice(corners)

        self.player_a_position = corner
        self.player_b_position = (corner[0], corner[1] + 1) if corner[1] == 0 else (corner[0], corner[1] - 1)
        
        #monster spawn
        possible_positions = [(i, j) for i in range(5) for j in range(5)]
        possible_positions.remove(self.player_a_position)
        possible_positions.remove(self.player_b_position)
        
        self.player_dm_position = random.choice(possible_positions)
        possible_positions.remove(self.player_dm_position)

        while True:
            blocked = random.sample(possible_positions, k=2)
            if self.is_valid_blocked(blocked):
                self.cells_blocked = blocked
                break

    def is_valid_blocked(self, blocked):
        #the blocked cells can not completely separate players and the monster
        all_positions = [self.player_a_position, self.player_b_position, self.player_dm_position]
        blocked_set = set(blocked)

        def neighbors(pos):
            directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            result = [(pos[0] + d[0], pos[1] + d[1]) for d in directions]
            return [p for p in result if 0 <= p[0] < 5 and 0 <= p[1] < 5 and p not in blocked_set]

        def bfs(start):
            queue = [start]
            visited = set([start])
            while queue:
                current = queue.pop(0)
                for neighbor in neighbors(current):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            return visited

        visited_from_a = bfs(self.player_a_position)
        return all(pos in visited_from_a for pos in all_positions)

    def generate_dungeon(self):
        self.generate_positions()

        def pos_to_str(pos):

            #turn position to string
            return chr(pos[0] + ord('A')) + str(pos[1] + 1)
        
        
        self.player_a_position = pos_to_str(self.player_a_position)
        self.player_b_position = pos_to_str(self.player_b_position)
        self.player_dm_position = pos_to_str(self.player_dm_position)
        self.cells_blocked = f"{', '.join(pos_to_str(pos) for pos in self.cells_blocked)}"