import copy
import re
import string
from typing import List, Dict, Tuple
from string import Template
import numpy as np
import scipy

import clemgame.metrics as ms
from clemgame.clemgame import GameMaster, GameBenchmark, DialogueGameMaster, GameScorer
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
        self.reprompt_count: int = 0



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

        # random dungeon generation
        dungeon = Dungeon()
        dungeon.generate_dungeon()
        self.player_a_position = dungeon.player_a_position
        self.player_b_position = dungeon.player_b_position
        self.boss_position = dungeon.player_dm_position
        self.blocked_cells  = dungeon.cells_blocked

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
        bol = True


        # append the initial message of each player to their history
        self.player_a.history.append({'role': 'user', 'content': prompt_player_a})
        self.player_b.history.append({'role': 'user', 'content': prompt_player_b})
        self.player_dm.history.append({'role': 'user', 'content': prompt_player_dm})


        # log the messages as events for the transcriptions
        action = {'type': 'send message', 'content': prompt_player_a}
        self.log_event(from_='GM', to='Player 1', action=action)
        answer_a = self.get_utterance('a')
        answer_a_cleaned = re.sub(r'[!.,]', '', answer_a)
        if self.player_a.clss.lower() != answer_a_cleaned.lower():
            bol, error_message = self.reprompt_initial(self.player_a, answer_a_cleaned, prompt_player_a)
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None


        action = {'type': 'send message', 'content': prompt_player_b}
        self.log_event(from_='GM', to='Player 2', action=action)

        answer_b = self.get_utterance('b')
        answer_b_cleaned = re.sub(r'[!.,]', '', answer_b)
        if self.player_b.clss.lower() != answer_b_cleaned.lower():
            bol, error_message = self.reprompt_initial(self.player_b, answer_b_cleaned, prompt_player_b)
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None


        action = {'type': 'send message', 'content': prompt_player_dm}
        self.log_event(from_='GM', to='Dungeon Master', action=action)
        answer_dm = self.get_utterance('dm')
        answer_dm_cleaned = re.sub(r'[!.,]', '', answer_dm)
        if "Dungeon Master".lower() != answer_dm_cleaned.lower():
            bol, error_message = self.reprompt_initial(self.player_dm, answer_dm_cleaned, prompt_player_dm)
        if bol == False:
            content = "game failed due to: " + error_message
            action = {'type': 'info', 'content': content}
            self.log_event(from_='GM', to='GM', action=action)
            self.aborted = True
            return None


    def reprompt_initial(self, player, answer_cleaned, prompt):

        attempts = 2
        bol = False
        error_message = ""

        if player == self.player_a:
            for attempt in range(attempts):
                bol = self.player_a.clss.lower() == answer_cleaned.lower()
                if bol:
                    break
                error_string =  "Please reply only with your class name. For example, if your assigned class is Wizard, you should only respond with one word 'Wizard'.\n"
                new_attempt = error_string + prompt
                action = {'type': 'send message', 'content': new_attempt}
                self.log_event(from_='GM', to=f'Player 1', action=action)
                answer = self.get_utterance('a')
                answer_cleaned = re.sub(r'[!.,]', '', answer)
                self.reprompt_count += 1
                self.invalid_response = True


        if player == self.player_b:
            for attempt in range(attempts):
                bol = self.player_b.clss.lower() == answer_cleaned.lower()
                if bol:
                    break
                error_string =  "Please reply only with your class name. For example, if your assigned class is Wizard, you should only respond with one word 'Wizard'.\n"
                new_attempt = error_string + prompt
                action = {'type': 'send message', 'content': new_attempt}
                self.log_event(from_='GM', to=f'Player 2', action=action)
                answer = self.get_utterance('b')
                answer_cleaned = re.sub(r'[!.,]', '', answer)
                self.reprompt_count += 1
                self.invalid_response = True

        if player == self.player_dm:
            for attempt in range(attempts):
                bol = "Dungeon Master".lower() == answer_cleaned.lower()
                if bol:
                    break
                error_string =  "Please reply only with your class name. For example, if you are a Dungeon Master, you should only respond with 'Dungeon Master'.\n"
                new_attempt = error_string + prompt
                action = {'type': 'send message', 'content': new_attempt}
                self.log_event(from_='GM', to=f'Dungeon Master', action=action)
                answer = self.get_utterance('dm')
                answer_cleaned = re.sub(r'[!.,]', '', answer)
                self.reprompt_count += 1
                self.invalid_response = True

        if bol == False:
            error_message = "A player does not enter the class name with the correct format (Answer only with the name of the class)."

        return bol, error_message



    @classmethod
    def applies_to(cls, game_name: str) -> bool:
        return game_name == GAME_NAME
    
    def play(self) -> None:
        while self.does_game_proceed():
            self.current_turn += 1
            self.complete_turns += 1

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

        # log other eval assets
        self.log_key('Played turns', self.current_turn)
        self.log_key('Complete turns', self.complete_turns)
        self.log_key('Reprompt count', self.reprompt_count)
        self.log_key(ms.METRIC_ABORTED, self.aborted)
        self.log_key(ms.METRIC_LOSE, self.lose)
        self.log_key(ms.METRIC_REQUEST_COUNT, self.request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_PARSED, self.parsed_request_counts)
        self.log_key(ms.METRIC_REQUEST_COUNT_VIOLATED, self.violated_request_counts)

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
            
        return False

    def _on_parse_response(self, player, utterance: str):
        """Assess whether the player's response needs to be edited before it is logged."""
    
        # RONJA'S NOTE: Do we still need this ?

        return False, utterance
    
    def _score_move(self, player, action: str, target: str):
        """Assess whether the player's move was a bad choice. Bad choices are:
        1. Targeting the boss with an attack it is resistant to.
        2. Choosing not to revive a dead adventurer when able to.
        3. Choosing to heal when above 70% hit points.
        4. Doing nothing even though an action is possible.
        
        This is only done for adventurers and not the DM."""

        if player == self.player_a:
            player_dict = self.player_a_dict
            player_cls = self.player_a.clss
            player_slots = self.player_a_slots
            player_hp = self.player_a_hp
            other_adv_hp = self.player_b_hp
            player_pos = self.player_a_position
        if player == self.player_b:
            player_dict = self.player_b_dict
            player_cls = self.player_b.clss
            player_slots = self.player_b_slots
            player_hp = self.player_b_hp
            other_adv_hp = self.player_a_hp
            player_pos = self.player_b_position
        if player == self.player_dm:
            raise Exception("Invalid player.")

        boss_res = self.boss_dict['Resistance']
        boss_pos = self.boss_position
        action_list = player_dict['Actions']
        action_type = ""

        # classes which can perform ranged attacks even without using a spell slot
        ranged_classes = ["Wizard", "Sorcerer", "Ranger"]
        # classes which can only attack in melee range
        melee_classes = ["Fighter", "Cleric"]

        for i, a in enumerate(action_list):
            if a["Name"] == action:
                action_type = action_list[i]["Type"]

        # 1. targeting the boss with an attack it is resistant to
        if target.lower() == "boss":
            if action_type == boss_res:
                    return False

        # 2. Choosing not to revive a player when able to
        if player_cls == "Cleric":
            if other_adv_hp == 0 and player_slots != 0:
                return False
            
        # 3. Choosing to heal when above 70% HP
        max_hp = player_dict["Hit Points"]
        if (player_hp / max_hp) > 0.7:
            if action_type == "Healing":
                if target.lower() == "self":
                    return False
                if player == self.player_a and target.lower() == "player a":
                    return False
                elif player == self.player_b and target.lower() == "player b":
                    return False
                
        # 4. Doing nothing even though an action is possible
        if action.lower() == "do nothing":

            # Melee-only damage dealers
            if player_cls in melee_classes:
                # if the player COULD attack the boss (is in range) but decides to do nothing
                if self._check_move(n=1, pos_1=player_pos, pos_2=boss_pos):
                    return False
            # Players able to deal damage at a distance
            if player_cls in ranged_classes:
                
                if player_cls == "Ranger":  # ranger can always shoot
                    return False
                
                # careful: cantrips don't cost spell slots but could be bad dmg type (allowed)
                # therefore only judge it as a bad move not to attack if spells also available
                else:
                    if player_slots > 0:
                        return False
        return True

    def _validate_player_response(self, player, utterance: str):
        """
        Parse the player's response according to the instance's given response format.
        Check for violations of the game rules.
        Returns validity and if valid == True, also returns a dictionary of the response, and error message string to log into the event and reprompt.
        """
        lines = utterance.split('\n')
        response_tags = list(self.response_dict)

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

        # the num of lines of a player's response should be equal to 4 (num of response tags)
        if len(lines) != len(response_tags):
            self.invalid_response = True
            action = {'type': 'error', 'content': 'invalid format'}
            self.log_event(from_='GM', to='GM', action=action)
            error_message = "Incorrect Response Format. Your response should only have 4 lines:\n MOVE:\n ACTION:\n TARGET:\n ROLL:\nPlease follow the format."
            return False, None, error_message
        
        # each line should also start with response tags.
        for i in range(len(lines)):
            tag = response_tags[i]
            # check if tagged correctly
            if not lines[i].startswith(tag):
                self.invalid_response = True
                action = {'type': 'error', 'content': 'invalid format'}
                self.log_event(from_='GM', to='GM', action=action)
                error_message = "Incorrect Response Format. Your response should start with:\n MOVE:\n ACTION:\n TARGET:\n ROLL:\nPlease follow the format."
                return False, None, error_message
        
        # Eszter's NOTE: this is basically equal to reply_dict, but the content is yet parsed. so it is your raw_response but in dictionary 
        # response into dictionary: ex: {'MOVE': 'A1', 'ACTION': 'Attack: Quarterstaff attack', 'TARGET': 'Boss in A3', 'ROLL': '7'}
        response_dic = {}
        for line in lines:
            # split each string at the first occurrence of the colon
            key, value = line.split(': ', 1)
            response_dic[key] = value.rstrip()      # RONJA'S NOTE: maybe this will help current parsing issues

        if not response_dic["ACTION"].lower() == "do nothing":

            act_dice_roll = ""
            for act_dic in player_dict["Actions"]:
                if act_dic["Name"] == response_dic["ACTION"].rstrip():
                    act_dice_roll = act_dice_roll + act_dic["Dice"]
            
            if act_dice_roll == "":
                self.invalid_response = True
                action = {'type': 'error', 'content': 'invalid action'}
                self.log_event(from_='GM', to='GM', action=action)
                error_message = "The ACTION you picked is not one of the action options, please select the action from the options we give you."
                return False, None, error_message            

            dice_min = int(act_dice_roll[0])
            dice_num = int(act_dice_roll[-1])
            dice_max = dice_min * dice_num

            # is the response a number?:
            if response_dic["ROLL"].isdigit():
                response_roll = int(response_dic["ROLL"])
            else:
                self.invalid_response = True
                action = {'type': 'error', 'content': 'invalid format'}
                self.log_event(from_='GM', to='GM', action=action)
                error_message = "Incorrect Dice Roll. Please respond with only the sum of your dice roll result.\n For example, if your chosen action has “Dice: 3d4”, and you roll 3, 4, and 4, then your dice roll result is 11. So your response is ROLL: 11\n"
                return False, None, error_message

            #is the sum of the dice roll is possible?
            if response_roll not in range(dice_min, dice_max + 1):
                self.invalid_response = True
                action = {'type': 'error', 'content': 'invalid roll'}
                self.log_event(from_='GM', to='GM', action=action)
                error_message = f"Your Dice Roll result is not between {dice_min} and {dice_max} and therefore not a result of the given dice."
                return False, None, error_message
 
        # now check if response follows game rules

        # fetch contents of response to compare
        player_move = response_dic['MOVE']
        player_action = response_dic['ACTION']
        target = ' '.join(response_dic['TARGET'].split(' ')[:-2])
        target_pos = response_dic['TARGET'].split(' ')[-1]
        roll = response_dic['ROLL']
        if roll.isdigit():
            roll = int(roll)

        ####### Player cannot move to a cell that is occupied (blocked, or someone is already there.)
        if player == self.player_a:
            if player_move == self.player_b_position or player_move == self.boss_position:
                self.invalid_response = True
                error_message = "The position you move to is taken, please try again. Remember: if the cell is taken by another player or is blocked, then you cannot move to there. Your stamina also determines the steps you can take."
                action = {'type': 'error', 'content': 'invalid move'}
                self.log_event(from_='GM', to='GM', action=action)
   
        if player == self.player_b:
            if player_move == self.player_a_position or player_move == self.boss_position:
                self.invalid_response = True
                error_message = "The position you move to is taken, please try again. Remember: if the cell is taken by another player or is blocked, then you cannot move to there. Your stamina also determines the steps you can take."
                action = {'type': 'error', 'content': 'invalid move'}
                self.log_event(from_='GM', to='GM', action=action)
  
        if player == self.player_dm:
            if player_move == self.player_a_position or player_move == self.player_b_position:
                self.invalid_response = True
                error_message = "The position you move to is taken, please try again. Remember: if the cell is taken by another player or is blocked, then you cannot move to there. Your stamina also determines the steps you can take."
                action = {'type': 'error', 'content': 'invalid move'}
                self.log_event(from_='GM', to='GM', action=action) 
        
        if player_move in self.blocked_cells:
            self.invalid_response = True
            error_message = "The position you move to is blocked, please try again. Remember: if the cell is taken by another player or is blocked, then you cannot move to there. Your stamina also determines the steps you can take."
            action = {'type': 'error', 'content': 'invalid move'}
            self.log_event(from_='GM', to='GM', action=action)             

 
        ####### CHECK TARGETING VALIDITY

        # special case for DM
        if player == self.player_dm:
            if target.lower()=='boss':
                self.invalid_response = True
                error_message = "The Dungeon Master cannot target the Boss. Remember you are acting in the boss' place."
                action = {'type': 'error', 'content': 'DM targets boss'}
                self.log_event(from_='GM', to='GM', action=action)
                return False, None, error_message
            
        # otherwise: check if target is actually in the position
        position_check = [('player a', self.player_a_position), ('player b', self.player_b_position), ('boss', self.boss_position)]

        for check in position_check:
            name, position = check
            if target.lower() == name and not position == target_pos:
                self.invalid_response = True
                error_message = "The specified target is not in the position you gave."
                action = {'type': 'error', 'content': 'invalid target position'}
                self.log_event(from_='GM', to='GM', action=action)
                return False, None, error_message


        # if player stayed in same position, no need to check
        if not player_move == player_pos:
            # check if the move is allowed based on the player's stamina
            n = player_dict['Stamina']
            valid = self._check_move(n, player_pos, player_move)
            if not valid:
                action = {'type': 'error', 'content': 'invalid move'}
                self.log_event(from_='GM', to='GM', action=action)
                self.invalid_response = True
                error_message = "Invalid Move. You can only move as many steps as you have stamina and cannot move diagonally. You cannot move into another player's place."
                return False, None, error_message

        # check if input is contained in player's list of possible actions
        for action_dict in action_lst:
            if action_dict['Name'] == player_action:
                condition = action_dict['Condition']
                if not condition == "None":
                    # spell slot condition requires at least spell slot remaining
                    if condition == "spell slot" and player_slots == 0:
                    #    self.log_to_self("condition not met")   # NOTE: logging optional (?)
                        self.invalid_response = True
                        action = {'type': 'error', 'content': 'out of spell slots'}
                        self.log_event(from_='GM', to='GM', action=action)
                        error_message = "You are out of Spell Slots."
                        return False, None, error_message
                    # adjacency condition requires target to be within range (n=1)
                    elif condition == "adjacency":
                        if not target=="self":
                            if not self._check_move(n=1, pos_1=player_move, pos_2=target_pos):
                            #    self.log_to_self("condition not met")
                                self.invalid_response = True
                                action = {'type': 'error', 'content': 'target out of range'}
                                self.log_event(from_='GM', to='GM', action=action)
                                error_message = "Your target is out of range. Remember if you choose to use a melee attack, please move to a position that is next to the target. For example, if you move to C2, you can only target B1, B2, B3, C1, C3, D1, D2, D3"
                                return False, None, error_message
                    # potions condition requires potions remaining
                    elif condition == "potions" and self.potions == 0:
                        #    self.log_to_self("condition not met")
                            self.invalid_response = True
                            action = {'type': 'error', 'content': 'out of spell slots'}
                            self.log_event(from_='GM', to='GM', action=action)
                            error_message = "You have no Potions left"
                            return False, None, error_message
                    
        # some special cases
        if player_action=="Spell: Revivify":   # revivify must be aimed at a dead adventurer
            if player==self.player_a:
                if not target.lower()=='player b' and not self.player_b_hp==0:
                    self.invalid_response = True
                    error_message = "Invalid target. You cannot revive the boss, yourself, or a player who is alive."
                    action = {'type': 'error', 'content': 'invalid target'}
                    self.log_event(from_='GM', to='GM', action=action)
                    return False, None, error_message
            elif player==self.player_b:
                if not target.lower()=='player a' and not self.player_a_hp==0:
                    self.invalid_response = True
                    error_message = "Invalid target. You cannot revive the boss, yourself, or a player who is alive."
                    action = {'type': 'error', 'content': 'invalid target'}
                    self.log_event(from_='GM', to='GM', action=action)
                    return False, None, error_message
        
        if player_action=="Potion: Use healing potion":    # cannot use potions on someone else
            if not target.lower()=='self':
                if player==self.player_a and not target.lower()=='player a':
                    self.invalid_response = True
                    error_message = "Potions cannot be used on someone else"
                    action = {'type': 'error', 'content': 'invalid target'}
                    self.log_event(from_='GM', to='GM', action=action)
                    return False, None, error_message
                elif player==self.player_b and not target.lower()=='player b':
                    self.invalid_response = True
                    error_message = "Potions cannot be used on someone else"
                    action = {'type': 'error', 'content': 'invalid target'}
                    self.log_event(from_='GM', to='GM', action=action)
                    return False, None, error_message
                else:
                    self.potions = self.potions - 1     # remove potion if use was valid 
            else:
                self.potions = self.potions - 1
        # if nothing was False until now, return LLM's reply to feed into next prompt
        # and update player position in the dungeon 

        if player == self.player_a:
            self.player_a_position = player_move
        elif player == self.player_b:
            self.player_b_position = player_move
        elif player == self.player_dm:
            self.boss_position = player_move

        reply_dict = {
            "Position" : player_move,
            "Action" : player_action,
            "Target" : f"{target} in {target_pos}",
            "Roll" : roll
        }

        # check if the move was bad if it was an adventurer
        if not player == self.player_dm:
            if self._score_move(player=player, action=player_action, target=target):
                None
            else:
                action = {'type': 'info', 'content': 'bad move'}
                self.log_event(from_='GM', to='GM', action=action)

        error_message = "No Error"
        # log a valid move
        # action = {'type': 'info', 'content': 'valid move'}
        # self.log_event(from_='GM', to='GM', action=action)
        return True, reply_dict, error_message

    def reprompt(self, player, initial_answer, prompt):
        attempts = 2
        if player == self.player_a:
            for attempt in range(attempts):
                bol, reply_dict, error_message = self._validate_player_response(player, initial_answer)
                if bol:
                    break
                error_string = f"Please try again. The problem of your response is: {error_message}\n"
                new_attempt = error_string + prompt
                player.history.append({'role': 'user', 'content': new_attempt})
                action = {'type': 'send message', 'content': new_attempt}
                self.log_event(from_='GM', to=f'Player 1', action=action)
                initial_answer = self.get_utterance('a')
                self.reprompt_count += 1

        if player == self.player_b:
            for attempt in range(attempts):
                bol, reply_dict, error_message = self._validate_player_response(player, initial_answer)
                if bol:
                    break
                error_string = f"Please try again. The problem of your response is: {error_message}\n"
                new_attempt = error_string + prompt
                player.history.append({'role': 'user', 'content': new_attempt})
                action = {'type': 'send message', 'content': new_attempt}
                self.log_event(from_='GM', to=f'Player 2', action=action)
                initial_answer = self.get_utterance('b')
                self.reprompt_count += 1

        if player == self.player_dm:
            for attempt in range(attempts):
                bol, reply_dict, error_message = self._validate_player_response(player, initial_answer)
                if bol:
                    break
                error_string = f"Please try again. The problem of your response is: {error_message}\n"
                new_attempt = error_string + prompt
                player.history.append({'role': 'user', 'content': new_attempt})
                action = {'type': 'send message', 'content': new_attempt}
                self.log_event(from_='GM', to=f'Dungeon Master', action=action)
                initial_answer = self.get_utterance("dm")
                self.reprompt_count += 1



        return bol, reply_dict, error_message

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
        
        if bol == True:
            action = {'type': 'info', 'content': 'valid move'}
            self.log_event(from_='GM', to='GM', action=action)


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
        if bol == True:
            action = {'type': 'info', 'content': 'valid move'}
            self.log_event(from_='GM', to='GM', action=action)


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
        if bol == True:
            action = {'type': 'info', 'content': 'valid move'}
            self.log_event(from_='GM', to='GM', action=action)


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

