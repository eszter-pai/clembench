import copy
import re
import string
from typing import List, Dict, Tuple
from string import Template

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
        self.boss_position = "A3"
        self.blocked_cells = "C2, B3, E4"

        # initialise common metrics
        self.request_counts = [0] * (self.max_turns + 1)
        self.parsed_request_counts = [0] * (self.max_turns + 1)
        self.violated_request_counts = [0] * (self.max_turns + 1)

        # save players' response
        self.player_a_response = []
        self.player_b_response = []
        self.player_dm_response = []

        # log the details of players
        self.log_players({
            'GM': 'Game master for DnD',
            'Player 1': f'Adventurer A: {self.model_a}',
            'Player 2': f'Adventurer B: {self.model_b}',
            'Player Dungeon Master': f'Dungeon Master: {self.model_dm}'
            })

        self.initiate(prompt_player_a, prompt_player_b, prompt_dm)
    

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
        answer_a = self.get_utterance('a')

  


        action = {'type': 'send message', 'content': prompt_player_b}
        self.log_event(from_='GM', to='Player 2', action=action)

        answer_b = self.get_utterance('b')




        action = {'type': 'send message', 'content': prompt_player_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)

        answer_dm = self.get_utterance('dm')



    @classmethod
    def applies_to(cls, game_name: str) -> bool:
        return game_name == GAME_NAME
    
    def play(self) -> None:
        while self.does_game_proceed():
            self.current_turn += 1

            # always call log_next_turn when a new turn starts
            self.log_next_turn()

            if  self.current_turn == 2:
                self.combat_turn()
            else:
                self.new_turn()


        if self.complete_turns == self.max_turns:
            # log a message informing that the game was successfuly played
            action = {'type': 'info', 'content': 'game successful'}
            self.log_event(from_='GM', to='GM', action=action)
        
        if self.boss_hp <= 0:
            action = {'type': 'info', 'content': 'boss defeated'}
            self.log_event(from_='GM', to='GM', action=action)
        # log a final message saying that the game did came to an end
        action = {'type': 'info', 'content': 'end game'}
        self.log_event(from_='GM', to='GM', action=action)
        return None


    def does_game_proceed(self) -> None:

        # does the game continue
    #    if self.current_turn > self.max_turns: # if max turns reached 
    #        self.log_to_self("max turns reached", str(self.max_turns))
    #        return False
    #    if self.invalid_response:               # if invalid response - reprompt??
    #        self.log_to_self("invalid response", "abort game")
    #        return False

        if not self.aborted:
            # game ends if max turns reached
            if self.current_turn > self.max_turns:
                self.lose = True
                return False
            # game ends if boss is dead
            elif self.boss_hp <= 0:
                return False
            # game ends if all adventurers are dead
            elif self.player_a_hp <= 0 and self.player_b_hp <= 0:
                self.lose = True
                return False
            # if none of the above is true and max turns not reached, continue
            elif self.current_turn <= self.max_turns:
                return True
            else:
                return False
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
            self.player_a_response.append(answer_a)

            return answer_a


        if player == 'b':

            #API call (or get a programmatic response) from player b
            prompt_b, raw_answer_b, answer_b = self.player_b(self.player_b.history,
                                                    self.current_turn)
            #API call to the records
            action = {'type': 'get message', 'content': answer_b}
            self.log_event(from_='Player 2', to='GM', action=action,
                        call=(copy.deepcopy(prompt_b), raw_answer_b))
            
            self.player_b_response.append(answer_b)
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
            
            self.player_dm_response.append(answer)
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
        Returns validity and if valid == True, also returns a dictionary of the response, and error message string to log into the event and reprompt.
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
                error_message = "Incorrect Response Format"
                return False, None, error_message
            # check if content matches regex
            if not re.match(pattern, line_content, re.IGNORECASE):
                self.invalid_response = True
                error_message = "Incorrect Response Format"
                return False, None, error_message
            
        # log if format was valid 
    #    self.log_to_self("valid format", "continue")

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
        target = ' '.join(raw_response[2].split(sep=' ')[:-2])
        target_pos = raw_response[2].split(sep=' ')[-1]
        roll = int(raw_response[3])

        # if player stayed in same position, no need to check
        if not player_move == player_pos:
            # check if the move is allowed based on the player's stamina
            n = player_dict['Stamina']
            if self._check_move(n, player_pos, player_move):
                # update player's position if the move is valid
                if player == self.player_a:
                    self.player_a_position = player_move
                elif player == self.player_b:
                    self.player_b_position = player_move
                elif player == self.player_dm:
                    self.boss_position = player_move
            else:
                #action = {'type': 'info', 'content': 'invalid move'}
                #self.log_event(from_='GM', to='GM', action=action)
            #    self.log_to_self("invalid move")
                self.invalid_response = True
                error_message = "Invalid Move"
                return False, None, error_message

        # check if input is contained in player's list of possible actions
        for action_dict in action_lst:
            if action_dict['Name'] == action:
                condition = action_dict['Condition']
                if not condition == "None":
                    # spell slot condition requires at least spell slot remaining
                    if condition == "spell slot" and player_slots == 0:
                    #    self.log_to_self("condition not met")   # NOTE: logging optional (?)
                        self.invalid_response = True
                        error_message = "Out of Spell Slots"
                        return False, None, error_message
                    # adjacency condition requires target to be within range (n=1)
                    elif condition == "adjacency":
                        if not target=="self":
                            if not self._check_move(n=1, pos_1=player_move, pos_2=target_pos):
                            #    self.log_to_self("condition not met")
                                self.invalid_response = True
                                error_message = "Target out of range"
                                return False, None, error_message
                    # potions condition requires potions remaining
                    elif condition == "potions" and self.potions == 0:
                        #    self.log_to_self("condition not met")
                            self.invalid_response = True
                            error_message = "No Potions left"
                            return False, None, error_message
                    
        # some special cases
        if action=="Spell: Revivify":   # revivify must be aimed at a dead adventurer
            if player==self.player_a:
                if not target.lower()=='player b' and not self.player_b_hp==0:
                    self.invalid_response = True
                    error_message = "The Target is not dead (hp = 0)"
                    return False, None, error_message
            elif player==self.player_b:
                if not target.lower()=='player a' and not self.player_a_hp==0:
                    self.invalid_response = True
                    error_message = "The Target is not dead (hp = 0)"
                    return False, None, error_message
        
        if action=="Potion: Use healing potion":    # cannot use potions on someone else
            self.potions = self.potions - 1
            if not target.lower()=='self':
                if player==self.player_a and not target.lower()=='player a':
                    self.invalid_response = True
                    error_message = "Potions cannot be used on someone else"
                    return False, None, error_message
                elif player==self.player_b and not target.lower()=='player b':
                    self.invalid_response = True
                    error_message = "Potions cannot be used on someone else"
                    return False, None, error_message
                
        # if nothing was False until now, return LLM's reply to feed into next prompt
        reply_dict = {
            "Position" : player_move,
            "Action" : action,
            "Target" : f"{target} in {target_pos}",
            "Roll" : roll
        }

        error_message = "No Error"
        return True, reply_dict, error_message


    def combat_turn(self) -> None:


        # make action list for a into a single string:
        action_a_string = "\n"
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
            "num_turn": self.current_turn,
            "position": self.player_a_position,
            "position_2": self.player_b_position,
            "blocked_cells": self.blocked_cells,
            "boss_info": boss_info,
            "class": self.player_a.clss,
            "hp": self.player_a_hp,
            "armor": self.player_a_dict["Armor Class"],
            "stamina": self.player_a_dict["Stamina"],
            "additional_info": "",
            "player": "Player A",
            "action_list": action_a_string
        }
        
        # combat prompt for a, first combat turn
        combat_prompt_a = Template(self.combat_prompt_a)
        combat_prompt_a = combat_prompt_a.substitute(**replacements_a)
        self.player_a.history.append({'role': 'user', 'content': combat_prompt_a})

        # also log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': combat_prompt_a}
        self.log_event(from_='GM', to='Player 1', action=action)

        answer_a = self.get_utterance('a')
        bol, reply_dict_a, error_message = self._validate_player_response(self.player_a, answer_a)

        # if the bol is Flase (the response is invalid due to the reason described in error message)
        if bol == False:
            error_string = "Please try again. The problem of your response is: "+ error_message + "\n"
            new_attempt_combat_a = error_string + combat_prompt_a
            self.player_a.history.append({'role': 'user', 'content': new_attempt_combat_a})
            action = {'type': 'send message', 'content': new_attempt_combat_a}
            self.log_event(from_='GM', to='Player 1', action=action)
            answer_a = self.get_utterance('a')
            bol, reply_dict_a, error_message = self._validate_player_response(self.player_a, answer_a)
        
        # after reprompt and the response is still invalid, abort game
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None


        # make action list for a into a single string:
        action_b_string = "\n"
        for item in self.player_b_dict['Actions']:
            for key, value in item.items():
                action_b_string += f"{key}: {value}\n"
            action_b_string += ".....\n"        
                        
        replacements_b = {
            "num_turn": self.current_turn,
            "position": self.player_b_position,
            "position_2": self.player_a_position,
            "blocked_cells": self.blocked_cells,
            "boss_info": boss_info,
            "class": self.player_b.clss,
            "hp": self.player_b_hp,
            "armor": self.player_b_dict["Armor Class"],
            "stamina": self.player_b_dict["Stamina"],
            "additional_info": "",
            "player": "Player B",
            "action_list": action_b_string
        }
        
        # combat prompt for b, first combat turn

        combat_prompt_b = Template(self.combat_prompt_b)
        combat_prompt_b = combat_prompt_b.substitute(**replacements_b)
        self.player_b.history.append({'role': 'user', 'content': combat_prompt_b})
        action = {'type': 'send message', 'content': combat_prompt_b}
        self.log_event(from_='GM', to='Player 2', action=action)

        answer_b = self.get_utterance('b')
        bol, reply_dict_b, error_message = self._validate_player_response(self.player_b, answer_b)


        if bol == False:
            error_string = "Please try again. The problem of your response is: "+ error_message + "\n"
            new_attempt_combat_b = error_string + combat_prompt_b
            self.player_b.history.append({'role': 'user', 'content': new_attempt_combat_b})
            action = {'type': 'send message', 'content': new_attempt_combat_b}
            self.log_event(from_='GM', to='Player 2', action=action)
            answer_a = self.get_utterance('b')
            bol, reply_dict_b, error_message = self._validate_player_response(self.player_b, answer_b)
        
        # after reprompt and the response is still invalid, abort game
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None



        # information to parse for dm:
        # player a and b's positions after they move


        action_dm_string = "\n"
        for item in self.boss_dict['Actions']:
            for key, value in item.items():
                action_dm_string += f"{key}: {value}\n"
            action_dm_string += ".....\n" 

        replacements_dm = {
            "num_turn": self.current_turn,
            "position_boss": self.boss_position, #this will need to be updated after this turn, for now its fixed for test
            "position_a": self.player_a_position,
            "position_b": self.player_b_position,
            "blocked_cells": self.blocked_cells, 
            "target_a": reply_dict_a["Target"], 
            "target_b": reply_dict_b["Target"], 
            "roll_a": reply_dict_a["Roll"], 
            "roll_b": reply_dict_b["Roll"],
            "stamina_boss": self.boss_dict["Stamina"],
            "action_list_boss": action_dm_string,
        }
        
        combat_prompt_dm = Template(self.combat_prompt_dm)
        combat_prompt_dm = combat_prompt_dm.substitute(**replacements_dm)

        self.player_dm.history.append({'role': 'user', 'content': combat_prompt_dm})
        action = {'type': 'send message', 'content': combat_prompt_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)
        answer_dm = self.get_utterance('dm')
        bol, reply_dict_dm, error_message = self._validate_player_response(self.player_dm, answer_dm)

        if bol == False:
            error_string = "Please try again. The problem of your response is: "+ error_message + "\n"
            new_attempt_combat_dm = error_string + combat_prompt_dm
            self.player_dm.history.append({'role': 'user', 'content': new_attempt_combat_dm})
            action = {'type': 'send message', 'content': new_attempt_combat_dm}
            self.log_event(from_='GM', to='Dungeon Master', action=action)
            answer_dm = self.get_utterance('dm')
            bol, reply_dict_dm, error_message = self._validate_player_response(self.player_dm, answer_dm)
        
        # after reprompt and the response is still invalid, abort game
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None


    def new_turn(self) -> None:

        # the responses from the previous turn should all be valid

        _ , reply_a, _ = self._validate_player_response(self.player_a, self.player_a_response[-1])
        _, reply_b, _ = self._validate_player_response(self.player_b, self.player_b_response[-1])
        _, reply_dm, _ = self._validate_player_response(self.player_dm, self.player_dm_response[-1])


        # get player_a_stats and player_b_status (player position, hp and spell slots)
        # hp calcuation:
        a_armor = self.player_a_dict["Armor Class"]
        b_armor = self.player_b_dict["Armor Class"]
        dm_armor = self.boss_dict["Armor Class"]

        #boss hp left
        total_damage_done = 0 #damage done in this turn
        if reply_a["Action"].startswith(("Spell", "Attack", "Cantrip")):
            total_damage_done = total_damage_done + reply_a["Roll"]

        if reply_b["Action"].startswith(("Spell", "Attack", "Cantrip")):
            total_damage_done = total_damage_done + reply_b["Roll"]

        # the target only takes damage if the damage roll is equal or greater to AC
        if total_damage_done >= dm_armor:
            # make sure hp doesn't drop below 0
            if self.boss_hp - total_damage_done <= 0:
                self.boss_hp = 0
            else:
                self.boss_hp = self.boss_hp - total_damage_done

        #player hp left:
        if reply_dm["Action"].startswith("Attack"):
            if "player a" in reply_dm["Target"].lower() and reply_dm["Roll"] >= a_armor:
                # make sure hp doesn't drop below 0
                if self.player_a_hp - reply_dm["Roll"] <= 0:
                    self.player_a_hp = 0
                else:
                    self.player_a_hp = self.player_a_hp - reply_dm["Roll"]
            if "player b" in reply_dm["Target"].lower() and reply_dm["Roll"] >= b_armor:
                # make sure hp doesn't drop below 0
                if self.player_b_hp - reply_dm["Roll"] <= 0:
                    self.player_b_hp = 0
                else:
                    self.player_b_hp = self.player_b_hp - reply_dm["Roll"]

        # if anyone's action belongs to the type: healing ex. healing spells or potions on a target.
        # no over-heal, that is, if someone roll heal 10 on a target, and the target health is 43/46, then the target's hp is back to 46/46
        # does player A uses healing action:
        if "healing" in reply_a["Action"].lower():
            healing_done = reply_a["Roll"]
            if "player a" in reply_a["Target"].lower():
                hp_diff = self.player_a_dict["Hit Points"] - self.player_a_hp
                if hp_diff >= healing_done:
                    self.player_a_hp = self.player_a_hp + healing_done
                if hp_diff < healing_done:
                    # recover to original health
                    self.player_a_hp = self.player_a_dict["Hit Points"]

            if "player b" in reply_a["Target"].lower():
                hp_diff = self.player_b_dict["Hit Points"] - self.player_b_hp
                if hp_diff >= healing_done:
                    self.player_b_hp = self.player_b_hp + healing_done
                if hp_diff < healing_done:
                    # recover to original health
                    self.player_b_hp = self.player_b_dict["Hit Points"]
        
        # does player B uses healing action:
        if "healing" in reply_b["Action"].lower():
            healing_done = reply_b["Roll"]
            if "player a" in reply_b["Target"].lower():
                hp_diff = self.player_a_dict["Hit Points"] - self.player_a_hp
                if hp_diff >= healing_done:
                    self.player_a_hp = self.player_a_hp + healing_done
                if hp_diff < healing_done:
                    # recover to original health
                    self.player_a_hp = self.player_a_dict["Hit Points"]

            if "player b" in reply_b["Target"].lower():
                hp_diff = self.player_b_dict["Hit Points"] - self.player_b_hp
                if hp_diff >= healing_done:
                    self.player_b_hp = self.player_b_hp + healing_done
                if hp_diff < healing_done:
                    # recover to original health
                    self.player_b_hp = self.player_b_dict["Hit Points"]
        
        
        # check if the player uses spell, if so, the spell slots minus 1
        if "spell" in reply_a["Action"].lower():
            self.player_a_slots = self.player_a_slots - 1
        if "spell" in reply_b["Action"].lower():
            self.player_b_slots = self.player_b_slots - 1    
        
        a_stats_string = f"Hit Points: {self.player_a_hp}\nPosition: {self.player_a_position}\nSpell slots: {self.player_a_slots}"
        b_stats_string = f"Hit Points: {self.player_b_hp}\nPosition: {self.player_b_position}\nSpell slots: {self.player_b_slots}"
        boss_stats_string = f"Hit Points: {self.boss_hp}\nPosition: {self.boss_position}"

        # make action list for a into a single string:
        action_a_string = "\n"
        for item in self.player_a_dict['Actions']:
            for key, value in item.items():
                action_a_string += f"{key}: {value}\n"
            action_a_string += ".....\n"


        previous_turn_count = self.current_turn - 1
        replacements_a = {
            "turn_count": previous_turn_count,
            "target_a": reply_a["Target"], 
            "target_b": reply_b["Target"], 
            "action_a": reply_a["Action"],
            "action_b": reply_b["Action"], 
            "roll_a": reply_a["Roll"], 
            "roll_b": reply_b["Roll"], 
            "target_boss": reply_dm["Target"], 
            "action_boss": reply_dm["Action"], 
            "roll_boss": reply_dm["Roll"],
            "player_a_stats": a_stats_string,
            "player_b_stats": b_stats_string,
            "boss_stats": boss_stats_string,
            "additional_info": "",
            "player": "Player A",
            "stamina": self.player_a_dict["Stamina"],
            "action_list": action_a_string,
            
        }
        
        newturn_prompt_a = Template(self.newturn_prompt_a)
        newturn_prompt_a = newturn_prompt_a.substitute(**replacements_a)
        self.player_a.history.append({'role': 'user', 'content': newturn_prompt_a})

        # also log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': newturn_prompt_a}
        self.log_event(from_='GM', to='Player 1', action=action)

        answer_a = self.get_utterance('a')

        # update reply_a dict, because this info needs to be passed on
        bol, reply_a, error_message = self._validate_player_response(self.player_a, answer_a)


        # if the bol is Flase (the response is invalid due to the reason described in error message)
        if bol == False:
            error_string = "Please try again. The problem of your response is: "+ error_message + "\n"
            new_attempt_newturn_a = error_string + newturn_prompt_a
            self.player_a.history.append({'role': 'user', 'content': new_attempt_newturn_a})
            action = {'type': 'send message', 'content': new_attempt_newturn_a}
            self.log_event(from_='GM', to='Player 1', action=action)
            answer_a = self.get_utterance('a')
            bol, reply_a, error_message = self._validate_player_response(self.player_a, answer_a)
        
        # after reprompt and the response is still invalid, abort game
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None

        # remember now player A move, so the position is already updated inside _validate_player_response, and this info needs to be passed on:
        a_stats_string = f"Hit Points: {self.player_a_hp}\nPosition: {self.player_a_position}\nSpell slots: {self.player_a_slots}"
        
        # make action list for a into a single string:
        action_b_string = "\n"
        for item in self.player_b_dict['Actions']:
            for key, value in item.items():
                action_b_string += f"{key}: {value}\n"
            action_b_string += ".....\n"

        replacements_b = {
            "turn_count": previous_turn_count,
            "target_a": reply_a["Target"], 
            "target_b": reply_b["Target"], 
            "action_a": reply_a["Action"],
            "action_b": reply_b["Action"], 
            "roll_a": reply_a["Roll"], 
            "roll_b": reply_b["Roll"], 
            "target_boss": reply_dm["Target"], 
            "action_boss": reply_dm["Action"], 
            "roll_boss": reply_dm["Roll"],
            "player_a_stats": a_stats_string,
            "player_b_stats": b_stats_string,
            "boss_stats": boss_stats_string,
            "additional_info": "",
            "player": "Player B",
            "stamina": self.player_b_dict["Stamina"],
            "action_list": action_b_string,
            
        }

        newturn_prompt_b = Template(self.newturn_prompt_b)
        newturn_prompt_b = newturn_prompt_b.substitute(**replacements_b)
        self.player_b.history.append({'role': 'user', 'content': newturn_prompt_b})

        # also log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': newturn_prompt_b}
        self.log_event(from_='GM', to='Player 2', action=action)

        answer_b = self.get_utterance('b')

        # remember now player B move, so the position is updated inside _validate_player_response, and this info needs to be passed on:
        bol, reply_b, error_message = self._validate_player_response(self.player_b, answer_b)

        # if the bol is Flase (the response is invalid due to the reason described in error message)
        if bol == False:
            error_string = "Please try again. The problem of your response is: "+ error_message + "\n"
            new_attempt_newturn_b = error_string + newturn_prompt_a
            self.player_b.history.append({'role': 'user', 'content': new_attempt_newturn_b})
            action = {'type': 'send message', 'content': new_attempt_newturn_b}
            self.log_event(from_='GM', to='Player 2', action=action)
            answer_b = self.get_utterance('b')
            bol, reply_b, error_message = self._validate_player_response(self.player_b, answer_b)
        
        # after reprompt and the response is still invalid, abort game
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None
        
        b_stats_string = f"Hit Points: {self.player_b_hp}\nPosition: {self.player_b_position}\nSpell slots: {self.player_b_slots}"

        action_dm_string = "\n"
        for item in self.boss_dict['Actions']:
            for key, value in item.items():
                action_dm_string += f"{key}: {value}\n"
            action_dm_string += ".....\n"


        replacements_dm = {
            "turn_count": previous_turn_count,
            "target_a": reply_a["Target"], 
            "target_b": reply_b["Target"], 
            "action_a": reply_a["Action"],
            "action_b": reply_b["Action"], 
            "roll_a": reply_a["Roll"], 
            "roll_b": reply_b["Roll"], 
            "name_boss": self.boss_dict["Class Name"],
            "target_boss": reply_dm["Target"], 
            "action_boss": reply_dm["Action"], 
            "roll_boss": reply_dm["Roll"],
            "player_a_stats": a_stats_string,
            "player_b_stats": b_stats_string,
            "boss_stats": boss_stats_string,
            "additional_info": "",
            "stamina": self.boss_dict["Stamina"],
            "action_list": action_dm_string,
            
        }


        newturn_prompt_dm = Template(self.newturn_prompt_dm)
        newturn_prompt_dm = newturn_prompt_dm.substitute(**replacements_dm)
        self.player_dm.history.append({'role': 'user', 'content': newturn_prompt_dm})
        
        # also log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': newturn_prompt_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)

        answer_dm = self.get_utterance('dm')

        # remember now player DM move, so the position is updated inside _validate_player_response, and this info needs to be passed on:
        bol, reply_dm, error_message = self._validate_player_response(self.player_dm, answer_dm)
        # if the bol is Flase (the response is invalid due to the reason described in error message)

        if bol == False:
            error_string = "Please try again. The problem of your response is: "+ error_message + "\n"
            new_attempt_newturn_dm = error_string + newturn_prompt_dm
            self.player_dm.history.append({'role': 'user', 'content': new_attempt_newturn_dm})
            action = {'type': 'send message', 'content': new_attempt_newturn_dm}
            self.log_event(from_='GM', to='Dungeon Master', action=action)
            answer_dm = self.get_utterance('dm')
            bol, reply_dm, error_message = self._validate_player_response(self.player_dm, answer_dm)
        
        # after reprompt and the response is still invalid, abort game
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None




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
    
