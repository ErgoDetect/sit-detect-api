import numpy as np
import math


class processData:
    def __init__(self, data):
        self.data = data

    def get_shoulder_position(self):
        if (
            self.data["leftShoulder"] is not None
            and self.data["rightShoulder"] is not None
        ):
            shoulder_left = self.data["leftShoulder"]
            shoulder_right = self.data["rightShoulder"]
            return (shoulder_left["y"] + shoulder_right["y"]) / 2
        elif self.data["leftShoulder"] is not None:
            return self.data["leftShoulder"]["y"]
        elif self.data["rightShoulder"] is not None:
            return self.data["rightShoulder"]["y"]
        return None

    def get_blink_right(self):
        if (
            self.data["rightEye"]["33"] is not None
            and self.data["rightEye"]["133"] is not None
            and self.data["rightEye"]["144"] is not None
            and self.data["rightEye"]["153"] is not None
            and self.data["rightEye"]["158"] is not None
            and self.data["rightEye"]["160"] is not None
        ):
            dis_p1p4 = math.sqrt(
                pow(
                    self.data["rightEye"]["33"]["x"]
                    - self.data["rightEye"]["133"]["x"],
                    2,
                )
                + pow(
                    self.data["rightEye"]["33"]["y"]
                    - self.data["rightEye"]["133"]["y"],
                    2,
                )
            )
            dis_p2p6 = math.sqrt(
                pow(
                    self.data["rightEye"]["160"]["x"]
                    - self.data["rightEye"]["144"]["x"],
                    2,
                )
                + pow(
                    self.data["rightEye"]["160"]["y"]
                    - self.data["rightEye"]["144"]["y"],
                    2,
                )
            )
            dis_p3p5 = math.sqrt(
                pow(
                    self.data["rightEye"]["158"]["x"]
                    - self.data["rightEye"]["153"]["x"],
                    2,
                )
                + pow(
                    self.data["rightEye"]["158"]["y"]
                    - self.data["rightEye"]["153"]["y"],
                    2,
                )
            )
            eAR = (dis_p2p6 + dis_p3p5) / (dis_p1p4)
            return eAR
        return None

    def get_blink_left(self):
        if (
            self.data["leftEye"]["263"] is not None
            and self.data["leftEye"]["362"] is not None
            and self.data["leftEye"]["373"] is not None
            and self.data["leftEye"]["380"] is not None
            and self.data["leftEye"]["385"] is not None
            and self.data["leftEye"]["387"] is not None
        ):
            dis_p1p4 = math.sqrt(
                pow(
                    self.data["leftEye"]["362"]["x"] - self.data["leftEye"]["263"]["x"],
                    2,
                )
                + pow(
                    self.data["leftEye"]["362"]["y"] - self.data["leftEye"]["263"]["y"],
                    2,
                )
            )
            dis_p2p6 = math.sqrt(
                pow(
                    self.data["leftEye"]["385"]["x"] - self.data["leftEye"]["380"]["x"],
                    2,
                )
                + pow(
                    self.data["leftEye"]["385"]["y"] - self.data["leftEye"]["380"]["y"],
                    2,
                )
            )
            dis_p3p5 = math.sqrt(
                pow(
                    self.data["leftEye"]["387"]["x"] - self.data["leftEye"]["373"]["x"],
                    2,
                )
                + pow(
                    self.data["leftEye"]["387"]["y"] - self.data["leftEye"]["373"]["y"],
                    2,
                )
            )
            eAR = (dis_p2p6 + dis_p3p5) / (dis_p1p4)
            return eAR
        return None

    def get_diameter_right(self):
        if self.data["rightIris"]["469"] is not None and self.data["rightIris"]["471"]:
            iris1 = self.data["rightIris"]["469"]
            iris2 = self.data["rightIris"]["471"]
            return math.sqrt(
                pow((iris1["x"] - iris2["x"]), 2) + pow((iris1["y"] - iris2["y"]), 2)
            )
        return None

    def get_diameter_left(self):
        if (
            self.data["leftIris"]["474"] is not None
            and self.data["leftIris"]["476"] is not None
        ):
            iris1 = self.data["leftIris"]["474"]
            iris2 = self.data["leftIris"]["476"]
            return math.sqrt(
                pow((iris1["x"] - iris2["x"]), 2) + pow((iris1["y"] - iris2["y"]), 2)
            )
        return None
