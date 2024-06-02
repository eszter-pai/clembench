"""
Scripts used to expand the dataset dnd_monsters.csv sourced from:
https://www.kaggle.com/datasets/mrpantherson/dnd-5e-monsters
License: CC0 Public Domain
"""

import pandas as pd
import random
import numpy as np

monsters = pd.read_csv('./games/dnd/resources/dnd_monsters.csv')


#################### Generate resistances ####################

monster_type_lst = monsters['type'].unique()    # grab monster types from dataframe

resistances = ["Fire", "Ice", "Blunt", "Piercing", "Slashing"]

resist_dic = {resistance: [] for resistance in resistances}

for monster in monster_type_lst:
    monster_lower = monster.lower()

    if 'fire' in monster_lower or 'fiend' in monster_lower:
        resist_dic['Fire'].append(monster)

    if 'frost giant' in monster_lower or 'cold' in monster_lower:
        resist_dic['Ice'].append(monster)

    if 'ooze' in monster_lower or 'construct' in monster_lower:
        resist_dic['Blunt'].append(monster)

    if 'undead' in monster_lower or 'dragon' in monster_lower:
        resist_dic['Piercing'].append(monster)

    if 'dragon' in monster_lower in monster_lower:
        resist_dic['Slashing'].append(monster)

#randomly give unassigned 
assigned_monsters = set(monster for monsters in resist_dic.values() for monster in monsters)
for monster in monster_type_lst:
    if monster not in assigned_monsters:
        random_resistance = random.choice(resistances)
        resist_dic[random_resistance].append(monster)
        assigned_monsters.add(monster)

# add resistances to df
cond = [
    (monsters['type'].isin(resist_dic['Fire'])),
    (monsters['type'].isin(resist_dic['Ice'])),
    (monsters['type'].isin(resist_dic['Blunt'])),
    (monsters['type'].isin(resist_dic['Piercing'])),
    (monsters['type'].isin(resist_dic['Slashing']))
]

monsters['resistance'] = np.select(cond, resistances)


#################### Cleaning ####################

# make challenge rating numeric
monsters['cr'] = pd.to_numeric(monsters['cr'], errors='coerce')

# drop any with too low cr (i.e. fractions that were removed, e.g. 1/4, 1/2)
monsters = monsters.dropna(subset=['cr'])

#################### Stamina ####################

# add stamina as a function of size
cond_s = [
    (monsters['size'] == 'Tiny'),
    (monsters['size'] == 'Small'),
    (monsters['size'] == 'Medium'),
    (monsters['size'] == 'Large'),
    (monsters['size'] == 'Huge'),
    (monsters['size'] == 'Gargantuan')
]

stamina = [2, 3, 4, 3, 2, 1]

monsters['stamina'] = np.select(cond_s, stamina)
monsters.head(10)