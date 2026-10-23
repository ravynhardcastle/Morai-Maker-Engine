extends Node2D

@export var layers: Array[TileMapLayer]
@export var camera: Camera2D
@export var grid: Node2D
@export var camera_move_speed: float
@export var camera_selection_sprite: Sprite2D
@export var shadow_viewport: SubViewport
@export var shadow_rect: ColorRect
@onready var fg_layer:TileMapLayer = layers[layers.find_custom(func(layer): return layer.name == "ForegroundLayer")]
@onready var grid_size: Vector2 = fg_layer.get_used_rect().size
@onready var tile_size: int = fg_layer.tile_set.tile_size.x

func _ready() -> void:
	shadow_viewport.world_2d = get_viewport().world_2d
	shadow_rect.material.set_shader_parameter("caster_texture", shadow_viewport.get_texture())
	RenderingServer.frame_pre_draw.connect(_sync_shadow_transform)

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
