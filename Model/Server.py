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
MODEL_PATH = Path("Server.weights.h5")
minimumInteractionConfidence = 0.0001  # trying something lower than 0.01
confidenceDelta = 0.001
map_length = 40  # Left to right
map_height = 15  # Top to bottom
# ————— END CONFIG ————— #

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
#region Selections
class Selection_Object:
	'''
	Class that holds the selection information
	'''
	def __init__(self, size, objects, root_position=None):
		self.name = ""# This is whatever "name" this selection (tile) will be called
		self.strength = 0 # this is how much the user likes this selection. high is good, low is bad
		self.size = tuple(size) # (x,y)
		self.objects = objects # the list of "objects" or "actions" that when done will create the selection
		self.root_position = tuple(root_position) if root_position is not None else None # the position of the BOTTOM LEFT CORNER of the slection, with (x,y) also from the bottom left

	def __eq__(self, other):
		if not isinstance(other, Selection_Object):
			return False
		return self.size == other.size and self.objects == other.objects

	def __hash__(self):
		return hash(self.objects)

	def __repr__(self):
		return f"Selection({self.name}, size={self.size}, strength={self.strength}, root={self.root_position}) (bottom left corner)"
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
def server_process_godot_selection(selection_data, selection_cache, objects_data, fg_data, bg_data):
	'''
	selection_data is a list of dicts in the format:
	List<{'position': [x, y], # THE TOP LEFT OF THE SELECTION, BUT THE GIVEN POSITION IS RELATIVE TO 0,0 BEING THE BOTTOM LEFT CORNER
	      'positive': bool,
	       'size': [width, height]}

	Each selection is turned into a Selection_Object and saved in selection_cache
	'''
	# if we ever just don't send selection data, we will return the old selection_cache
	if not selection_data:
		return selection_cache

	for selection_info in selection_data:
		# obtain the selection and process it intop the custom class
		selection, sign = obtain_selection(selection_info, objects_data, fg_data, bg_data)

		# Check to see if this selection is already present within our cache
		found_in_cache = False
		for select in selection_cache:
			if select == selection:
				#TODO we may also wanna consider resetting the strength if the sign flips
				# so if its a negative selection and we set it positive, we now treat it as positive
				select.strength += sign
				found_in_cache = True
				break

		if not found_in_cache:
			selection.strength = sign
			selection_cache.append(selection)
	return selection_cache
def obtain_selection(selection_info, objects_data, fg_data, bg_data):
	'''
	Builds a Selection_Object

	root position of the selection is the BOTTOM LEFT CORNER, RELATIVE TO 0,0 BEING THE BOTTOM LEFT CORNER
	# (this is how other objects are stored in our data set)
	'''

	# Store all our variables
	sel_x, sel_y = selection_info["position"]
	width, height = selection_info["size"]
	sign = 1 if selection_info["positive"] else -1
	map_height = len(fg_data[0])
	grid_x = sel_x
	grid_y = (map_height - 1) - sel_y

	# Collect the index of every object inside the selection (fg and bg)
	object_indexes = set()
	# Watch for empty stuff that we selected
	empty_coords = []
	for dx in range(width):
		for dy in range(height):
			x = grid_x + dx
			y = grid_y + dy
			# edge check
			if x < 0 or x >= len(fg_data) or y < 0 or y >= len(fg_data[x]):
				continue

			# get the object
			found = {fg_data[x][y], bg_data[x][y]} - {-1}

			# either add it as empty or not
			if found:
				object_indexes |= found
			else:
				# nothing in fg or bg, so this cell is EMPTY
				empty_coords.append([dx, height - 1 - dy])

	# The root is the bottom left cell (sel_y is the top row, so go down height - 1)
	root_x = sel_x
	root_y = sel_y - height + 1

	objects = []
	for index in object_indexes:
		if 0 <= index < len(objects_data) and objects_data[index].get("name"):
			obj = objects_data[index]
			objects.append({"coords": [obj["coords"][0] - root_x, obj["coords"][1] - root_y],
							"layer": obj["layer"],
							"name": obj["name"]})
	# EMPTY gets added at the end
	for coords in empty_coords:
		objects.append({"coords": coords, "layer": "fg", "name": "EMPTY"})

	return Selection_Object((width, height), objects, (root_x, root_y)), sign
### NEGATIVE SELECTIONS
def would_complete_negative(name, layer, x, y_bottom, world, negatives):
	'''
	True if placing a tile with name "name" would complete any negative selection,
	if so, we wanna stop that action from happening

	NOTE, WE ARE REFERENCE FROM THE BOTTOM
	'''
	layer = layer.lower()
	for sel in negatives:
		pieces = [(o["name"], o["layer"].lower(), o["coords"][0], o["coords"][1]) for o in sel.objects]
		for (pname, player, dx, dy) in pieces:
			if pname != name or player != layer:
				continue
			# if this placement is that piece, the selection's bottom left would be here
			ox, oy = x - dx, y_bottom - dy
			if all((n, l, ox + px, oy + py) in world
				   for (n, l, px, py) in pieces
				   if not (n == name and l == layer and px == dx and py == dy)):
				return True
	return False
