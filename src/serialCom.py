import math
import threading
import time
import serial
import asyncio
import websockets
import json
from src import config


class serialCom:

    def commandThread(self):
        while self.running:
            parseRefCommand(self)

            drive = ("sd:" + str(self.speed[0]) + ":" + str(self.speed[1]) + ":" + str(self.speed[2]) + "\r\n")
            throw = ("d:" + str(self.throwSpeed) + "\r\n")
            print(drive)
            time.sleep(0.0001)
            self.ser.write(drive.encode("utf-8"))
            time.sleep(0.0001)
            self.ser.write(throw.encode("utf-8"))

            while self.ser.inWaiting() > 0:
                self.ser.read()

    def __init__(self):
        #Params
        self.throwSpeed, self.speed = 100, [0, 0, 0]
        self.middle_wheel_angle = 0
        self.forward_movement_angle = 90
        self.right_wheel_angle = 120
        self.left_wheel_angle = 240
        self.running = True
        self.gameStatus = False
        self.baskets = "magenta"
        self.robotID = parser.get("Game", "robotID")
        #Connection to websocket
        self.uri = parser.get("Params", "websocket")
        self.socket = asyncio.get_event_loop()
        self.socket.create_task(self.parseRefCommand())
        self.socket.run_forever()
        #Serial connection
        self.ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.01)
        print(self.ser.name)
        #Thread
        self.w = threading.Thread(name='commandThread', target=self.commandThread)
        self.w.start()

    def gs(self):
        self.ser.write('gs\r\n'.encode("utf-8"))
        response = self.ser.read(20).decode("utf-8")
        print(response)

    # sd:right:middle:left
    def forward(self, speed):
        self.speed = [-speed, 0, speed]

    def reverse(self, speed):
        self.speed = [speed, 0, -speed]

    def left(self, speed):
        self.speed = [-speed, -speed, -speed]

    def right(self, speed):
        self.speed = [speed, speed, speed]

    def move(self, speed):
        self.speed = [speed[0], speed[1], speed[2]]

    def startThrow(self, speed):
        self.throwSpeed = speed

    def stopThrow(self):
        self.throwSpeed = 100

    def stopMoving(self):
        self.speed = [0, 0, 0]

    def rotateAroundBall(self, speed):
        self.speed = [0, speed, 0]

    def calcDirectionAngle(self, robotDirectionAngle, middle_px, X, Y):
        try:
            robotDirectionAngle = int(math.degrees(math.atan((middle_px-X) / Y)) + robotDirectionAngle)
        except ZeroDivisionError:
            robotDirectionAngle = 0.1
        return robotDirectionAngle

    def wheelLinearVelocity(self, robotSpeed, wheelAngle, robotDirectionAngle, middle_px=None, X=None, Y=None):
        if Y is not None and Y != 0:
            robotDirectionAngle = self.calcDirectionAngle(robotDirectionAngle, middle_px, X, Y)
            wheelLinearVelocity = robotSpeed * math.cos(math.radians(robotDirectionAngle - wheelAngle))
        else:
            wheelLinearVelocity = robotSpeed * math.cos(math.radians(robotDirectionAngle - wheelAngle))
        return wheelLinearVelocity

    def omniMovement(self, speed, middle_px, X=None, Y=None):
        self.speed[0] = int(self.wheelLinearVelocity(-speed, self.right_wheel_angle, self.forward_movement_angle, middle_px, X, Y))
        self.speed[1] = int(self.wheelLinearVelocity(-speed, self.middle_wheel_angle, self.forward_movement_angle, middle_px, X, Y))
        self.speed[2] = int(self.wheelLinearVelocity(-speed, self.left_wheel_angle, self.forward_movement_angle, middle_px, X, Y))

    def moveHorizontal(self, speed):
        self.speed[0] = int(self.wheelLinearVelocity(-speed, self.right_wheel_angle, 180))
        self.speed[1] = int(self.wheelLinearVelocity(speed, self.middle_wheel_angle, 180))
        self.speed[2] = int(self.wheelLinearVelocity(-speed, self.left_wheel_angle, 180))

    async def parseRefCommand(self):
        async with websockets.connect(self.uri) as websocket:
            data = await websocket.recv()
            if data != "":
                parse = json.loads(data)
                if len(parse) == 3:
                    if self.robotID in parse['targets']:
                        idx = parse['targets'].index('Io')
                        self.baskets = parse['baskets'][idx]
                        if parse['signal'] == "start":
                            self.gameStatus = True
                elif len(parse) == 2:
                    if self.robotID in parse['targets']:
                        if parse['signal'] == "stop":
                            self.gameStatus = False

    def setStopped(self, stopped):
        self.running = stopped
        self.speed = [0, 0, 0]
        self.socket.stop()
        time.sleep(0.2)
        self.ser.close()



