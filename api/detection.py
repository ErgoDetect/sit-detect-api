class detection:
    def __init__(self, frame_per_second=1, correct_frame=5):
        # Constants
        self.correct_frame = correct_frame
        self.frame_per_second = frame_per_second
        self.ear_threshold_low = 0.4
        self.ear_threshold_high = 0.5

        # Initialization of variables
        self.response_counter = 0
        self.saved_values = []
        self.correct_values = {}
        self.ear_below_threshold = False
        self.blink_detected = False

        self.latest_nearest_distance = 0
        self.blink_stack = 0
        self.sitting_stack = 0
        self.distance_stack = 0
        self.thoracic_stack = 0

        self.blink_stack_threshold = 5
        self.sitting_stack_threshold = 2700
        self.distance_stack_threshold = 30
        self.thoracic_stack_threshold = 2
        self.result = [
            False,
            False,
            False,
            False,
        ]  # [blink_alert, sitting_alert, distance_alert, thoracic_alert]

        self.timeline_result = {
            "blink": [],
            "sitting": [],
            "distance": [],
            "thoracic": [],
        }
        self.response_counter = 0

    def set_correct_value(self, input):
        self.response_counter += 1
        self.saved_values.append(input)

        def average(values):
            valid_values = [v for v in values if v is not None]
            return sum(valid_values) / len(valid_values) if valid_values else None

        if self.response_counter == self.correct_frame:
            self.correct_values = {
                "shoulderPosition": average(
                    [v["shoulderPosition"] for v in self.saved_values]
                ),
                "diameterRight": average(
                    [v["diameterRight"] for v in self.saved_values]
                ),
                "diameterLeft": average([v["diameterLeft"] for v in self.saved_values]),
            }

    def detect(self, input, faceDetect):
        self.response_counter += 1
        if self.response_counter > self.correct_frame:
            if input["shoulderPosition"] == None:
                self.thoracic_stack = 0
            elif (
                self.correct_values["shoulderPosition"] + 0.05
                <= input["shoulderPosition"]
            ):
                self.thoracic_stack += 1
            else:
                self.thoracic_stack = 0

            if faceDetect == False:
                self.blink_stack = 0
                self.sitting_stack = 0
                self.distance_stack = 0
            else:
                self.sitting_stack += 1

                # Update distance_stack
                diameter_right = input.get("diameterRight")
                diameter_left = input.get("diameterLeft")
                correct_diameter_right = self.correct_values.get("diameterRight")
                correct_diameter_left = self.correct_values.get("diameterLeft")
                self.latest_nearest_distance = max(
                    diameter_right or self.latest_nearest_distance,
                    diameter_left or self.latest_nearest_distance,
                )

                self.correct_distance = max(
                    correct_diameter_right or 0, correct_diameter_left or 0
                )

                if self.correct_distance and self.latest_nearest_distance:
                    if self.correct_distance * 1.10 <= self.latest_nearest_distance:
                        self.distance_stack += 1
                    else:
                        self.distance_stack = 0

                # Update blink_stack
                ear_left = input.get("eyeAspectRatioLeft")
                ear_right = input.get("eyeAspectRatioRight")

                if (ear_left is not None and ear_left <= self.ear_threshold_low) or (
                    ear_right is not None and ear_right <= self.ear_threshold_low
                ):
                    self.ear_below_threshold = True
                    self.blink_stack += 1
                elif self.ear_below_threshold and (
                    (ear_left is not None and ear_left >= self.ear_threshold_high)
                    or (ear_right is not None and ear_right >= self.ear_threshold_high)
                ):
                    if not self.blink_detected:
                        self.blink_stack = 0
                        self.blink_detected = True
                    self.ear_below_threshold = False
                else:
                    self.blink_detected = False
                    self.blink_stack += 1

            if self.blink_stack >= self.blink_stack_threshold * self.frame_per_second:
                if self.result[0] == False:
                    self.timeline_result["blink"].append([])
                    self.timeline_result["blink"][
                        len(self.timeline_result["blink"]) - 1
                    ].append(self.response_counter - self.blink_stack_threshold)
                self.result[0] = True
            else:
                if self.result[0] == True:
                    self.timeline_result["blink"][
                        len(self.timeline_result["blink"]) - 1
                    ].append(self.response_counter)
                self.result[0] = False

            if (
                self.sitting_stack
                >= self.sitting_stack_threshold * self.frame_per_second
            ):
                if self.result[1] == False:
                    self.timeline_result["sitting"].append([])
                    self.timeline_result["sitting"][
                        len(self.timeline_result["sitting"]) - 1
                    ].append(self.response_counter - self.sitting_stack_threshold)
                self.result[1] = True
            else:
                if self.result[1] == True:
                    self.timeline_result["sitting"][
                        len(self.timeline_result["sitting"]) - 1
                    ].append(self.response_counter)
                self.result[1] = False

            if (
                self.distance_stack
                >= self.distance_stack_threshold * self.frame_per_second
            ):
                if self.result[2] == False:
                    self.timeline_result["distance"].append([])
                    self.timeline_result["distance"][
                        len(self.timeline_result["distance"]) - 1
                    ].append(self.response_counter - self.distance_stack_threshold)
                self.result[2] = True
            else:
                if self.result[2] == True:
                    self.timeline_result["distance"][
                        len(self.timeline_result["distance"]) - 1
                    ].append(self.response_counter)
                self.result[2] = False

            if (
                self.thoracic_stack
                >= self.thoracic_stack_threshold * self.frame_per_second
            ):
                if self.result[3] == False:
                    self.timeline_result["thoracic"].append([])
                    self.timeline_result["thoracic"][
                        len(self.timeline_result["thoracic"]) - 1
                    ].append(self.response_counter - self.thoracic_stack_threshold)
                self.result[3] = True
            else:
                if self.result[3] == True:
                    self.timeline_result["thoracic"][
                        len(self.timeline_result["thoracic"]) - 1
                    ].append(self.response_counter)
                self.result[3] = False

    def get_timeline_result(self):
        return self.timeline_result

    def get_alert(self):
        return self.result
