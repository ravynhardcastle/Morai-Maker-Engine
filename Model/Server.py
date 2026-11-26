#!/usr/bin/env python
# scp ./testserver.py eilab@morrible.cc.gt.atl.ga.us:./Desktop/UserStudyResults/testserver.py



# ————— IMPORTS ————— #
import json
import socket, csv, time, struct
from dataclasses import dataclass
import numpy as np
from pathlib import Path
import tensorflow as tf
# Old version, we are updating to a new version
#from tflearn import conv_2d, max_pool_2d, local_response_normalization, batch_normalization, fully_connected, regression, input_data, dropout, custom_layer, flatten, reshape, embedding,conv_2d_transpose
# New imports, swapping to tensorflow keras
from tensorflow.keras import layers, models, optimizers #NGL these are shown as errors despite working so.. I just ignore that
# Personal File Imports
from tile_config import allNames, actions
# ————— END IMPORTS ————— #

# ————— CONFIG ————— #
@dataclass
class ServerConfig:
	TCP_IP: str = '127.0.0.1' #localhost' (yeah this could stay local host, im just hard coding this for now)
	TCP_PORT: int = 8039

# ————— END CONFIG ————— #

# ————— Old Implementation ————— #
# region Old Implementation
def GetEmptyMap(allNames):
	emptyMap = []
	for x in range(0, 40):
		column = []
		for y in range(0, 15):
			column.append([0] * len(allNames))
		emptyMap.append(column)
	return emptyMap
def FlattenMap(mapInput, allNames):
	flatMap = []
	for y in range(0, 15):
		for x in range(0, 40):
			for z in range(0, len(allNames)):
				flatMap.append(mapInput[x][y][z])
	return flatMap
def UnflattenMap(mapInput, allNames):
	emptyMap = GetEmptyMap(allNames)
	for x in range(0, 40):
		for y in range(0, 15):
			for z in range(0, len(allNames)):
				emptyMap[x][y][z] = mapInput[y * 40 * len(allNames) + x * len(allNames) + z]
	return emptyMap
def StringToList(strVal):
	listVal = []
	for s in strVal:
		listVal.append(int(s))
	return listVal
def StringToMap(strVal, allNames):
	emptyMap = GetEmptyMap(allNames)
	splits1 = strVal.split("-")
	for s1 in splits1:
		if len(s1) > 0:
			splits2 = s1.split("*")
			emptyMap[int(splits2[0])][int(splits2[1])][int(splits2[2])] = 1
	return emptyMap
# In this 8 by 8 localized on the added point find what prompted it
# shape=(4, 4, 34, 8)
def GetExplanation(weights, mapVal, x, y, allNames):
	maxPatch = [0, 0]
	maxVal = -5
	for xi in range(-4 + x, x):
		for yi in range(-4 + y, y):
			thisPatchMax = -5
			bestfilter = -1
			for j in range(0, 8):
				thisScore = 0
				for xj in range(xi, xi + 4):
					for yj in range(yi, yi + 4):
						if xj >= 0 and xj < 40 and yj >= 0 and yj < 15:
							for z in range(0, 34):
								try:
									thisScore += float((weights[xj - xi][yj - yi][z][j] * mapVal[xj][yj][z]))
								except IndexError:
									thisScore += 0
				if thisScore > thisPatchMax:
					thisPatchMax = thisScore
					bestfilter = j
			if thisPatchMax > maxVal:
				maxPatch = [xi, yi, bestfilter]
				maxVal = thisPatchMax
	buildString = "" + str([maxPatch[0] - x, maxPatch[1] - y, maxVal, "filter: " + str(maxPatch[2])]) + "\n"
	for y in range(maxPatch[1] + 3, maxPatch[1] - 1, -1):
		line = ""
		for x in range(maxPatch[0], maxPatch[0] + 4):
			if x >= 0 and x < 40 and y >= 0 and y < 15:
				if 1 in mapVal[x][y]:
					line += (allNames[mapVal[x][y].index(1)]) + "-"
				else:
					line += " -"
			else:
				line += "0-"
		buildString += line + "\n"
	return buildString
