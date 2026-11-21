'''

Please note:
This code is using pre-training data which is not "public" and thus this code is available, but it refers to .csv and .txt
files which are in hidden folder.
'''

# ————— IMPORTS ————— #
#region Imports
import json
from pathlib import Path
import socket, csv, time, struct
from dataclasses import dataclass
import numpy as np
import tensorflow as tf
# Old version, we are updating to a new version
#from tflearn import conv_2d, max_pool_2d, local_response_normalization, batch_normalization, fully_connected, regression, input_data, dropout, custom_layer, flatten, reshape, embedding,conv_2d_transpose
# New imports, swapping to tensorflow keras
from tensorflow.keras import layers, models, optimizers #NGL these are shown as errors despite working so.. I just ignore that
# Personal File Imports
from tile_config import allNames, actions
#endregion
# ————— END IMPORTS ————— #


# ————— CONSTANTS ————— #
data_path = Path(__file__).resolve().parent.parent / "Pretraining" / "AgentTraining" / "Log Data"
# ————— END CONSTANTS ————— #







# ————— PUBLIC API ————— #
def pre_training():
	# collect all of the .txt files at our data path location
	for file_name in data_path.glob('*/*.txt'):
		print(file_name)
	pass


# ————— END PUBLIC API ————— #



def main():
	# For now, im just gonna call the main pretraining function if this is ever called solo
	pre_training()


if __name__ == '__main__':
	main()