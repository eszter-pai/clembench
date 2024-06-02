from typing import List, Dict, Tuple

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark
from clemgame import get_logger

from games.dnd.players import Hero, DungeonMaster
from games.dnd.instancegenerator import GAME_NAME

# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)

class DND(GameMaster):
    """Implement mechanisms for playing FirstLast."""
    def __init__(self, experiment: Dict, player_backends: List[str]):
        super().__init__(GAME_NAME, experiment, player_backends)

        # save experiment and player attributes that will be necessary later
        self.model_a = player_backends[0]
        self.model_b = player_backends[1]
        self.model_c = player_backends[2]
        self.cls = ["Wizard", "Sorcerer", "Cleric", "Fighter", "Rogue", "Ranger"]

        # stats and actions?


        
        # initialise attributes that will be used for the evaluation scores
        self.max_turn = 15
        self.aborted: bool = False
        self.lose: bool = False
        self.complete_turns: int = 0


    def set_up(self, **game_instance):

        #initialize players
        self.player_a = Hero()
        self.player_b = Hero()
        self.player_dm = DungeonMaster()

        #initialize game variable
        self.current_turn: int = 0
        self.potions = 7

        #log the details of players
        self.log_players({
            'GM': 'Game master for DnD',
            'Player 1': f'Hero A: {self.model_a}',
            'Player 2': f'Hero B: {self.model_b}',
            'Dungeon Master': f'Dungeon Master: {self.model_c}'
            })


        #perhpas for evaluation
        # self.log_key('n_turns', n_turns)
    def play(self) -> None:
        while self.does_game_proceed():
            self.current_turn += 1

        return None


    def does_game_proceed(self) -> None:
        #does the game continue
        if self.current_turn < 15 and not self.aborted:
            return True
        else:
            return False
        
    def initiate(prompt_a, prompt_b, prompt_dm):



    
