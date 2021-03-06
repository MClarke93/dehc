from multiprocessing import Process, Queue
import queue
import time

import ctypes
import os
import usb.core ## python -m pip install pyusb
import usb.backend.libusb1

os.chdir('./mods/zebra_ds22_reader/DLL') # Assumes we start from dehc/
try:
    #check = ctypes.WinDLL('./libusb-1.0.dll')
    backend = usb.backend.libusb1.get_backend(find_library=lambda x: './libusb-1.0.dll')
    usb.core.find()
except Exception as err:
    print(f'USB Loading error: {err}')
os.chdir('../../..') # Go back to start

from mods.dehc_worker import Hardware_Worker

class Barcode_Worker(Hardware_Worker):

    usbDevice = None
    idVendor = 0x05E0
    idProduct = 0x1300
    
    def __init__(self, inQueue: Queue = None, outQueue: Queue = None):
        super().__init__(inQueue=inQueue, outQueue=outQueue)
    
    def detectDevice(self):
        return super().detectDevice()
    
    def openDevice(self):
        #TODO: Do exception handling
        try:
            self.usbDevice = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        except Exception as err:
            print(f'USB Connection Error: {err}')
        if self.usbDevice is None:
            print(f"USB Device could not be opened. Vendor {self.idVendor}, Product: {self.idProduct}")
            return
        self.usbDevice.set_configuration() # TODO: Work out what this does..
        self.usbEndpoint = self.usbDevice[0][(0,0)][0] # TODO: Documentation
        self.connection = True
        print(f'USB Device opened with Vendor: {self.idVendor}, Product: {self.idProduct}')

    def closeDevice(self):
        self.usbDevice = None
        self.connection = None
        print('Closed Barcode hardware connection')

    def processQueueMessage(self, message):
        return super().processQueueMessage(message)

    def parseBarcodeResponse(self, response):
        
        headerLength = 4

        i = len(response) - 1

        while(i > 0):
            if response[i] == 0:
                i -= 1
                continue
            else:
                break

        ## Assume that leading 4 bytes are some header
        ## Assume that trailing zeros are padding
        ##  -2, to include the last valid byte (before trailing zeros)
        value = bytes(response)[headerLength:i-2].decode()

        return value

    def readCurrentBarcode(self):
        self.currentBarcode = None
        if self.usbDevice is not None:
            try:
                data = None
                data = self.usbDevice.read(self.usbEndpoint.bEndpointAddress, self.usbEndpoint.wMaxPacketSize)
                recontructedData = self.parseBarcodeResponse(data)
                self.currentBarcode = recontructedData
            except usb.core.USBError as err:
                if err.args == ('Operation timed out',):
                    pass
                else:
                    self.currentBarcode = None
    
    def sendCurrentBarcode(self):
        if self.currentBarcode is not None:
            msg = {"message": "data", "barcode": self.currentBarcode}
            if self.outQueue is not None:
                try:
                    self.outQueue.put(msg, block=False)
                except queue.Full:
                    time.sleep(0.1)
            else:
                print(msg)

    def readNewData(self, type=None):
        self.readCurrentBarcode()

    def sendNewData(self):
        self.sendCurrentBarcode()

if __name__ == "__main__":

    barcode = Barcode_Worker()

    data_updated = True
    
    while(True):
        barcode.readCurrentBarcode()
        if barcode.currentBarcode is not None:
            print(f'Barcode: {barcode.currentBarcode}')
            data_updated = True
        else:
            if data_updated:
                print(f'No data')
            data_updated = False
            time.sleep(0.2)