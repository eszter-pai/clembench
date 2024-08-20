# Dungeon & Dragon-Inspired Game

Developed by Ronja & Eszter as part of the Cognitive Systems Master's program at the University of Potsdam.

## Game Overview

This game is inspired by the classic Dungeon & Dragons format. It involves three players: two adventurers and one Dungeon Master (DM). The adventurers aim to defeat the boss controlled by the DM within a dungeon.

## Player Roles and Classes

- **Adventurers:** Choose from the following classes:
  - Wizard
  - Sorcerer
  - Cleric
  - Fighter
  - Rogue
  - Ranger

- **Dungeon Master:** Controls the dungeon's boss and aims to defeat the adventurers.

## Dungeon Layout

- The dungeon is a 5x5 grid labeled from rows A to E and columns 1 to 5 (e.g., A1 represents the first row and first column).
- Some cells are blocked, and players cannot move onto these cells.

## Gameplay

- **Turn Order:** Player 1 → Player 2 → Dungeon Master, and then repeat.
- **Actions:** On their turn, players select an action based on their class, then roll a dice to determine the outcome (damage dealt, healing done, etc.).

## Player Turn Format

Each player must follow this format during their turn:

- **MOVE:** `<position>`
- **ACTION:** `<action>`
- **TARGET:** `<target>` in `<target’s position>`
- **ROLL:** `<dice roll result>` (sum only, individual roll results are not shown)