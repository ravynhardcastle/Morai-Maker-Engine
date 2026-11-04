class_name EditorTile

extends TextureRect

var selected: bool = false:
	set(value):
		material.set_shader_parameter("selected", value)
		selected = value

func init(_texture: ImageTexture, tile_size: Vector2, tile_scale: float) -> void:
	texture = _texture
	custom_minimum_size.x = _texture.get_size().x * tile_scale
	custom_maximum_size.x = _texture.get_size().x * tile_scale
	custom_minimum_size.y = tile_size.y * tile_scale
	custom_maximum_size.y = tile_size.y * tile_scale

func _on_clickbox_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_mask == MOUSE_BUTTON_LEFT:
		Game.selected_tile = self
