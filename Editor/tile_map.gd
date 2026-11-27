extends Node2D

@export var layers: Array[TileMapLayer]
@export var camera: Camera2D
@export var grid: Node2D
@export var camera_move_speed: float
@export var camera_selection_sprite: Sprite2D
@export var shadow_viewport: SubViewport
@export var shadow_rect: ColorRect
@export var selection_highlight: Node2D
@export var cursor_collider: Area2D
@export var error_highlight: AnimationPlayer
@export var error_cooldown: Timer
@export var selecting_box: Node2D
@export var name_popup: PopupPanel
@export var file_name: LineEdit
@export var save_file: FileDialog
@export var load_file: FileDialog
@onready var fg_layer:TileMapLayer = layers[layers.find_custom(func(layer): return layer.name == "ForegroundLayer")]
@onready var bg_layer:TileMapLayer = layers[layers.find_custom(func(layer): return layer.name == "BackgroundLayer")]
@onready var grid_size: Vector2i = fg_layer.get_used_rect().size - Vector2i(2, 19) # Remove padding, there's some top padding
@onready var tile_size: int = fg_layer.tile_set.tile_size.x
var objects_list: Array[Dictionary] # of which the dictionary contains Name: Name, Coords: Vector2i and Layer: FG or Layer: BG
var deleted_objects: Array[int] # an array of indexes of objects_list that are currently empty from deletion
var occupied_fg_grid: Array[Array] # Each array contains an int that is just the index of the thing in the objects list
var occupied_bg_grid: Array[Array]
var last_object_index: int # The last index for a placed object
var preference_selecting: bool
var selecting: bool
var selection_positive: bool
var selection_start: Vector2i
var selection_end: Vector2i
var selections: Array[Dictionary] # Dictionary is like "selection": Rect2i "positive": bool

var scene_info_cache: Dictionary # Dictionary[PackedScene, {size: Vector2i, name: StringName}]
var select_pos: Vector2i: # the grid position you have selected
	set(value):
		select_pos = Vector2i(
				clamp(value.x, 0, grid_size.x - 1),
				clamp(value.y, 0, grid_size.y - 1)
		)
		# You may be asking: Why don't we just use the occupied grid directly always?
		# Well, we probably could do something efficient that doesn't check for collisions at all,
		# but we need to differentiate between FG and BG anyways, so I use this approach
		var selecting_fg: bool = false # Whether we're selecting a foreground block
		var is_selecting: bool = false # Whether we're selecting anything at all
		if Game.selected_tile and Game.selected_tile.tile:
			selecting_fg = Game.selected_tile.fg
			is_selecting = true
		if not cursor_collider.get_overlapping_areas().is_empty() and (selecting_fg or not is_selecting):
			# Ideally this would only run whenever the select_pos actually changes, to simplify computation
			# However when you move the mouse really fast sometimes this isn't reliable
			var object_area: Area2D = cursor_collider.get_overlapping_areas()[0]
			var object_rect: Rect2 = object_area.shape_owner_get_owner(0).shape.get_rect()
			select_rect = Rect2i(round(object_area.global_position.x / scale.x + object_rect.position.x),
				round(object_area.global_position.y / scale.y + object_rect.position.y),
				round(object_rect.size.x), round(object_rect.size.y))
			var object: Tile = object_area.get_parent()
			# Always FG since we're just checking areas right now, so scenes
			selected_object = occupied_fg_grid[select_pos.x][select_pos.y]
		else:
			# We're selecting something on the map, but it's always 1x1 since it's a tile, so get the tile at that pos
			if not cursor_collider.get_overlapping_bodies().is_empty():
				var tile: TileData = fg_layer.get_cell_tile_data(select_pos)
				var layer: StringName = &"FG"
				if not tile:
					tile = bg_layer.get_cell_tile_data(select_pos)
					layer = &"BG"
				if tile:
					if layer == &"FG":
						if is_selecting and !selecting_fg: selected_object = -1
						else: selected_object = occupied_fg_grid[select_pos.x][select_pos.y]
					else:
						if is_selecting and selecting_fg: selected_object = -1
						else: selected_object = occupied_bg_grid[select_pos.x][select_pos.y]
			else:
				selected_object = -1 # Nothing is selected
			if selected_object == -1 or objects_list[selected_object].is_empty() or not Game.object_sizes.has(objects_list[selected_object].name):
				if Game.selected_tile and Game.selected_tile.tile != "":
					var selected_tile_size: Vector2i = Game.object_sizes[Game.selected_tile.tile]
					select_rect = Rect2i(select_pos.x * tile_size as int,
							select_pos.y * tile_size as int + tile_size,
							selected_tile_size.x * tile_size as int,
							-selected_tile_size.y * tile_size as int)
				else:
					select_rect = Rect2i(select_pos.x * tile_size as int,
						select_pos.y * tile_size as int,
						tile_size as int,
						tile_size as int)
			else:
				var object: Dictionary = objects_list[selected_object]
				var object_size: Vector2i = Game.object_sizes[object.name]
				select_rect = Rect2i(object.coords.x * tile_size,
						(object.coords.y - object_size.y + 1) * tile_size,
						object_size.x * tile_size,
						object_size.y * tile_size)
			
		selection_highlight.queue_redraw()
			
