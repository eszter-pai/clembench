import pandas as pd
import random
import string
import os
import sys
import numpy as np
from pathlib import Path

from clemgame.clemgame import GameInstanceGenerator
"""
path = Path('./games/dnd')

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

    boss_name = boss['name']
    boss_dict = boss.to_dict()

    # filter out columns we won't need 
    unnecessary = [
        'str', 'con', 'dex', 'int', 'wis', 'cha', 'source', 'url', 'speed', 'align'
        ]
    for i in unnecessary:
        if i in boss_dict:
            del boss_dict[i]

    return boss_name, boss_dict


######################## DND INSTANCE GENERATOR ########################

GAME_NAME = 'dnd'
N_INSTANCES = 1
SEED = 123

class DnDGameInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        super().__init__('DND')

    def on_generate(self):
        
        # get list of experiments which for us will be levels
        levels = self.load_file('resources/levels.txt').strip('\n').split('\n')

        # get initial prompt templates for adventurers and dm
        prompt_adv_a = self.load_template('resources/initial_prompts/game_intro_a.template')
        prompt_adv_b = self.load_template('resources/initial_prompts/game_intro_b.template')
        prompt_adv_given = self.load_template('resources/initial_prompts/game_intro_given.template')
        prompt_dm = self.load_template('resources/initial_prompts/game_intro_dm.template')

        # experiment names grouped by whether player chooses their class or not
        chosen_class = ['easy-guided', 'easy-unguided', 'hard-guided', 'hard-unguided', 
                        'legendary-guided', 'legendary-unguided']
        given_class = ['magic-only-guided', 'magic-only-unguided', 'melee-only-guided', 
                       'melee-only-unguided', 'balanced-guided', 'balanced-unguided']
        magic_classes = ['Wizard', 'Sorcerer']
        melee_classes = ['Fighter', 'Rogue', 'Cleric']
        ranged_classes = ['Wizard', 'Sorcerer', 'Ranger']
        easy_lvls = ['easy-guided', 'easy-unguided', 'magic-only-guided', 'magic-only-unguided', 
                     'melee-only-guided', 'melee-only-unguided', 'balanced-guided', 'balanced-unguided']

        # building the file, one experiment at a time

        for level in levels:

            # create an experiment 
            experiment = self.add_experiment(level)
            # build N_INSTANCES instances for each experiment
            for game_id in range(N_INSTANCES):
                instance = self.add_game_instance(experiment, game_id)

                # if the player chooses their class, no further action needed, give corresp. template
                if level in chosen_class:
                    instance['prompt_player_a'] = prompt_adv_a
                    instance['prompt_player_b'] = prompt_adv_b
                    instance['player_a_class'] = None
                    instance['player_b_class'] = None

                # if player is given their class, randomly assign options, create corresp. template
                elif level in given_class:
                    prompt_a = prompt_adv_given
                    prompt_b = prompt_adv_given

                    if level=='magic-only-guided' or level=='magic-only-unguided':
                        class_a = random.choice(magic_classes)
                        class_b = random.choice(magic_classes)
                    elif level=='melee-only-guided' or level=='melee-only-unguided':
                        class_a = random.choice(melee_classes)
                        class_b = random.choice(melee_classes)
                    elif level=='balanced-guided' or level=='balanced-unguided':
                        class_a = random.choice(melee_classes)
                        class_b = random.choice(ranged_classes)
                    else:
                        raise Exception("Level couldn't be assigned.")
                    
                    instance['player_a_class'] = class_a
                    instance['player_b_class'] = class_b
                    instance['prompt_player_a'] = self.create_prompt('adventurer', class_a, prompt_a)
                    instance['prompt_player_b'] = self.create_prompt('adventurer', class_b, prompt_b)

                ####### BOSS ASSIGNMENT ########

                if level in easy_lvls:
                    boss_name, boss_dict = generate_boss('easy')
                elif level=='hard-guided' or level=='hard-unguided':
                    boss_name, boss_dict = generate_boss('hard')
                elif level=='legendary-guided' or level=='legendary-unguided':
                    boss_name, boss_dict = generate_boss('legendary')

                instance['boss_name'] = boss_name
                instance['boss_dict'] = boss_dict
                instance['prompt_dm'] = self.create_prompt('dm', boss_name, prompt_dm)
                
    # generate the prompt 
    def create_prompt(self, player_type: str, name: str, prompt: str) -> str:
        """Fill prompt template."""

        if player_type == 'adventurer':
            text = string.Template(prompt).substitute(player_class=name)
        elif player_type == 'dm':
            text = string.Template(prompt).substitute(boss=name)
        else:
            raise Exception('Please specify a valid player type.')
        
        return text
    
if __name__ == '__main__':
    random.seed(SEED)
    # always call this, which will actually generate and save the JSON file
    DnDGameInstanceGenerator().generate()
