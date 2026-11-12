extends Node
const TCP_IP: String = "127.0.0.1"
const PORT: int = 8039
const RECEIVE_BYTES: int = 0
var server: StreamPeerTCP
var pending: Array
var last_status: int = StreamPeerTCP.STATUS_NONE
var bHasSentCache:bool = false

var object_sizes: Dictionary[StringName, Vector2i] # Object size by RL name

var selected_tile: EditorTile:
	set(new_tile):
		if selected_tile:
			selected_tile.selected = false
		if new_tile:
			new_tile.selected = true
		selected_tile = new_tile
		
func _ready() -> void:
	server = StreamPeerTCP.new()
	#var connection: int = server.connect_to_host("localhost", PORT) # this defaults to an IPV6 address, which im not sure if we wanna use? commenting out for now
	var connection: int = server.connect_to_host(TCP_IP, PORT)
	print(connection)
	print(server.get_connected_host())
	print(server.get_connected_port())
	server.set_no_delay(true)
	
func _process(_delta: float) -> void:
	server.poll()
	var status := server.get_status()
	# If it's not connected yet, wait, and once it gets connected, send whatever didnt get sent earlier
	if status != last_status:
		last_status = status
		if status == StreamPeerTCP.STATUS_CONNECTED and !pending.is_empty():
			send_state.callv(pending)
			pending.clear()

	
	# —————————————————————————————————————————————————————————————————————
	# ————— Division for where the Godot will be listening for data ————— #
	# Ensure we are still connected to the server
	if (not StreamPeerTCP.STATUS_CONNECTED): return
	# attempt to recieve bytes from the server
	if (not server.get_available_bytes()): return
	# Get the lengto of the packet we recieved 
	var packet_length := server.get_u32()
	var res := server.get_data(packet_length)
	# check for the code of the recieved data
	if (not res[0] == OK): return
	# By this point, we know we have recieved valid data. lets read it
	var json_string = res[1].get_string_from_utf8()
	var data = JSON.parse_string(json_string)
	if (data is Dictionary):
		# For now im just looking for my 'msg' key, as thats all im sending LOL
		var msg = data.get("msg")
		if (msg): print(msg)
		
		var suggestions = data.get("suggestions")
		if (suggestions): _on_receive_suggestion(suggestions)
	else:
		print("[Client] Failed to read server sent data")
		
	# —————————————————————————————————————————————————————————————————————
	
	

func _on_receive_suggestion(suggestion: Array) -> void:
	# YIPPIE here you go!
	# this SHOULD be called with the following:
	'''
	a List<Dict<>> where:
		"coords" : (int, int), (x,y), the coordinates of the suggestion
		"name" : str, the name of the suggestion (from allNames / cache. w/e we end up sticking with)
		"size" : (int, int), (width, height), the size of the tile from the cache... we prolly dont need to send this but yeah
	'''
	# is it fully correct... I was tired and didnt test everything, but for now lets just assume working untill proven otherwise ( ͡° ͜ʖ ͡°)
	# if its helpful, I was thinking this could also send if its a fg or bg suggestion, just to make that very obvious
	print("[Client] We received a suggestion from the server")
	print(suggestion)
	print("——————————————————————————————————————————————————")
	

		
func send_state(objects_list: Array[Dictionary], occupied_fg_grid: Array[Array], occupied_bg_grid: Array[Array], camera_position: int) -> void: # info in tile_map.gd
	print("Sending game state to python server for calculation")
	# We need to convert the Vector2i's to arrays or else they'll just send as strings
	var objects: Array
	for object in objects_list:
		var clone: Dictionary = object.duplicate()
		clone[&"coords"] = [-1, -1]
		if object.has(&"coords"):
			var coords: Vector2i = object[&"coords"]
			clone[&"coords"] = [coords.x, coords.y]
		objects.append(clone)

	# —————————————————————————————————————————————————————————————————————
	# ————— Ensure that we only send the cache information once ————— #
	# Yeah I know there is a better way to do this, but this is what im doing LOL
	var data: Dictionary = {}
	if (not bHasSentCache):
		data = {"objects": objects, "fg": occupied_fg_grid, "bg": occupied_bg_grid, "camera": camera_position, "cache": object_sizes}
		bHasSentCache = true
	else:
		data = {"objects": objects, "fg": occupied_fg_grid, "bg": occupied_bg_grid, "camera": camera_position}
	# —————————————————————————————————————————————————————————————————————
	var json: String = JSON.stringify(data)
	var bytes: PackedByteArray = json.to_utf8_buffer()
	
	# If our status is messed up, save what we have rn into pending
	if server.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		pending = [objects_list, occupied_fg_grid, occupied_bg_grid, camera_position]
		return
	
	server.big_endian = true
	server.put_u32(bytes.size())
	server.put_data(bytes)
	server.get_data(RECEIVE_BYTES) # TODO: Do something with this