#endregion

#region Data processing
def server_process_godot_data(fg_data, bg_data, objects_data, start_x, allNames, map_width:int =40, map_height:int=15):
	'''
	fg_data: 2D list of either -1 or the index of the object in objects_data (0,0) is the top left
	bg_data: 2D list of either -1 or the index of the object in objects_data (0,0) is the top left
	objects_data: list of dicts, each dict has keys "coords", "layer", and "name"
	start_x: the x coord which will be used to offset the x values of the objects in objects_data
	allNames: List of all of the names of objects that can be in the level.

	THIS IS INDEXED FROM THE TOP LEFT CORNER
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
	The cache that is sent on the very first send of data, we will cache for use throughout the rest of the application

	ALSO TOP LEFT INDEX ORIGIN
	'''

	# For now its just object sizes (since some stuff like pipes are 2x2)
	object_sizes = {}
	for name in cache_data:
		size = cache_data[name] # this is a string in format "(width,height)"
		size = size.strip("()").split(",")
		object_sizes[name] = [int(size[0]), int(size[1])]
	return object_sizes
def GetEmptyMap(allNames, map_window_length:int = 40, map_window_height:int = 15):
	emptyMap = []
	for x in range(0, map_window_length):
		column = []
		for y in range(0, map_window_height):
			column.append([0] * len(allNames))
		emptyMap.append(column)
	return emptyMap
#endregion

#region Action Masking and Tile Placement
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


#region Model Creation & Server Setup
def server_build_model(learning_rate=0.0005, conv_filters=(4, 8, 16), kernel_sizes=(4, 3, 3), activation='leaky_relu'):
	#networkInput = tflearn.input_data(shape=[None, 40, 15, len(allNames)])
	network_inputs = layers.Input(shape=(40,15,len(allNames)))
	conv = network_inputs
	for filters, kernel in zip(conv_filters, kernel_sizes):
		conv = layers.Conv2D(filters=filters, kernel_size=kernel, activation=activation)(conv)
	flatten_layer = layers.Flatten()(conv)
	fc = layers.Dense(40 * 15 * len(actions), activation=activation)(flatten_layer) #TODO: trying to remove the activation from this
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
#endregion
def init_server(config: ServerConfig):
	print("————— Starting Server Connection —————")

	# Wait for the server connection
	print(f"[Server] Listening on {config.TCP_IP}:{config.TCP_PORT}")
	print(f"[Server] Waiting for connection from Godot.")
	conn, addr = socket.accept()
	print(f"[Server] Connected {addr}. Thanks Godot! :)")

	return conn, addr

def server_connection_handler(config: ServerConfig, socket, model, minimumInteractionConfidence, confidenceDelta ):
	conn, addr = init_server(config)

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

	while 1:
		if attempt_server_receive(conn, model, minimumInteractionConfidence, confidenceDelta, prevMap, prevAction, prevStartX, rejections, object_sizes, object_layers, selection_cache) == False:
			break

def attempt_server_receive(conn, model, minimumInteractionConfidence, confidenceDelta, prevMap, prevAction, prevStartX: int, rejections: list, object_sizes: dict, object_layers: dict, selection_cache: list) -> bool | None:
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
			if "selections" in data:
				selection_cache = server_process_godot_selection(data["selections"], selection_cache, objects_data, fg_data, bg_data)
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
			negatives = [s for s in selection_cache if s.strength < 0]
			world = {(o["name"], o["layer"].lower(), o["coords"][0], o["coords"][1])
					 for o in objects_data if o.get("name") and "layer" in o and "coords" in o}
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

								# NEW: batch-aware negative selection check
								y_bottom = (map_height - 1) - y  # grid y (from the top) -> y from the bottom
								layer = object_layers[actions[z]]
								if negatives and would_complete_negative(actions[z], layer, x + thisStartX, y_bottom, world, negatives):
									continue  # this would finish a negative shape, skip it
								world.add((actions[z], layer.lower(), x + thisStartX,y_bottom))  # later suggestions in this batch see it
								# fill our local grid so we dont try to play ontop of it later
								server_fill_placement(fill_grid, placed_grid)
								# END ACTION MASKING INCLUSION ————————————————————————————————

								sents.append([x, y, z])
								print("SENDING: " + str([actions[z], x + thisStartX, y, predY[0][x][y][z]]))
								rejections.append([actions[z], x + thisStartX, y])
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
			prevMap = list(currMap)
			prevAction = list(thisAction)
			prevStartX = thisStartX
		#conn, addr = socket.accept()  # Reset (i dont think we actually want to do this? NOPE we dont lol)
			return True
	except ConnectionError as e:
		print(f"[Server] Connection error: {e}. CLosing Connection")
		conn.close()
		del conn
		return False
	except KeyboardInterrupt:
		conn.close()
		del conn
		return False
	
	return None



def main():
	config = ServerConfig()
	model = server_create_model(force_retrain=False)
	socket = server_create_socket(config)
	server_connection_handler(config=config, socket=socket, model=model, minimumInteractionConfidence=minimumInteractionConfidence, confidenceDelta=confidenceDelta)


if __name__ == "__main__":
	main()
