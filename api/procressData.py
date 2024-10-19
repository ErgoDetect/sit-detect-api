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


# class processData:
#     def __init__(self, data):
#         self.data = data

#     def get_shoulder_position(self):
#         left_shoulder = self.data.get("leftShoulder")
#         right_shoulder = self.data.get("rightShoulder")

#         if left_shoulder and right_shoulder:
#             return (left_shoulder["y"] + right_shoulder["y"]) / 2
#         elif left_shoulder:
#             return left_shoulder["y"]
#         elif right_shoulder:
#             return right_shoulder["y"]
#         return None

#     def calculate_ear(self, points):
#         """Helper function to calculate Eye Aspect Ratio (EAR)"""
#         p1, p2, p3, p4, p5, p6 = points
#         dis_p1p4 = math.hypot(p1["x"] - p4["x"], p1["y"] - p4["y"])
#         dis_p2p6 = math.hypot(p2["x"] - p6["x"], p2["y"] - p6["y"])
#         dis_p3p5 = math.hypot(p3["x"] - p5["x"], p3["y"] - p5["y"])
#         return (dis_p2p6 + dis_p3p5) / dis_p1p4 if dis_p1p4 else None

#     def get_blink_right(self):
#         right_eye = self.data.get("rightEye")
#         if right_eye:
#             points = [
#                 right_eye.get("33"),
#                 right_eye.get("160"),
#                 right_eye.get("158"),
#                 right_eye.get("133"),
#                 right_eye.get("144"),
#                 right_eye.get("153"),
#             ]
#             if all(points):
#                 return self.calculate_ear(points)
#         return None

#     def get_blink_left(self):
#         left_eye = self.data.get("leftEye")
#         if left_eye:
#             points = [
#                 left_eye.get("362"),
#                 left_eye.get("385"),
#                 left_eye.get("387"),
#                 left_eye.get("263"),
#                 left_eye.get("380"),
#                 left_eye.get("373"),
#             ]
#             if all(points):
#                 return self.calculate_ear(points)
#         return None

#     def calculate_iris_diameter(self, iris_points):
#         """Helper function to calculate iris diameter"""
#         p1, p2 = iris_points
#         return math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"])

#     def get_diameter_right(self):
#         right_iris = self.data.get("rightIris")
#         if right_iris:
#             points = [right_iris.get("469"), right_iris.get("471")]
#             if all(points):
#                 return self.calculate_iris_diameter(points)
#         return None

#     def get_diameter_left(self):
#         left_iris = self.data.get("leftIris")
#         if left_iris:
#             points = [left_iris.get("474"), left_iris.get("476")]
#             if all(points):
#                 return self.calculate_iris_diameter(points)
#         return None