#endregion
# ————— END Old Implementation ————— #



# ————— Networking Functions ————— #
# region Networking Functions
# Used to receive information from the Godot client.
def server_receive(bytes, conn):  # This is for the 4 bytes that tell us how many bytes we're about to receive
	buffer = b""
	while len(buffer) < bytes:
		data = conn.recv(bytes - len(buffer))
		# adding a check to make sure we dont et stuck if the client disconnects
		if not data:
			raise ConnectionError("Connection closed by the client.")
		buffer += data
	return buffer
# Used to send information to the Godot client.
def server_send(data: dict, connection):
	'''
	This is setup to send some dict of data to the client, referencing Godot code
	'''
	print(f"[Server] Sending data to Godot: {data}")
	print("[Server] ——————————————————————————————")
	json_str = json.dumps(data)
	bytes = json_str.encode('utf-8')
	prefix = struct.pack(">I", len(bytes))
	connection.sendall(prefix + bytes)
#endregion
# ————— END Networking Functions ————— #


# ————— New Implementation ————— #
#region New Implementation

# Creating a new class to hold a selection.. since I think itll end up being easier to work with later?
class Selection_Object:
	'''
	Class that will be treated like a "siongle tile" in regards to the RL pipeline, and will be use as an "option"
	'''
	def __init__(self, size, objects):
		self.name = ""# This is whatever "name" this selection (tile) will be called
		self.strength = 0 # this is how much the user likes this selection. high is good, low is bad
		self.size = tuple(size) # (x,y)
		self.objects = objects # the list of "objects" or "actions" that when done will create the selection

	def __eq__(self, other):
		if not isinstance(other, Selection_Object):
			return False
		return self.size == other.size and self.objects == other.objects

	def __hash__(self):
		return hash(self.objects)

	def __repr__(self):
		return f"Selection({self.name}, size={self.size}, strength={self.strength})"

	def get_object_actions(self, origin_x, origin_y):
		'''
		if given a starting point, this will provide all the "objects" or "actions" that will rebuild the selection
		'''
		object_actions = []
		for object in self.objects:
			# construct an "object" in the same syntax the RL agent will expect
			object_actions.append({"coords": [origin_x + object["coords"][0], origin_y + object["coords"][1]],
							   "layer": object["layer"],
							   "name": object["name"]})
		return object_actions


def server_process_godot_data(fg_data, bg_data, objects_data, start_x, allNames, map_width:int =40, map_height:int=15):
	'''
	This will convert the dict data provided by Godot into Tensors that can be used within the network
	PARAMS:
	fg_data: 2D list of either -1 or the index of the object in objects_data
	bg_data: 2D list of either -1 or the index of the object in objects_data
	objects_data: list of dicts, each dict has keys "coords", "layer", and "name"
	start_x: the x coord which will be used to offset the x values of the objects in objects_data
	allNames: List of all of the names of objects that can be in the level.
	'''
	# Create the tensor of our data.
	map = np.zeros((map_width, map_height, len(allNames)), dtype=np.float32)
	# process the objects by connecting them to objects within the allNames list
	#TODO: Its important to ensure that allNames actually contains all the objects that are within our data
	objects = []
	for object in objects_data:
		# This name SHOULD be in this list
		if object.get("name") in allNames:
			objects.append(allNames.index(object["name"]))
		else:
			# cause -1 means nothing is there
			objects.append(-1)
	# Process the Background
	for x in range(map_width):
		# Consider the offset
		true_x = x + start_x
		# Ensure we are within bounds of the level
		if true_x < 0 or true_x >= len(bg_data):
			continue
		for y in range(map_height):
			if y >= len(bg_data[true_x]):
				continue
			# its valid if its not -1
			value = bg_data[true_x][y]
			# Ensure its non-negative, and within the bounds
			if value >=0 and value < len(objects) and objects[value] >= 0:
				map[x][y][objects[value]] = 1.0

	# run it back for the foregrond
	for x in range(map_width):
		# Consider the offset
		true_x = x + start_x
		# Ensure we are within bounds of the level
		if true_x < 0 or true_x >= len(fg_data):
			continue
		for y in range(map_height):
			if y >= len(fg_data[true_x]):
				continue
			# its valid if its not -1
			value = fg_data[true_x][y]
			# Ensure its non-negative, and within the bounds of objects (value is an index into objects_data)
			if value >=0 and value < len(objects) and objects[value] >= 0:
				map[x][y][objects[value]] = 1.0
	# so this should be a tensor where we have x,y value, and at that x,y value we have the index of the object that is there
	# or 0 if nothing is there
	return map
