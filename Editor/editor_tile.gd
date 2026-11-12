class_name EditorTile

extends TextureRect

var selected: bool = false:
	set(value):
		material.set_shader_parameter("selected", value)
		selected = value
@export var tile: StringName
@export var fg: bool

func init(_texture: ImageTexture, tile_size: Vector2, tile_scale: float, _tile_name: StringName, _fg: bool) -> void:
	texture = _texture
	custom_minimum_size.x = _texture.get_size().x * tile_scale
	custom_maximum_size.x = _texture.get_size().x * tile_scale
	custom_minimum_size.y = tile_size.y * tile_scale
	custom_maximum_size.y = tile_size.y * tile_scale
	tile = _tile_name
	fg = _fg

func _on_clickbox_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_mask == MOUSE_BUTTON_LEFT:
			Game.selected_tile = self
		elif event.button_mask == MOUSE_BUTTON_RIGHT:
			Game.selected_tile = null
