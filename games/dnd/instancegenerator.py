import pandas as pd
import random
import string
import os
import sys
import json
import numpy as np
from pathlib import Path

from clemgame.clemgame import GameInstanceGenerator

path = Path('./games/dnd')
"""
os.mkdir(path / 'in')
os.mkdir(path / 'resources')
os.mkdir(path / 'resources' / 'initial_prompts')
os.mkdir(path / 'resources' / 'combat_prompts')

# define the levels which will make up experiments
basegame_levels = ['magic-only', 'melee-only', 'balanced']

with open(path / 'resources' / 'basegame_levels.txt', 'w') as file:
    for level in basegame_levels:
        file.write(level + '\n') 
"""

def generate_boss(difficulty: str):
    """
    Generate a random dungeon boss whose properties are tied to difficulty.
    Returns a dictionary of the boss' properties in a similar format as players' class dictionary.
    Accepts difficulties: "easy", "hard", "legendary"
    """

    # initialise boss dictionary
    boss_dict = {"Class Name": "Boss"}

    # pool of set values for generation
    size_stamina = {'Tiny': 2, 'Small': 3, 'Medium': 4, 'Large': 3, 'Huge': 2, 'Gargantuan': 1}
    resistances = ['Fire', 'Ice', 'Piercing', 'Slashing', 'Blunt']

    ############# Difficulty-independent properties #############
    size = random.choice(list(size_stamina))    # generate boss' size (independent of difficulty)
    boss_dict['Size'] = size
    boss_dict['Stamina'] = size_stamina[size]   # generate boss' stamina (dependent on size)
    boss_dict['Resistance'] = random.choice(resistances)

    ############# Difficulty-dependent properties #############
    # boss's health, armour class, and attack dice depend on difficulty
    if difficulty == 'easy':
        hp_pool = (20,80)
        ac_pool = (5,9)
        atk_dice = '2d6'
        boss_dict['Difficulty'] = 'Easy'
    elif difficulty == 'hard':
        hp_pool = (80,150)
        ac_pool = (9,13)
        atk_dice = '3d6'
        boss_dict['Difficulty'] = 'Hard'
    elif difficulty == 'legendary':
        hp_pool = (150,200)
        ac_pool = (14,18)
        atk_dice = '4d6'
        boss_dict['Difficulty'] = 'Legendary'
    else:
        raise Exception("Please provide a valid difficulty.")
    
    # generate boss' Hit Points
    boss_dict['Hit Points'] = random.randint(hp_pool[0], hp_pool[1])
    # generate boss' Armour Class
    boss_dict['Armor Class'] = random.randint(ac_pool[0], ac_pool[1])

    # generate attacks boss can do
    boss_actions = []
    # all bosses can do a melee attack which requires being in a position adjacent to the target's
    melee_action = {"Name": "Attack: Melee attack", "Dice": atk_dice, "Type": "Blunt", "Condition": "adjacency"}
    boss_actions.append(melee_action)

    # bosses get an additional action based on their resistance-type
    special_actions = {
        "Fire": {"Name": "Attack: Fire Breath", "Dice": atk_dice, "Type": "Fire", "Condition": "None"},
        "Ice": {"Name": "Attack: Ice Storm", "Dice": atk_dice, "Type": "Ice", "Condition": "None"},
        "Piercing": {"Name": "Attack: Arrow of Death", "Dice": atk_dice, "Type": "Piercing", "Condition": "None"},
        "Slashing": {"Name": "Attack: Whip", "Dice": atk_dice, "Type": "Slashing", "Condition": "None"},
        "Blunt": {"Name": "Attack: Hammer Throw", "Dice": atk_dice, "Type": "Blunt", "Condition": "None"}
    }
    
    # assign special action
    special_action = special_actions[boss_dict['Resistance']]
    boss_actions.append(special_action)

    # add actions to boss dict
    boss_dict['Actions'] = boss_actions

    return boss_dict