class DnDScorer(GameScorer):
    
    def __init__(self, experiment: Dict, game_instance: Dict):
        super().__init__(GAME_NAME, experiment, game_instance)

    def compute_scores(self, episode_interactions: Dict) -> None:

        """Compute episode-level and turn-level scores (mandatory)."""

        max_turns = 15
        invalid_response = False
        adventurers_won = False
        game_aborted = False
        format_violations = 0
        rule_violations = 0
        valid_moves = 0
        bad_moves = 0
        turn_scores = []

        for turn_idx, turn in enumerate(episode_interactions["turns"]):
            turn_score = {"request_count": 1,
                              "violated_request_count": 0,
                              "parsed_request_count": 0,
                              "format_violation_count": 0}

            for event in turn:
                action = event["action"]
                if action["type"] == "error":
                        # differentiate format vs rule violations and log separately:
                    if action["content"] == "invalid format":
                        turn_score["violated_request_count"] = turn_score["violated_request_count"] + 1
                    else:
                        rule_violations += 1
                        turn_score["parsed_request_count"] = turn_score["parsed_request_count"] + 1
                        
                if action["type"] == "info":
                    if action["content"] == "valid move":
                        valid_moves += 1
                    if "game failed due to" in action["content"]:
                        game_aborted = True
                    if action["content"] == "bad move":
                        bad_moves += 1

                if action["content"] == "boss defeated":
                    adventurers_won = True

            turn_score["rule_violation_count"] = rule_violations

                # log turn scores
            self.log_turn_score(turn_idx, ms.METRIC_REQUEST_COUNT_VIOLATED, turn_score["violated_request_count"])
            self.log_turn_score(turn_idx, ms.METRIC_REQUEST_COUNT_PARSED, turn_score["parsed_request_count"])
            self.log_turn_score(turn_idx, ms.METRIC_REQUEST_COUNT, turn_score["request_count"])
            self.log_turn_score(turn_idx, "Rule Violations", turn_score["rule_violation_count"])
            turn_scores.append(turn_score)
        
        # log episode scores
        played_turns = episode_interactions['Played turns']
        self.log_episode_score("Played turns", played_turns)
        complete_turns = episode_interactions['Complete turns']
        self.log_episode_score("Complete turns", complete_turns)
       
        violated_request_count = sum([turn["violated_request_count"] for turn in turn_scores])
        self.log_episode_score(ms.METRIC_REQUEST_COUNT_VIOLATED, violated_request_count)

        parsed_request_count = sum([turn["parsed_request_count"] for turn in turn_scores])
        self.log_episode_score(ms.METRIC_REQUEST_COUNT_PARSED, parsed_request_count)

        request_count = sum([turn["request_count"] for turn in turn_scores])
        self.log_episode_score(ms.METRIC_REQUEST_COUNT, request_count)

        self.log_episode_score(ms.METRIC_REQUEST_SUCCESS, parsed_request_count / request_count)

        rule_violation_count = sum([turn["rule_violation_count"] for turn in turn_scores])
        self.log_episode_score("Rule Violations", rule_violation_count)

        # Common metrics
        if game_aborted:  # if the game had to be aborted
            self.log_episode_score(ms.METRIC_ABORTED, 1)
            self.log_episode_score(ms.METRIC_SUCCESS, 0)
            self.log_episode_score(ms.METRIC_LOSE, 0)
            self.log_episode_score(ms.BENCH_SCORE, np.nan)  # metric not applicable

        else:
            self.log_episode_score(ms.METRIC_ABORTED, 0)

            # if the adventurers won: compute bench score
            if adventurers_won == True:
                self.log_episode_score(ms.METRIC_SUCCESS, 1)
                self.log_episode_score(ms.METRIC_LOSE, 0)

                speed = 1 - (played_turns / max_turns)  # how fast did they beat the boss?
                intel = 1 - (bad_moves/valid_moves)   # how many valid but bad moves did they make?

                # bench score as harmonic mean of speed & intelligence
                self.log_episode_score(ms.BENCH_SCORE, 1 - scipy.stats.hmean([speed, intel]))  

            else:
                self.log_episode_score(ms.METRIC_SUCCESS, 0)
                self.log_episode_score(ms.METRIC_LOSE, 1)
                self.log_episode_score(ms.BENCH_SCORE, 0)  # failure
                 

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
    
    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return DnDScorer(experiment, game_instance)
        
    
