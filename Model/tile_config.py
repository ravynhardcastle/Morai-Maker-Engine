# ————— Configs for tile types ————— #
# All names of tiles
allNames = [
	'Ground',
	'Stair',
	'Treetop',
	'Block',
	'Bar',
	'Koopa',
	'Koopa 2',
	'PipeBody',
	'Pipe',
	'Question',
	'Coin',
	'Goomba',
	'CannonBody',
	'Cannon',
	'Lakitu',
	'Bridge',
	'Hard Shell',
	'SmallCannon',
	'Plant',
	'Waves',
	'Hill',
	'Castle',
	'Snow Tree 2',
	'Cloud 2',
	'Cloud',
	'Bush',
	'Tree 2',
	'Bush 2',
	'Tree',
	'Snow Tree',
	'Fence',
	'Bark',
	'Flag',
	'Mario'
]
# All names of actions
actions = [
	'Ground',
	'Stair',
	'Treetop',
	'Block',
	'Bar',
	'Koopa',
	'Koopa 2',
	'PipeBody',
	'Pipe',
	'Question',
	'Coin',
	'Goomba',
	'CannonBody',
	'Cannon',
	'Lakitu',
	'Bridge',
	'Hard Shell',
	'SmallCannon',
	'Plant',
	'Waves',
	'Hill',
	'Castle',
	'Snow Tree 2',
	'Cloud 2',
	'Cloud',
	'Bush',
	'Tree 2',
	'Bush 2',
	'Tree',
	'Snow Tree',
	'Fence',
	'Bark',
	'Nothing'
]


'''
Old function body here as a backup / refernece

				dataSplits = data.split("|")

				currMap = StringToMap(dataSplits[0], allNames)

				thisStartX = int(dataSplits[1])
				# Retrain
				if not prevMap == None and abs(thisStartX - prevStartX) < 30:
					anyChange = False
					differenceX = thisStartX - prevStartX
					for x in range(0, 40):
						if x + differenceX < 40 and x + differenceX >= 0:
							for y in range(0, 15):
								for z in range(0, len(actions)):
									if prevAction[x + differenceX][y][z] > 0:
										if currMap[x][y][z] > 0:
											anyChange = True
											prevAction[x + differenceX][y][z] += 0.1
										else:
											anyChange = True
											prevAction[x + differenceX][y][z] -= 0.1

											print("REMOVED: " + str([actions[z], x + thisStartX, y]))
									elif currMap[x][y][z] > 0:
										anyChange = True
										prevAction[x + differenceX][y][z] += 0.1
						# LEARN
					if anyChange:
						minimumInteractionConfidence += confidenceDelta
						print("RETRAIN")
						model.fit([prevMap],
								  Y_targets=[prevAction],
								  n_epoch=1,
								  shuffle=False,
								  show_metric=False,
								  snapshot_epoch=False,
								  batch_size=1,
								  run_id='activeLearning')

				predY = model.predict([currMap])
				thisAction = GetEmptyMap(actions)

				# REPLY
				toString = ""
				nothingSent = True
				maxToSend = []
				maxVal = -1

				sents = []
				for x in range(0, 40):
					for y in range(0, 15):
						for z in range(0, len(actions)):
							if predY[0][x][y][z] > minimumInteractionConfidence and currMap[x][y][z] == 0 and len(
									sents) < 30:
								if not [actions[z], x + thisStartX, y] in rejections:
									conn.send(str(x) + "," + str(y) + "," + str(z) + "," + str(predY[0][x][y][z]) + "*")
									sents.append([x, y, z])
									print("SENDING: " + str([actions[z], x + thisStartX, y, predY[0][x][y][z]]))
									rejections.append([actions[z], x + thisStartX, y])
									# print ("     EXPLANATION: "+GetExplanation(convW, currMap, x, y, allNames))
									thisAction[x][y][z] = predY[0][x][y][z]
									nothingSent = False
							elif nothingSent:
								if predY[0][x][y][z] > maxVal and currMap[x][y][z] == 0 and not z == len(actions) - 1:
									if not [actions[z], x + thisStartX, y] in rejections:
										maxToSend = [x, y, z, predY[0][x][y][z]]
										maxVal = predY[0][x][y][z]
				# MUST DO SOMETHING
				if nothingSent:
					thisAction[x][y][z] = minimumInteractionConfidence + confidenceDelta
					sents.append([x, y, z])
					print("FAILURE CASE: " + str([actions[maxToSend[2]], maxToSend[0], maxToSend[1], maxToSend[3]]))
					conn.send(
						str(maxToSend[0]) + "," + str(maxToSend[1]) + "," + str(maxToSend[2]) + "," + str(
							maxToSend[3]) + "*")
				conn.close()  # Close

				# PRINT MAP
				
				currMapStr = ""
				for y in range(14, -1, -1):
					line = ""
					for x in range(0, 40):
						if 1 in currMap[x][y]:
							line+= allNames[currMap[x][y].index(1)]+"-"
						else:
							line+="      -"
					currMapStr+=line+"\n"
				print (currMapStr)
				
				# EXPLANATIONS (commented out for now)
				
				convW = np.array(model.get_weights(conv.W))
				for sent in sents:
					print("---")
					print("FOR SENT: " + str([actions[sent[2]], sent[0], sent[1], predY[0][sent[0]][sent[1]][sent[2]]]))
					if 1 in currMap[sent[0]][sent[1]]:
						# WHY IS THIS NOT HIT????
						print("IN CURR MAP: " + str(allNames[currMap[sent[0]][sent[1]].index(1)]))
					print("EXPLAIN:\n" + GetExplanation(convW, currMap, sent[0], sent[1], allNames))
				

				prevMap = list(currMap)
				prevAction = list(thisAction)
				prevStartX = thisStartX
				conn, addr = socket.accept()  # Reset
		except KeyboardInterrupt:
			conn.close()
			del conn
			break
'''