extends Node2D

@export var layers: Array[TileMapLayer]
@export var camera: Camera2D
@export var grid: Node2D
@export var camera_move_speed: float
@export var camera_selection_sprite: Sprite2D
@export var shadow_viewport: SubViewport
@export var shadow_rect: ColorRect
@onready var fg_layer:TileMapLayer = layers[layers.find_custom(func(layer): return layer.name == "ForegroundLayer")]
@onready var bg_layer:TileMapLayer = layers[layers.find_custom(func(layer): return layer.name == "BackgroundLayer")]
@onready var grid_size: Vector2 = fg_layer.get_used_rect().size
@onready var tile_size: int = fg_layer.tile_set.tile_size.x
var objects_list: Array[Dictionary] # of which the dictionary contains Name: Name, Coords: Vector2i and Layer: FG or Layer: BG
var occupied_fg_grid: Array[Array] # Each array contains an int that is just the index of the thing in the objects list
var occupied_bg_grid: Array[Array]
var scene_info_cache: Dictionary # Dictionary[PackedScene, {size: Vector2i, name: StringName}]

func _ready() -> void:
	shadow_viewport.world_2d = get_viewport().world_2d
	shadow_rect.material.set_shader_parameter("caster_texture", shadow_viewport.get_texture())
	RenderingServer.frame_pre_draw.connect(_sync_shadow_transform)
	generate_map()

func _process(delta: float) -> void:
	var max_x: float = get_viewport().get_visible_rect().size.x
	var ratio: float = get_viewport().get_mouse_position().x / max_x
	if get_viewport().get_mouse_position().y == clamp(get_viewport().get_mouse_position().y, 0, get_viewport().get_visible_rect().size.y):
		if ratio > camera.drag_right_margin:
			var ratio_above: float = clamp(1 - (1.0 - ratio) * (1 / (1 - camera.drag_right_margin)), 0, 1)
			if ratio_above >= 1: ratio_above = 2 # double move speed at max
			camera.move_local_x(camera_move_speed * delta * ratio_above)
		if ratio < 1 - camera.drag_left_margin:
			var ratio_below: float = clamp(1 - (ratio * (1 / (1 - camera.drag_left_margin))), 0, 1)
			if ratio_below >= 1: ratio_below = 2 # double move speed at max
			camera.move_local_x(-camera_move_speed * delta * ratio_below)
		camera.position = clamp(camera.position, Vector2(camera.limit_left, camera.limit_top), Vector2((camera.limit_right - camera.get_viewport_rect().size.x)/scale.x, 0))

	camera_selection_sprite.queue_redraw()
	camera_selection_sprite.position = ((camera.get_screen_center_position() - camera.get_viewport_rect().size / 2) - Vector2(tile_size * 3, tile_size/2)) / (scale * 2)
			
func _sync_shadow_transform() -> void:
	shadow_viewport.canvas_transform = get_viewport().canvas_transform
			
func _on_grid_draw() -> void:
	var lines := PackedVector2Array()
	for y in range(grid_size.y):
		lines.append(Vector2(0, y * tile_size))
		lines.append(Vector2(grid_size.x * tile_size, y * tile_size))
	for x in range(grid_size.x):
		lines.append(Vector2(x * tile_size, 0))
		lines.append(Vector2(x * tile_size, grid_size.y * tile_size))

	grid.draw_multiline(lines, Color.BLACK, 1.5)

func _on_camera_selection_sprite_draw() -> void:
	camera_selection_sprite.draw_rect(Rect2(camera_selection_sprite.position, camera_selection_sprite.texture.get_size()), Color.WHITE, false, tile_size)

