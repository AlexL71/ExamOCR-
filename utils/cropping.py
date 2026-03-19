import numpy as np

ROIS_P1 = {
    'Student_ID':    {'x': (0.202, 0.518),   'y': (0.0534, 0.2051)},
    'DOB':           {'x': (0.5265, 0.719),  'y': (0.0537, 0.2044)},
    'Name':          {'x': (0.7285, 0.993),  'y': (0.0127, 0.0566)},
    'Examiner_Sign': {'x': (0.011, 0.1935),  'y': (0.1368, 0.2047)},
    'Wongoji_P1':    {'x': (0.0095, 0.993),  'y': (0.2207, 0.976)}
}

ROIS_P2 = {
    'Wongoji_P2':    {'x': (0.01, 0.9935),   'y': (0.2238, 0.9791)}
}

class ExamCropper:
    def __init__(self, image, is_p1=True):
        self.img = image
        self.is_p1 = is_p1

    def get_crops(self):
        if self.img is None:
            return {}
            
        h, w = self.img.shape[:2]
        rois = ROIS_P1 if self.is_p1 else ROIS_P2
        
        return {
            name: self.img[
                max(0, int(h * roi['y'][0])):min(h, int(h * roi['y'][1])), 
                max(0, int(w * roi['x'][0])):min(w, int(w * roi['x'][1]))
            ] for name, roi in rois.items()
        }