def server_process_godot_cache(cache_data):
	'''
	The cache thats sent on the very first send of data, we will cache for use throughout the rest of the application
	'''

	# For now its just object sizes (since some stuff like pipes are 2x2)
	object_sizes = {}
	for name in cache_data:
		size = cache_data[name] # this is a string in format "(width,height)"
		size = size.strip("()").split(",")
		object_sizes[name] = [int(size[0]), int(size[1])]
	return object_sizes
def server_process_godot_selection(selection_data, selection_cache, objects_data, fg_data, bg_data):
	'''
	This is the primary mask that is used with the "explicit" learning.
	it will be a List2D<> with the following possible values
	-1 = negative selection, the user has specified this is NOT something that they want
	0 = neutral, this is a basic selection
	1 = positive selection, the user has sp[ecified this is something they want to see more of

	for -1 and 1 selections, the following process will be done
	0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
	0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
	0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
	0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 -1 -1 -1 -1 0 0 0 0
	0 1 1 0 0 0 0 0 0 0 0 1 1 1 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 0
	0 1 1 0 0 0 0 0 0 0 0 1 1 1 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 0
	0 1 1 0 0 0 0 0 0 0 0 1 1 1 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 0

	we will look through this, and when we reach a 1 (or -1) we will then scan horizontally untill we reach a 0
	and then we will return to the original starting x, go down in y, and then keep scanning,
	we will do this will we reach no ones 1s. this will mark a "selection"
	we will then treat that as a tile, so we will provide it a name ("selection_01"), and mark its size.
	we will check out cache of selections, and if this selection is not in the cache, we will add it to the cache,
	if its already in the cache, we will increment its "strength by either: 1 or -1 depending on if it was a positive or negative selection.

	For example the above example (assuming the two 2x3 are the same items) would create 3 entries into our cache
	selection_01, size: (2, 3), strength: 2
	selection_02, size: (3, 3), strength: 1
	selection_03, size: (4, 1), strength: -1
	'''
	# Create a copy, so we can track locations we have visited
	visited = [column[:] for column in selection_data]
	# if we ever just don't send selection data, we will return the old selection_cache
	if len(selection_data) == 0:
		return selection_cache
	map_width = len(selection_data)
	map_height = len(selection_data[0])
	for x in range(map_width):
		for y in range(map_height):
			# Check to see if we have already visited this location
			current_cell = selection_data[x][y]
			if visited[x][y] == 'V':
				continue
			# Now we check to see if its a selection
			if current_cell == 0:
				# Mark as visited and continue
				visited[x][y] = 'V'
				continue

			# If we reach this point, we have hit either 1 or -1. we need to process the selection
			selection, sign = obtain_selection(selected_data=selection_data, objects_data=objects_data, fg_data=fg_data, bg_data=bg_data, visited=visited, initial_x=x, initial_y=y)


			# Check to see if this selection is already present within our cache
			found_in_cache = False
			for select in selection_cache:
				if select == selection:
					# if its already present, we want to update the "strength"
					# we may also wanna consider like... if we add a negative selection should that just instantly reset it?
					# like if a +10 gets a negative so we reset to -1, or a -10 gets a possitive do we reset to 1?
					select.strength += sign
					found_in_cache = True
					break

			if not found_in_cache:
				selection.strength = sign
				selection_cache.append(selection)

			# Mark this cell as visited
			visited[x][y] = 'V'

	return selection_cache
