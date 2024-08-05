import numpy as np
import math


class processData:
    def __init__(self, data):
       self.data = data
       

    def get_shoulder_position(self):
        if (self.data['leftShoulder'] and self.data['rightShoulder']):
            shoulder_left = self.data['leftShoulder']
            shoulder_right = self.data['rightShoulder']
            shoulder_position = {'x':(shoulder_left['x']+shoulder_right['x'])/2,
                                 'y':(shoulder_left['y']+shoulder_right['y'])/2,
                                 'z':(shoulder_left['z']+shoulder_right['z'])/2}
            return shoulder_position 
        return None
    
    def get_blink_right(self):
        if self.data['rightIris']:
            dis_p1p4 = math.sqrt(pow(self.data['rightIris']['33']['x']-self.data['rightIris']['133']['x'],2)+pow(self.data['rightIris']['33']['y']-self.data['rightIris']['133']['y'],2))
            dis_p2p6 = math.sqrt(pow(self.data['rightIris']['160']['x']-self.data['rightIris']['144']['x'],2)+pow(self.data['rightIris']['160']['y']-self.data['rightIris']['144']['y'],2))
            dis_p3p5 = math.sqrt(pow(self.data['rightIris']['158']['x']-self.data['rightIris']['153']['x'],2)+pow(self.data['rightIris']['158']['y']-self.data['rightIris']['153']['y'],2))
            eAR = (dis_p2p6+dis_p3p5)/dis_p1p4
            return eAR
        return None
    
    def get_blink_left(self):
        if self.data['leftIris']:
            dis_p1p4 = math.sqrt(pow(self.data['leftIris']['362']['x']-self.data['leftIris']['263']['x'],2)+pow(self.data['leftIris']['362']['y']-self.data['leftIris']['263']['y'],2))
            dis_p2p6 = math.sqrt(pow(self.data['leftIris']['385']['x']-self.data['leftIris']['380']['x'],2)+pow(self.data['leftIris']['385']['y']-self.data['leftIris']['380']['y'],2))
            dis_p3p5 = math.sqrt(pow(self.data['leftIris']['387']['x']-self.data['leftIris']['373']['x'],2)+pow(self.data['leftIris']['387']['y']-self.data['leftIris']['373']['y'],2))
            eAR = (dis_p2p6+dis_p3p5)/dis_p1p4
            return eAR
        return None