GAME_NAME = 'dnd'
N_INSTANCES = 10
SEED = 123

class_info = json.load(open('games/dnd/resources/classes_data.json'))

class DnDGameInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        super().__init__('DND')

    def on_generate(self):
        
        # get list of experiments which for us will be levels
        levels = self.load_file('resources/basegame_levels.txt').strip('\n').split('\n')
        difficulties = ['easy', 'hard', 'legendary']

        # get initial prompt templates for adventurers and dm
        prompt_adv = self.load_template('resources/initial_prompts/game_intro_given.template')
        prompt_dm = self.load_template('resources/initial_prompts/game_intro_dm.template')
        combat_prompt_adv = self.load_template('resources/combat_prompts/combat_adv.template')
        combat_prompt_dm = self.load_template('resources/combat_prompts/combat_dm.template')
        newturn_prompt_adv = self.load_template('resources/combat_prompts/newturn_adv.template')
        newturn_prompt_dm = self.load_template('resources/combat_prompts/newturn_dm.template')

        # experiment names grouped by whether player chooses their class or not
        magic_classes = ['Wizard', 'Sorcerer']
        melee_classes = ['Fighter', 'Rogue', 'Cleric']
        ranged_classes = ['Wizard', 'Sorcerer', 'Ranger']

        # building the file, one experiment at a time

        for level in levels:
            for difficulty in difficulties:
                # create an experiment 
                experiment = self.add_experiment(f"{level}_{difficulty}")
                
                # build N_INSTANCES instances for each experiment
                for game_id in range(N_INSTANCES):
                    instance = self.add_game_instance(experiment, game_id)

                    # game mode: only guided in base game ?? 
                    # NOTE: would like to add unguided as well
                    instance['mode'] = 'guided'
                    
                    # assign random classes to players from level specification
                    if level=='magic-only':
                        player_a_cls = random.choice(magic_classes)
                        player_b_cls = random.choice(magic_classes)
                    elif level=='melee-only':
                        player_a_cls = random.choice(melee_classes)
                        player_b_cls = random.choice(melee_classes)
                    elif level=='balanced':
                        player_a_cls = random.choice(melee_classes)
                        player_b_cls = random.choice(ranged_classes)
                    else:
                        raise Exception("Level couldn't be assigned.")
                    
                    instance['player_a_class'] = player_a_cls
                    instance['player_b_class'] = player_b_cls
                    # create prompts 
                    instance['prompt_player_a'] = string.Template(prompt_adv).substitute(
                        player_class=player_a_cls)
                    instance['prompt_player_b'] = string.Template(prompt_adv).substitute(
                        player_class=player_b_cls)
                    instance['prompt_dm'] = prompt_dm
                    instance['combat_prompt_adv'] = combat_prompt_adv
                    instance['combat_prompt_dm'] = combat_prompt_dm
                    instance['newturn_prompt_adv'] = newturn_prompt_adv
                    instance['newturn_prompt_dm'] = newturn_prompt_dm

                    # store players' info
                    for dict in class_info:
                        if dict['Class Name'] == player_a_cls:
                            instance['player_a_dict'] = dict
                        if dict['Class Name'] == player_b_cls:
                            instance['player_b_dict'] = dict

                    #generate instance boss based on the exp-difficulty
                    instance['boss_dict'] = generate_boss(difficulty)

                    # continued responses must follow given format:
                    response_dict = {
                        'MOVE: ': '(?:[A-E][1-5]|stay)',
                        'ACTION: ': '(?P<content>)',
                        'TARGET: ': '(none|(player a|player b|self|boss)\sin\s[A-E][1-5])',
                        'ROLL: ': '(?:none|1[1-9]|2[0-4])' # highest dice is 4d6 so highest possible roll is 24
                    }
                    instance['response_format'] = response_dict
    
if __name__ == '__main__':
    random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    DnDGameInstanceGenerator().generate()