func generate_map() -> void:
	# This would be better as a Resource, of course, but I'm doing it as a Dictionary for easier JSONifying to send to python
	# By the way, all tiles originate in bottom left as 0,0, and y rises as it goes up
	# This is because there are some tiles that have blank tiles in the top left
	# So I want the origin of everything to be bottom left
	
	occupied_fg_grid.resize(grid_size.x as int - 2) # Ignore boundaries
	occupied_bg_grid.resize(grid_size.x as int - 2)
	for x in occupied_fg_grid:
		x.resize(grid_size.y as int - 2)
	for x in occupied_bg_grid:
		x.resize(grid_size.y as int - 2)
	
	# We don't need to -1 to our coords because the boundaries technically start at -1!
	var new_object: Callable = func(_name: StringName, coords: Vector2i, layer: StringName) -> Dictionary:
		return {&"Name": _name, &"Coords": coords, &"Layer": layer}
		
	var add_to_grid: Callable = func(_grid: Array[Array], coords: Vector2i, index: int) -> void:
		_grid[coords.x][coords.y] = index
		
	var find_and_add_tile: Callable = func(coords: Vector2i, fg: bool) -> void:
		var occupied_grid: Array[Array]
		var layer_name: StringName
		var layer: TileMapLayer
		if fg:
			occupied_grid = occupied_fg_grid
			layer_name = &"FG"
			layer = fg_layer
		else:
			occupied_grid = occupied_bg_grid
			layer_name = &"BG"
			layer = bg_layer
			
		if occupied_grid[coords.x][coords.y] != null: return # If it's already occupied, we can skip adding this tile
		# This is relevant for a few niche cases, mostly for things like the water which occupies 2 spaces
			
		var add_multitile: Callable = func(new_coords: Vector2i, _name: StringName, atlas_coords: Vector2i, index: int, self_function: Callable) -> void:
			var tile: TileData = layer.get_cell_tile_data(new_coords)
			if !tile: return
			var tile_name: StringName = tile.get_custom_data("RLName")
			if !tile_name.split("&").has(_name): return
			var objects: Dictionary[StringName, Vector2i]
			objects.assign(tile.get_custom_data("RLObjects"))
			if objects.is_empty(): return
			if !objects.has(_name): return
			if objects[_name] != atlas_coords: return
			occupied_grid[new_coords.x][new_coords.y] = index
			
			# Since we always originate from the bottom left, we can always flood right and up
			if new_coords.x + 1 < occupied_grid.size():
				self_function.call(new_coords + Vector2i(1, 0), _name, atlas_coords + Vector2i(1, 0), index, self_function) # Right
			if new_coords.y - 1 > 0:
				self_function.call(new_coords - Vector2i(0, 1), _name, atlas_coords + Vector2i(0, 1), index, self_function) # Up, remember that atlas coords are y up positive
		
		var source_id: int = layer.get_cell_source_id(coords)
		if source_id != -1:
			var source: TileSetSource = layer.tile_set.get_source(source_id)
			if source is TileSetAtlasSource:
				var tile: TileData = layer.get_cell_tile_data(coords)
				if tile and !tile.get_custom_data("Boundary"): # Only tiles that are part of the game
					var tile_name: StringName = tile.get_custom_data("RLName")
					if tile_name != "": # If the tile is supported by RL
						var objects: Dictionary[StringName, Vector2i]
						objects.assign(tile.get_custom_data("RLObjects"))
						if objects.is_empty():
							add_to_grid.call(occupied_grid, coords, objects_list.size())
							objects_list.append(new_object.call(tile_name, coords, layer_name))
						else:
							var object_name: StringName = tile_name # In the 1-size case, the object is always the same as the tile name.
							if objects.size() != 1:
								# in the case where there are two possible objects, figure out which one is appropriate by looking up
								# this works because all duplicate objects share a 0,0
								var above_tile: TileData = layer.get_cell_tile_data(coords - Vector2i(0, 1))
								if !above_tile: 
									print("ERROR: " + object_name + " was somehow cut off at the top at coords %s!" % coords)
									return
								for check_name: StringName in objects.keys():
									var above_tile_name: StringName = above_tile.get_custom_data("RLName")
									if !above_tile_name: continue
									if !above_tile_name.split("&").has(check_name): continue
									object_name = check_name # We found it, an object that's vertically contiguous!
									break
							if !objects.has(object_name): 
								print("ERROR: " + object_name + " was somehow attempted to be checked")
								return
							if objects[object_name] != Vector2i.ZERO: return # We only originate from 0,0
							add_multitile.call(coords, object_name, Vector2i.ZERO, objects_list.size(), add_multitile)
							if tile.get_custom_data("Loops"):
								if tile.get_custom_data("Loops").x > 0:
									for i in tile.get_custom_data("Loops").x:
										add_multitile.call(coords + Vector2i(i + 1, 0), object_name, Vector2i.ZERO, objects_list.size(), add_multitile)
								if tile.get_custom_data("Loops").y > 0:
									for i in tile.get_custom_data("Loops").y:
										add_multitile.call(coords - Vector2i(0, i + 1), object_name, Vector2i.ZERO, objects_list.size(), add_multitile)

							objects_list.append(new_object.call(object_name, coords, layer_name))
			elif source is TileSetScenesCollectionSource:
				var info: Dictionary = get_scene_info(source, layer.get_cell_alternative_tile(coords))
				if !info.name: return # Delete anything that we haven't given an RL name, because it's not in our database
				for x in info.size.x:
					for y in info.size.y:
						add_to_grid.call(occupied_grid, coords + Vector2i(x, -y), objects_list.size())
				objects_list.append(new_object.call(info.name, coords, layer_name))
				
	# -2 here because of the boundaries; one in the negatives, one positive + 1
	for x in grid_size.x - 2:
		for y in grid_size.y - 2:
			var coords := Vector2i(x as int, y as int)
			
			find_and_add_tile.call(coords, true)
			find_and_add_tile.call(coords, false)
			
	# replace nulls with -1
	for x in occupied_bg_grid.size():
		for y in occupied_bg_grid[x].size():
			if occupied_bg_grid[x][y] == null:
				occupied_bg_grid[x][y] = -1
			if occupied_fg_grid[x][y] == null:
				occupied_fg_grid[x][y] = -1
				
	# temporary for debugging, for some reason pads a couple extra rows, idk
	var rotated_grid: Array = range(occupied_fg_grid[0].size()).map(func(col): return occupied_fg_grid.map(func(row): return row[col]))
	for x in rotated_grid:
		var row = x
		for y in row.size():
			row[y] = "%3d" % row[y]
		print(row)

func get_scene_info(source: TileSetScenesCollectionSource, scene_id: int) -> Dictionary:
	var tile_scene: PackedScene = source.get_scene_tile_scene(scene_id)
	if scene_info_cache.has(tile_scene):
		return scene_info_cache[tile_scene]
	var tile: Tile = tile_scene.instantiate()
	var rl_name: StringName = tile.rl_name
	var size: Vector2i = tile.get_size(tile_size)
	tile.free()
	scene_info_cache[tile_scene] = {"name": rl_name, "size": size}
	return scene_info_cache[tile_scene]


func _on_end_turn_button_pressed() -> void:
	Game.send_state(objects_list, occupied_fg_grid, occupied_bg_grid)
