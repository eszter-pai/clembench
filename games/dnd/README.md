# Dungeon & Dragon-Inspired Game

Developed by Ronja & Eszter as part of the Cognitive Systems Master's program at the University of Potsdam.

## Game Overview

This game is inspired by the classic Dungeons & Dragons format. It involves three players: two adventurers and one Dungeon Master (DM). The adventurers aim to defeat the boss controlled by the DM within a dungeon.

## Player Roles and Classes

- **2 Adventurers:** Choose from the following classes: Wizard, Sorcerer, Cleric, Fighter, Rogue, Ranger

- **1 Dungeon Master:** Controls the dungeon's boss and aims to defeat the adventurers.

## Dungeon Layout
![image](https://github.com/user-attachments/assets/b505b939-042d-40a2-b790-8847b2286657)

- The dungeon is a 5x5 grid labeled from rows A to E and columns 1 to 5 (e.g., The monster 👾 in the dungeon above spawns at C5).
- Some cells are blocked, and players cannot move onto these cells.

## Gameplay

![image](https://github.com/user-attachments/assets/57859768-240e-48a8-b000-6eadd4d01b90)
- **Turn Order:** Player 1 → Player 2 → Dungeon Master, and then repeat. If the gameplay reaches **15 turns and boss is still alive (HP>0), the game fails.**
- **Actions:** On their turn, players select an action based on their class, then roll a dice to determine the outcome (damage dealt, healing done, etc.). If an action is a spell, the player needs to remember the number of spell slots. If the spell has spell slots 7, that means the spell can only be used 7 times in this game. A player can also choose to use a potion to heal themselves, however 2 adventurers share only 5 potions together.
- **Game Versions**: There are guided and unguided versions. If guided, the game master informs the player the number of resources they have left. For example: If there are only 4 potions left, the player is a spell caster so they need to consider spell slots, then this line will be added into the prompt if the game is guided, **You and Player B have 4 potions left, and you have 6 spell slots left.**

## Player Turn Format

Each player must follow this format during their combat turn:

- **MOVE:** `<position>`
- **ACTION:** `<action>`
- **TARGET:** `<target>` in `<target’s position>`
- **ROLL:** `<dice roll result>` (sum only, individual roll results are not shown)

## Turn Sequence Overview

### Initial Turn

1. **Game Master:**
   - Provide each adventurer with the dungeon layout, including spawn points, boss location, and blocked cells.
   - Explain Action Types, Class Descriptions, and each player's assigned class.
   - Request confirmation from each player by asking them to reply with their class name in one word.

2. **Player 1:**
   - Confirms their class by replying with the class name in one word.
   
![image](https://github.com/user-attachments/assets/46de4089-02e8-482e-84a4-bdd50fbea52c)

3. **Player 2:**
   - Confirms their class by replying with the class name in one word.
   
![image](https://github.com/user-attachments/assets/bdbed675-f5d2-4c12-8b82-8e85e694dfca)


4. **Game Master:**
   - Provide the Dungeon Master with the dungeon layout, including spawn points, boss location, and blocked cells.
   - Share information about adventurer profiles.
   - Request confirmation from the Dungeon Master by asking them to reply with "Dungeon Master."

5. **Dungeon Master:**
   - Confirms their role by replying with "Dungeon Master."

![image](https://github.com/user-attachments/assets/3141c3bb-0fa6-4616-8475-2853d25d7b43)

### Combat Turn
1. **Game Master:**
   - Share profiles of all players, including actions available to each player. Prompt the Player 1 and 2 to respond with the given format.

2. **Player 1:**

![image](https://github.com/user-attachments/assets/14186fe4-9f05-48ee-b312-d55ed6ae520e)


3. **Player 2:**

![image](https://github.com/user-attachments/assets/7e66c27f-a37c-4037-91d8-28116055d592)

4. **Game Master:**
   - Inform what the players have done in this turn, players' profile, and boss's available actions and profile. Prompt the Dungeon Master to respond with the given format.

3. **Dungeon Master:**

![image](https://github.com/user-attachments/assets/c7826dbd-bbdb-4654-815a-01d2d883d3cc)

Examples of full transcripts for 4 models under the same condition (hard and guided with 2 wizards) are in the folder `transcripts_2wizards_hard_guided`

## Results

Results can be found in the `results` directory of the main branch. We ran all 4 game modes on 4 different cLLMs, and additionally ran llama-3.1-8b on guided-reprompt. Files are named by mode; in order to run evaluation, results directories must be renamed 'dnd'. 
For the plots of the evaluation. Please refer to dnd/result-plots directory

| Models                | Average % Played in | Average Quality Score | dnd-guided-reprompt, Quality Score | dnd-guided-reprompt, Quality Score (std) |
|-----------------------|---------------------|-----------------------|------------------------------------|------------------------------------------|
| Llama-3-70B-Instruct   | 0.00                | NaN                   | NaN                                | NaN                                      |
| Llama-3-8B-Instruct    | 0.28                | 0.00                  | 0.00                               | NaN                                      |
| Mixtral-8x22B-Instruct | 2.50                | 79.78                 | 70.21                              | 21.00                                    |
| Mixtral-8x7B-Instruct  | 0.00                | NaN                   | NaN                                | NaN                                      |
| Llama-3.1-8b-Instruct  | 3.33                | 91.54                 | 91.54                              | 4.52                                     |

The table is a subsect of the generated table via clembench scorer. It includes performance metrics for different models, including the percentage of usage, quality scores, and standard deviations. Notably, Llama-3.1-8b-Instruct stands out with the highest quality score (91.54) and a moderate usage rate of 3.33%.
## CLI

`python3 scripts/cli.py run -g dnd -m "model_name"`
