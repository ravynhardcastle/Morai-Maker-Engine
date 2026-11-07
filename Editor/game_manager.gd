extends Node

const PORT: int = 8009
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
	var connection: int = server.connect_to_host("localhost", PORT)
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
		
func send_state(objects_list: Array[Dictionary], occupied_fg_grid: Array[Array], occupied_bg_grid: Array[Array]) -> void: # info in tile_map.gd
	# We need to convert the Vector2i's to arrays or else they'll just send as strings
	var objects: Array
	for object in objects_list:
		var clone: Dictionary = object.duplicate()
		var coords: Vector2i = clone[&"Coords"]
		clone[&"Coords"] = [coords.x, coords.y]
		objects.append(clone)

	var data: Dictionary = {"objects": objects, "fg": occupied_fg_grid, "bg": occupied_bg_grid}
	var json: String = JSON.stringify(data)
	var bytes: PackedByteArray = json.to_utf8_buffer()
	
	# If our status is messed up, save what we have rn into pending
	if server.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		pending = [objects_list, occupied_fg_grid, occupied_bg_grid]
		return
	
	server.big_endian = true
	server.put_u32(bytes.size())
	server.put_data(bytes)
	server.get_data(RECEIVE_BYTES) # TODO: Do something with this