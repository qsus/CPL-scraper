#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
from time import sleep

# load config
config = json.load(open("config.json", "r"))
webhook = config["webhook"]
sendWebhooks = config["sendWebhooks"]
webUrl = config["webUrl"]
interval = config["interval"]

def sendWebhook(message):
	print(message.replace("*", "").replace("_", ""))
	if sendWebhooks: requests.post(webhook, json={"content": message})

def updateMatches():
	# read old data
	oldData = json.load(open("matches.json", "r"))
	oldGameObjects = oldData["matches"]
	
	res = requests.get(webUrl + "curround.php")
	soup = BeautifulSoup(res.text, "html.parser")
	gameHTMLs = soup.findAll('tr', attrs={'class':'listrow'})
	# find round description; reliability questionable
	round = soup.find('div', attrs={'class':'pagecontent'}).findAll("div")[1].text
	gameObjects = []
	for gameHTML in gameHTMLs:
		gameHTML = gameHTML.findAll('td', attrs={'class':'listcell'}) # split
		gameObject = {
			"table": gameHTML[0].text,
			"dateStatus": None,
			"date": gameHTML[1].text[17:],
			"player1": gameHTML[2].text[5:-1],
			"player2": gameHTML[6].text[5:-1],
			"resultStatus": None,
			"result1": gameHTML[3].text,
			"result2": gameHTML[5].text,
			"resultUrl": gameHTML[0].find("a")["href"]
		}
		# deteremine date status
		if gameObject["date"] == "":
			gameObject["dateStatus"] = "no"
		elif gameHTML[1].find("span") == None: # date not colored in gray
			gameObject["dateStatus"] = "approved"
		else:
			gameObject["dateStatus"] = "offered"
		
		# determine result status; only checking result 1
		if gameObject["result1"] == "":
			gameObject["resultStatus"] = "no"
		elif gameHTML[3].find("span") == None: # result not colored in gray
			gameObject["resultStatus"] = "approved"
		else:
			gameObject["resultStatus"] = "offered"


		gameObjects.append(gameObject)

	# save to matches.json
	json.dump({
		"round": round,
		"skipOnce": False,
		"matches": gameObjects
	}, open("matches.json", "w"), indent="  ")

	# comparing
	# force skip
	if oldData["skipOnce"]:
		print("Skipped using skipOnce.")
		return
	# compare round
	if oldData["round"] != round:
		sendWebhook(f"Začalo **nové kolo**! _{round}_")
		return
	# iterate tables in the current round; O(n^2) and three indent levels, but it works
	for oldGameObject in oldGameObjects:
		for gameObject in gameObjects:
			if oldGameObject["table"] == gameObject["table"]:
				# compare date
				if oldGameObject["dateStatus"] != gameObject["dateStatus"] \
				or oldGameObject["date"]       != gameObject["date"]:
					match gameObject["dateStatus"]:
						case "no":
							sendWebhook(f"Navržený termín zápasu mezi **{gameObject['player1']}** a **{gameObject['player2']}** byl __odvolán__.")
						case "offered":
							sendWebhook(f"Pro zápas mezi **{gameObject['player1']}** a **{gameObject['player2']}** byl __navržen__ termín **{gameObject['date']}**.")
						case "approved":
							sendWebhook(f"Pro zápas mezi **{gameObject['player1']}** a **{gameObject['player2']}** byl __schválen__ termín **{gameObject['date']}**.")
					
				# compare results (comparing only one result is enough)
				if oldGameObject["resultStatus"] != gameObject["resultStatus"] \
				or oldGameObject["result1"]      != gameObject["result1"]:
					match gameObject["resultStatus"]:
						case "no":
							sendWebhook(f"<@865535260804775936> Error, please check console. (resultStatus == no)")
						case "offered":
							sendWebhook(f"Zápas mezi **{gameObject['player1']}** a **{gameObject['player2']}** skončil nepotvrzeným [výsledkem]({webUrl + gameObject['resultUrl']}) **{gameObject['result1']}:{gameObject['result2']}**.")
						case "approved":
							sendWebhook(f"Zápas mezi **{gameObject['player1']}** a **{gameObject['player2']}** skončil potvrzeným [výsledkem]({webUrl + gameObject['resultUrl']}) **{gameObject['result1']}:{gameObject['result2']}**.")
					


try:
	print("\033[91mWebhooks will be sent: " + str(sendWebhooks) + "\033[0m")
	while True:
		print("Updating matches...")
		updateMatches()
		# sleep(60 if production else 10)
		sleep(interval)
except KeyboardInterrupt:
	print("Exiting...")
except Exception as e:
	sendWebhook(f"<@865535260804775936> Error, please check console.")
	print(e)