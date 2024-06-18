import copy
import re
from typing import List, Dict, Tuple

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark
from clemgame import get_logger

from games.dnd.players import Adventurer, DungeonMaster
from games.dnd.dungeon import Dungeon
from games.dnd.instancegenerator import GAME_NAME

# use the framework logger to log events relevant at runtime;
# this is independent from the game records / transcript
logger = get_logger(__name__)

class DnD(GameMaster):
    """Implement mechanisms for playing DND."""
    def __init__(self, experiment: Dict, player_backends: List[str]):

        super().__init__(GAME_NAME, experiment, player_backends)


        # all levels are in dnd/in/resources/basegamelevels.txt
        self.levels = experiment['name']
        self.model_a = player_backends[0]
        self.model_b = player_backends[0]
        self.model_dm = player_backends[1] 

        # initialise attributes that will be used for the evaluation scores
        self.max_turn = 15
        self.aborted: bool = False
        self.lose: bool = False
        self.complete_turns: int = 0


    def setup(self, **game_instance)-> None:

        # initialize players' classes: 
        # if GM does not give them class, then its null
        player_a_class = game_instance['player_a_class']
        player_B_class = game_instance['player_b_class']
        player_dm_monster = game_instance['boss_dict']['Class Name']

        # instantiate players
        self.player_a = Adventurer(self.model_a, "A", player_a_class)
        self.player_b = Adventurer(self.model_b, "B", player_B_class)
        self.player_dm = DungeonMaster(self.model_dm, "DM", player_dm_monster)

        # all classes/boss of each player: self.player_a.clss | self.player_b.clss | self.player_dm.clss

        prompt_player_a = game_instance['prompt_player_a']
        prompt_player_b = game_instance['prompt_player_b']
        prompt_dm = game_instance['prompt_dm']


        # initialize game variable
        self.current_turn: int = 0
        # the potions are shared among the heroes
        self.potions = 5    # RONJA'S NOTE: i think 7 is a bit much .. 
                            # maybe we should tie them to difficulty / instance?

        # keep player's dicts & response format dict to access later
        self.player_a_dict = game_instance['player_a_dict']
        self.player_b_dict = game_instance['player_b_dict']
        self.boss_dict = game_instance['boss_dict']
        self.response_dict = game_instance['response_format']

        # initialize hp counts which must be updated throughout game
        self.player_a_hp = game_instance['player_a_dict']['Hit Points']
        self.player_b_hp = game_instance['player_b_dict']['Hit Points']
        self.boss_hp = game_instance['boss_dict']['Hit Points']
        # initialize spell slots which may be updated throughout game
        self.player_a_slots = game_instance['player_a_dict']['Spell slots']
        self.player_b_slots = game_instance['player_b_dict']['Spell slots']
        
        self.initiate(prompt_player_a, prompt_player_b, prompt_dm)

        # log the details of players
        self.log_players({
            'GM': 'Game master for DnD',
            'Player 1': f'Adventurer A: {self.model_a}',
            'Player 2': f'Adventurer B: {self.model_b}',
            'Dungeon Master': f'Dungeon Master: {self.model_dm}'
            })

        self.initiate(prompt_player_a, prompt_player_b, prompt_dm)
        #perhpas for evaluation
        # self.log_key('n_turns', n_turns)

    def initiate(self, prompt_player_a, prompt_player_b, prompt_player_dm):

        # always call log_next_turn when a new turn starts
        self.log_next_turn()

        # append the initial message of each player to their history
        self.player_a.history.append({'role': 'user', 'content': prompt_player_a})
        self.player_b.history.append({'role': 'user', 'content': prompt_player_b})
        self.player_dm.history.append({'role': 'user', 'content': prompt_player_dm})


        # log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': prompt_player_a}
        self.log_event(from_='GM', to='Player 1', action=action)
        action = {'type': 'send message', 'content': prompt_player_b}
        self.log_event(from_='GM', to='Player 2', action=action)
        action = {'type': 'send message', 'content': prompt_player_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)

    @classmethod
    def applies_to(cls, game_name: str) -> bool:
        return game_name == GAME_NAME
    
    def play(self) -> None:
        while self.does_game_proceed():
            self.current_turn += 1

            # always call log_next_turn when a new turn starts
            self.log_next_turn()
            self.turn()


        if self.complete_turns == self.max_turn:
            # log a message informing that the game was successfuly played
            action = {'type': 'info', 'content': 'game successful'}
            self.log_event(from_='GM', to='GM', action=action)
        
        # log a final message saying that the game did came to an end
        action = {'type': 'info', 'content': 'end game'}
        self.log_event(from_='GM', to='GM', action=action)
        return None


    def does_game_proceed(self) -> None:
        # does the game continue
        if self.current_turn >= self.max_turns: # if max turns reached
            self.log_to_self("max turns reached", str(self.max_turns))
            return False
        if self.invalid_response:               # if invalid response - reprompt??
            self.log_to_self("invalid response", "abort game")
            return False
        if self.current_turn < 15 and not self.aborted:
            return True
        else:
            return False
        

    def get_utterance(self, player) -> str:

        if player == 'a':            

            # API call (or get a programmatic response) from player a
            prompt_a, raw_answer_a, answer_a = self.player_a(self.player_a.history,
                                                    self.current_turn)
            # API call to the records
            action = {'type': 'get message', 'content': answer_a}
            self.log_event(from_='Player A', to='GM', action=action,
                        call=(copy.deepcopy(prompt_a), raw_answer_a))
            
            #reply to its own memory

            return answer_a


        if player == 'b':

            #API call (or get a programmatic response) from player a
            prompt_b, raw_answer_b, answer_b = self.player_b(self.player_b.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer_b}
            self.log_event(from_='Player B', to='GM', action=action,
                        call=(copy.deepcopy(prompt_b), raw_answer_b))
            
            #reply to its own memory

            return answer_b


        else:
            #for dm
            #API call (or get a programmatic response) from player a
            prompt, raw_answer, answer = self.player_dm(self.player_dm.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer}
            self.log_event(from_='Player DM', to='GM', action=action,
                        call=(copy.deepcopy(prompt), raw_answer))
            
            #reply to its own memory
        
            return answer
    
    def _check_adjacency(self, person_a: str, person_b: str):
        """ Check if two players are in adjacent positions in the dungeon 
            to satisfy the adjacency condition."""

        # define dungeon layout
        rows = 'ABCDE'
        cols = '12345'

        # get row & column indeces
        row_a, col_a = rows.index(person_a[0]), cols.index(person_a[1])
        row_b, col_b = rows.index(person_b[0]), cols.index(person_b[1])

        # check if the positions are adjacent (not equal)
        if not person_a == person_b:    # NOTE: can't be in same position anyway -> redundant (but for safety)
            # players are adjacent if they difference between their row & column indeces is exactly 0 & 1
            if abs(row_a - row_b) <= 1 and abs(col_a - col_b) <= 1:
                return True
            
        return False

    def _on_parse_response(self, player, utterance: str):
        """Assess whether the player's response needs to be edited before it is logged."""
    
        return False, utterance

    def _validate_player_response(self, player, utterance: str):
        """
        Parse the player's response according to the instance's given response format.
        Check for violations of the game rules.
        """
        lines = utterance.split('\n')
        response_tags = list(self.response_dict)
        raw_response = []

        for i in range(len(lines)):
            tag = response_tags[i]
            pattern = self.response_dict[tag]
            line_content = lines[i].replace(tag, '')
            raw_response.append(line_content)

            # check if tagged correctly
            if not lines[i].startswith(tag):
                self.invalid_response = True
                return False
            # check if content matches regex
            if not re.match(pattern, line_content):
                self.invalid_response = True
                return False
            
        # log if format was valid 
        self.log_to_self("valid format", "continue")

        # now check if response follows game rules
        if player == self.player_a:
            player_dict = self.player_a_dict
            player_slots = self.player_a_slots
        elif player == self.player_b:
            player_dict = self.player_b_dict
            player_slots = self.player_b_slots
        elif player == self.player_dm:
            player_dict = self.boss_dict
            player_slots = 0

        action_lst = player_dict['Actions']
        player_pos = raw_response[0]
        action = raw_response[1]
        target = raw_response[2].split(sep=' ')[0]
        target_pos = raw_response[2].split(sep=' ')[2]

        # check if input is contained in player's list of possible actions
        for action_dict in action_lst:
            if action_dict['Name'] == action:
                condition = action_dict['Condition']
                if not condition == "None":
                    # spell slot condition requires at least spell slot remaining
                    if condition == "spell slot" and player_slots == 0:
                        self.log_to_self("condition not met")   # NOTE: logging optional (?)
                        self.invalid_response = True
                        return False
                    # adjacency condition requires player & target be in adjacent positions
                    elif condition == "adjacency":
                        if not target=="self":
                            if not self._check_adjacency(player_pos, target_pos):
                                self.log_to_self("condition not met")
                                self.invalid_response = True
                                return False
                    # potions condition requires potions remaining
                    elif condition == "potions" and self.potions == 0:
                            self.log_to_self("condition not met")
                            self.invalid_response = True
                            return False
                    
        # some special cases
        if action=="Spell: Revivify":   # revivify must be aimed at a dead adventurer
            if player==self.player_a:
                if not target=='Player B' and not self.player_b_hp==0:
                    self.invalid_response = True
                    return False
            elif player==self.player_b:
                if not target=='Player A' and not self.player_a_hp==0:
                    self.invalid_response = True
                    return False
        
        if action=="Potion: Use healing potion":    # cannot use potions on someone else
            if not target=='self':
                if player==self.player_a and not target=='Player A':
                    self.invalid_response = True
                    return False
                elif player==self.player_b and not target=='Player B':
                    self.invalid_response = True
                    return False
        
        return True 


    def turn(self) -> None:
        #get A, B, and DM's response
        answer_a = self.get_utterance('a')
        answer_b = self.get_utterance('b')
        answer_dm = self.get_utterance('dm')

        #check A's response's validity

        #if not turn_idx == 1: NOTE: at turn 1 there is a special format !!!
        is_valid_turn = self._validate_player_response(player=self.player_a, utterance=answer_a)
       # if not is_valid_turn:
            #stop game
        return None
        
        #also add the reply to the transcript

        action = {'type': 'send message', 'content': answer_a}
        self.log_event(from_='GM', to='Player 2', action=action)
        
    def _append_utterance(self, utterance: str, player: str, role: str) -> None:
        """Add an utterance to the history of a player (dnd game specific)."""
        assert player in ('a', 'b', 'dm')
        if player == 'a':
            self.player_a.history.append({'role': role, 'content': utterance})
        elif player == 'b':
            self.player_b.history.append({'role': role, 'content': utterance})
        else:
            self.player_dm.history.append({'role': role, 'content': utterance})


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
        return DnD(experiment, player_backends)
    
