class detection:
    def __init__(self, frame_per_second=1, correct_frame=15):
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
        self.not_sitting_stack = 0

        self.blink_stack_threshold = 5
        self.sitting_stack_threshold = 2700
        self.distance_stack_threshold = 30
        self.thoracic_stack_threshold = 2
        self.not_sitting_stack_threshold = 5
        self.result = {
            "blink_alert": False,
            "sitting_alert": False,
            "distance_alert": False,
            "thoracic_alert": False,
            "time_limit_exceed": False,
        }  # [blink_alert, sitting_alert, distance_alert, thoracic_alert]

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
            if input["shoulderPosition"] is None:
                self.thoracic_stack = 0
            elif (
                self.correct_values.get("shoulderPosition") is not None
                and self.correct_values["shoulderPosition"] + 0.05
                <= input["shoulderPosition"]
            ):
                self.thoracic_stack += 1
            else:
                self.thoracic_stack = 0

            if faceDetect is False:
                self.blink_stack = 0
                self.distance_stack = 0
                self.not_sitting_stack += 1
                if (
                    self.not_sitting_stack
                    >= self.not_sitting_stack_threshold * self.frame_per_second
                ):
                    self.sitting_stack = 0
                else:
                    self.sitting_stack += 1
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
                if self.result["blink_alert"] is False:
                    self.timeline_result["blink"].append([])
                    self.timeline_result["blink"][
                        len(self.timeline_result["blink"]) - 1
                    ].append(
                        self.response_counter
                        - (self.blink_stack_threshold * self.frame_per_second)
                    )
                self.result["blink_alert"] = True
            else:
                if self.result["blink_alert"] is True:
                    self.timeline_result["blink"][
                        len(self.timeline_result["blink"]) - 1
                    ].append(self.response_counter)
                self.result["blink_alert"] = False

            if (
                self.sitting_stack
                >= self.sitting_stack_threshold * self.frame_per_second
            ):
                if self.result["sitting_alert"] is False:
                    self.timeline_result["sitting"].append([])
                    self.timeline_result["sitting"][
                        len(self.timeline_result["sitting"]) - 1
                    ].append(
                        self.response_counter
                        - (self.sitting_stack_threshold * self.frame_per_second)
                    )
                self.result["sitting_alert"] = True
            else:
                if self.result["sitting_alert"] is True:
                    self.timeline_result["sitting"][
                        len(self.timeline_result["sitting"]) - 1
                    ].append(
                        self.response_counter
                        - (self.not_sitting_stack_threshold * self.frame_per_second)
                    )
                self.result["sitting_alert"] = False

            if (
                self.distance_stack
                >= self.distance_stack_threshold * self.frame_per_second
            ):
                if self.result["distance_alert"] is False:
                    self.timeline_result["distance"].append([])
                    self.timeline_result["distance"][
                        len(self.timeline_result["distance"]) - 1
                    ].append(
                        self.response_counter
                        - (self.distance_stack_threshold * self.frame_per_second)
                    )
                self.result["distance_alert"] = True
            else:
                if self.result["distance_alert"] is True:
                    self.timeline_result["distance"][
                        len(self.timeline_result["distance"]) - 1
                    ].append(self.response_counter)
                self.result["distance_alert"] = False

            if (
                self.thoracic_stack
                >= self.thoracic_stack_threshold * self.frame_per_second
            ):
                if self.result["thoracic_alert"] is False:
                    self.timeline_result["thoracic"].append([])
                    self.timeline_result["thoracic"][
                        len(self.timeline_result["thoracic"]) - 1
                    ].append(
                        self.response_counter
                        - (self.thoracic_stack_threshold * self.frame_per_second)
                    )
                self.result["thoracic_alert"] = True
            else:
                if self.result["thoracic_alert"] is True:
                    self.timeline_result["thoracic"][
                        len(self.timeline_result["thoracic"]) - 1
                    ].append(self.response_counter)
                self.result["thoracic_alert"] = False

            if self.response_counter >= 7200 * self.frame_per_second:
                self.result["time_limit_exceed"] = True

    def get_timeline_result(self):
        return self.timeline_result

    def get_alert(self):
        return self.result
