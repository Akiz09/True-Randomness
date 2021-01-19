from datetime import datetime
from enum import Enum, unique, auto
from typing import Tuple, Union

import cv2
import websocket
from simple_pid import PID

from src import config, vision, imageProcessing
from src.referee import Referee
from src.serialCom import serialCom


@unique
class STATE(Enum):
    EMPTYING = auto()
    WAITING = auto()
    FINDING_BALL = auto()
    DRIVING_TO_BALL = auto()
    PICKING_UP_BALL = auto()
    FINDING_BASKET = auto()
    DRIVING_TO_BASKET = auto()
    STARTING_THROWER = auto()
    THROWING_BALL = auto()


class RobotState:
    current: STATE = STATE.WAITING
    target_x: int = 0
    target_y: int = 0
    timer: Union[datetime, None] = 0

    def change_state(self, next_state):
        self.current = next_state
        self.timer = None

    def timer_ms_passed(self):
        if self.timer is None:
            self.timer = datetime.now()
        return (datetime.now() - self.timer).microseconds/1000000

    def timer_seconds_passed(self):
        if self.timer is None:
            self.timer = datetime.now()
        return (datetime.now() - self.timer).seconds


def main():
    state = RobotState()

    parser = config.config()

    image_thread = vision.imageCapRS2()
    #ws = Referee(websocket.create_connection('ws://192.168.2.220:8111/'))
    robot = serialCom()
    distances = []
    teamColor = "magenta"
    basketxs = []
    finaldistance = 0

    middle_px = parser.get('Cam', 'Width') / 2
    toBallSpeed = PID(0.4, 0.00001, 0.0001, setpoint=460)
    toBallSpeed.output_limits = (0, 25)  # Motor limits

    basketCenterSpeed = PID(0.10, 0.000001, 0.00001, setpoint=320)
    basketCenterSpeed.output_limits = (-5, 5)  # Motor limits

    while True:
        frame = image_thread.getFrame()

        if state.current is STATE.EMPTYING:
            #if robot.recive.ir == 1:
            #robot.setIr(1)
            #robot.setServo(100)
            #if state.timer_seconds_passed() > 1.0:
            state.change_state(STATE.WAITING)
            #else:
            #    state.change_state(STATE.WAITING)
        elif state.current is STATE.WAITING:
            # waiting
            robot.setIr(0)
            robot.setServo(0)
            state.change_state(STATE.FINDING_BALL)
            #
        elif state.current is STATE.FINDING_BALL:
            # finding ball
            ballCnts, basketCnts = imageProcessing.getContours(frame, teamColor)
            if len(ballCnts) > 0:
                ball_x, ball_y = imageProcessing.detectObj(frame, ballCnts)
                if ball_y > parser.get('Cam', 'Height') - 35 and ball_y < 470:  # 30 - 60
                    print('found ball')
                    state.change_state(STATE.PICKING_UP_BALL)
                else:
                    robot.omniMovement(int(toBallSpeed(ball_y)), middle_px, ball_x, ball_y)
            else:
                robot.left(5)
            #
        elif state.current is STATE.PICKING_UP_BALL:
            # picking up ball
            robot.forward(10)
            if state.timer_seconds_passed() > 0.5:
                robot.stopMoving()
                robot.setIr(0)
                robot.setServo(50)
                if state.timer_seconds_passed() > 10:
                    robot.setServo(-100)  # eject
                    state.change_state(STATE.FINDING_BALL)  # ball disappeared, restart
                elif robot.recive.ir == 1:
                    state.change_state(STATE.FINDING_BASKET)
                    pass
            #
        elif state.current is STATE.FINDING_BASKET:
            # finding basket
            # to add if basket too close go back a little
            ballCnts, basketCnts = imageProcessing.getContours(frame, teamColor)
            if len(basketCnts) > 0:
                target_x, target_y, w, h = imageProcessing.detectObj(frame, basketCnts, False)
                print("target_x", target_x)
                distance = imageProcessing.calc_distance(w)
                if (len(distances) > 15):
                    distances.pop(0)
                    distances.append(distance)
                    finaldistance = sum(distances) / len(distances)
                else:
                    distances.append(distance)

                dist_from_centerX = 320
                if target_x > -1:
                    dist_from_centerX = middle_px - target_x

                print("dist_from_center", abs(dist_from_centerX))
                basketxs.append(dist_from_centerX)
                if len(basketxs) > 20:
                    basketxs.pop(0)

                if state.timer_seconds_passed() > 9:
                    robot.stopMoving()
                    state.change_state(STATE.DRIVING_TO_BASKET)

                robot.rotate(-basketCenterSpeed(target_x))
            else:
                robot.left(5)
            #
        elif state.current is STATE.DRIVING_TO_BASKET:
            # driving to basket
            state.current = STATE.STARTING_THROWER
            #
        elif state.current is STATE.STARTING_THROWER:
            # starting thrower
            throwSpeed = -0.000161064 * finaldistance**2 + 0.180854 * finaldistance + 14.205
            print(throwSpeed)
            robot.startThrow(throwSpeed)
            if state.timer_ms_passed() > 0.5:
                state.change_state(STATE.THROWING_BALL)
            #
        elif state.current is STATE.THROWING_BALL:
            # throwing ball
            robot.setIr(1)
            if state.timer_seconds_passed() > 2:
                robot.setIr(0)
                robot.setServo(0)
                robot.startThrow(0)
                state.change_state(STATE.FINDING_BALL)
            #
        else:
            raise Exception(f'State not implemented in main(): {state.current}')
        pass

        cv2.putText(frame, str(state.current), (10, 30), cv2.FONT_HERSHEY_DUPLEX, 1,
                    cv2.COLOR_YUV420sp2GRAY)
        cv2.imshow('Processed', frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break

    image_thread.setStopped(False)
    robot.stopThrow()
    robot.setStopped(False)
    cv2.destroyAllWindows()
