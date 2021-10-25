'''The module containing pbjects that create and manage photos.'''

import cv2
from PIL import Image

import mods.log as ml

# ----------------------------------------------------------------------------

class PhotoManager:
    '''A class which handles taking photos from a webcam.'''

    def __init__(self, level: str = "NOTSET", size: tuple = (256, 256)):
        '''Constructs a PhotoManager object.
        
        level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
        '''
        self.logger = ml.get(name="PhotoManager", level=level)
        self.logger.debug(f"PhotoManager object instantiated")

        self.cameras = []
        for i in range(10):
            camera = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            result, img = camera.read()
            if result == True:
                self.cameras.append(camera)
            else:
                camera.release()
        
        self.size = size

        self.logger.info(f"Found {len(self.cameras)} cameras")


    def destroy(self):
        '''Deletes the VideoCapture objects, them as a resource.'''
        for camera in self.cameras:
            camera.release()
        del(self.cameras)
        cv2.destroyAllWindows()


    def take_photo(self, feed: int = 0):
        '''Takes a photo and returns it as a PIL object.
        
        feed: Which feed to use. The first feed is 0, regardless of its cv2 ID.
        '''
        if len(self.cameras) > feed:
            result, img = self.cameras[feed].read()
            if result == True:
                img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                img.thumbnail(size=self.size)
                return img
        return None
