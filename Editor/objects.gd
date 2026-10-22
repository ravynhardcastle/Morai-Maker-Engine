extends ScrollContainer

@export var tilemap: Node2D
@export var tabs: Array[Button]
@export var tiles: HBoxContainer
@export var tile_scale: int
@onready var layers: Array[TileMapLayer] = tilemap.layers
@onready var tileset: TileSet = tilemap.fg_layer.tile_set # The tile set is the same among all layers
var tile_set_sources: Dictionary[String, int]
var placeables: Array[Array] # Array[Array[int]], int corresponse to tilesetsource, inner int is pattern id
var tab_by_title: Dictionary[String, Button] # Maps the string title of a tilesetsource to a button
var tab: String # active tab

func _ready() -> void:
	
	for i in tileset.get_source_count():
		var source: TileSetSource = tileset.get_source(i)
		tile_set_sources[source.resource_name.to_lower()] = i
		tab_by_title[source.resource_name] = tabs[tabs.find_custom(\
				func(tab: Button): return tab.text.to_lower() == source.resource_name.to_lower())]
		
	tab = tab_by_title.find_key(tabs[0]) # initial tab is first in array
	tabs[0].set_pressed_no_signal(true)
	
	placeables.resize(tileset.get_source_count()) # As many placeables categories as there are sources
	for i in tileset.get_patterns_count():
		var pattern: TileMapPattern = tileset.get_pattern(i)
		placeables[pattern.get_cell_source_id(Vector2.ZERO)].append(i)
		
	for tab_button: Button in tabs:
		tab_button.button_down.connect(_tab_changed.bind(tab_button.text.to_lower()))
		
	re_render_placeables()
		
func _tab_changed(new_tab: String) -> void:
	tab = new_tab
	for tab_button: Button in tabs:
		tab_button.set_pressed_no_signal(false) # Including the tab we're managing, since it sets to true after
	re_render_placeables()
	
func re_render_placeables(new_tab: String = tab) -> void:
	var new_placeables: Array = placeables[tile_set_sources[new_tab.to_lower()]] # Array[int]
	var source: TileSetAtlasSource = tileset.get_source(tile_set_sources[new_tab.to_lower()])
	var tile_size_rect: Rect2i = Rect2i(0, 0, tileset.tile_size.x, tileset.tile_size.y)
	for child in tiles.get_children():
		child.queue_free()
	for placeable_index: int in new_placeables:
		var placeable: TileMapPattern = tileset.get_pattern(placeable_index)
		var _size: Vector2i = placeable.get_size()
		var image: Image = Image.create(_size.x * tileset.tile_size.x, _size.y * tileset.tile_size.y, false, Image.FORMAT_RGBA8)
		for x in _size.x:
			for y in _size.y:
				var tile_coords: Vector2i = placeable.get_cell_atlas_coords(Vector2i(x, y))
				var region: Rect2i = source.get_tile_texture_region(tile_coords)
				var cell_image: Image = source.texture.get_image()
				image.blit_rect(cell_image.get_region(region), tile_size_rect, Vector2i(x * tileset.tile_size.x, y * tileset.tile_size.y))
				
				
		var texture: ImageTexture = ImageTexture.create_from_image(image)
		var texture_rect: TextureRect = TextureRect.new()
		texture_rect.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
		texture_rect.size_flags_horizontal = SIZE_EXPAND_FILL
		texture_rect.size_flags_vertical = SIZE_EXPAND_FILL
		texture_rect.offset_transform_enabled = true
		texture_rect.offset_transform_scale = Vector2(tile_scale, tile_scale)
		texture_rect.texture = texture
		texture_rect.custom_minimum_size.x = texture.get_size().x * tile_scale
		texture_rect.custom_maximum_size.x = texture.get_size().x * tile_scale
		tiles.add_child(texture_rect)
