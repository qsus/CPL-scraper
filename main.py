#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
from time import sleep

# load config
config = json.load(open("config.json", "r"))

class Scraper:
	def __init__(self, config) -> None:
		self.webhook: str = config["webhook"]
		self.sendWebhooks: bool = config["sendWebhooks"]
		self.webUrl: str = config["webUrl"]
		self.interval: int = config["interval"]
		self.currentData: list[dict] | None = None # None before first updateMatches
		self.currentRound: str | None = None
		self.messages: dict = config["messages"]
		self.discordNotifications: dict = config["discordNotifications"]
		self.dateOffset: int = config["dateOffset"]

	def sendWebhook(self, message: str) -> None:
		print(message.replace("*", "").replace("_", ""))
		if self.sendWebhooks:
			requests.post(self.webhook, json={"content": message})

	def getNewMatches(self) -> tuple[str, list[dict]]:
		res = requests.get(self.webUrl + "curround.php")
		soup = BeautifulSoup(res.text, "html.parser")
		gameHTMLs = soup.find_all('tr', attrs={'class':'listrow'})
		# find round description; reliability questionable
		round = soup.find('div', attrs={'class':'pagecontent'}).find_all("div")[1].text
		gameObjects = []
		for gameHTML in gameHTMLs:
			gameHTML = gameHTML.find_all('td', attrs={'class':'listcell'}) # split
			gameObject = {
				"table": gameHTML[0].text,
				"dateStatus": None,
				"date": gameHTML[1].text[self.dateOffset:],
				"player1": gameHTML[2].text[3:-1],
				"player2": gameHTML[6].text[3:-1],
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

		return round, gameObjects
	
	def notifyChanges(self, newRound: str, newData: list[dict]) -> None:
		# compare round
		if self.currentRound and self.currentRound != newRound:
			self.sendWebhook(f"Začalo **nové kolo**! _{newRound}_")
			return

		# if first run, do not notify
		if not self.currentData:
			return

		# prefix all urls
		for newGameData in newData:
			newGameData["resultUrl"] = self.webUrl + newGameData["resultUrl"]

		# iterate tables in the current round; O(n^2) and three indent levels, but it works
		for currentGameData in self.currentData:
			for newGameData in newData:
				if currentGameData["table"] == newGameData["table"]:
					message: str | None = None
					# compare date
					if currentGameData["dateStatus"] == newGameData["dateStatus"] \
					or currentGameData["date"]       != newGameData["date"]:
						match newGameData["dateStatus"]:
							case "no":
								message = self.messages["dateRevoked"].format_map(newGameData)
							case "offered":
								message = self.messages["dateOffered"].format_map(newGameData)
							case "approved":
								message = self.messages["dateAccepted"].format_map(newGameData)
						
					# compare results (comparing only one result is enough)
					if currentGameData["resultStatus"] != newGameData["resultStatus"] \
					or currentGameData["result1"]      != newGameData["result1"]:
						match newGameData["resultStatus"]:
							case "no":
								message = self.messages["resultRevoked"].format_map(newGameData)
							case "offered":
								message = self.messages["resultOffered"].format_map(newGameData)
							case "approved":
								message = self.messages["resultApproved"].format_map(newGameData)

					# if we know message is about to be sent, add mentions for relevant players
					if message:
						# using wulrus operator := sets id value and then does if check
						if id := self.discordNotifications.get(newGameData["player1"]):
							message += f" <@{id}>"
						if id := self.discordNotifications.get(newGameData["player2"]):
							message += f" <@{id}>"

						self.sendWebhook(message)
					
	def update(self) -> None:
		newRound, newData = self.getNewMatches()
		self.notifyChanges(newRound, newData)
		self.currentRound = newRound
		self.currentData = newData
					

scraper = Scraper(config)

try:
	print("\033[91mWebhooks will be sent: " + str(config["sendWebhooks"]) + "\033[0m")
	while True:
		print("Updating matches...")
		scraper.update()
		sleep(config["interval"])
except KeyboardInterrupt:
	print("Exiting...")
except Exception as e:
	scraper.sendWebhook(config["errorMessage"])
	print(e)
