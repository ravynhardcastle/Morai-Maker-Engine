extends ScrollContainer

@export var tilemap: Node2D
@export var tabs: Array[Button]
@export var tiles: HBoxContainer
@export var tile_scale: int
@export var outline_padding: int # padding for the outline shader
@onready var layers: Array[TileMapLayer] = tilemap.layers
@onready var tileset: TileSet = tilemap.fg_layer.tile_set # The tile set is the same among all layers
@onready var editor_tile: PackedScene = preload("res://Tiles/editor_tile.tscn")
var tile_set_sources: Dictionary[String, int]
var placeables: Array[Array] # Array[Array[int]], int corresponds to tilesetsource, inner int is pattern id
var tab_by_title: Dictionary[String, Button] # Maps the string title of a tilesetsource to a button
var tab: String # active tab
var tab_tiles: Dictionary[String, Array] # Array[EditorTile], All the tiles in every tab
var placeable_to_rl_name: Dictionary[TileMapPattern, StringName] # Maps the placeable to its RL name, for size computing
var object_sizes: Dictionary[StringName, Vector2i] # Maps an RL name to a size

func _ready() -> void:
	for i in tileset.get_source_count():
		var source: TileSetSource = tileset.get_source(i)
		tile_set_sources[source.resource_name.to_lower()] = i
		tab_by_title[source.resource_name.to_lower()] = tabs[tabs.find_custom(\
				func(tab: Button): return tab.text.to_lower() == source.resource_name.to_lower())]
		tab_tiles[source.resource_name.to_lower()] = Array()
		
	tab = tab_by_title.find_key(tabs[0]) # initial tab is first in array
	tabs[0].set_pressed_no_signal(true)
	
	placeables.resize(tileset.get_source_count()) # As many placeables categories as there are sources
	for i in tileset.get_patterns_count():
		var pattern: TileMapPattern = tileset.get_pattern(i)
		var cell_source: int = -1
		for x in pattern.get_size().x:
			for y in pattern.get_size().y:
				if !pattern.has_cell(Vector2(x, y)): continue
				cell_source = pattern.get_cell_source_id(Vector2(x, y))
				if cell_source != -1:
					var source: TileSetSource = tileset.get_source(cell_source)
					if source is TileSetAtlasSource:
						# We can check top left for this since all duplicates are on the bottom left
						var tile_atlas_coords: Vector2i = pattern.get_cell_atlas_coords(Vector2i(x, y))
						var tile_alternative_tile: int = pattern.get_cell_alternative_tile(Vector2i(x, y))
						var tile: TileData = source.get_tile_data(tile_atlas_coords, tile_alternative_tile)
						var tile_name: StringName = tile.get_custom_data("RLName")
						if tile_name.contains("&"):
							# We're measuring the top left here, so if there's ever a conflict, it has to be the one to the right of the '&'
							# Since taller is prioritized before the &
							tile_name = tile_name.split("&")[1]
						if tile_name:
							placeable_to_rl_name[pattern] = tile_name
					elif source is TileSetScenesCollectionSource:
						var tile_id: int = pattern.get_cell_alternative_tile(Vector2i(x, y))
						var tile: Tile = source.get_scene_tile_scene(tile_id).instantiate()
						placeable_to_rl_name[pattern] = tile.rl_name
						tile.queue_free()
					break
			if cell_source != -1: break
		placeables[cell_source].append(i)
		
	for tab_button: Button in tabs:
		tab_button.button_down.connect(_tab_changed.bind(tab_button.text.to_lower()))
		
	render_placeables()
	change_placeables()
	
	Game.object_sizes = object_sizes
	var rl_name_to_placeable: Dictionary[StringName, TileMapPattern]
	for placeable in placeable_to_rl_name:
		rl_name_to_placeable[placeable_to_rl_name[placeable]] = placeable
	Game.rl_name_to_placeable = rl_name_to_placeable
		
func _tab_changed(new_tab: String) -> void:
	if tab == new_tab:
		# Set it to false so you can't unselect a category
		tab_by_title[new_tab.to_lower()].set_pressed_no_signal(false)
		return
	tab = new_tab
	for tab_button: Button in tabs:
		tab_button.set_pressed_no_signal(false) # Including the tab we're managing, since it sets to true after
	change_placeables()
	