def obtain_selection(selected_data, objects_data, fg_data, bg_data, visited, initial_x, initial_y):
	'''
	THERE IS A POTENTIAL ISSUE IF TWO SELECTIONS ARE TOUCHING
	THIS WILL NEED TO BE UPDATED, SINCE RIGHT NOW I AM MAKING ALOT OF ASSUMPTIONS!!!
	'''
	# Since we know this is called from the start of a selection, we can just grab if its a 1 or -1
	sign = selected_data[initial_x][initial_y]
	map_width = len(selected_data)
	map_height = len(selected_data[0])

	# Loop through the selection_data, starting from the initial_x and initial_y, and find the bounds of the selection
	#TODO: Recall, this has a issue if two selections are right beside each other!!!
	width = 0
	while initial_x + width < map_width and visited[initial_x + width][initial_y] == sign:
		width += 1

	# Do the same for the height
	height = 1
	while initial_y + height < map_height and all(visited[initial_x + dx][initial_y + height] == sign for dx in range(width)):
		height += 1

	# Now that we know the bounds, go through every cell of the selection
	# we treat 0,0 as the top left corner of this selection
	object_indexes = set()
	empty_coords = set()
	for dx in range(width):
		for dy in range(height):
			# Mark as visited
			visited[initial_x + dx][initial_y + dy] = 'V'
			# loop through both the fg and bg
			for grid in (fg_data, bg_data):
				val = grid[initial_x + dx][initial_y + dy]
				if val != -1:
					object_indexes.add(val)
				# later we will handle air blocks

	objects = []
	for index in object_indexes:
		#TODO: Th
		if index >= 0 and index < len(objects_data) and objects_data[index].get("name"):
			obj = objects_data[index]
			objects.append({"coords": [obj["coords"][0] - initial_x, obj["coords"][1] - initial_y],
							"layer": obj["layer"],
							"name": obj["name"]})
	# create a new object
	return Selection_Object((width, height), objects), sign


def server_check_tile_placement(tile, pos, occupied_grid, object_sizes):
	# pretty much the copy from the Godot implementation + adding a bounds check
	# Get the size of the tile we are trying to check
	selected_size = object_sizes[tile]
	fill_grid = []
	for x in range(selected_size[0]):
		for y in range(selected_size[1]):
			fill_grid.append((pos[0] + x, pos[1] - y))
			# Out of bounds check to make sure the placement doesnt go.. well.. out of bounds
			if pos[0] + x < 0 or pos[0] + x >= len(occupied_grid) or pos[1] - y < 0 or pos[1] - y >= len(occupied_grid[pos[0] + x]):
				return None
			# if we hit anything other than a "-1", then we know this is trying to place overtop of another object
			if occupied_grid[pos[0] + x][pos[1] - y] != -1:
				return None

	# if we successfully return this, we have a List<(x,y)> of all the positions that this tile would occupy
	return fill_grid
def server_fill_placement(fill_grid, occupied_grid):
	for cell in fill_grid:
		occupied_grid[cell[0]][cell[1]] = 0 # just not -1, to show SOMETHING is here

def server_get_action_mask(fg_grid, bg_grid, object_sizes, object_layers, start_x, actions, map_width:int=40, map_height:int=15):

	mask = np.zeros((map_width, map_height, len(actions)), dtype=bool)
	for x in range(map_width):
		for y in range(map_height):
			for z in range(len(actions)):
				tile = actions[z]
				if tile not in object_sizes or tile not in object_layers:
					continue # safe guard against.. well weird cases
				fg = object_layers[tile] == "fg"
				occupied_grid = fg_grid if fg else bg_grid
				mask[x][y][z] = server_check_tile_placement(tile, (x + start_x, y), occupied_grid, object_sizes) is not None
	return mask