var selected_object: int = -1 # index of object from the objects list we have selected right now
var select_rect: Rect2i # the shape that the object is

func _ready() -> void:
	Game.tile_size = tile_size
	Game.grid_size = grid_size
	shadow_viewport.world_2d = get_viewport().world_2d
	shadow_rect.material.set_shader_parameter("caster_texture", shadow_viewport.get_texture())
	RenderingServer.frame_pre_draw.connect(_sync_shadow_transform)
	RenderingServer.frame_pre_draw.connect(_sync_cursor)
	generate_map()
	Game.receive_suggestion.connect(_on_receive_suggestion)

func _physics_process(_delta: float) -> void:
	# Highlight the tile / semantic object you're selecting
	var mouse: Vector2 = get_global_mouse_position()
	select_pos = floor(mouse / tile_size / scale)
	
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

	if selecting:
		var mouse: Vector2 = floor(get_global_mouse_position() / scale / tile_size)
		if mouse.x * tile_size < selection_start.x:
			selection_end.x = floor(mouse.x * tile_size - selection_start.x - tile_size)
		else:
			selection_end.x = floor((mouse.x + 1) * tile_size - selection_start.x)
		if mouse.y * tile_size < selection_start.y:
			selection_end.y = floor(mouse.y * tile_size - selection_start.y - tile_size)
		else:
			selection_end.y = floor((mouse.y + 1) * tile_size - selection_start.y)
		selecting_box.queue_redraw()

func _on_run_button_pressed() -> void:
	# TODO: run simulator
	pass

func _on_save_button_pressed() -> void:
	save_file.show()

func _on_save_file_file_selected(path: String) -> void:
	save_level(path)

func _on_load_button_pressed() -> void:
	load_file.show()

func _on_open_file_file_selected(path: String) -> void:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	var size: PackedStringArray = file.get_csv_line()
	if size.size() != 2: return # Not a size
	level_resize(size[0].to_int(), size[1].to_int())
	clear()
	while file.get_position() < file.get_length():
		var object: PackedStringArray = file.get_csv_line()
		if object.size() != 5: return # Not an object
		place_object(object[0], Vector2i(object[1].to_int(), size[1].to_int() - 1 - object[2].to_int()))

func _on_clear_button_pressed() -> void:
	clear()

func _on_remove_button_pressed() -> void:
	for suggest: Dictionary in Game.last_suggestion:
		var object: Dictionary = objects_list[suggest.object_index]
		if object:
			if object.name == suggest.name and object.coords == suggest.coords:
				delete_object(suggest.object_index)

func _on_end_button_pressed() -> void:
	name_popup.show()

func _on_file_save_button_pressed() -> void:
	if save_level("res://Levels/%s.csv" % file_name.text):
		name_popup.hide()
		get_tree().quit()

func _on_selection_toggled(toggled_on: bool) -> void:
	preference_selecting = toggled_on
	
