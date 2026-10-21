extends Node2D

@export var tilemap: Node2D
@export var viewport: SubViewport
@export var camera: Camera2D
@onready var fg_layer:TileMapLayer = tilemap.layers[tilemap.layers.find_custom(func(layer): return layer.name == "ForegroundLayer")]

@onready var tile_size: int = fg_layer.tile_set.tile_size.x
# plus and minus one because we have a buffer layer of block blocks around
@onready var world_rect: Rect2 = Rect2(
		Vector2(fg_layer.get_used_rect().position + Vector2i.ONE) * tile_size,
		Vector2(fg_layer.get_used_rect().size - Vector2i.ONE * 2) * tile_size # 2 for 1 buffer on each side
)

@onready var zoom: Vector2 = Vector2(viewport.size) / world_rect.size
@onready var target_zoom: float = min(zoom.x, zoom.y) / 3

func _ready() -> void:
	viewport.get_viewport().world_2d = tilemap.get_viewport().world_2d
	
	camera.position = world_rect.get_center() * 3
	
	camera.zoom = Vector2(target_zoom, target_zoom)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton or event is InputEventMouseMotion and event.button_mask == MOUSE_BUTTON_LEFT:
		var map_ratio: float = event.position.x / viewport.size.x
		var map_distance: int = round(tilemap.camera.limit_right * map_ratio)
		var camera_size: Vector2 = tilemap.camera.get_viewport_rect().size
		tilemap.camera.position = Vector2((map_distance - camera_size.x/2) / tilemap.scale.x, 0)
