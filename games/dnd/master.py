import copy
from typing import List, Dict, Tuple

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark
from clemgame import get_logger

from games.dnd.players import Adventurer, DungeonMaster
from games.dnd.instancegenerator import GAME_NAME

# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)

class DND(GameMaster):
    """Implement mechanisms for playing DND."""
    def __init__(self, experiment: Dict, player_backends: List[str]):
        super().__init__(GAME_NAME, experiment, player_backends)


        #all levels are in dnd/in/resources/levels.txt
        self.levels = experiment['name']
        self.model_a = player_backends[0]
        self.model_b = player_backends[1]
        self.model_c = player_backends[2]

        self.cls = ["Wizard", "Sorcerer", "Cleric", "Fighter", "Rogue", "Ranger"]

        # initialise attributes that will be used for the evaluation scores
        self.max_turn = 15
        self.aborted: bool = False
        self.lose: bool = False
        self.complete_turns: int = 0


    def set_up(self, **game_instance):

        self.game_instance = game_instance # fetch game parameters here

        #instantiate players
        self.player_a = Adventurer()
        self.player_b = Adventurer()
        self.player_dm = DungeonMaster()

        #initialize game variable
        self.current_turn: int = 0
        #the potions are shared among the heroes
        self.potions = 7
        

        #log the details of players
        self.log_players({
            'GM': 'Game master for DnD',
            'Player 1': f'Adventurer A: {self.model_a}',
            'Player 2': f'Adventurer B: {self.model_b}',
            'Dungeon Master': f'Dungeon Master: {self.model_c}'
            })


        #perhpas for evaluation
        # self.log_key('n_turns', n_turns)

    def initiate(self, prompt_player_a, prompt_player_b, prompt_player_dm):

        #append the initial message of each plaeyr to their history
        self.player_a.history.append({'role': 'user', 'content': prompt_player_a})
        self.player_b.history.append({'role': 'user', 'content': prompt_player_b})
        self.player_dm.history.append({'role': 'user', 'content': prompt_player_dm})


        #log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': prompt_player_a}
        self.log_event(from_='GM', to='Player 1', action=action)
        action = {'type': 'send message', 'content': prompt_player_b}
        self.log_event(from_='GM', to='Player 2', action=action)
        action = {'type': 'send message', 'content': prompt_player_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)

    def play(self) -> None:
        while self.does_game_proceed():
            self.current_turn += 1
            self.log_next_turn()
            self.turn()
        if self.complete_turns == self.max_turn:
            # log a message informing that the game was successfuly played
            action = {'type': 'info', 'content': 'game successful'}
            self.log_event(from_='GM', to='GM', action=action)
        
        return None


    def does_game_proceed(self) -> None:
        #does the game continue
        if self.current_turn < 15 and not self.aborted:
            return True
        else:
            return False
        

    def get_utterance(self, player) -> str:

        if player == 'a':            

            #API call (or get a programmatic response) from player a
            prompt_a, raw_answer_a, answer_a = self.player_a(self.player_a.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer_a}
            self.log_event(from_='Player 1', to='GM', action=action,
                        call=(copy.deepcopy(prompt_a), raw_answer_a))
            
            #reply to its own memory


        if player == 'b':

            #API call (or get a programmatic response) from player a
            prompt_b, raw_answer_b, answer_b = self.player_b(self.player_b.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer_b}
            self.log_event(from_='Player 1', to='GM', action=action,
                        call=(copy.deepcopy(prompt_b), raw_answer_b))
            
            #reply to its own memory


        else:
            #for dm
            #API call (or get a programmatic response) from player a
            prompt, raw_answer, answer = self.player_a(self.player_a.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer}
            self.log_event(from_='Player 1', to='GM', action=action,
                        call=(copy.deepcopy(prompt), raw_answer))
            
            #reply to its own memory
            

    #def _check_validity(self, answer: str) -> bool:


    def turn(self) -> None:
        #get A, B, and DM's response
        answer_a = self.get_utterance('a')
        answer_a = self.get_utterance('b')
        answer_a = self.get_utterance('dm')

        #check A's response's validity
        is_valid_turn = self._check_validity(answer_a)
        if not is_valid_turn:
            #stop game
            return None
        
        #also add the reply to the transcript
        


# always add the GameBenchmark child with this structure
class DnDGameBenchmark(GameBenchmark):
    """Integrate the game into the benchmark run."""
    def __init__(self):
        super().__init__(GAME_NAME)

    def is_single_player(self):
        return False

    def get_description(self):
        return "A fantasy RPG game in which the adventurers ventured into a dungeon and their goal is to defeat the boss."

    def create_game_master(self,
                           experiment: Dict,
                           player_backends: List[str]
                           ) -> GameMaster:
        return DND(experiment, player_backends)
    
