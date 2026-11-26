'''

Please note:
This code is using pre-training data which is not "public" and thus this code is available, but it refers to .csv and .txt
files which are in hidden folder.
'''

# ————— IMPORTS ————— #
#region Imports
import json
import copy
import random
from pathlib import Path
import socket, csv, time, struct
from dataclasses import dataclass
import numpy as np
import tensorflow as tf
from tqdm.keras import TqdmCallback
# Old version, we are updating to a new version
#from tflearn import conv_2d, max_pool_2d, local_response_normalization, batch_normalization, fully_connected, regression, input_data, dropout, custom_layer, flatten, reshape, embedding,conv_2d_transpose
# New imports, swapping to tensorflow keras
from tensorflow.keras import layers, models, optimizers #NGL these are shown as errors despite working so.. I just ignore that
# Personal File Imports
from tile_config import allNames, actions
from Server import server_build_model, MODEL_PATH
#endregion
# ————— END IMPORTS ————— #


# ————— CONSTANTS ————— #
data_path = Path(__file__).resolve().parent.parent / "Pretraining" / "AgentTraining" / "Log Data"
scores_path = Path(__file__).resolve().parent.parent / "Pretraining" / "AgentTraining" / "totalResults.csv"
testNames = ['0215', '1206', '2114', '2005', '1204', '2101', '2001', '1200', '1002', '1203', '0103']
# ————— END CONSTANTS ————— #



# ————— DATA LOADING ————— #
#region Data Loading
def load_final_scores():
	'''
	Taken from yalini_test.py
	'''
	finalScores = {}
	with open(scores_path, "r", newline="") as source:
		reader = csv.reader(source)
		readRow = False
		for row in reader:
			if readRow:
				score = float(row[8])
				playerID = row[0]
				if len(playerID) == 3:
					playerID = "0" + playerID
				finalScores[playerID + "-1"] = score
				finalScores[playerID + "-2"] = -1 * score
			readRow = True

	finalScores["2106-2b"] = -1
	return finalScores
