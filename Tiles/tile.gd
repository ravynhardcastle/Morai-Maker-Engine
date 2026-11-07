class_name Tile

extends Node2D

@export var sprite: AnimatedSprite2D
@export var rl_name: StringName
@export var hit_detection: CollisionShape2D
	
func get_image() -> Image:
	return sprite.sprite_frames.get_frame_texture(sprite.animation, sprite.frame).get_image()
	
func get_size(tile_size: int) -> Vector2i:
	return hit_detection.shape.size / tile_size