#endregion
# ————— END New Implementation ————— #
# BETTER MODEL BUILDING THAT CAN TAKE IN PARAMS FOR TUNING
MODEL_PATH = Path("Server.weights.h5")
def server_build_model(learning_rate=0.0005, conv_filters=(4, 8, 16), kernel_sizes=(4, 3, 3), activation='relu'):
	#networkInput = tflearn.input_data(shape=[None, 40, 15, len(allNames)])
	network_inputs = layers.Input(shape=(40,15,len(allNames)))
	conv = network_inputs
	for filters, kernel in zip(conv_filters, kernel_sizes):
		conv = layers.Conv2D(filters=filters, kernel_size=kernel, activation=activation)(conv)
	flatten_layer = layers.Flatten()(conv)
	fc = layers.Dense(40 * 15 * len(actions), activation=activation)(flatten_layer)
	network_output = layers.Reshape((40, 15, len(actions)))(fc)
	model = models.Model(inputs=network_inputs, outputs=network_output)
	model.compile(
		optimizer=optimizers.Adam(learning_rate=learning_rate),
		loss='mean_squared_error',
		metrics=['accuracy']
	)
	return model
def server_create_model(force_retrain: bool = False):
	if(force_retrain):
		print("[Server] Force retrain is set to true. if this is an accident change it in main()")
	model = server_build_model()
	try:
		# try to load the model if we have one
		if MODEL_PATH.exists() and (not force_retrain) :
			print("[Server] We have a pretrained model, loading it.")
			model.load_weights(str(MODEL_PATH))
		else:
			print("[Server] No pretrained model found, training a new one.")
			from Pretraining import pre_training
			pre_training(True) # bool for if we want to force a retrain
			model.load_weights(str(MODEL_PATH))

		print("Model weights loaded")
	except Exception as e:
		print("model weights no failed to load: " + str(e))
	return model
def server_create_socket(config: ServerConfig):
	TCP_IP = config.TCP_IP
	TCP_PORT = config.TCP_PORT

	s = socket.socket()
	s.bind((TCP_IP, TCP_PORT))
	s.listen(1)
	return s
