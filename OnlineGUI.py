import tkinter as tk
from tkinter import messagebox

from CustomWidgets import *
from UICommonPart import GUI_Common
from Game import *
from Code2CardList import *
from GenerateRNGPools import *

import socket
import numpy
import threading
import pickle

def pickleObj2Bytes(obj):
	s = pickle.dumps(obj, 0)
	print("bytes from obj is", s)
	return s
	
def unpickleBytes2Obj(s):
	obj = pickle.loads(s)
	print("objs from bytes is ", obj)
	return obj
	
	
class MulliganFinishButton_3(tk.Button):
	def __init__(self, GUI):
		tk.Button.__init__(self, master=GUI.GamePanel, text="Replace Card", bg="green3", width=13, height=3, font=("Yahei", 12, "bold"))
		self.GUI = GUI
		self.configure(command=self.respond)
		
	def respond(self):
		GUI = self.GUI
		ID, game = GUI.ID, GUI.Game
		indices = [i for i, status in enumerate(GUI.mulliganStatus) if status]
		game.Hand_Deck.mulligan1Side(ID, indices) #之后生成一个起手调度信息
		#牌库和起始手牌决定
		handsAndDecks = [[type(card) for card in game.Hand_Deck.hands[ID]], [type(card) for card in game.Hand_Deck.decks[ID]]]
		s = b"Exchange Deck&Hand||%d||%s"%(ID, pickleObj2Bytes(handsAndDecks))
		GUI.sock.sendall(s)
		while True: #得到的回复可能是b"Wait for Opponent's Mulligan", b"Decks and Hands decided"
			data = GUI.sock.recv(1024)
			if data:
				if data.startswith(b"Wait for Opponent's Mulligan"): #把自己完成的手牌和牌库会给对方
					messagebox.showinfo(message="Wait for opponent to finish mulligan")
				elif data.startswith(b"P1 Initiates Game"):
					action, handsAndDecks = data.split(b"||")
					game = GUI.Game
					hands, decks = unpickleBytes2Obj(handsAndDecks)
					game.Hand_Deck.decks[2] = [card(game, 2) for card in decks]
					game.Hand_Deck.hands[2] = [card(game, 2) for card in hands]
					GUI.UI = 0
					GUI.update()
					game.Hand_Deck.startGame()
					guides = game.fixedGuides
					game.guides, game.fixedGuides = [], []
					GUI.sock.sendall(b"P1 Sends Start of Game RNG||"+pickleObj2Bytes(guides))
					#游戏开始时的那些随机过程会被发送给对方，而自己可以开始自己的游戏
					break
				elif data.startswith(b"P2 Starts Game After P1"): #会携带对方完成的游戏定义
					action, handsAndDecks, guides = data.split(b"||")
					game = GUI.Game
					hands, decks = unpickleBytes2Obj(handsAndDecks)
					game.Hand_Deck.decks[1] = [card(game, 1) for card in decks]
					game.Hand_Deck.hands[1] = [card(game, 1) for card in hands]
					GUI.UI = 0
					game.guides = unpickleBytes2Obj(guides)
					GUI.update()
					game.Hand_Deck.startGame()
					break
		if GUI.ID == 2:
			print("Start waiting for the opponent to make moves")
			GUI.wait4EnemyMovefromServer()
		else:
			print("Start making your moves")
			
	def plot(self, x, y):
		self.place(x=x, y=y, anchor='c')
		self.GUI.btnsDrawn.append(self)
		
		
class Button_Connect2Server(tk.Button):
	def __init__(self, GUI):
		tk.Button.__init__(self, master=GUI.initConnPanel, bg="green3", text="Connect", font=("Yahei", 15), width=20)
		self.GUI = GUI
		self.bind("<Button-1>", self.leftClick)
		
	def leftClick(self, event): #在这时检测所带的卡组是不正确
		deckCorrect, deck, hero = self.GUI.decideDeckandClass()
		if deckCorrect: #卡组正确时可以尝试连接服务器
			self.GUI.initConntoServer(hero, deck)
		else:
			messagebox.showinfo(message="Deck code is wrong. Check before retry")
			
			
