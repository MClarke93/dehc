from multiprocessing import Process, Queue
import queue
import sys
import time

def listPrinters():
    return Printer.listPrinters()

def  getDefaultPrinter():
    return Printer.getDefaultPrinter()

class Hardware:

    processes = []

    SCALES_EXIST = False
    NFCREADER_EXIST = False
    BARCODEREADER_EXIST = False
    PRINTER_EXIST = False

    lastNFCUID = ''

    inQueueBarcode = None
    outQueueBarcode = None

    inQueueNFC = None
    outQueueNFC = None

    inQueueScales = None
    outQueueScales = None

    inQueuePrinter = None
    outQueuePrinter = None

    def __init__(self, makeScales = False, makeBarcodeReader = False, makeNFCReader = False, makePrinter = False):
        
        if makeScales:
            import mods.wedderburn_di_166.dehc_scales as Scales
            self.inQueueScales = Queue(maxsize=1) # Only store the most recent value
            self.outQueueScales = Queue(maxsize=1) # For now, we don't need to stack up C2 messages
            self.processScales = Process(target=Scales.Scales_Worker, args=(self.outQueueScales, self.inQueueScales))
            self.processes.append(self.processScales)
        else:
            print("Scale support deactivated")
        
        #Note, pycard is currently not installing correctly through pip. NFC support has been temporarily disabled!
        if makeNFCReader and False:
            import mods.acr122u.dehc_nfc as NFC
            self.inQueueNFC = Queue(maxsize=1) # Only store the most recent value
            self.outQueueNFC = Queue(maxsize=1) # For now, we don't need to stack up C2 messages
            self.processNFC = Process(target=NFC.NFC_Worker, args=(self.outQueueNFC, self.inQueueNFC))
            self.processes.append(self.processNFC)
        else:
            print("NFC Reader support deactivated")

        if makeBarcodeReader:
            import mods.zebra_ds22_reader.dehc_barcode as Barcode
            self.inQueueBarcode = Queue(maxsize=1) # Only store the most recent value
            self.outQueueBarcode = Queue(maxsize=1) # For now, we don't need to stack up C2 messages
            self.processBarcode = Process(target=Barcode.Barcode_Worker, args=(self.outQueueBarcode, self.inQueueBarcode))
            self.processes.append(self.processBarcode)
        else:
            print("Barcode reader support deactivated")

        if makePrinter and sys.platform == "win32":
            import mods.zebra_zc300_printer.dehc_printer as Printer
            from PIL import Image
            self.inQueuePrinter = Queue(maxsize=1) # Only store the most recent value
            self.outQueuePrinter = Queue(maxsize=1000) # For now, we don't need to stack up C2 messages
            self.processPrinter = Process(target=Printer.Printer_Worker, args=(self.outQueuePrinter, self.inQueuePrinter))
            self.processes.append(self.processPrinter)
        else:
            print("Printer support deactivated")

        self.startProcesses()

        #Note, pycard is currently not installing correctly through pip. NFC support has been temporarily disabled!
        self.SCALES_EXIST = makeScales
        self.NFCREADER_EXIST = False
        self.BARCODEREADER_EXIST = makeBarcodeReader
        if sys.platform == "win32":
            self.PRINTER_EXIST = makePrinter
        else:
            self.PRINTER_EXIST = False

    def startProcesses(self):
        for process in self.processes:
            if process is None:
                continue
            process.start()

    def terminateProcesses(self):
        if self.outQueueScales is not None:
            self.outQueueScales.put({"message": "close"})
        if self.outQueueNFC is not None:
            self.outQueueNFC.put({"message": "close"})
        if self.outQueueBarcode:
            self.outQueueBarcode.put({"message": "close"})
        if self.outQueuePrinter:
            self.outQueuePrinter.put({"message": "close"})
        
        time.sleep(1) # Allow some time for process to do cleanup
        
        for process in self.processes:
            if process is None:
                continue
            if process._popen is not None:
                process.join(1)
                process.terminate()

    def getCurrentWeight(self):
        if not self.SCALES_EXIST:
            self.lastWeight = ''
        else:
            try:
                tmpData = self.inQueueScales.get(timeout=0.01)
                if 'weight' in tmpData:
                    self.lastWeight = tmpData['weight']
            except queue.Empty:
                self.lastWeight = ''
        return self.lastWeight

    def getCurrentNFCUID(self):
        if not self.NFCREADER_EXIST:
            self.lastNFCUID = ''
        else:
            try:
                tmpData = self.inQueueNFC.get(timeout=0.01)
                if 'uid' in tmpData:
                    self.lastNFCUID = tmpData['uid']
            except queue.Empty:
                self.lastNFCUID = ''
        return self.lastNFCUID
    
    def getCurrentBarcode(self):
        if not self.BARCODEREADER_EXIST:
            self.lastBarcode = ''
        else:
            try:
                tmpData = self.inQueueBarcode.get(timeout=0.01)
                if 'barcode' in tmpData:
                    self.lastBarcode = tmpData['barcode']
            except queue.Empty:
                self.lastBarcode = ''
        return self.lastBarcode

    def sendNewIDCard(self, idCardImage, printer):
        self.outQueuePrinter.put({"message": "idcard", "idcard": idCardImage, "printer": printer})

if __name__ == "__main__":

    hardware = Hardware(makeScales=True,makeBarcodeReader=True, makeNFCReader=True, makePrinter=True)

    time.sleep(1)

    weight = hardware.getCurrentWeight()
    
    # barcode = hardware.getCurrentBarcode()
    
    # nfcUID = hardware.getCurrentNFCUID()

    # for _ in range(0,1):
    #     tmpIDCard = Image.new('RGB', (400,640), (random.randint(0,255),random.randint(0,255),random.randint(0,255)))
    #     hardware.sendNewIDCard(tmpIDCard)
    
    print(f'Weight: {weight}')
    # print(f'Barcode: {barcode}')
    # print(f'NFC UID: {nfcUID}')
    
    time.sleep(1)
    
    hardware.terminateProcesses()