func render_placeables() -> void:
	for tab_title in tab_by_title.keys():
		var fg: bool = tab_title.to_lower() != "decorative" # Currently, hardcoded to be the only background layer
		var new_placeables: Array = placeables[tile_set_sources[tab_title.to_lower()]] # Array[int]
		var source: TileSetSource = tileset.get_source(tile_set_sources[tab_title.to_lower()])
		var tile_size_rect: Rect2i = Rect2i(0, 0, tileset.tile_size.x, tileset.tile_size.y)
		for placeable_index: int in new_placeables:
			var placeable: TileMapPattern = tileset.get_pattern(placeable_index)
			var _size: Vector2i = placeable.get_size()
			# Every example has the same tilesize among a placeable. This might be a false assumption later
			var placeable_tile_size: Vector2i = Vector2i.ONE
			if source is TileSetAtlasSource:
				placeable_tile_size = source.get_tile_size_in_atlas(placeable.get_cell_atlas_coords(Vector2i.ZERO))
			var image: Image = Image.create(_size.x * tileset.tile_size.x * placeable_tile_size.x, _size.y * tileset.tile_size.y * placeable_tile_size.y, false, Image.FORMAT_RGBA8)
			var tile_name: StringName
			if source is TileSetAtlasSource:
				if placeable_to_rl_name.has(placeable):
					tile_name = placeable_to_rl_name[placeable]
					object_sizes[tile_name] = _size
				for x in _size.x:
					for y in _size.y:
						var tile_coords: Vector2i = placeable.get_cell_atlas_coords(Vector2i(x, y))
						var region: Rect2i = source.get_tile_texture_region(tile_coords)
						var cell_image: Image = source.texture.get_image()
						image.blit_rect(cell_image.get_region(region), 
								Rect2i(tile_size_rect.position, tile_size_rect.size * placeable_tile_size), 
								Vector2i(x * tileset.tile_size.x, y * tileset.tile_size.y))
						print(tile_name, Rect2i(tile_size_rect.position, tile_size_rect.size * placeable_tile_size))
			elif source is TileSetScenesCollectionSource:
				# For now, making an assumption that scene placeables will be one tile (that is the scene)
				# More complicated logic needed if this assumption is violated
				var tile_id: int = placeable.get_cell_alternative_tile(Vector2.ZERO)
				var tile: Tile = source.get_scene_tile_scene(tile_id).instantiate()
				image = tile.get_image()
				tile_name = tile.rl_name
				if tile_name != "":
					object_sizes[tile_name] = tile.get_size(tileset.tile_size.x)
				tile.queue_free() # i don't wanna play with you anymore...
					
			image = pad_image(image)
			var texture: ImageTexture = ImageTexture.create_from_image(image)
			var curr_tile: EditorTile = editor_tile.instantiate()
			curr_tile.init(texture, tileset.tile_size, tile_scale, tile_name, fg)
			Game.rl_name_scene[tile_name] = source is TileSetScenesCollectionSource
			
			if fg: Game.fg_objects.append(tile_name)
			
			tab_tiles[tab_title.to_lower()].append(curr_tile)

func change_placeables(new_tab: String = tab) -> void:
	Game.selected_tile = null # Deselect anything selected or else the selection doesn't get unselected
	for child in tiles.get_children():
		child.queue_free()
		
	for tile: EditorTile in tab_tiles[new_tab.to_lower()]:
		var curr_tile: EditorTile = tile.duplicate()
		tiles.add_child(curr_tile)
		var available_height: float = size.y - get_h_scroll_bar().get_combined_minimum_size().y + outline_padding * 2 * tile_scale
		var fit_scale: float = clamp(floor(available_height / curr_tile.texture.get_height()), 1.0, 3.0)
		curr_tile.offset_transform_scale = Vector2(fit_scale, fit_scale)

func pad_image(src: Image) -> Image:
	var padded := Image.create(src.get_width() + outline_padding * 2, src.get_height() + outline_padding * 2, false, Image.FORMAT_RGBA8)
	padded.blit_rect(src, Rect2i(Vector2i.ZERO, src.get_size()), Vector2i(outline_padding, outline_padding))
	return padded