def load_training_examples_by_player(finalScores):
	'''
	taken from yalini_test.py / test.py
	'''
	gamma = 0.1
	SARSAS = [] # lowkey im still trying to figure out what this word is
	trainingExamplesByPlayer = {}
	totalAdditions = 0
	totalDeletions = 0
	for file_name in data_path.glob('*/*.txt'):
		content = []
		additions = 0
		deletions = 0
		with open(file_name) as f:
			content = f.readlines()
		content = [x.strip() for x in content]
		blocks = {}
		currentPrevState = {}
		aiActions = {}
		thisSequence = []
		if len(content) > 0 and "Start" in content[0]:
			playerControl = True
			designMode = True
			lastHit = 0

			for line in content:
				if not designMode and lastHit > 0:
					# Check if still out of design mode
					splits = line.split("time = ")
					thisTime = float(splits[-1])
					if thisTime > lastHit:
						designMode = True

				if "Added" in line and " at " in line:
					subline = line[6:]
					atStart = subline.find(" at ")
					nameOfAddition = subline[:atStart]

					subline = subline[atStart + 4:]
					indexTimeSplit = subline.split(":  ")
					indexString = indexTimeSplit[0]
					indexSplit = indexString.split(", ")
					trueTime = float(indexTimeSplit[1][7:])
					x = int(indexSplit[0])
					y = int(indexSplit[1])

					if designMode:
						if playerControl:
							if x in blocks.keys() and y in blocks[x].keys() and blocks[x][y][allNames.index(nameOfAddition)] > 0:
								# Player Removed
								blocks[x][y][allNames.index(nameOfAddition)] = 0
								if x in aiActions.keys() and y in aiActions[x].keys() and aiActions[x][y][
									allNames.index(nameOfAddition)] > 0:
									totalDeletions += 1
							else:
								# Player Added
								if not x in blocks.keys():
									blocks[x] = {}
								if not y in blocks[x].keys():
									blocks[x][y] = [0] * len(allNames)
								blocks[x][y][allNames.index(nameOfAddition)] = 1
						else:
							if not x in blocks.keys() or not y in blocks[x].keys() or not blocks[x][y] == 1:
								if not x in aiActions.keys():
									aiActions[x] = {}
								if not y in aiActions[x].keys():
									aiActions[x][y] = [0] * len(allNames)
								aiActions[x][y][allNames.index(nameOfAddition)] = 1
								# Bot Added
								if not x in blocks.keys():
									blocks[x] = {}
								if not y in blocks[x].keys():
									blocks[x][y] = [0] * len(allNames)
								totalAdditions += 1
								blocks[x][y][allNames.index(nameOfAddition)] = 1



				elif "Ended Turn" in line:
					s1 = dict(currentPrevState)
					a1 = dict(aiActions)
					s2 = dict(blocks)
					thisSequence.append([s1, a1, s2])

					# totalInteractions+=1
					playerControl = False
					# freeze current prev state
					currentPrevState = dict(blocks)
					aiActions = {}  # erase prior AI actions
				elif "Player Turn" in line:
					playerControl = True
				elif "Starting Run" in line:
					designMode = False
					lastHit = 0
				elif "Grid Cleared" in line and not designMode:
					splits = line.split("time = ")
					lastHit = float(splits[-1])
		if not len(aiActions.keys()) == 0:
			# Final state
			s1 = copy.deepcopy(currentPrevState)
			a1 = copy.deepcopy(aiActions)
			s2 = copy.deepcopy(blocks)
			thisSequence.append([s1, a1, s2])

		if not blocks.keys() == 0 and len(thisSequence) > 0:
			# Determine training values
			#splits = str(file_name).split("/")
			#splits2 = splits[-1].split(".")
			playerID = file_name.stem
			thisScore = 0
			if playerID in finalScores.keys():
				thisScore = finalScores[playerID]

			trainingSequence = []
			for j in range(0, len(thisSequence)):
				currSequence = thisSequence[len(thisSequence) - 1 - j]

				# Initialize
				X = []  # Current full level
				Y = []  # Additions
				for x in range(0, 100):
					column = []
					columnY = []
					for y in range(0, 15):
						columnY.append([0] * len(actions))
						column.append([0] * len(allNames))
					X.append(column)
					Y.append(columnY)

				# Copy over state
				for x in currSequence[0].keys():
					for y in currSequence[0][x].keys():
						X[x][y] = currSequence[0][x][y]

				# Determine addition weights
				for x in currSequence[1].keys():
					for y in currSequence[1][x].keys():
						noAction = True
						for z in range(0, len(actions) - 1):
							# Found an action
							if currSequence[1][x][y][z] == 1:
								noAction = False
								reward = 0
								if j == 0:
									reward = thisScore
								# Did player delete what the AI Added
								if not currSequence[1][x][y][z] == currSequence[2][x][y][z]:
									reward -= 0.1

								value = reward
								if not j == 0:
									value += (gamma ** j) * max(trainingSequence[-1][1][x][y])

								Y[x][y][z] = value

						if noAction:
							# Handle emptiness
							# We added nothing, was that right?
							reward = 0
							if j == 0:
								reward = thisScore
							# Did player change anything
							if not currSequence[1][x][y] == currSequence[2][x][y]:
								reward -= 0.1
							value = reward
							if not j == 0:
								value += (gamma ** j) * max(trainingSequence[-1][1][x][y])
							Y[x][y][z] = value
				trainingSequence.append([X, Y])
			SARSAS.append(thisSequence)
			splits = playerID.split("-")
			playerIDForReal = splits[0]
			if not playerIDForReal in trainingExamplesByPlayer:
				trainingExamplesByPlayer[playerIDForReal] = []
			trainingExamplesByPlayer[playerIDForReal].append(trainingSequence)

	return trainingExamplesByPlayer
def create_training_test_split(trainingExamplesByPlayer):
	'''
	taken from yalini_test.py / test.py
	'''
	finalTrainingSet = []
	finalTestingSet = []
	totalTestNumber = int(len(trainingExamplesByPlayer.keys()) * 0.2) #Train: 880, Test: 176
	for key in trainingExamplesByPlayer.keys():
		if not key in testNames:
			for xy in trainingExamplesByPlayer[key]:
				finalTrainingSet += xy
		else:
			for xy in trainingExamplesByPlayer[key]:
				finalTestingSet += xy
	return finalTrainingSet, finalTestingSet