def server_connection_handler(config: ServerConfig, socket, model):
	print("————— Starting Server Connection —————")

	# Wait for the server connection
	print(f"[Server] Listening on {config.TCP_IP}:{config.TCP_PORT}")
	print(f"[Server] Waiting for connection from Godot.")
	conn, addr = socket.accept()
	print(f"[Server] Connected {addr}. Thanks Godot! :)")

	# Initialize variables
	prevMap = None
	prevAction = None
	prevStartX = -1
	rejections = []  # HOLD ON TO ALL REJECTIONS. NEVER ADD AGAIN
	# ————— Caches ————— #
	object_sizes = {} # Initialize the cache
	object_layers = {} # Initialize the cache

	'''
	This is the cache that holds all the selection information for the running application. It is in the following format:
	List<Selection_Object>. Where a Selection 
	'''
	selection_cache = []
	# ————— END Caches ————— #
	# WAIT FOR PROMPT

	minimumInteractionConfidence = 0.0001 # trying something lower than 0.01
	confidenceDelta = 0.001
	map_length = 40  # Left to right
	map_height = 15  # Top to bottom
	while 1:
		try:
			length = struct.unpack(">I", server_receive(4, conn))[0]  # 4 because that's how many bytes we set in godot
			data = json.loads(server_receive(length, conn))
			print(f"Successfully obtained data from Godot! Payload size: {length} bytes")

			# FOR TESTING -----------------------
			# we will send a message back to Godot to inform them we recieved their data
			data_payload = {'msg': "[Server-msg] Data received successfully!"}
			server_send(data_payload, conn)
			# ------------------------------------
			if len(data) > 0:
				# TODO: Data processing to make it fit the old format. This won't work at all, it assumes that our data is one big string
				# but it's a dictionary now
				# print("Data: "+str(data)+", "+str(len(data)))

				# Data that's to be received comes in a dictionary in the following format:
				# Other notes to remember [0,0] is the top left corner of the grid
				'''
				{'bg': [[]], # where this contains a values of either -1 (nothing) or the index of whatever object is in this location, within the 'allNames" list (I assume)
				'fg': [[]], # same as above, but for foreground objects,
				'objects': [{'coords': [x, y],
							 'layer': 'BG' or 'FG',
							 'name': str, # name of the object, which should be in the allNames list
				'camera': int, the x value of the camera, used for its offset.
				'''
				# ————— Extract Data & Prepare Variables ————— #
				bg_data = data["bg"]
				fg_data = data["fg"]
				objects_data = data["objects"]
				# Fill the object_layers "cache" (its not really a cache I know)
				for object in objects_data:
					if "name" in object and "layer" in object:
						object_layers[object["name"]] = object["layer"]
				thisStartX = int(data["camera"]) # jk this is actually called "camera"
				if "cache" in data:
					object_sizes = server_process_godot_cache(data["cache"])
				if "mask" in data:
					selection_cache = server_process_godot_selection(data["mask"], selection_cache, objects_data, fg_data, bg_data)
				if len(selection_cache) > 0:
					print("----- Printing Selection Cache -----")
					print(selection_cache)
					print("------------------------------------")
				# ————— Need to convert everything to tensors ————— #
				currMap = server_process_godot_data(fg_data, bg_data, objects_data, thisStartX, allNames, map_length, map_height)
				# ————— Action Masking ————— #
				# making a copy, since these get modified and I dont wanna mess up the main ones
				fg_grid = [column[:] for column in fg_data]
				bg_grid = [column[:] for column in bg_data]
				actionMask = server_get_action_mask(fg_grid, bg_grid, object_sizes, object_layers, thisStartX, actions, map_length, map_height)
				#currMap = StringToMap(dataSplits[0], allNames)
				# ————— Retrain ————— #
				if not prevMap == None and abs(thisStartX - prevStartX) < 30: # replace 30 with a threshold percentage!
					anyChange = False
					differenceX = thisStartX - prevStartX
					for x in range(0, map_length):
						if x + differenceX < 40 and x + differenceX >= 0:
							for y in range(0, 15):
								for z in range(0, len(actions)):
									if prevAction[x + differenceX][y][z] > 0:
										if currMap[x][y][z] > 0:
											anyChange = True
											prevAction[x + differenceX][y][z] += 0.1
										else:
											anyChange = True
											prevAction[x + differenceX][y][z] -= 0.1

											print("REMOVED: " + str([actions[z], x + thisStartX, y]))
									elif currMap[x][y][z] > 0:
										anyChange = True
										prevAction[x + differenceX][y][z] += 0.1
						# LEARN
					if anyChange:
						minimumInteractionConfidence += confidenceDelta
						print("RETRAIN")
						model.fit(np.array([prevMap]),
								  np.array([prevAction]),
								  epochs=1,
								  shuffle=False,
								  batch_size=1,)

				#predY = model.predict([currMap])
				predY = model.predict(np.array([currMap]))
				thisAction = GetEmptyMap(actions)

				# REPLY
				toString = ""
				nothingSent = True
				maxToSend = []
				maxVal = -1

				sents = []
				for x in range(0, map_length):
					for y in range(0, map_height):
						for z in range(0, len(actions)):
							if predY[0][x][y][z] > minimumInteractionConfidence and currMap[x][y][z] == 0 and len(sents) < 30 and actionMask[x][y][z]:
								if not [actions[z], x + thisStartX, y] in rejections:
									#conn.send(str(x) + "," + str(y) + "," + str(z) + "," + str(predY[0][x][y][z]) + "*") # Commenting out to try a different style

									# ACTION MASKING, MAKE SURE WE NOTE THAT WE ARE CLAIMING SPACE
									# We try to claim the space (if we can)
									placed_grid = fg_grid if object_layers[actions[z]] == "fg" else bg_grid
									fill_grid = server_check_tile_placement(actions[z], (x + thisStartX, y), placed_grid, object_sizes)
									# nah, cant do it
									if fill_grid is None:
										continue
									# fill our local grid so we dont try to play ontop of it later
									server_fill_placement(fill_grid, placed_grid)
									# END ACTION MASKING INCLUSION ————————————————————————————————

									sents.append([x, y, z])
									print("SENDING: " + str([actions[z], x + thisStartX, y, predY[0][x][y][z]]))
									rejections.append([actions[z], x + thisStartX, y])
									# print ("     EXPLANATION: "+GetExplanation(convW, currMap, x, y, allNames))
									thisAction[x][y][z] = predY[0][x][y][z]
									nothingSent = False
							elif nothingSent:
								if predY[0][x][y][z] > maxVal and currMap[x][y][z] == 0 and not z == len(actions) - 1 and actionMask[x][y][z]:
									if not [actions[z], x + thisStartX, y] in rejections:
										maxToSend = [x, y, z, predY[0][x][y][z]]
										maxVal = predY[0][x][y][z]
				# MUST DO SOMETHING
				if nothingSent and len(maxToSend) > 0:
					thisAction[maxToSend[0]][maxToSend[1]][maxToSend[2]] = minimumInteractionConfidence + confidenceDelta
					sents.append([maxToSend[0], maxToSend[1], maxToSend[2]])
					#rejections.append([actions[maxToSend[2]], maxToSend[0] + thisStartX, maxToSend[1]]) # Do we need to do this? im unsure
					#conn.send(str(maxToSend[0]) + "," + str(maxToSend[1]) + "," + str(maxToSend[2]) + "," + str(maxToSend[3]) + "*") # since we are appending,
					# at the above line, we dont need to send this individually
					print("FAILURE CASE: " + str([actions[maxToSend[2]], maxToSend[0], maxToSend[1], maxToSend[3]]))

				# SLight change in format, all suggestions are gonna be sent at the very end!
				# the format being chosen is:
				'''
				"coords" : (int, int), (x,y), the coordinates of the suggestion
				"name" : str, the name of the suggestion (from allNames / cache. w/e we end up sticking with)
				"size" : (int, int), (width, height), the size of the tile from the cache... we prolly dont need to send this but yeah
				"confidence" : float, the confidence of the suggestion, from the model
				'''
				server_suggestions = []
				for sent in sents:
					server_suggestions.append({
						"coords": (sent[0] + thisStartX, sent[1]),
						"name": actions[sent[2]],
						"size": object_sizes.get(actions[sent[2]]),  # default size is 1x1 if not found in cache
						"confidence": float(predY[0][sent[0]][sent[1]][sent[2]])
					})

				# Yippie, time to send to Godot!
				server_send({"suggestions": server_suggestions}, conn)

				#conn.close()  # Close (idk if I wanna close right here LOL no we dont)

				# PRINT MAP
				'''
				currMapStr = ""
				for y in range(14, -1, -1):
					line = ""
					for x in range(0, 40):
						if 1 in currMap[x][y]:
							line+= allNames[currMap[x][y].index(1)]+"-"
						else:
							line+="      -"
					currMapStr+=line+"\n"
				print (currMapStr)
				'''
				# EXPLANATIONS (commented out for now)
				'''
				convW = np.array(model.get_weights(conv.W))
				for sent in sents:
					print("---")
					print("FOR SENT: " + str([actions[sent[2]], sent[0], sent[1], predY[0][sent[0]][sent[1]][sent[2]]]))
					if 1 in currMap[sent[0]][sent[1]]:
						# WHY IS THIS NOT HIT????
						print("IN CURR MAP: " + str(allNames[currMap[sent[0]][sent[1]].index(1)]))
					print("EXPLAIN:\n" + GetExplanation(convW, currMap, sent[0], sent[1], allNames))
				'''

				prevMap = list(currMap)
				prevAction = list(thisAction)
				prevStartX = thisStartX
				#conn, addr = socket.accept()  # Reset (i dont think we actually want to do this? NOPE we dont lol)
		except ConnectionError as e:
			print(f"[Server] Connection error: {e}. CLosing Connection")
			conn.close()
			del conn
			break
		except KeyboardInterrupt:
			conn.close()
			del conn
			break


def main():
	config = ServerConfig()
	model = server_create_model(force_retrain=True)
	socket = server_create_socket(config)
	server_connection_handler(config=config, socket=socket, model=model)


if __name__ == "__main__":
	main()
