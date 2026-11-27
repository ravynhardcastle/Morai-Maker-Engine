# ————— IMPORTS ————— #

from Pretraining import data_path, scores_path, testNames # use the same ones from Pretraining.py
# ————— END IMPORTS ————— #

# ————— CONSTANTS ————— #
data_path = Path(__file__).resolve().parent.parent / "Pretraining" / "AgentTraining" / "Log Data"
# ————— END CONSTANTS ————— #

'''
Notes to self:

Game Starts on the players turn!

Ended Turn:  time = 46.3905 Marks the end (MARKS THE END OF THE PLAYERS TURN, AND THE START OF THE AI TURN

Player Turn:  time = 21.63811 Marks the end of AI turn, and the START of the Player Turn

Placing tile on existing tile deletes it

'''

'''
Extraction format:
TBD

'''

def main():
	pass


if __name__ == "__main__":
	main()