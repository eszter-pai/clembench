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
levels = ['easy-guided', 'easy-unguided', 'hard-guided', 'hard-unguided', 
          'legendary-guided', 'legendary-unguided',
          'magic-only-guided', 'magic-only-unguided', 'melee-only-guided', 
          'melee-only-unguided', 'balanced-guided', 'balanced-unguided']

with open(path / 'resources' / 'levels.txt', 'w') as file:
    for level in levels:
        file.write(level + '\n') 

basegame_levels = ['magic-only', 'melee-only', 'balanced']

with open(path / 'resources' / 'basegame_levels.txt', 'w') as file:
    for level in basegame_levels:
        file.write(level + '\n') 
"""

# load (expanded) dataset 
# -- see scripts for how that was done in dnd_data.py
monsters = pd.read_csv('./games/dnd/resources/dnd_monsters_edited.csv')

# filtering difficulty levels
easy = monsters.loc[(monsters['cr']<=10) & (monsters['legendary'].isna())]
hard = monsters.loc[(monsters['cr'].between(11,15)) & (monsters['legendary'].isna())]
legendary = monsters.loc[monsters['legendary']=='Legendary']

# function to generate a random boss based on specified difficulty level

def generate_boss(difficulty: str):
    """Retrieve a random boss from the dataset based on a specified difficulty."""

    if difficulty=='easy':
        rdm_idx = np.random.choice(easy.index)
        boss = easy.loc[rdm_idx]
    elif difficulty=='hard':
        rdm_idx = np.random.choice(hard.index)
        boss = hard.loc[rdm_idx]
    elif difficulty=='legendary':
        rdm_idx = np.random.choice(legendary.index)
        boss = legendary.loc[rdm_idx]
    else:
        print("Please select a valid difficulty")

    boss_dict = boss.to_dict()

    # filter out columns we won't need 
    unnecessary = [
        'str', 'con', 'dex', 'int', 'wis', 'cha', 'source', 'url', 'speed', 'align'
        ]
    for i in unnecessary:
        if i in boss_dict:
            del boss_dict[i]

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

                    # store players' info
                    for dict in class_info:
                        if dict['Class Name'] == player_a_cls:
                            instance['player_a_dict'] = dict
                        elif dict['Class Name'] == player_b_cls:
                            instance['player_b_dict'] = dict

                    #generate instance boss based on the exp-difficulty
                    instance['boss_dict'] = generate_boss(difficulty)

                    ####### RESPONSES ####### 
                    # first response must be player's class or role
                    instance['player_a_first_resp'] = player_a_cls
                    instance['player_b_first_resp'] = player_b_cls
                    instance['dm_first_resp'] = "Dungeon Master"

                    # continued responses must follow given format:
                    instance['response_format'] = '^MOVE: (?:[A-E][1-5]|stay)\nACTION: (?P<content>)\n\
TARGET: (player a|player b|self|Boss) in [A-E][1-5]\nROLL: (none|[1-9]|[1-9][0-9])\n*(?P<remainder>.*)'
    
if __name__ == '__main__':
    random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    DnDGameInstanceGenerator().generate()