def construct_training_windows(finalTrainingSet):
	'''
	Taken from yalini_test.py / test.py
	'''
	trainX = []
	trainY = []
	full_map_width = 100
	full_map_height = 15
	window_width = 40
	for xy in finalTrainingSet:
		largeX = xy[0]
		largeY = xy[1]

		minPointX = 1000 # Higher, so we can easily beat it
		maxPointX = 0  # Lower, so we can easily beat it
		for x in range(0, full_map_width):
			for y in range(0, full_map_height):
				maxValue = max(largeY[x][y])
				minValue = min(largeY[x][y])
				maxValueIndex = largeY[x][y].index(maxValue)
				minValueIndex = largeY[x][y].index(minValue)
				if (maxValue>0 and maxValueIndex<len(actions)-1) or (minValue<0 and minValueIndex<len(actions)-1):
					if x<minPointX:
						minPointX = x
					if x>maxPointX:
						maxPointX = x

		if minPointX == 1000:
			# Pick a random position
			finalx = []
			finaly = []
			randXStart = random.randint(0, full_map_width - window_width)
			for x in range(randXStart, randXStart + window_width):
				column = []
				columny = []
				for y in range(0, full_map_height):
					column.append(list(largeX[x][y]))
					columny.append(list(largeY[x][y]))
				finalx.append(column)
				finaly.append(columny)
			trainX.append(finalx)
			trainY.append(finaly)
		else:
			if (maxPointX - minPointX) > window_width:
				for i in range(0, (maxPointX - minPointX) - window_width):
					finalx = []
					finaly = []
					for x in range(i, i + window_width):
						column = []
						columny = []
						for y in range(0, full_map_height):
							column.append(list(largeX[x][y]))
							columny.append(list(largeY[x][y]))
						finalx.append(column)
						finaly.append(columny)
					trainX.append(finalx)
					trainY.append(finaly)
			else:
				# Center on this point
				midPoint = int(minPointX + (maxPointX - minPointX) / 2)
				if midPoint + 20 >= full_map_width:
					midPoint -= (midPoint + 20) - full_map_width
				if midPoint - 20 < 0:
					midPoint += -1 * midPoint - 20
				finalx = []
				finaly = []
				for x in range(midPoint - 20, midPoint + 20):
					column = []
					columny = []
					for y in range(0, full_map_height):
						column.append(list(largeX[x][y]))
						columny.append(list(largeY[x][y]))
					finalx.append(column)
					finaly.append(columny)
				trainX.append(finalx)
				trainY.append(finaly)

	trainX = np.array(trainX, dtype=np.float32)
	trainY = np.array(trainY, dtype=np.float32)
	trainX = np.reshape(trainX, (-1, window_width, full_map_height, len(allNames)))
	trainY = np.reshape(trainY, (-1, window_width, full_map_height, len(actions)))
	return trainX, trainY

def load_datasets():
	finalScores = load_final_scores()
	trainingExamplesByPlayer = load_training_examples_by_player(finalScores)
	finalTrainingSet, finalTestingSet = create_training_test_split(trainingExamplesByPlayer)
	trainX, trainY = construct_training_windows(finalTrainingSet)
	testX, testY = construct_training_windows(finalTestingSet)
	return trainX, trainY, testX, testY
#endregion
# ————— END DATA LOADING ————— #





# ————— PUBLIC API ————— #
def pre_training(force_train: bool = False):

	if MODEL_PATH.exists() and not force_train:
		print("[Pretraining] We already have a model, we are not re-training")
		return

	finalScores = load_final_scores()
	trainingExamplesByPlayer = load_training_examples_by_player(finalScores)
	finalTrainingSet, finalTestingSet = create_training_test_split(trainingExamplesByPlayer)
	trainX, trainY = construct_training_windows(finalTrainingSet)
	# build the model with the same code as before
	model = server_build_model()
	model.fit(x=trainX,
			  y=trainY,
			  epochs=40,
			  batch_size=32,
			  shuffle=True,
			  verbose=0,
			  callbacks=[TqdmCallback(verbose=1)])

	# Server.py loads this same path on startup
	Path(MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
	model.save_weights(MODEL_PATH)
	print(f"Saved {MODEL_PATH}")
# ————— END PUBLIC API ————— #



def main():
	pre_training()


if __name__ == '__main__':
	main()