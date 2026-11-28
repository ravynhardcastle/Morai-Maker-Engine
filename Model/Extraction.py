# ————— IMPORTS ————— #

from Pretraining import data_path # use the same ones from Pretraining.py
from tile_config import allNames
# ————— END IMPORTS ————— #

# ————— CONSTANTS ————— #

# ————— END CONSTANTS ————— #

'''
Notes to self:

Game Starts on the players turn!

Ended Turn:  time = 46.3905 Marks the end (MARKS THE END OF THE PLAYERS TURN, AND THE START OF THE AI TURN

Player Turn:  time = 21.63811 Marks the end of AI turn, and the START of the Player Turn

Placing tile on existing tile deletes it

'''

'''
Extraction format:
Dictionary of x (int): Dictionary of...
	...y (int): List of...
		...Object name indexes (int)

'''

def main():
	print(extract_levels())

def extract_levels(path = data_path): 
	levels = {}
	for file_name in path.glob('*/*.txt'):
		levels[file_name] = {}
		content = []
		with open(file_name) as file:
			content = file.readlines()
		content = [x.strip() for x in content] 
		objects: dict[int, dict[int, list[int]]] = {} # Always the most recent rep of level
		player_actions: list[dict[int, dict[int, list[int]]]] = [{}] # What was added to the level by the player every turn
		ai_actions: list[dict[int, dict[int, list[int]]]] = [{}]
		ai_accepteds: list[dict[int, dict[int, list[int]]]] = [{}]
		ai_removals: list[dict[int, dict[int, list[int]]]] = [{}]
		additions: list[int] = [] # Additions per turn
		removals: list[int] = [] # Removals per turn
		state: list[dict[int, dict[int, list[int]]]] = [] # Objects rep per turn
		turn = 0
		if len(content)>0 and "Start" in content[0]:
			player_control = True
			for line in content:
				if "Added" in line and " at " in line:
					subline = line[6:]
					at_start = subline.find(" at ")
					name_of_addition = subline[:at_start]
					addition_index = allNames.index(name_of_addition)
					
					subline = subline[at_start + 4:]
					index_time_split = subline.split(":  ")
					index_string = index_time_split[0]
					index_split = index_string.split(", ")
					x = int(index_split[0])
					y = int(index_split[1])
					
					if player_control:
						if x in objects.keys() and y in objects[x].keys() and addition_index in objects[x][y]:
							# If the object already exists, trying to add it again is actually removing it
							objects[x][y].remove(addition_index)
							if len(objects[x][y]) == 0:
								objects[x].pop(y)
							if len(objects[x]) == 0:
								objects.pop(x)
							if x in player_actions[turn].keys() and y in player_actions[turn][x].keys() and addition_index in player_actions[turn][x][y]:
								remove_entry(player_actions, turn, x, y, addition_index)
							if x in ai_actions[turn].keys() and y in ai_actions[turn][x].keys() and addition_index in ai_actions[turn][x][y]:
								# Store the removal in the list of rejected AI suggestions
								if not x in ai_removals[turn]:
									ai_removals[turn][x] = {}
								if not y in ai_removals[turn][x]:
									ai_removals[turn][x][y] = []
								ai_removals[turn][x][y].append(addition_index)
						else:
							if not x in objects.keys():
								objects[x] = {}
							if not x in player_actions[turn].keys():
								player_actions[turn][x] = {}
							if not y in objects[x].keys():
								objects[x][y] = []
							if not y in player_actions[turn][x].keys():
								player_actions[turn][x][y] = []

							objects[x][y].append(addition_index)
							player_actions[turn][x][y].append(addition_index)

							if x in ai_removals[turn].keys() and y in ai_removals[turn][x].keys() and addition_index in ai_removals[turn][x][y]:
								# Remove the removal since we're not removing it anymore (this makes sense)
								remove_entry(ai_removals, turn, x, y, addition_index)
					else:
						if not x in ai_actions[turn].keys():
							ai_actions[turn][x] = {}
						if not y in ai_actions[turn][x].keys():
							ai_actions[turn][x][y] = []
						ai_actions[turn][x][y].append(addition_index)
				elif "Ended Turn" in line:
					player_control = False
					state.append(objects.copy())
					
					ai_accepteds[turn] = ai_actions[turn].copy()
					
					current_additions = 0
					for x in ai_actions[turn].keys():
						for y in ai_actions[turn][x]:
							current_additions += len(ai_actions[turn][x][y])
					additions.append(current_additions)
					
					current_removals = 0
					for x in ai_removals[turn].keys():
						for y in ai_removals[turn][x]:
							current_removals += len(ai_removals[turn][x][y])
							for removal in ai_removals[turn][x][y]:
								remove_entry(ai_accepteds, turn, x, y, removal)
					removals.append(current_removals)
					
					player_actions.append({})
					ai_actions.append({})
					ai_removals.append({})
					ai_accepteds.append({})
					turn += 1
				elif "Player Turn" in line:
					player_control = True
				elif "Study End" in line:
					state.append(objects.copy())
		
		levels[file_name] = {
			"final_level": objects,
			"state": state,
			"additions": additions,
			"removals": removals,
			"player_actions": player_actions,
			"ai_actions": ai_actions,
			"ai_accepteds": ai_accepteds,
			"ai_removals": ai_removals
		}
	
	return levels
	
def remove_entry(curr_list: list[dict[int, dict[int, list[int]]]], turn: int, x: int, y: int, index: int):
	curr_list[turn][x][y].remove(index)
	if len(curr_list[turn][x][y]) == 0:
		curr_list[turn][x].pop(y)
	if len(curr_list[turn][x]) == 0:
		curr_list[turn].pop(x)
					
if __name__ == "__main__":
	main()