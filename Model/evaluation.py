# ————— IMPORTS ————— #

from Pretraining import data_path, scores_path, testNames # use the same ones from Pretraining.py
from tile_config import allNames
from Extraction import extract_levels
from Server import server_create_model, ServerConfig, server_create_socket, server_send, init_server, attempt_server_receive, minimumInteractionConfidence, confidenceDelta
import json
import csv, time, struct
from dataclasses import dataclass
import numpy as np
from pathlib import Path
import tensorflow as tf
# Old version, we are updating to a new version
#from tflearn import conv_2d, max_pool_2d, local_response_normalization, batch_normalization, fully_connected, regression, input_data, dropout, custom_layer, flatten, reshape, embedding,conv_2d_transpose
# New imports, swapping to tensorflow keras
from tensorflow.keras import layers, models, optimizers #NGL these are shown as errors despite working so.. I just ignore that
# Personal File Imports
from tile_config import allNames, actions
# ————— END IMPORTS ————— #

# ————— CONSTANTS ————— #

# ————— END CONSTANTS ————— #

def main():
	levels = extract_levels() # TODO: specify data path for testing set seperate from training set. For now we're just doing it all

	config = ServerConfig()
	model = server_create_model(force_retrain = False) # TODO: Set this to True later 
	socket = server_create_socket(config)

	conn, addr = init_server(config)

	# Initialize variables
	prev_map = None
	prev_action = None
	prev_start_x = -1
	rejections = []  # HOLD ON TO ALL REJECTIONS. NEVER ADD AGAIN
	# ————— Caches ————— #
	object_sizes = {} # Initialize the cache
	object_layers = {} # Initialize the cache

	'''
	This is the cache that holds all the selection information for the running application. It is in the following format:
	List<Selection_Object>. Where a Selection 
	'''
	selection_cache = []
	# ————— END Caches ————— #

	def server_send_actions(actions: dict[int, dict[int, list[int]]]):
		pass

	def server_receive() -> bool:
		while True:
			server_turn: bool | None = attempt_server_receive(conn, model, minimumInteractionConfidence, confidenceDelta, prev_map, prev_action, prev_start_x, rejections, object_sizes, object_layers, selection_cache)
			if server_turn is None:
				continue
			if turn:
				return True
			else:
				print("Server error. Stopping evaluation.")
				return False
		
		print("Server turn somehow interrupted?")
		return False
			

	for level_name in levels:
		level = levels[level_name]
		final_level: dict[int, dict[int, list[int]]] = level["final_level"]
		
		for turn in range(len(level.player_actions)):
			state: dict[int, dict[int, list[int]]] = level["state"][turn]
			additions: int = level["additions"][turn]
			removals: int = level["removals"][turn]
			player_actions: dict[int, dict[int, list[int]]] = level["player_actions"][turn]
			ai_actions: dict[int, dict[int, list[int]]] = level["ai_actions"][turn]
			ai_accepteds: dict[int, dict[int, list[int]]] = level["ai_accepteds"][turn]
			ai_removals: dict[int, dict[int, list[int]]] = level["ai_removals"][turn]
			if turn > 0:
				server_send_actions(ai_actions)

			# player action
			server_send_actions(player_actions)
			if not server_receive():
				return
			
			server_send({"end_turn": True}, conn)

if __name__ == '__main__':
	main()