extends Node

var selected_tile: EditorTile:
	set(new_tile):
		if selected_tile:
			selected_tile.selected = false
		new_tile.selected = true
		selected_tile = new_tile