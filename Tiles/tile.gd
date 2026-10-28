class_name Tile

extends Node2D

@export var sprite: AnimatedSprite2D
var image: Image

func _ready() -> void:
	image = sprite.sprite_frames.get_frame_texture(sprite.animation, sprite.frame).get_image()