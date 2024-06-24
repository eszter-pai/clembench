import copy
import re
import string
from typing import List, Dict, Tuple

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark, DialogueGameMaster
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
        self.max_turns = 15
        self.aborted: bool = False
        self.lose: bool = False
        self.complete_turns: int = 0


    def setup(self, **game_instance)-> None:

        logger.info("_on_setup")

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

        #initial prompt
        prompt_player_a = game_instance['prompt_player_a']
        prompt_player_b = game_instance['prompt_player_b']
        prompt_dm = game_instance['prompt_dm']

        #combat prompt
        self.combat_prompt_a = game_instance['combat_prompt_adv']
        self.combat_prompt_b = game_instance['combat_prompt_adv']
        self.combat_prompt_dm = game_instance['combat_prompt_dm']

        #new turn prompt, every turn after the first combat round
        self.newturn_prompt_a = game_instance['newturn_prompt_adv']
        self.newturn_prompt_b = game_instance['newturn_prompt_adv']
        self.newturn_prompt_dm = game_instance['newturn_prompt_dm']


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

        # NOTE: DUMMY SPAWN POSITIONS TO TEST OTHER THINGS
        self.player_a_position = "A1"
        self.player_b_position = "A2"
        self.boss_position = "D4"
        self.blocked_cells = "C2, B3, E4"

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
        self.current_turn += 1
        self.log_next_turn()
        self.invalid_response = False


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

        #    if  self.current_turn == 1:
        #        self.turn()

           # if  self.current_turn == 2:
           #     self.combat_turn()
           # else:
            self.combat_turn() # for test
                #new_turn()


        if self.complete_turns == self.max_turns:
            # log a message informing that the game was successfuly played
            action = {'type': 'info', 'content': 'game successful'}
            self.log_event(from_='GM', to='GM', action=action)
        
        # log a final message saying that the game did came to an end
        action = {'type': 'info', 'content': 'end game'}
        self.log_event(from_='GM', to='GM', action=action)
        return None


    def does_game_proceed(self) -> None:

        # ESZ's NOTE: log_to_self is not initialized
        # does the game continue
    #    if self.current_turn > self.max_turns: # if max turns reached 
    #        self.log_to_self("max turns reached", str(self.max_turns))
    #        return False
    #    if self.invalid_response:               # if invalid response - reprompt??
    #        self.log_to_self("invalid response", "abort game")
    #        return False
        if self.current_turn <= self.max_turns and not self.aborted:
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
            self.log_event(from_='Player 1', to='GM', action=action,
                        call=(copy.deepcopy(prompt_a), raw_answer_a))
            
            #reply to its own memory

            return answer_a


        if player == 'b':

            #API call (or get a programmatic response) from player b
            prompt_b, raw_answer_b, answer_b = self.player_b(self.player_b.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer_b}
            self.log_event(from_='Player 2', to='GM', action=action,
                        call=(copy.deepcopy(prompt_b), raw_answer_b))
            
            #reply to its own memory

            return answer_b


        else:
            #for dm
            #API call (or get a programmatic response) from dm
            prompt, raw_answer, answer = self.player_dm(self.player_dm.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer}
            self.log_event(from_='Dungeon Master', to='GM', action=action,
                        call=(copy.deepcopy(prompt), raw_answer))
            
            #reply to its own memory
        
            return answer
    
    def _check_move(self, n: int, pos_1: str, pos_2: str):
        """ Check if two positions are n or less steps away from each other. 
            Can be used with n=1 to check the adjacency condition."""

        # define dungeon layout
        rows = 'ABCDE'
        cols = '12345'

        # get row & column indeces
        row_a, col_a = rows.index(pos_1[0]), cols.index(pos_1[1])
        row_b, col_b = rows.index(pos_2[0]), cols.index(pos_2[1])

        # check if absolute difference between rows & columns <= n
        # in which case positions are within n steps away from each other
        # (since diagonal movement is not allowed)

        if not pos_1 == pos_2:  # should not feed same position in anyway! 
                                # this is only for checking the adjacency condition
            if abs(row_a - row_b) + abs(col_a - col_b) <= n:
                return True
            
        # NOTE: this does not yet check if a blocked cell is traversed
        # needs to be implemented in the future
            
        return False

    def _on_parse_response(self, player, utterance: str):
        """Assess whether the player's response needs to be edited before it is logged."""
    
        return False, utterance

    def _validate_player_response(self, player, utterance: str):
        """
        Parse the player's response according to the instance's given response format.
        Check for violations of the game rules.
        Returns validity and if valid == True, also returns a dictionary of the response.
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
                return False, None
            # check if content matches regex
            if not re.match(pattern, line_content):
                self.invalid_response = True
                return False, None
            
        # log if format was valid 
        self.log_to_self("valid format", "continue")

        # now check if response follows game rules

        # first retrieve player-specific info
        if player == self.player_a:
            player_dict = self.player_a_dict
            player_slots = self.player_a_slots
            player_pos = self.player_a_position
        elif player == self.player_b:
            player_dict = self.player_b_dict
            player_slots = self.player_b_slots
            player_pos = self.player_b_position
        elif player == self.player_dm:
            player_dict = self.boss_dict
            player_slots = 0
            player_pos = self.boss_position
        
        action_lst = player_dict['Actions']

        # fetch contents of response to compare
        player_move = raw_response[0]
        action = raw_response[1]
        target = raw_response[2].split(sep=' ')[0]
        target_pos = raw_response[2].split(sep=' ')[2]
        roll = int(raw_response[3])

        # if player stayed in same position, no need to check
        if not player_move == player_pos:
            # check if the move is allowed based on the player's stamina
            n = player_dict['Stamina']
            if self._check_move(n, player_pos, player_move):
                # update player's position if the move is valid
                if player == "player_a":
                    self.player_a_position = player_move
                elif player == "player_b":
                    self.player_b_position = player_move
                elif player == "player_dm":
                    self.boss_position = player_move
            else:
                self.log_to_self("invalid move")
                self.invalid_response = True
                return False, None

        # check if input is contained in player's list of possible actions
        for action_dict in action_lst:
            if action_dict['Name'] == action:
                condition = action_dict['Condition']
                if not condition == "None":
                    # spell slot condition requires at least spell slot remaining
                    if condition == "spell slot" and player_slots == 0:
                        self.log_to_self("condition not met")   # NOTE: logging optional (?)
                        self.invalid_response = True
                        return False, None
                    # adjacency condition requires target to be within range (n=1)
                    elif condition == "adjacency":
                        if not target=="self":
                            if not self._check_move(n=1, pos_1=player_move, pos_2=target_pos):
                                self.log_to_self("condition not met")
                                self.invalid_response = True
                                return False, None
                    # potions condition requires potions remaining
                    elif condition == "potions" and self.potions == 0:
                            self.log_to_self("condition not met")
                            self.invalid_response = True
                            return False, None
                    
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
                
        # if nothing was False until now, return LLM's reply to feed into next prompt
        reply_dict = {
            "Player" : player,
            "Position" : player_move,
            "Action" : action,
            "Target" : f"{target} in {target_pos}",
            "Roll" : roll
        }

        return True, reply_dict


    def turn(self) -> None:
        #get A's response
        answer_a = self.get_utterance('a')
        #check A's response's validity

        #if not turn_idx == 1: NOTE: at turn 1 there is a special format !!!
    #    is_valid_turn = self._validate_player_response(player=self.player_a, utterance=answer_a)

    #    if not is_valid_turn:
            #stop game
    #        return None
        
        #also add the reply to the transcript

        action = {'type': 'send message', 'content': answer_a}
        self.log_event(from_='GM', to='Player 1', action=action)

        #get B's response
        answer_b = self.get_utterance('b')
    #    is_valid_turn = self._validate_player_response(player=self.player_a, utterance=answer_b)
    #    if not is_valid_turn:
        #stop game
    #        return None
        
        action = {'type': 'send message', 'content': answer_b}
        self.log_event(from_='GM', to='Player 2', action=action)

        #get DM's response
        answer_dm = self.get_utterance('dm')
    #    is_valid_turn = self._validate_player_response(player=self.player_a, utterance=answer_dm)
    #    if not is_valid_turn:
        #stop game
    #        return None
        action = {'type': 'send message', 'content': answer_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)


    def combat_turn(self) -> None:


        # make action list for a into a single string:
        action_a_string = ""
        for item in self.player_a_dict['Actions']:
            for key, value in item.items():
                action_a_string += f"{key}: {value}\n"
            action_a_string += ".....\n"
        # collect boss info to give players
        boss_info = f"Position: {self.boss_position}\n"
        for key, value in self.boss_dict.items():
            # hide certain info from players (for now)
            if not key == "Actions" and not key == "Difficulty":
                boss_info += f"{key}: {value}\n"


        replacements_a = {
            "$num_turn": self.current_turn,
            "$position": self.player_a_position,
            "$position_2": self.player_b_position,
            "$blocked_cells": self.blocked_cells,
            "$boss_info": boss_info,
            "$class": self.player_a.clss,
            "$hp": self.player_a_hp,
            "$armor": self.player_a_dict["Armor Class"],
            "$stamina": self.player_a_dict["Stamina"],
            "$additional_info": "",
            "$player": "Player A",
            "$action_list": action_a_string
        }
        
        # combat prompt for a, first combat turn
        for key, value in replacements_a.items():
            self.combat_prompt_a = self.combat_prompt_a.replace(key, str(value))
            print(str(value))
       # print(self.combat_prompt_a)
        self.player_a.history.append({'role': 'user', 'content': self.combat_prompt_a})

        print(self.combat_prompt_a)
        # also log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': self.combat_prompt_a}
        self.log_event(from_='GM', to='Player 1', action=action)

        answer_a = self.get_utterance('a')
        action = {'type': 'send message', 'content': answer_a}
        self.log_event(from_='Player 1', to='GM', action=action)

        # make action list for a into a single string:
        action_b_string = ""
        for item in self.player_b_dict['Actions']:
            for key, value in item.items():
                action_b_string += f"{key}: {value}\n"
            action_b_string += ".....\n"        
                        
        replacements_b = {
            "$num_turn": self.current_turn,
            "$position": self.player_b_position,
            "$position_2": self.player_a_position,
            "$blocked_cells": self.blocked_cells,
            "$boss_info": boss_info,
            "$class": self.player_b.clss,
            "$hp": self.player_b_hp,
            "$armor": self.player_b_dict["Armor Class"],
            "$stamina": self.player_b_dict["Stamina"],
            "$additional_info": "",
            "$player": "Player B",
            "action_list": action_b_string
        }
        
        # combat prompt for b, first combat turn
        for key, value in replacements_b.items():
            self.combat_prompt_b = self.combat_prompt_b.replace(key, str(value))


        print(self.combat_prompt_b)
        self.player_b.history.append({'role': 'user', 'content': self.combat_prompt_b})
        action = {'type': 'send message', 'content': self.combat_prompt_b}
        self.log_event(from_='GM', to='Player 2', action=action)

        answer_b = self.get_utterance('b')
        action = {'type': 'send message', 'content': answer_b}
        self.log_event(from_='Player 2', to='GM', action=action)
        # information to parse for dm:
        # player a and b's positions after they move
        # player a and b's target and dice rolls

        action_dm_string = ""
        for item in self.boss_dict['Actions']:
            for key, value in item.items():
                action_dm_string += f"{key}: {value}\n"
                action_dm_string += ".....\n" 

        replacements_dm = {
            "$position_boss": self.boss_position, #this will need to be updated after this turn, for now its fixed for test
            "$position_a": self.player_a_position, #this needs to be updated, for now its fixed for test
            "$position_b": self.player_b_position, #this needs to be updated, for now its fixed for test
            "$blocked_cells": self.blocked_cells, 
            "$target_a": "Boss", #this needs to be updated, for now its fixed for test
            "$target_b": "Boss", #this needs to be updated, for now its fixed for test
            "$roll_a": "12", #this needs to be updated, for now its fixed for test
            "$roll_b": "12", #this needs to be updated, for now its fixed for test
            "$stamina_boss": self.boss_dict["Stamina"],
            "$action_list_boss": action_dm_string,
        }

        for key, value in replacements_dm.items():
            self.combat_prompt_dm = self.combat_prompt_dm.replace(key, str(value))


        self.player_dm.history.append({'role': 'user', 'content': self.combat_prompt_dm})
        action = {'type': 'send message', 'content': self.combat_prompt_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)
        answer_dm = self.get_utterance('dm')
        action = {'type': 'send message', 'content': answer_dm}
        self.log_event(from_='Dungeon Master', to='GM', action=action)

    def _append_utterance(self, utterance: str, player: str, role: str) -> None:
        """Add an utterance to the history of a player (dnd game specific)."""
        assert player in ('a', 'b', 'dm')
        if player == 'a':
            self.player_a.history.append({'role': role, 'content': utterance})
        if player == 'b':
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
    