#import tkinter.font as tkFont
#fontStyle = tkFont.Font(family="Lucida Grande", size=3)
class GUI_Online(GUI_Common):
	def __init__(self):
		self.mulliganStatus, self.btnsDrawn = [], []
		self.selectedSubject = ""
		self.subject, self.target, self.discover = None, None, None
		self.position, self.choice, self.UI = -1, 0, -2 #起手调换的UI为-2
		self.boardID, self.ID = '', 1
		self.window = tk.Tk()
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.waiting4Server = False
		
		self.initConnPanel = tk.Frame(master=self.window, width=0.005*X, height=int(0.6*Y))
		self.initConnPanel.pack(side=tk.TOP)
		
		tk.Label(self.initConnPanel, text="Enter your deck code below", 
				font=("Yahei", 15)).grid(row=0, column=0)
		self.ownDeck = tk.Entry(self.initConnPanel, text="", font=("Yahei", 15, "bold"), width=20)
		self.ownDeck.grid(row=1, column=0)
		
		self.hero = tk.StringVar(self.initConnPanel)
		self.hero.set(list(ClassDict.keys())[0])
		heroOpt = tk.OptionMenu(self.initConnPanel, self.hero, *list(ClassDict.keys()))
		heroOpt.config(width=15, font=("Yahei", 15))
		heroOpt["menu"].config(font=("Yahei", 15))
		heroOpt.grid(row=2, column=0)
		#连接所需的数据，服务器IP address, port以及申请预订或者加入的桌子ID
		self.serverIP = tk.Entry(self.initConnPanel, font=("Yahei", 15), width=10)
		self.queryPort = tk.Entry(self.initConnPanel, font=("Yahei", 15), width=10)
		self.tableID = tk.Entry(self.initConnPanel, font=("Yahei", 15), width=10)
		self.serverIP.insert(0, "127.0.0.1")
		self.queryPort.insert(0, "65432")
		self.tableID.insert(0, "%d"%numpy.random.randint(6000))
		
		self.serverIP.grid(row=0, column=1)
		self.queryPort.grid(row=1, column=1)
		self.tableID.grid(row=2, column=1)
		tk.Label(self.initConnPanel, text="Server IP", 
				font=("Yahei", 15)).grid(row=0, column=2, sticky=tk.W)
		tk.Label(self.initConnPanel, text="Query Port", 
				font=("Yahei", 15)).grid(row=1, column=2, sticky=tk.W)
		tk.Label(self.initConnPanel, text="Start/Join Table", 
				font=("Yahei", 15)).grid(row=2, column=2, sticky=tk.W)
		Button_Connect2Server(self).grid(row=3, column=1, columnspan=2)
		
		self.window.mainloop()
		
	def initConntoServer(self, hero, deck):
		serverIP = self.serverIP.get()
		try: self.sock.connect((serverIP, int(self.queryPort.get()))) #Blocks. If the server port turns this attempt down, it raises error
		except ConnectionRefusedError:
			messagebox.showinfo(message="Can't connect to the server's query port")
			return
		data = self.sock.recv(1024)
		if data.startswith(b"Ports"): #b"Ports,65433,65434"
			print("Received available ports", data)
			ports = data.decode().split(',')[1:]
			print("Now trying to connect to an available port", ports[0])
			self.sock.close()
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.sock.connect((serverIP, int(ports[0]))) #Take the first available port returned from the server
			#Send the server the hero info and deck info, and tableID to request
			tableID = self.tableID.get()
			print("Attemp to start/join a table with ID", tableID, type(tableID.encode()), type(bytes(tableID.encode())))
			self.sock.sendall(b"Start/Join a Table||%s||%s"%(bytes(tableID.encode()), pickleObj2Bytes(hero)) )
			print("Waiting for response from server about START/JOIN TABLE request")
			data = self.sock.recv(1024) #socket之间的连接中断时，socket本身不会立即报错，而是会在尝试发送信息的时候才会发现错误 
			print("Received response to START/JOIN TABLE request:", data)
			if data:
				if data == b"Table reserved. Wait": #向服务发送预订/加入桌子的申请后，服务器会返回ID对已经被占用 / 或者预订成功
					print("Your table has been reserved. Start waiting for an opponent to join the table")
					data = self.sock.recv(1024) #期待收到b"Start Mulligan|1|26 Darkmoon Faire|Uther",从而开始起手调度过程
					if data: #开始起手调度,需要初始化游戏
						print("Game started. Start mulligan")
						action, self.ID, self.boardID, enemyHero = data.split(b'||')
						self.ID, self.boardID = int(self.ID), str(self.boardID.decode())
						enemyHero = unpickleBytes2Obj(enemyHero)
						game = Game(self)
						#需要生成一下cardPool
						board, self.transferStudentType = makeCardPool(monk=0, board=self.boardID)
						from CardPools import Classes, ClassesandNeutral, ClassDict, cardPool, MinionsofCost, RNGPools
						if self.ID == 1: #起手要换的牌会在游戏的初始过程中直接决定
							game.initialize(cardPool, MinionsofCost, RNGPools, hero, enemyHero, deck, deck)
						else:
							game.initialize(cardPool, MinionsofCost, RNGPools, enemyHero, hero, deck, deck)
						game.mode = 0
						self.UI, self.Game = -2, game
						game.Classes, game.ClassesandNeutral = Classes, ClassesandNeutral
						self.initConnPanel.destroy()
						self.initMuliganUI()
						
				elif data == b"Use another table ID":
					messagebox.showinfo(message="This table ID is already taken.")
		elif data == b"No Ports Left":
			messagebox.showinfo(message="No tables left. Please wait")
		else:
			print("Received smth else", data)
			
	def initSidePartofUI(self):
		self.GamePanel = tk.Frame(self.window, width=X, height=Y, bg="black")
		self.GamePanel.pack(fill=tk.Y, side=tk.LEFT if LeftorRight else tk.RIGHT)
		self.outputPanel = tk.Frame(self.window, width=0.005*X, height=int(0.2*Y), bg="cyan")
		self.outputPanel.pack(side=tk.TOP)
		self.inputPanel = tk.Frame(self.window, width=int(0.005*X), height=int(0.3*Y), bg="cyan")
		self.inputPanel.pack(side=tk.TOP)
		#The box of the output text printing the progress of the game
		lbl_Output = tk.Label(self.outputPanel, text="System Resolution", font=("Yahei", 15))
		scrollbar_hor = tk.Scrollbar(self.outputPanel, orient="horizontal")
		scrollbar_ver = tk.Scrollbar(self.outputPanel)
		self.output = tk.Listbox(self.outputPanel, xscrollcommand=scrollbar_hor.set, yscrollcommand=scrollbar_ver.set, width=40, height=6, bg="white", font=("Yahei", 13))
		scrollbar_hor.configure(command=self.output.xview)
		scrollbar_ver.configure(command=self.output.yview)
		scrollbar_ver.pack(fill=tk.Y, side=tk.RIGHT)
		scrollbar_hor.pack(fill=tk.X, side=tk.BOTTOM)
		lbl_Output.pack(fill=tk.X, side=tk.TOP)
		self.output.pack(side=tk.LEFT)
		
		self.lbl_Card = tk.Label(self.inputPanel, text="Resolving Card Effect")
		self.lbl_wish = tk.Label(master=self.inputPanel, text="Type Card You Wish", font=("Yahei", 15))
		self.wish = tk.Entry(master=self.inputPanel, font=("Yahei", 12))
		self.lbl_Card.pack(fill=tk.X)
		
	def initMuliganUI(self):
		self.initSidePartofUI()
		self.initGameDisplay()
		self.UI = -2
		self.heroZones[1].draw()
		self.heroZones[2].draw()
		self.canvas.draw()
		self.printInfo("The game starts. Select the cards you want to replace. Then click the button at the center of the screen")
		self.mulliganStatus = [0] * len(self.Game.mulligans[self.ID])
		#其他的两个GUI里面都是直接用update(),这里专门写一下
		for i, card in enumerate(self.Game.mulligans[self.ID]):
			pos = (shift+100+i*2*111, Y/2)
			MulliganButton(self, card).plot(x=pos[0], y=pos[1])
		MulliganFinishButton_3(self).plot(x=X/2, y=Y/2)
		
	def sendOwnMovethruServer(self):
		game = GUI.Game
		moves, gameGuides = game.moves, game.fixedGuides
		game.moves, game.fixedGuides = [], []
		if moves:
			s = b"Game Move||"+ pickleObj2Bytes(moves) + "||" + pickleObj2Bytes(gameGuides)
			GUI.conn.sendall(s)
			
	#Enter enemy's turn. Continously wait till it's your turn again.
	def startWaitingforEnemyMoves(self):
		self.sendOwnMovethruServer()
		#开始一个线程，希望达到的目标是让等待程序在此期间可以让玩家有右键点击等行为
		self.waiting4Server = True
		thread = threading.Thread(target=self.wait4EnemyMovefromServer, daemon=True)
		print("Start waiting for enemy moves from server")
		thread.start()
		
	def wait4EnemyMovefromServer(self):
		while self.waiting4Server:
			data = self.conn.recv(1024)
			if data:
				if data.startswith(b"TurnEnds"):
					self.waiting4Server = False
				self.decodePlayfromServer(data)
				
	def decodePlayfromServer(self):
		data = self.conn.recv(1024)
		moves, gameGuides = data.split(b"||")
		moves, gameGuides = unpickleBytes2Obj(moves), unpickleBytes2Obj(gameGuides)
		if isinstance(moves, list):
			self.printInfo("Reads in play")
			for move in moves:
				self.printInfo(move)
			self.Game.evolvewithGuide(moves, gameGuides)
			self.update()
		else: #需要能够处理在游戏正式开始之前
			pass
		#如果结束之后进入了玩家的回合，则不再等待对方的操作
		if self.ID == self.Game.turn:
			self.waiting4Server = False
			
	def decideDeckandClass(self):
		deck, hero = [], ClassDict[self.hero.get()]
		deckString, deckCorrect = self.ownDeck.get(), True
		if deckString:
			if deckString.startswith("names||"):
				deckString = deckString.split('||')
				deckString.pop(0)
				for name in deckString:
					if name != "": deck.append(cardName2Class(name))
			else: deck = decode_deckstring(deckString)
		for obj in deck:
			if obj is None: deckCorrect = False
		if deckCorrect:
			for card in deck:
				if card.Class != "Neutral" and "," not in card.Class:
					hero = ClassDict[card.Class] #The hero will be changed to the first non-neutral&non-dual cards
					break
		return deckCorrect, deck, hero
		
		
GUI_Online()