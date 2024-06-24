from clemgame.clemgame import Player
from typing import List

class Adventurer(Player):
    def __init__(self, model_name: str, player: str, clss: str):
        super().__init__(model_name)
        self.player: str = player

        #the player's given or chosen class, if the player chose class, it initialized with null.
        self.clss: str = clss

        self.history: List = []

    def _custom_response(self, messages, turn_idx) -> str:
        """Return a mock message with the suitable format."""

        if turn_idx == 1:
            return "Wizard"
        else:
            return "MOVE: A1\nACTION: Cantrip: Fire Bolt\nTARGET: boss in D3\nROLL: 12"

class DungeonMaster(Player):
    def __init__(self, model_name: str, player: str, clss: str):
        super().__init__(model_name)

        self.player:str = player

        #the given mosnter
        self.clss: str = clss

        self.history: List = []

    def _custom_response(self, messages, turn_idx) -> str:
        """Return a mock message with the suitable format."""
        if turn_idx == 1:
            return "Dungeon Master"
        
        else:
            return f"MOVE: A2\nACTION: Attack: Melee attack\nTARGET: player a in A1\nROLL: 21"