func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton or event is InputEventMouseMotion:
		if not preference_selecting:
			if event.button_mask == MOUSE_BUTTON_LEFT:
				if selected_object != -1 or not Game.selected_tile or not Game.selected_tile.tile:
					if Game.selected_tile != null:
						highlight_error()
					return
				place_object(Game.selected_tile.tile, select_pos, Game.selected_tile.fg, true)
				
			elif event.button_mask == MOUSE_BUTTON_RIGHT:
				delete_object(selected_object)
		else:
			if event is InputEventMouseButton:
				selecting = false
				if not event.is_pressed():
					var new_selection: Dictionary[String, Variant] = {&"selection": make_selection_rect(selection_start, selection_end), &"positive": selection_positive}
					selections.append(new_selection)
					selecting_box.queue_redraw()
			if not event.is_pressed():
				return
			if not selecting:
				selecting = true
				selection_positive = event.button_mask == MOUSE_BUTTON_LEFT
				selection_start = floor((get_global_mouse_position()/scale) / tile_size) * tile_size
	
func _sync_cursor() -> void:
	cursor_collider.position = get_global_mouse_position() / scale
			
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

func _on_end_turn_button_pressed() -> void:
	Game.send_state(objects_list, occupied_fg_grid, occupied_bg_grid, selections, round(camera.position.x / tile_size))

func _on_selection_highlight_draw() -> void:
	selection_highlight.draw_rect(select_rect, Color.WHITE, true)

func _on_selecting_box_draw() -> void:
	if selecting:
		selecting_box.draw_rect(make_selection_rect(selection_start, selection_end), Color.GREEN if selection_positive else Color.RED, false, 3)
	for current_selection in selections:
		selecting_box.draw_rect(current_selection.selection, Color.GREEN if current_selection.positive else Color.RED, false, 3)
		selecting_box.draw_rect(current_selection.selection, Color(Color.GREEN if current_selection.positive else Color.RED, 0.5), true)
		
func _on_receive_suggestion(tile: StringName, coords: Vector2i):
	place_object(tile, coords)
	Game.last_suggestion.append({"name": tile, "coords": coords, "object_index": last_object_index})

func make_selection_rect(_selection_start: Vector2i, _selection_end: Vector2i) -> Rect2i:
	var offset: Vector2i = Vector2i(tile_size if _selection_end.x < 0 else 0, tile_size if _selection_end.y < 0 else 0)
	return Rect2i(_selection_start + offset, _selection_end).abs()


func highlight_error():
	if error_cooldown.time_left == 0:
		error_highlight.play("error")
		error_cooldown.start()

func place_object(tile: StringName, pos: Vector2i, fg = null, user: bool = false) -> bool:
	if fg == null: fg = Game.fg_objects.has(tile)
	
	var selected_size: Vector2i = Game.object_sizes[tile]
	var occupied_grid: Array[Array] = occupied_fg_grid if fg else occupied_bg_grid
	var layer: TileMapLayer = fg_layer if fg else bg_layer
	var fill_grid: Array[Vector2i]
	for x in selected_size.x:
		for y in selected_size.y:
			fill_grid.append(Vector2i(pos.x + x, pos.y - y))
			if occupied_grid[pos.x + x][pos.y - y] != -1:
				if user:
					highlight_error()
				else:
					print("Object failed to place!")
					push_error("RL sent incorrect tile: " + tile + " at " + str(pos))
				return false
	
	# Okay, it's a valid placement position, you got me
	var index: int
	# WARNING: If this ends up fucking up the model, REMOVE THIS
	# We are recycling deleted indexes. This might be a bad thing for learning, actually!
	if not deleted_objects.is_empty():
		deleted_objects.sort()
		index = deleted_objects.pop_front()
	else:
		index = objects_list.size()
		objects_list.append({})
		
	last_object_index = index
	
	objects_list[index] = new_object(tile, pos, &"FG" if fg else &"BG")
	
	for cell: Vector2i in fill_grid:
		occupied_grid[cell.x][cell.y] = index
	
	# If it's a scene, we can just place it because it's already initialized bottom left
	# If it's not a scene, then we need to adjust its origin to account for the pattern being originated top right
	layer.set_pattern(pos - Vector2i(0, (selected_size.y - 1) if not Game.rl_name_scene[tile] else 0),
			Game.rl_name_to_placeable[tile])
	
	if user:
		error_cooldown.start() # To make dragging tiles not error
		error_highlight.play("RESET")
	print("Placed %s at %d,%d" % [tile, pos.x, pos.y])
	return true

