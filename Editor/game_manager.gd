extends Node
const TCP_IP: String = "127.0.0.1"
const PORT: int = 8039
const RECEIVE_BYTES: int = 0
var server: StreamPeerTCP
var pending: Array
var last_status: int = StreamPeerTCP.STATUS_NONE

var selected_tile: EditorTile:
	set(new_tile):
		if selected_tile:
			selected_tile.selected = false
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
	else:
		print("[Client] Failed to read server sent data")
		
	# —————————————————————————————————————————————————————————————————————
	
	


		
func send_state(objects_list: Array[Dictionary], occupied_fg_grid: Array[Array], occupied_bg_grid: Array[Array], camera_position: int) -> void: # info in tile_map.gd
	print("Sending game state to python server for calculation")
	# We need to convert the Vector2i's to arrays or else they'll just send as strings
	var objects: Array
	for object in objects_list:
		var clone: Dictionary = object.duplicate()
		var coords: Vector2i = clone[&"coords"]
		clone[&"coords"] = [coords.x, coords.y]
		objects.append(clone)

	var data: Dictionary = {"objects": objects, "fg": occupied_fg_grid, "bg": occupied_bg_grid, "camera": camera_position}
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
