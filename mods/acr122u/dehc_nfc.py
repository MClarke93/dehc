from multiprocessing import Process, Queue
from multiprocessing.spawn import freeze_support
import queue
import time
import sys
import os

from smartcard.System import readers

from mods.dehc_worker import Hardware_Worker

COMMAND_HANDSHAKE   = [0xFF, 0xCA, 0x00, 0x00, 0x00]
COMMAND_GETUID      = [0xFF, 0xCA, 0x00, 0x00, 0x04]

class NFC_Worker(Hardware_Worker):
    
    reader = None
    systemReaders = None

    def __init__(self, inQueue: Queue = None, outQueue: Queue = None):
        super().__init__(inQueue=inQueue, outQueue=outQueue)
    
    def detectDevice(self):
        try:
            self.systemReaders = readers()
            print(f'Found NFC readers: {self.systemReaders}')
        except Exception as err:
            print(f'Smartcard reader error: {err}')
        
    def openDevice(self):
        if self.systemReaders is not None:
            if len(self.systemReaders) > 0:
                if 'ACR122U' in self.systemReaders[0]: #TODO: Confirm correct functionality
                    self.reader = self.systemReaders[0] 
                else: #Preserve original functionality (grab first reader)
                    self.reader = self.systemReaders[0] 
                self.connection = True
                #TODO: Check for alive connection, get reader ATR?
                print(f'Device opened, {self.reader}')
    
    def closeDevice(self):
        #TODO: Check if cleanup necessary
        self.reader = None
        self.connection = False
        print('Closed NFC hardware connection.')

    def processQueueMessage(self, message):
        return super().processQueueMessage(message)

    def parseNFCResponse(self, response):
        if isinstance(response, tuple):
            temp = response[0]
            code = response[1]
        else:
            temp = response
            code = 0
        response = ''
        for val in temp:
            response += format(val, '#04x')[2:] #TODO: Documentation
        response = response.upper()
        if code == 144: #TODO: Find reference
            return response        

    def readNFCTag(self, COMMAND):
        if self.reader is not None:
            try:
                cardConnection = self.reader.createConnection()
                statusConnection = cardConnection.connect()
                cardConnection.transmit(COMMAND_HANDSHAKE)
                response = cardConnection.transmit(COMMAND)
                response = self.parseNFCResponse(response)
                if response is not None:
                    print(f'NFC response: {response}')
                    return response
            except Exception as err:
                pass #TODO: Do actual error handling
                return None
        return None

    def readCurrentUID(self):
        self.currentUID = None
        if self.reader is not None:
            response = self.readNFCTag(COMMAND_GETUID)
            if response is not None:
                self.currentUID = response
            else:
                self.currentUID = None
                self.currentData = None

    def sendCurrentUID(self):
        if self.currentUID is not None:
            msg = {"message": "data", "uid": self.currentUID}
            if self.outQueue is not None:
                try:
                    self.outQueue.put(msg, block=False)
                except queue.Full:
                    time.sleep(0.1)
            else:
                print(f'currentUID is None: {msg}')

    def readNewData(self, type = COMMAND_GETUID):
        if type == COMMAND_GETUID:
            self.readCurrentUID()
    
    def sendNewData(self):
        self.sendCurrentUID()

if __name__ == "__main__":

    nfc = NFC_Worker()
    
    lastData = {}

    while(True):

        nfc.readCurrentUID()
        if nfc.currentUID is not None:
            if nfc.currentUID != lastData:
                print(f'Data: {nfc.currentUID}')
                lastData = nfc.currentUID
        time.sleep(0.1)
            