func generate_map() -> void:
	# This would be better as a Resource, of course, but I'm doing it as a Dictionary for easier JSONifying to send to python
	# By the way, all tiles originate in bottom left as 0,0, and y rises as it goes up
	# This is because there are some tiles that have blank tiles in the top left
	# So I want the origin of everything to be bottom left
	
	occupied_fg_grid.resize(grid_size.x as int) # Ignore boundaries
	occupied_bg_grid.resize(grid_size.x as int)
	for x in occupied_fg_grid:
		x.resize(grid_size.y as int)
	for x in occupied_bg_grid:
		x.resize(grid_size.y as int)
		
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
							objects_list.append(new_object(tile_name, coords, layer_name))
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
								
							objects_list.append(new_object(object_name, coords, layer_name))
			elif source is TileSetScenesCollectionSource:
				var info: Dictionary = get_scene_info(source, layer.get_cell_alternative_tile(coords))
				if !info.name: return # Delete anything that we haven't given an RL name, because it's not in our database
				for x in info.size.x:
					for y in info.size.y:
						add_to_grid.call(occupied_grid, coords + Vector2i(x, -y), objects_list.size())
				objects_list.append(new_object(info.name, coords, layer_name))
				
	# -2 here because of the boundaries; one in the negatives, one positive + 1
	for x in grid_size.x:
		for y in grid_size.y:
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
	var rotated_grid: Array = range(occupied_bg_grid[0].size()).map(func(col): return occupied_bg_grid.map(func(row): return row[col]))
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

# We don't need to -1 to our coords because the boundaries technically start at -1!
func new_object(_name: StringName, coords: Vector2i, layer: StringName) -> Dictionary:
	return {&"name": _name, &"coords": coords, &"layer": layer}

func delete_object(object_index: int) -> void:
	if object_index == -1: return # trying to delete an empty tile!
	if objects_list[object_index].is_empty(): return # already deleted!
	var layer_name: StringName = objects_list[object_index].layer
	var deleted_object = objects_list[object_index].duplicate()
	objects_list[object_index] = {}
	var occupied_grid: Array[Array]
	var layer: TileMapLayer
	if layer_name == &"FG":
		occupied_grid = occupied_fg_grid
		layer = fg_layer
	else:
		occupied_grid = occupied_bg_grid
		layer = bg_layer
	
	var delete_coords: Array[Vector2i]
	
	for x: int in occupied_grid.size():
		for y: int in occupied_grid[x].size():
			if occupied_grid[x][y] == object_index:
				occupied_grid[x][y] = -1
				delete_coords.append(Vector2i(x, y))
				
	for coords: Vector2i in delete_coords:
		layer.set_cell(coords) # delete the tile at this cell

	print("Deleted %s at %d,%d" % [deleted_object.name, deleted_object.coords.x, deleted_object.coords.y])
		
	deleted_objects.append(object_index)
	
func clear() -> void:
	for object: int in objects_list.size():
		delete_object(object)
	
	objects_list = []
	deleted_objects = []

func save_level(directory: String) -> bool: # true if succeeds, false if fails
	if directory.is_empty() or directory == "res://Levels/.csv": return false
	var objects_csv_string: String
	objects_csv_string = "%d,%d" % [grid_size.x, grid_size.y]
	for object:Dictionary in objects_list:
		if object.is_empty(): continue
		var obj_string: String
		var obj_size: Vector2i = Game.object_sizes[object.name]
		obj_string = "\n%s,%d,%d,%d,%d" % [object.name, object.coords.x, grid_size.y - 1 - object.coords.y, obj_size.x, obj_size.y]
		objects_csv_string += obj_string
	var file: FileAccess = FileAccess.open(directory, FileAccess.WRITE)
	file.store_string(objects_csv_string)
	return true

func level_resize(x: int, y: int):
	# TODO: change level from the 100x15 default size
	pass
