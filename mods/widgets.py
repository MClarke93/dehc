'''The module containing objects that create and manage groups of tkinter widgets.'''

import json
import re
import time
import webbrowser

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

import mods.database as md
import mods.log as ml
import mods.photo as mp
import mods.dehc_hardware as hw
import mods.id_card_generation as card_gen


# ----------------------------------------------------------------------------

busystatus = False

def busy(func):
    '''A decorator used to indicate the program is busy to the user.
    
    Can only be used in objects with a 'statusbar' and 'root'.
    '''
    def wrapper(self, *args, **kwargs):
        global busystatus
        if busystatus == True:
            func(self, *args, **kwargs)
        else:
            busystatus = True
            self.statusbar.w_status.configure(text="App is working...", background="#fcf0cf")
            self.root.configure(cursor="clock")
            self.root.update_idletasks() # Redraws screen to reflect changes
            func(self, *args, **kwargs)
            self.statusbar.w_status.configure(text="Done", background="#dcdad5")
            self.root.configure(cursor="")
            busystatus = False
    return wrapper


# ----------------------------------------------------------------------------

class SuperWidget:
    '''A class which represents a self-contained collection of tkinter widgets.
    
    Not to be instantiated directly; use the various sub-classes instead.
    When subclassing, overwrite _pack_children() with code to pack the various child widgets beneath self.w_fr.

    db: The database object which the widget uses for database transactions.
    master: The widget that the SuperWidget's component widgets will be instantiated under.
    logger: The logger object used for logging.
    w_fr: The frame widget that contains the SuperWidget's component widgets.
    '''

    def __init__(self, master: tk.Misc, db: md.DEHCDatabase, *, level: str = "NOTSET"):
        '''Constructs a SuperWidget object.
        
        master: The widget that the SuperWidget's component widgets will be instantiated under.
        db: The database object which the widget uses for database transactions.
        level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
        '''
        # Logging
        suffix = 1
        while True:
            logger_name = f"{type(self).__name__}{suffix if suffix > 1 else ''}"
            if not ml.check(name=logger_name) or suffix > 99:
                break
            suffix += 1
        self.logger = ml.get(logger_name, level=level)
        self.logger.debug(f"{logger_name} object instantiated")
        self.db = db

        # Placement
        self.master = master
        self.w_fr = ttk.Frame(master=self.master)


    def pack(self, *args, **kwargs):
        '''Packs the frames and widgets of the SuperWidget.
        
        Arguments are the same as tkinter's .pack() methods.
        '''
        self.logger.debug(f"Packing self ({self.w_fr})")
        self.w_fr.pack(*args, **kwargs)
        self._pack_children()

    
    def grid(self, *args, **kwargs):
        '''Grids the frames and widgets of the SuperWidget.
        
        Arguments are the same as tkinter's .grid() methods.
        '''
        self.logger.debug(f"Gridding self ({self.w_fr})")
        self.w_fr.grid(*args, **kwargs)
        self._pack_children()


    def _pack_children(self):
        '''Packs & grids children frames and widgets of the SuperWidget.
        
        Should be overwritten for each new SuperWidget.
        '''
        raise NotImplementedError


# ----------------------------------------------------------------------------

class StatusBar(SuperWidget):
    '''A SuperWidget representing a database status bar.
    
    db: The database object which the widget uses for database transactions.
    logger: The logger object used for logging.
    master: The widget that the StatusBar's component widgets will be instantiated under.
    '''

    def __init__(self, master: tk.Misc, db: md.DEHCDatabase, *, level: str = "NOTSET", prepare: bool = True):
        '''Constructs a StatusBar object.
        
        master: The widget that the StatusBar's component widgets will be instantiated under.
        level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
        prepare: If true, automatically prepares widgets for packing.
        '''
        super().__init__(master=master, db=db, level=level)

        if prepare == True:
            self.prepare()


    def prepare(self):
        '''Constructs the frames and widgets of the StatusBar.'''
        self.logger.debug(f"Preparing widgets")
        self.w_status = tk.Label(master=self.w_fr, text="", justify=tk.LEFT, anchor="w", font="Arial 9 bold", background='#dcdad5')
        self.w_time = tk.Label(master=self.w_fr, text="Server Online", justify=tk.RIGHT, anchor="e", font="Arial 9 bold", background='#dcdad5')
        
    
    def _pack_children(self):
        '''Packs & grids children frames and widgets of the StatusBar.'''
        self.logger.debug(f"Packing and gridding widgets")
        self.w_status.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3,0), pady=(0,1))
        self.w_time.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0,3), pady=(0,1))


# ----------------------------------------------------------------------------

class DataEntry(SuperWidget):
    '''A SuperWidget representing a data entry pane.'''

    def __init__(self, master: tk.Misc, db: md.DEHCDatabase, *, cats: list = [], delete: Callable = None, godmode: bool = False, level: str = "NOTSET", newchild: Callable = None, prepare: bool = True, readonly: bool = False, save: Callable = None, show: Callable = None, statusbar: StatusBar = None, trash: str = None, web: str = "web_auth.json", hardware: hw.Hardware = None):
        '''Constructs a DataEntry object.
        
        master: The widget that the DataEntry's component widgets will be instantiated under.
        db: The DEHCDatabase object associated with this DataEntry.
        cats: The categories of items that can be created using the New button.
        delete: If present, a callback function that triggers when an item is deleted.
        level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
        newchild: If present, a callback function that triggers when 'create' is pressed in a guardian field.
        prepare: If true, automatically prepares widgets for packing.
        save: If present, a callback function that triggers when an item is saved.
        show: If present, a callback function that triggers when 'show' or 'back' is pressed in the data pane.
        trash: The document corresponding to the recycle bin.
        hardware: The hardware manager associated with this DataEntry.
        '''
        super().__init__(master=master, db=db, level=level)

        self.cats = cats                       # The list of item categories this DataEntry can select and work with.
        self.editing = False                   # Whether or not the user is currently editing a document.
        self.back_doc = {}                     # The document to return to when the back button is pressed.
        self.last_doc = {}                     # The most recently selected and retrieved document from the database.
        self.godmode = godmode                 # Whether or not the application is in 'god mode' (admin mode)
        self.guardian_doc = {}                 # The guardian's document when 'new child' is pressed.
        self.child_doc = {}                    # Information for child document when 'new child' is pressed.
        self.current_photo = None              # The currently slown photo.
        self.last_photo = None                 # The most recently retrieved photo from the database.
        self.level = level                     # The logging level
        self.readonly = readonly               # Whether or not the application is in readonly mode
        self.root = self.w_fr.winfo_toplevel() # Root widget that contains this SuperWidget
        self.statusbar = statusbar             # The status bar associated with this DataEntry
        self.trash = trash                     # The UUID of the recycle bin
        self.web = web                         # The filepath to the web server authentication file
        self._delete = delete                  # The parent object's callback to run when delete is pressed.
        self._newchild = newchild              # The parent object's callback to run when new child is pressed.
        self._save = save                      # The parent object's callback to run when save is pressed.
        self._show = show                      # The parent object's callback to run when show is pressed.
        self.hardware = hardware               # The hardware manager object associated with this DataEntry
        
        self.photomanager = mp.PhotoManager(level=self.level)
        self.photo_blank = Image.new("RGB", (256, 256), (220, 218, 213))

        if prepare == True:
            self.prepare()


    def prepare(self):
        '''Constructs the frames and widgets of the DataEntry.'''
        self.logger.debug(f"Preparing widgets")
        self.w_fr_head = ttk.Frame(master=self.w_fr)
        self.w_fr_photo = ttk.Frame(master=self.w_fr)
        self.w_fr_flags = ttk.Frame(master=self.w_fr)
        self.w_fr_body = ttk.Frame(master=self.w_fr)
        self.w_ca_data = tk.Canvas(master=self.w_fr_body, background="#DCDAD5", bd=0, highlightthickness=0, relief='ridge')
        self.w_fr_data = ttk.Frame(master=self.w_ca_data)
        self.w_fr_foot = ttk.Frame(master=self.w_fr)
        self.w_ca_data.create_window((0, 0), window=self.w_fr_data, anchor="nw", tags="frame")

        def redraw_canvas_window(*args):
            self.w_ca_data.itemconfig('frame', width=self.w_ca_data.winfo_width())

        def mouse_scroll(*args):
            event, *_ = args
            self.w_ca_data.yview_scroll(int(-1*(event.delta/120)), "units")

        def mouse_enter_canvas(*args):
            self.w_ca_data.bind_all("<MouseWheel>", mouse_scroll)

        def mouse_exit_canvas(*args):
            self.w_ca_data.unbind_all("<MouseWheel>")

        self.w_ca_data.bind("<Configure>", redraw_canvas_window)
        self.w_ca_data.bind("<Double-Button-1>", lambda *_: self.w_bu_edit.invoke())
        self.w_fr_data.bind('<Enter>', mouse_enter_canvas)
        self.w_fr_data.bind('<Leave>', mouse_exit_canvas)

        self.root.bind('<Control-e>', lambda *_: self.w_bu_edit.invoke())
        self.root.bind('<Control-s>', lambda *_: self.w_bu_save.invoke())
        self.root.bind('<Control-n>', lambda *_: self.w_bu_new.invoke())

        self.w_fr.columnconfigure(index=0, weight=1000, minsize=280)
        self.w_fr.columnconfigure(index=1, weight=1000)
        self.w_fr.columnconfigure(index=2, weight=1, minsize=16)
        self.w_fr.rowconfigure(index=0, weight=1, minsize=24)
        self.w_fr.rowconfigure(index=1, weight=1)
        self.w_fr.rowconfigure(index=2, weight=1000)
        self.w_fr.rowconfigure(index=3, weight=1, minsize=24)

        self.w_fr_head.columnconfigure(index=0, weight=1000)
        self.w_fr_head.columnconfigure(index=1, weight=1, minsize=48)
        self.w_fr_head.columnconfigure(index=2, weight=1, minsize=48)
        self.w_fr_head.columnconfigure(index=3, weight=1, minsize=48)
        self.w_fr_head.rowconfigure(index=0, weight=1000)

        self.w_fr_photo.columnconfigure(index=0, weight=1000)
        self.w_fr_photo.rowconfigure(index=0, weight=1000)
        self.w_fr_photo.rowconfigure(index=1, weight=1, minsize=24)

        self.w_fr_flags.columnconfigure(index=0, weight=1000)
        self.w_fr_flags.columnconfigure(index=1, weight=1000)
        self.w_fr_flags.columnconfigure(index=2, weight=1000)
        self.w_fr_flags.columnconfigure(index=3, weight=1, minsize=16)
        self.w_fr_flags.rowconfigure(index=0, weight=1, minsize=24)
        self.w_fr_flags.rowconfigure(index=1, weight=1000)
        self.w_fr_flags.rowconfigure(index=2, weight=1, minsize=24)

        self.w_fr_body.columnconfigure(index=0, weight=1000)
        self.w_fr_body.rowconfigure(index=0, weight=1000)

        self.w_fr_foot.columnconfigure(index=0, weight=1000)
        self.w_fr_foot.columnconfigure(index=1, weight=1000)
        self.w_fr_foot.columnconfigure(index=2, weight=1000)
        self.w_fr_foot.columnconfigure(index=3, weight=1000)
        self.w_fr_foot.columnconfigure(index=4, weight=1000)
        self.w_fr_foot.columnconfigure(index=5, weight=1000)
        if self.godmode == True:
            self.w_fr_foot.columnconfigure(index=6, weight=1000)
        self.w_fr_foot.rowconfigure(index=0, weight=1000)

        # Variables
        self.w_var_data = []
        self.w_var_cat = tk.StringVar()
        self.w_var_flags = tk.StringVar()

        # Widgets
        self.w_la_title = ttk.Label(master=self.w_fr_head, text="Title", font="Arial 12 bold")
        self.w_bu_generate_id = ttk.Button(master=self.w_fr_head, text="Print ID", command=self.generate_id_card)
        self.w_bu_copyid = ttk.Button(master=self.w_fr_head, text="Copy ID", command=self.copyid)
        self.w_bu_back = ttk.Button(master=self.w_fr_head, text="Back", command=self.back)
        self.w_bu_photo = ttk.Button(master=self.w_fr_photo, text="Photo", command=self.photo)
        self.w_bu_editphoto = ttk.Button(master=self.w_fr_photo, text="Edit Photo", command=self.photo)
        self.w_la_flags = ttk.Label(master=self.w_fr_flags, text="Flags")
        self.w_li_flags = tk.Listbox(master=self.w_fr_flags, selectmode=tk.SINGLE, relief=tk.GROOVE, exportselection=False)
        self.w_co_flags = ttk.Combobox(master=self.w_fr_flags, textvariable=self.w_var_flags, state="readonly")
        self.w_bu_add = ttk.Button(master=self.w_fr_flags, text="Add", command=self.add)
        self.w_bu_remove = ttk.Button(master=self.w_fr_flags, text="Remove", command=self.remove)
        self.w_la_data = []
        self.w_input_data = []
        self.w_bu_edit = ttk.Button(master=self.w_fr_foot, text="Edit",)
        self.w_bu_cancel = ttk.Button(master=self.w_fr_foot, text="Cancel")
        self.w_bu_save = ttk.Button(master=self.w_fr_foot, text="Save")
        self.w_bu_delete = ttk.Button(master=self.w_fr_foot, text="Delete")
        self.w_bu_new = ttk.Button(master=self.w_fr_foot, text="New")
        self.w_co_cat = ttk.Combobox(master=self.w_fr_foot, values=self.cats, textvariable=self.w_var_cat, state="readonly")
        if self.godmode == True:
            self.w_bu_admin = ttk.Button(master=self.w_fr_foot, text="Admin")
        self.w_co_cat.current(0)

        if self.readonly == False:
            self.w_bu_edit.configure(command=self.edit)
            self.w_bu_cancel.configure(command=self.cancel)
            self.w_bu_save.configure(command=self.save)
            self.w_bu_delete.configure(command=self.delete)
            self.w_bu_new.configure(command=self.new)
            if self.godmode == True:
                self.w_bu_admin.configure(command=self.admin)

        # Scrollbars
        self.w_sc_flags = ttk.Scrollbar(master=self.w_fr_flags, orient="vertical", command=self.w_li_flags.yview)
        self.w_li_flags.config(yscrollcommand=self.w_sc_flags.set)

        self.w_sc_data = ttk.Scrollbar(master=self.w_fr, orient="vertical", command=self.w_ca_data.yview)
        self.w_fr_data.bind("<Configure>", lambda e: self.w_ca_data.configure(scrollregion=self.w_ca_data.bbox("all")))
        self.w_ca_data.configure(yscrollcommand=self.w_sc_data.set)

        self.show()


    def _pack_children(self):
        '''Packs & grids children frames and widgets of the DataEntry.'''
        self.logger.debug(f"Packing and gridding widgets")
        self.w_fr_head.grid(column=0, row=0, columnspan=3, sticky="nsew", padx=2, pady=2)
        self.w_fr_photo.grid(column=0, row=1, sticky="nsew", padx=2, pady=2)
        self.w_fr_flags.grid(column=1, row=1, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.w_fr_body.grid(column=0, row=2, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.w_sc_data.grid(column=2, row=2, sticky="nsew", padx=1, pady=2)
        self.w_fr_foot.grid(column=0, row=3, columnspan=2, sticky="nsew", padx=2, pady=1)

        self.w_ca_data.grid(column=0, row=0, sticky="nsew")

        self.w_la_title.grid(column=0, row=0, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.w_bu_generate_id.grid(column=1,row=0,sticky="nsew",padx=2,pady=2)
        self.w_bu_copyid.grid(column=2, row=0, sticky="nsew", padx=2, pady=2)
        self.w_bu_back.grid(column=3, row=0, sticky="nsew", padx=2, pady=2)
        
        self.w_bu_photo.grid(column=0, row=0, sticky="nsew", padx=2, pady=1)
        self.w_bu_editphoto.grid(column=0, row=1, sticky="nsew", padx=2, pady=1)

        self.w_la_flags.grid(column=0, row=0, columnspan=4, sticky="nsew", padx=1, pady=1)
        self.w_li_flags.grid(column=0, row=1, columnspan=3, sticky="nsew", padx=1, pady=1)
        self.w_sc_flags.grid(column=3, row=1, sticky="nse", padx=1, pady=1)
        self.w_co_flags.grid(column=0, row=2, sticky="nsew", padx=1, pady=1)
        self.w_bu_add.grid(column=1, row=2, sticky="nsew", padx=1, pady=1)
        self.w_bu_remove.grid(column=2, row=2, sticky="nsew", padx=1, pady=1)

        self.w_bu_edit.grid(column=0, row=0, sticky="nsew", padx=1, pady=1)
        self.w_bu_cancel.grid(column=1, row=0, sticky="nsew", padx=1, pady=1)
        self.w_bu_save.grid(column=2, row=0, sticky="nsew", padx=1, pady=1)
        self.w_bu_delete.grid(column=3, row=0, sticky="nsew", padx=1, pady=1)
        self.w_bu_new.grid(column=4, row=0, sticky="nsew", padx=(8,1), pady=1)
        self.w_co_cat.grid(column=5, row=0, sticky="nsew", padx=1, pady=1)
        if self.godmode == True:
            pass
            self.w_bu_admin.grid(column=6, row=0, sticky="nsew", padx=(8,1), pady=1)


    def yes_no(self, title: str, message: str, always: bool = False):
        '''Shows the user an "are you sure?" dialog and returns their answer.
        
        title: Title of the dialog window.
        message: The message inside the dialog  window.
        always: If true, it'll always ask, even if not in "edit mode".
        '''
        if self.editing == True or always == True:
            self.logger.info(f"Asked {repr(message)} ...")
            answer = messagebox.askyesno(title=title, message=message)
            if answer == True:
                if always == False:
                    self.editing = False
                self.logger.info(f"... user selected yes, setting edit mode to {self.editing}")
                return True
            else:
                self.logger.info(f"... user selected no")
                return False
        else:
            self.logger.debug(f"Asked {repr(message)} ...")
            self.logger.debug(f"... automatically selected yes, as edit mode is {self.editing}")
            return True


    def read_scales(self):
        if self.scales is not None:
            if self.scales.in_waiting > 0:
                line = self.scales.readline()
                self.last_weight = float(line.decode().strip('\r\n').strip('KG'))
        else:
            #TODO: Remove random weight generation
            import random
            self.last_weight = round(90+random.random()*5, 2)


    def close_scales(self):
        if self.scales is not None:
            self.scales.close()
            self.scales = None


    def add(self, *args):
        '''Callback for when the flag add button is pressed.'''
        self.logger.debug(f"Add flag button activated")
        flag = self.w_var_flags.get()
        if flag not in self.w_li_flags.get(0, "end"):
            self.w_li_flags.insert("end", flag)
            self.logger.info(f"Inserted {flag} into flag list")
            self.data_change()
        else:
            self.logger.debug(f"Did not insert {flag} into flag list, as it was already there")


    def admin(self, *args):
        '''Callback for when the admin button is pressed.'''
        self.logger.debug(f"Admin button activated")
        window = tk.Toplevel()
        window.attributes("-topmost", True)
        window.focus_force()
        window.title("Item Administration")
        window.configure(background="#DCDAD5")

        with open(self.web, "r") as f:
            webfile = json.loads(f.read())
            url = webfile['url']

        def buttona(*args):
            id = self.last_doc.get("_id","")
            if id != "":
                webbrowser.open(f"{url}/gatecheck?contid={id}")

        def buttonb(*args):
            id = self.last_doc.get("_id","")
            if id != "":
                self.db.flag_assign_tree(container=id, flag="Ub-Unboarded")

        def buttonc(*args):
            id = self.last_doc.get("_id","")
            if id != "":
                self.db.flag_revoke_tree(container=id, flag="Ub-Unboarded")

        def buttond(*args):
            webbrowser.open(f"{url}/function?somedataname=somedata&someotherdataname=someotherdata")

        w_bu_a = ttk.Button(master=window, text="Gate Check", command=buttona)
        w_bu_b = ttk.Button(master=window, text="Assign All Unboarded", command=buttonb)
        w_bu_c = ttk.Button(master=window, text="Revoke All Unboarded", command=buttonc)
        w_bu_d = ttk.Button(master=window, text="Button D", command=buttond)

        window.columnconfigure(index=0, weight=1000)
        window.rowconfigure(index=0, weight=1000)
        window.rowconfigure(index=1, weight=1000)
        window.rowconfigure(index=2, weight=1000)
        window.rowconfigure(index=3, weight=1000)

        #w_bu_a.grid(column=0, row=0, sticky="nsew", padx=2, pady=2)
        w_bu_b.grid(column=0, row=1, sticky="nsew", padx=2, pady=2)
        w_bu_c.grid(column=0, row=2, sticky="nsew", padx=2, pady=2)
        #w_bu_d.grid(column=0, row=3, sticky="nsew", padx=2, pady=2)


    @busy
    def back(self, *args):
        '''Callback for when the back button is pressed.'''
        self.logger.debug(f"Back button activated")
        if self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to open a different item?"):
            if "_id" in self.back_doc:
                last, back = self.back_doc, self.last_doc
                self.logger.info(f"Going back to {last['_id']}")
                self._show(last["_id"])

                def restore_history():
                    '''Prevents intermediate actions from _show() messing up the history'''
                    self.last_doc, self.back_doc = last, back
                    self.logger.debug(f"Back doc is now {self.back_doc.get('_id','_')}")
                
                self.w_fr.after(ms=1, func=restore_history) # Required to ensure it triggers after <<TreeboxSelect>>
            else:
                self.logger.debug(f"Didn't go back, as previous document had no id")
        else:
            self.logger.debug(f"Didn't go back, as user declined")


    @busy
    def cancel(self, *args):
        '''Callback for when the cancel button is pressed.'''
        self.logger.debug(f"Cancel button activated")
        if self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to cancel?"):
            self.logger.info(f"Reverting data pane to last doc {self.last_doc.get('_id','_')}")
            self.show()
        else:
            self.logger.debug(f"Not reverting data pane, as user declined")


    def show_id_window(self):
        '''...'''
        printers = hw.listPrinters()
        printers = [printer[2] for printer in printers]

        button = self.w_bu_generate_id
        state = str(button.cget("state"))

        if state != "disabled":
            for child in button.winfo_children():
                child.destroy()
            window = tk.Toplevel(master=button)
            window.attributes("-topmost", True)
            window.focus_force()
            window.title("ID Generation")
            window.configure(background="#DCDAD5")

            msg = ttk.Label(master=window)
            if len(printers) > 0:
                variable = tk.StringVar(window)
                variable.set(hw.getDefaultPrinter())
                printer_list = tk.OptionMenu(window, variable, printers[0], *printers[1:])
                print_button = ttk.Button(master=window, text="Print")

            def show_image(image: Image):
                panel = tk.Label(window, image=image)
                panel.grid(column=0,row=0)

            def print_id_card():
                if len(printers) == 0:
                    return
                #TODO Link to self.hw.Hardware and print
                self.logger.info('Printing ID Card')
                self.logger.debug(f'Printing to: {variable.get()}')
                self.hardware.sendNewIDCard(self.id_card_printable, variable.get())

            show_image(self.id_card_image)

            msg.grid(column=0, row=0, sticky="nsew", padx=10, pady=10)

            if len(printers) > 0:
                print_button.config(command=print_id_card)
                printer_list.grid(column=0, row=1, sticky='nsew', padx=10, pady=10)
                print_button.grid(column=0, row=2, sticky="nsew", padx=10, pady=10)


    def generate_id_card(self, *args):
        '''...'''
        card_builder = card_gen.IDCardBuilder()

        self.id_card_printable = card_builder.generateIDCard(
            #TODO: Change qrcode_id to be one of available Physical IDs, not _id
            qrcode_id=self.last_doc['_id'] if '_id' in self.last_doc else 'NILQRCODE',
            embedded_logo_path='assets/embedded-logo.png',
            #TODO: Change barcode_id to be one of available Physical IDs, not _id
            barcode_id=self.last_doc['_id'] if '_id' in self.last_doc else 'NILBARCODE',
            name=self.last_doc['Display Name'] if 'Display Name' in self.last_doc else 'UNKNOWN NAME',
            secondary_texts=(
                'SEX: ' + (self.last_doc['Sex'] if 'Sex' in self.last_doc else 'UNKNOWN'),
                'DOB: ' + (self.last_doc['Date Of Birth'] if 'Date Of Birth' in self.last_doc else 'NIL'),
                'PASSPORT: ' + (self.last_doc['Passport Number'] if 'Passport Number' in self.last_doc else 'NIL'),
                'NATIONALITY: ' + (self.last_doc['Nationality'] if 'Nationality' in self.last_doc else 'UNKNOWN'),
            ),
            tag_text='DEHC 2021',
            logo=Image.open('assets/logo.png'),
            portrait=self.last_photo if self.last_photo is not None else Image.new('RGB', (150,200), (0,0,0)),
            save_path='data/'+ self.last_doc['_id'] + '.png'
        )
        
        self.id_card_image = ImageTk.PhotoImage(self.id_card_printable)

        self.show_id_window()


    def copyid(self, *args):
        '''Call back for when the copy id button is pressed.'''
        self.logger.debug(f"Copy id button activated")
        root = self.w_fr.winfo_toplevel()
        root.clipboard_clear()
        id = self.last_doc.get("_id", "")
        root.clipboard_append(id)
        self.logger.info(f"{repr(id)} copied to clipboard")


    def data_change(self, *args):
        '''Callback for when an item's information in the data pane is modified.'''
        if self.editing == False:
            self.editing = True
            self.logger.info(f"Item edited, setting edit mode to {self.editing}")


    @busy
    def delete(self, *args):
        '''Callback for when the delete button is pressed'''
        self.logger.debug(f"Delete item button activated")
        id = self.last_doc["_id"]
        lock = self.db.schema_lock(id=id)
        name = self.last_doc[self.db.schema_name(id=id)]
        parents  = self.db.item_parents(item=id)
        if len(parents) >= 1:
            source, *_ = parents
        else:
            source = None
        trash = self.trash["_id"]
        
        if source == trash:
            if self.last_doc.get(lock, 0) == 1:
                messagebox.showwarning("Locked Item", f"Could not delete \"{name}\" ({id}) because item is locked.")
                self.logger.debug(f"Not deleting item, as item is locked")
                return
            if self.yes_no("Delete Item",f"Are you sure you want to delete \"{name}\" ({id}) and all of its children?", always=True):
                if len(parents) >= 1:
                    self.logger.info(f"Deleting item {id} and all its children")
                    self.db.item_delete(id=id, all=True, recur=True)
                    self.last_doc = {}
                    self.show()
                    if self._delete != None:
                        self._delete(id, parents)
                else:
                    self.logger.debug("Can't delete top level item")
            else:
                self.logger.debug(f"Not deleting item, as user declined")
        
        else:
            if self.last_doc.get(lock, 0) == 1:
                messagebox.showwarning("Locked Item", f"Could not move \"{name}\" ({id}) to the recycle bin because item is locked.")
                self.logger.debug(f"Not deleting item, as item is locked")
                return
            if self.yes_no("Delete Item",f"Are you sure you want to move \"{name}\" ({id}) and all of its children to the recycle bin?", always=True):
                if len(parents) >= 1:
                    self.logger.info(f"Recycling item {id} and all its children")
                    self.db.container_move(from_con=source, to_con=trash, item=id)
                    self.last_doc = {}
                    self.show()
                    if self._delete != None:
                        self._delete(id, parents)
                else:
                    self.logger.debug("Can't recycle top level item")
            else:
                self.logger.debug(f"Not recycling item, as user declined")


    @busy
    def edit(self, *args):
        '''Callback for when the edit button is pressed'''
        cat = self.last_doc.get('category','')
        if cat not in self.cats:
            messagebox.showwarning("Permission Denied","This item can only be edited by an administrator.")
            return

        lock = self.db.schema_lock(cat=cat)
        if self.last_doc.get(lock, 0) == 1:
            if not self.yes_no("Locked Item",f"This item is locked. Are you sure you want to edit it?", always=True):
                return

        for entry, buttona, buttonb, buttonc, hidden in zip(self.w_input_data, self.w_buttona_data, self.w_buttonb_data, self.w_buttonc_data, self.w_hidden_data):
            if hidden == None:
                entry.config(state="normal")
            if buttona != None:
                buttona.config(state="normal")
            if buttonb != None:
                buttonb.config(state="normal")
            if buttonc != None:
                buttonc.config(state="normal")
        self.w_bu_photo.config(command=self.photo)
        self.w_bu_editphoto.config(state="normal")
        self.w_bu_edit.config(state="disabled")
        self.w_bu_cancel.config(state="normal")
        self.w_bu_save.config(state="normal")
        self.w_bu_delete.config(state="normal")
        self.w_bu_add.config(state="normal")
        self.w_bu_remove.config(state="normal")
        self.w_co_flags.config(state="normal")
        if "category" in self.last_doc:
            flags = self.db.schema_flags(cat=self.last_doc["category"])
            if len(flags) > 0:
                self.w_co_flags['values'] = flags
                self.w_co_flags.current(0)
        self.w_input_data[0].focus_set()
        self.logger.debug(f"Data pane buttons are now active")


    @busy
    def new(self, *args):
        '''Callback for when the new button is pressed.'''
        self.logger.debug(f"New item button activated")
        if self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to create a new item?"):
            if len(self.guardian_doc) > 0:
                self.logger.debug(f"Using prespecified guardian {self.guardian_doc.get('_id','_')}")
                self.back_doc = self.guardian_doc
                self.last_doc = {"category": self.child_doc["category"], self.child_doc["field"]: [self.child_doc["value"]]}
                self.last_photo = None
                self.child_doc = {}
                self.guardian_doc = {}
            else:
                self.back_doc = self.last_doc
                self.logger.debug(f"No prespecified guardian for new item")
                self.last_doc = {"category": self.w_var_cat.get()}
                self.last_photo = None
            self.logger.debug(f"Back doc is now {self.back_doc.get('_id','_')}")
            self.logger.debug(f"Showing new item of category {self.last_doc['category']}")
            self.show()
            self.logger.debug(f"Activating edit as part of the new item process")
            self.edit()
            self.w_bu_delete.config(state="disabled")
            self.logger.info(f"New {self.last_doc['category']} ready to be edited")
        else:
            self.logger.debug(f"Did not open a new item, as user declined")


    @busy
    def newchild(self, event: tk.Event):
        '''Callback for when the new child button is pressed.'''
        self.logger.debug(f"Create child button activated")
        id = self.last_doc.get("_id", "")
        if id != "":
            if self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to create a new item?"):
                self.logger.info(f"Creating new child of {id}")
                button = event.widget
                row = self.w_buttonc_data.index(button)
                field = self.w_la_data[row].cget("text")
                guardian_schema = self.db.schema_schema(id=id)
                self.guardian_doc = self.last_doc
                self.child_doc = {
                    "category": guardian_schema[field]["childcat"], 
                    "field": guardian_schema[field]["childfield"],
                    "value": self.guardian_doc["_id"]
                }
                self.logger.debug(f"New child information: {self.child_doc}")
                if self._newchild != None:
                    self._newchild(target=id)
                self.w_fr.after(ms=1, func=self.new) # .after is required to make self.new trigger after <<TreeviewSelect>>
                self.logger.debug(f"Data pane set to new child of {id}")
            else:
                self.logger.debug(f"Did not create new child, as user declined")
        else:
            self.logger.debug(f"Did not create new child, as parent has no id")


    @busy
    def photo(self, *args):
        '''Callback for when the photo is pressed.'''
        self.logger.debug(f"Photo button activated")
        for child in self.w_bu_photo.winfo_children():
            child.destroy()
        window = tk.Toplevel(master=self.w_bu_photo)
        self.logger.info(f"Photo window opened")
        window.attributes("-topmost", True)
        window.focus_force()
        window.title("Photo")
        window.configure(background="#DCDAD5")

        def clear():
            '''Removes current photo from data pane.'''
            self.logger.debug(f"Photo clear button activated")
            self.current_photo = None
            img = ImageTk.PhotoImage(self.photo_blank)
            self.w_bu_photo.config(image=img)
            self.w_bu_photo.image = img
            self.logger.info(f"Photo cleared from data pane")
            self.data_change()

        def fetch_photo(feed: int = 0):
            '''Updates the photoframe with a new photo.'''
            photo = self.photomanager.take_photo(feed)
            if photo != None:
                img = ImageTk.PhotoImage(image=photo)
                photoframe[feed].config(image=img)
                photoframe[feed].image = img
                window.after(ms=250, func=lambda *_: fetch_photo(feed=feed))

        def from_file():
            '''Loads a file from disk.'''
            self.logger.debug(f"From file button activated")

        def update(feed: int = 0):
            '''Pushes current photo to data pane. Can function as a callback.'''
            self.logger.debug(f"Photo update button activated")
            self.current_photo = self.photomanager.take_photo(feed)
            if self.current_photo != None:
                img = ImageTk.PhotoImage(self.current_photo)
                self.w_bu_photo.config(image=img)
                self.w_bu_photo.image = img
                self.logger.info(f"Photo pushed to data pane")
            window.destroy()
            self.logger.debug(f"Closed photo window")
            self.data_change()

        self.logger.debug(f"Preparing photo window widgets")

        clearbut = ttk.Button(master=window, text="Clear", command=clear)
        fromfilebut = ttk.Button(master=window, text="From File", command=from_file)
        window.bind("<Return>", update, add="+")

        window.columnconfigure(index=0, weight=1000)
        window.columnconfigure(index=1, weight=1000)
        window.rowconfigure(index=0, weight=1000)
        window.rowconfigure(index=1, weight=1000)
        window.rowconfigure(index=2, weight=1, minsize=25)

        self.logger.debug(f"Packing and gridding photo window widgets")

        clearbut.grid(column=0, row=2, sticky='nsew', padx=2, pady=2)
        fromfilebut.grid(column=1, row=2, sticky='nsew', padx=2, pady=2)

        cameras = len(self.photomanager.cameras)
        photoframe = []
        if cameras > 0:
            photoframe.append(ttk.Button(master=window, text="A", command=lambda *_: update(feed=0)))
            if cameras == 1:
                photoframe[0].grid(column=0, row=0, columnspan=2, sticky='nsew', padx=2, pady=2)
            else:
                photoframe[0].grid(column=0, row=0, sticky='nsew', padx=2, pady=2)
            fetch_photo(0)
        if cameras > 1:
            photoframe.append(ttk.Button(master=window, text="B", command=lambda *_: update(feed=1)))
            photoframe[1].grid(column=1, row=0, sticky='nsew', padx=2, pady=2)
            fetch_photo(1)
        if cameras > 2:
            photoframe.append(ttk.Button(master=window, text="C", command=lambda *_: update(feed=2)))
            if cameras == 3:
                photoframe[2].grid(column=0, row=1, columnspan=2, sticky='nsew', padx=2, pady=2)
            else:
                photoframe[2].grid(column=0, row=1, sticky='nsew', padx=2, pady=2)
            fetch_photo(2)
        if cameras > 3:
            photoframe.append(ttk.Button(master=window, text="D", command=lambda *_: update(feed=3)))
            photoframe[3].grid(column=1, row=1, sticky='nsew', padx=2, pady=2)
            fetch_photo(3)


    def read(self, event: tk.Event, source: str):
        '''Callback for when read field's read button is pressed.
        
        event: The tkinter event object associated with the callback.
        source: The source to read from.
        '''
        self.logger.debug(f"Read button activated")
        button = event.widget
        state = str(button.cget("state"))
        if state != "disabled":
            row = self.w_buttona_data.index(button)
            entry = self.w_input_data[row]
            field = self.w_la_data[row]
            self.logger.debug(f"Activated read button corresponds to {field['text']} field")

            for child in button.winfo_children():
                child.destroy()
            window = tk.Toplevel(master=button)
            self.logger.info(f"Read window opened")
            window.attributes("-topmost", True)
            window.focus_force()
            window.title(field.cget("text"))
            window.configure(background="#D9D9D9")

            if source == "WEIGHT":
                import random
                self.logger.debug(f"Read source is WEIGHT")

                def read_weight(*args):
                    '''Reads the current weight from another device.'''
                    result = ''
                    if self.hardware is not None and self.hardware.SCALES_EXIST:
                        result = self.hardware.getCurrentWeight()
                    else:
                        result = round(80+random.random()*10, 2) 
                    if result != '':
                        msg.config(text=str(result))
                    window.after(100, read_weight)

                def commit_weight(*args):
                    '''Inserts current weight into data pane.'''
                    self.logger.info(f"Pushed weight to data pane")
                    entry.delete(0, "end")
                    entry.insert(0, msg.cget('text'))
                    window.destroy()
                    self.logger.debug(f"Close read window")
                    self.data_change()

                self.logger.debug(f"Prepare read window widgets")
                msg = ttk.Label(master=window)
                getbutton = ttk.Button(master=window, text="Update")
                window.bind("<Return>", commit_weight, add="+")

                self.logger.debug(f"Pack and grid read window widgets")
                getbutton.config(command=commit_weight)
                msg.grid(column=0, row=0, sticky="nsew", padx=10, pady=10)
                getbutton.grid(column=0, row=1, sticky="nsew", padx=10, pady=10)
                read_weight()
            
            else:
                self.logger.error(f"Could not display read window contents, as read source is unknown")

        else:
            self.logger.debug(f"Did not open read window, as button is disabled")


    def readlist(self, event: tk.Event, source: str):
        '''Callback for when list field's read button is pressed.
        
        event: The tkinter event object associated with the callback.
        source: The source to read from.
        '''
        self.logger.debug(f"List field's read button activated")
        button = event.widget
        state = str(button.cget("state"))
        if state != "disabled":
            row = self.w_buttonb_data.index(button)
            entry = self.w_input_data[row]
            field = self.w_la_data[row]
            self.logger.debug(f"Activated read button corresponds to {field['text']} field")

            for child in button.winfo_children():
                child.destroy()
            window = tk.Toplevel(master=button)
            self.logger.info(f"Read window opened")
            window.attributes("-topmost", True)
            window.focus_force()
            window.title(field.cget("text"))
            window.configure(background="#D9D9D9")

            if source == "IDS":
                self.logger.debug(f"Read source is IDS")
                cur_id = self.last_doc.get("_id","")
                parents = self.db.item_parents(item=cur_id)
                base = self.db.item_get(id=parents[0]) if len(parents) > 0 else self.db.items_query(cat="Evacuation", selector={"Display Name":{"$eq":"DEHC"}}, fields=["_id", "Display Name"])[0]

                listids = [] if self.w_hidden_data[row] == "" else self.w_hidden_data[row]
                self.logger.debug(f"Existing ids for read window: {listids} / {entry['values']}")

                def addname():
                    '''Callback when tree -> list button is pressed.'''
                    self.logger.debug(f"Add button activated in ID name list window")
                    id, name = tree.tree_get()
                    if name not in namelist.get(0, "end"):
                        listids.append(id)
                        namelist.insert("end", name)
                        self.logger.info(f"Added {id} / {name} to ID name list")
                    else:
                        self.logger.debug(f"Did not add {id} / {name} to ID name list, as it was already there")

                def removename():
                    '''Callback when tree <- list button is pressed.'''
                    self.logger.debug(f"Remove button activated in ID name list window")
                    indexes = namelist.curselection()
                    if len(indexes) > 0:
                        index, *_ = indexes
                        id = listids.pop(index)
                        namelist.delete(index)
                        self.logger.info(f"Removed {id} from ID name list")
                    else:
                        self.logger.debug(f"Did not remove any IDs from name list, as nothing was selected")

                def submit(*args):
                    '''Submits current list to the data pane.'''
                    self.logger.debug(f"Submit button activated in ID name list window")
                    values = namelist.get(0,"end")
                    entry.config(values=values)
                    if len(values) > 0:
                        entry.current(0)
                    self.w_hidden_data[row] = listids
                    self.logger.info(f"Pushed ids to date pane: {listids} / {values}")
                    window.destroy()
                    self.logger.debug(f"List field's read window closed")
                    self.data_change()

                self.logger.debug(f"Prepare read window widgets")
                tree = SearchTree(master=window, db=self.db, base=base, cats=self.cats, level=self.level, prepare=True, simple=True, hardware=self.hardware)
                namelistlb = ttk.Label(master=window, text="Guardians")
                namelist = tk.Listbox(master=window, selectmode=tk.SINGLE)
                for name in entry['values']:
                    namelist.insert("end", name)
                addbut = ttk.Button(master=window, text="Add", command=addname)
                removebut = ttk.Button(master=window, text="Remove", command=removename)
                submitbut = ttk.Button(master=window, text="Update", command=submit)
                tree.w_tr_tree.focus_set()

                window.bind("<Return>", lambda *_: addname(), add="+")
                window.bind("<Shift-Return>", lambda *_: submit(), add="+")

                window.columnconfigure(0, weight=1000)
                window.columnconfigure(1, weight=1000)
                window.columnconfigure(2, weight=1000)
                window.columnconfigure(3, weight=1000)
                window.rowconfigure(0, weight=1, minsize=24)
                window.rowconfigure(1, weight=1000)
                window.rowconfigure(2, weight=1000)
                window.rowconfigure(3, weight=1000)

                self.logger.debug(f"Pack and grid read window widgets")
                tree.grid(column=0, row=0, rowspan=4, sticky="nsew", padx=2, pady=2)
                namelistlb.grid(column=1, row=0, sticky="nsew", padx=2, pady=2)
                namelist.grid(column=1, row=1, rowspan=3, sticky="nsew", padx=2, pady=2)
                addbut.grid(column=2, row=1, sticky="nsew", padx=2, pady=2)
                removebut.grid(column=2, row=2, sticky="nsew", padx=2, pady=2)
                submitbut.grid(column=2, row=3, sticky="nsew", padx=2, pady=2)
            
            elif source == "PHYSIDS":
                self.logger.debug(f"Read source is PHYSIDS")
                
                def addid():
                    '''Callback when add button is pressed.'''
                    self.logger.debug(f"Add button activated in physical ID list window")
                    id = idvar.get()
                    if id not in idlist.get(0, "end") and len(id) > 0:
                        idlist.insert("end", id)
                        identry.delete(0, "end")
                        self.logger.info(f"Added {id} to physical ID list")
                    else:
                        self.logger.debug(f"Did not add to physical ID list, as id was blank or already existed")

                def removeid():
                    '''Callback when remove button is pressed.'''
                    self.logger.debug(f"Remove button activated in physical ID list window")
                    indexes = idlist.curselection()
                    if len(indexes) > 0:
                        index, *_ = indexes
                        idlist.delete(index)
                        self.logger.info(f"Deleted physical ID at index {index}")
                    else:
                        self.logger.debug(f"Did not delete physical ID, as none were selected")

                def getNFCorBarcode():
                    result = ''
                    if self.hardware is not None:
                        nfcResult = self.hardware.getCurrentNFCUID()
                        barcodeResult = self.hardware.getCurrentBarcode()
                        if nfcResult == '':
                            if barcodeResult != '':
                                result = barcodeResult
                        if barcodeResult == '':
                            if nfcResult != '':
                                result = nfcResult
                    if result != '':
                        idvar.set(result)
                    window.after(250, getNFCorBarcode)

                def submit(*args):
                    '''Callback when submit button is pressed.'''
                    self.logger.debug(f"Submit button activated in physical ID list window")
                    values = idlist.get(0,"end")
                    entry.config(values=values)
                    if len(values) > 0:
                        entry.current(0)
                    self.w_hidden_data[row] = values
                    self.logger.info(f"Pushed physical ids to date pane: {values}")
                    window.destroy()
                    self.logger.debug(f"List field's read window closed")
                    self.data_change()

                self.logger.debug(f"Prepare read window widgets")
                idvar = tk.StringVar()
                idlistlb = ttk.Label(master=window, text="Physical IDs")
                idlist = tk.Listbox(master=window, selectmode=tk.SINGLE)
                for id in entry['values']:
                    idlist.insert("end", id)
                identry = ttk.Entry(master=window, textvariable=idvar)
                addbut = ttk.Button(master=window, text="Add", command=addid)
                removebut = ttk.Button(master=window, text="Remove", command=removeid)
                submitbut = ttk.Button(master=window, text="Update", command=submit)
                identry.focus()

                window.bind("<Return>", lambda *_: addid(), add="+")
                window.bind("<Shift-Return>", lambda *_: submit(), add="+")

                window.columnconfigure(0, weight=1000)
                window.columnconfigure(1, weight=1000)
                window.rowconfigure(0, weight=1000)
                window.rowconfigure(1, weight=1000)
                window.rowconfigure(2, weight=1000)
                window.rowconfigure(3, weight=1000)
                window.rowconfigure(4, weight=1000)

                self.logger.debug(f"Pack and grid read window widgets")
                idlistlb.grid(column=0, row=0, columnspan=2, sticky="nsew", padx=2, pady=2)
                idlist.grid(column=0, row=1, rowspan=4, sticky="nsew", padx=2, pady=2)
                identry.grid(column=1, row=1, sticky="nsew", padx=2, pady=2)
                addbut.grid(column=1, row=2, sticky="nsew", padx=2, pady=2)
                removebut.grid(column=1, row=3, sticky="nsew", padx=2, pady=2)
                submitbut.grid(column=1, row=4, sticky="nsew", padx=2, pady=2)

                getNFCorBarcode()
            
            else:
                self.logger.error(f"Could not display read window contents, as read source is unknown")
        
        else:
            self.logger.debug(f"Did not open read window, as button is disabled")


    def remove(self, *args):
        '''Callback for when the flag remove button is pressed'''
        self.logger.debug(f"Remove flag button activated")
        sel, *_ = self.w_li_flags.curselection()
        self.w_li_flags.delete(sel)
        self.logger.info(f"Removed flag from flag list with index {sel}")
        self.data_change()


    @busy
    def save(self, *args):
        '''Callback for when the save button is pressed.'''
        self.logger.debug(f"Save button activated")
        doc = self.last_doc
        physid = None
        schema = self.db.schema_schema(cat=self.last_doc["category"])
        for index, (field, info) in enumerate(schema.items()):
            if self.w_hidden_data[index] == None:
                if info.get('type','') == 'multitext':
                    value = self.w_input_data[index].get("1.0","end").rstrip()
                else:
                    value = self.w_var_data[index].get()
            else:
                if info.get('type','') == 'list' and info.get('source','') == 'PHYSIDS':
                    physid = self.w_hidden_data[index]
                    value = ""
                else:
                    value = self.w_hidden_data[index]
            if info['required'] == True and value == "":
                messagebox.showwarning("Missing Information", f"Could not save item because required field \"{field}\" is empty.")
                self.logger.warning(f"Could not save item because required field \"{field}\" is empty")
                break
            regex = info.get('regex', None)
            if regex != None:
                if not re.match(regex, value):
                    messagebox.showwarning("Incorrect Information", f"Could not save item because field \"{field}\" fails validation.")
                    self.logger.warning(f"Could not save item because field \"{field}\" fails validation.")
                    break
            doc[field] = value
        else:
            self.editing = False
            self.logger.info(f"Edit mode set to {self.editing}")
            doc["flags"] = list(self.w_li_flags.get(0, "end"))
            if "_id" in doc:
                self.logger.info(f"Editing {doc['category']} {doc['_id']}")
                self.db.item_edit(id=doc["_id"], data=doc)
                id = None
            else:
                self.logger.info(f"Saving new {doc['category']}")
                doc["_id"] = self.db.item_create(cat=doc["category"], doc=doc)
                id = doc["_id"]
            if physid != None:
                self.db.ids_edit(item=doc["_id"], ids=physid)
            if self.current_photo != None:
                self.db.photo_save(item=doc["_id"], img=self.current_photo)
            else:
                if self.last_photo != None:
                    self.db.photo_delete(item=doc["_id"])
            if self._save != None:
                self._save(id)
            self.back_doc = self.last_doc
            self.logger.debug(f"Back doc is now {self.back_doc.get('_id','_')}")
            self.last_doc = doc
            self.w_bu_cancel.invoke()
            self.logger.info("Save completed")
            return True
        return False


    @busy
    def show(self, doc: dict = None):
        '''Displays a new document.
        
        doc: The document to display. If omitted, the previous document will be used.
        '''
        if doc != None:
            if self.last_doc != doc:
                self.back_doc = self.last_doc
                self.logger.debug(f"Back doc is now {self.back_doc.get('_id','_')}")
                self.last_doc = doc
            id = self.last_doc.get("_id", "")
            self.logger.info(f"Showing document {id if id != '' else '_'} in the data pane")
            self.last_photo = self.db.photo_load(item=id)
        else:
            self.logger.info("Showing document _ in the data pane")

        for child in self.w_fr_data.winfo_children():
            child.destroy()

        self.w_bu_photo.config(image="")
        self.current_photo = self.last_photo
        self.w_li_flags.delete(0, "end")
        self.w_co_flags.set("")
        self.w_co_flags['values'] = []

        self.w_var_data = []
        self.w_la_data = []
        self.w_input_data = []
        self.w_buttona_data = []
        self.w_buttonb_data = []
        self.w_buttonc_data = []
        self.w_hidden_data = []

        self.editing = False
        self.w_bu_photo.config(command="")
        self.w_bu_editphoto.config(state="disabled")
        self.w_bu_edit.config(state="disabled")
        self.w_bu_cancel.config(state="disabled")
        self.w_bu_save.config(state="disabled")
        self.w_bu_delete.config(state="disabled")
        self.w_bu_add.config(state="disabled")
        self.w_bu_remove.config(state="disabled")
        self.w_co_flags.config(state="disabled")
        self.logger.debug(f"Data pane buttons are now disabled")

        if self.current_photo != None:
            img = ImageTk.PhotoImage(self.current_photo)
        else:
            img = ImageTk.PhotoImage(self.photo_blank)
        self.w_bu_photo.config(image=img)
        self.w_bu_photo.image = img

        if len(self.last_doc) > 0:
            self.w_bu_edit.config(state="normal")

            cat = self.last_doc["category"]
            schema = self.db.schema_schema(cat=cat)
            title = f"{self.last_doc.get(self.db.schema_name(cat=cat), cat)} ({self.last_doc.get('_id','New')})"
            self.w_la_title.config(text=title)
            self.w_fr_data.columnconfigure(index=0, weight=1000, minsize=96)
            self.w_fr_data.columnconfigure(index=1, weight=1000, minsize=96)
            self.w_fr_data.columnconfigure(index=2, weight=1000, minsize=32)
            self.w_fr_data.columnconfigure(index=3, weight=1000, minsize=32)
            self.w_fr_data.columnconfigure(index=4, weight=1000, minsize=32)

            for index, (field, info) in enumerate(schema.items()):
                value = self.last_doc.get(field, "")
                label = ttk.Label(master=self.w_fr_data, text=field, justify=tk.LEFT, anchor="w")
                w_type = info['type']

                if w_type == "lock":
                    var = tk.IntVar()
                    if value in [0, 1]:
                        var.set(value)
                    else:
                        var.set(0)
                else:
                    var = tk.StringVar()
                    var.set(value)
                var.trace("w", self.data_change)

                if w_type == "text":
                    entry = ttk.Entry(master=self.w_fr_data, textvariable=var, state="disabled")
                    buttona = None
                    buttonb = None
                    buttonc = None
                    hidden = None

                elif w_type == "multitext":
                    entry = tk.Text(master=self.w_fr_data, wrap=tk.WORD, height=3)
                    entry.insert("1.0", value)
                    entry.config(state="disabled")
                    buttona = None
                    buttonb = None
                    buttonc = None
                    hidden = None

                elif w_type == "lock":
                    entry = ttk.Checkbutton(master=self.w_fr_data, text="Locked?", variable=var, state="disabled")
                    buttona = None
                    buttonb = None
                    buttonc = None
                    hidden = None

                elif w_type == "option":
                    entry = ttk.Combobox(master=self.w_fr_data, textvariable=var, values=info['options'], state="disabled")
                    buttona = None
                    buttonb = None
                    buttonc = None
                    hidden = None

                elif w_type == "read":
                    entry = ttk.Entry(master=self.w_fr_data, textvariable=var, state="disabled")
                    buttona = ttk.Button(master=self.w_fr_data, text="Read", state="disabled")
                    source = info['source']
                    if source == "WEIGHT":
                        buttona.bind("<Button-1>", lambda e: self.read(event=e, source="WEIGHT"))
                    buttonb = None
                    buttonc = None
                    hidden = None

                elif w_type == "list":
                    source = info['source']
                    if value != "":
                        names = [item["Display Name"] for item in self.db.items_get(ids=value, fields=["Display Name"])]
                    else:
                        last_id = self.last_doc.get("_id", "")
                        if last_id != "" and source == "PHYSIDS":
                            names = self.db.ids_get(item=self.last_doc["_id"])
                            value = names
                        else:
                            names = []
                    
                    entry = ttk.Combobox(master=self.w_fr_data, values=names, state="readonly")
                    if len(entry['values']) > 0:
                        entry.current(0)
                    
                    buttonb = ttk.Button(master=self.w_fr_data, text="Edit", state="disabled")
                    if source == "IDS":
                        buttonb.bind("<Button-1>", lambda e: self.readlist(event=e, source="IDS"))
                        buttona = ttk.Button(master=self.w_fr_data, text="Show", state="normal")
                        buttona.bind("<Button-1>", lambda e: self.showlist(event=e, source="IDS"))
                        buttonc = ttk.Button(master=self.w_fr_data, text="Create", state="normal")
                        if self.readonly == False:
                            buttonc.bind("<Button-1>", self.newchild)
                    elif source == "PHYSIDS":
                        buttonb.bind("<Button-1>", lambda e: self.readlist(event=e, source="PHYSIDS"))
                        buttonc = None
                    else:
                        buttona = None
                        buttonc = None
                    hidden = value

                elif w_type == "sum":
                    entry = ttk.Entry(master=self.w_fr_data)
                    if self.last_doc.get('_id','') != "":
                        children = self.db.container_children_all(container=self.last_doc["_id"], cat=info['cat'], result="DOC")
                        target = info['target']
                        items = []
                        defaulted = False
                        for child in children:
                            value = child.get(target, "")
                            if value == "":
                                default = self.db.schema_schema(cat=child['category'])[target].get('default', 0)
                                value = default
                                defaulted = True
                            try:
                                items.append(float(value))
                            except:
                                items.append(0.0)
                        itemsum = f"{sum(items):.1f}" if len(items) > 0 else ""
                        if defaulted == True:
                            itemsum += "*"
                        entry.insert(0, itemsum)
                    entry.config(state="disabled")
                    buttona = None
                    buttonb = None
                    buttonc = None
                    hidden = ""
                
                elif w_type == "count":
                    entry = ttk.Entry(master=self.w_fr_data)
                    if self.last_doc.get('_id','') != "":
                        children = self.db.container_children_all(container=self.last_doc["_id"], cat=info['cat'], result="DOC")
                        counts = len(children)
                        entry.insert(0, counts)
                    entry.config(state="disabled")
                    buttona = None
                    buttonb = None
                    buttonc = None
                    hidden = ""

                else:
                    entry = ttk.Label(master=self.w_fr_data)
                    buttona = None
                    buttonb = None
                    buttonc = None
                    hidden = None

                missing = 0
                for button in [buttona, buttonb, buttonc]:
                    if button == None:
                        missing += 1
                
                label.bind("<Double-Button-1>", lambda *_: self.w_bu_edit.invoke())
                entry.bind("<Double-Button-1>", lambda *_: self.w_bu_edit.invoke())

                label.grid(column=0, row=index, sticky="nsew", padx=1, pady=1)
                entry.grid(column=1, row=index, columnspan=missing+1, sticky="nsew", padx=1, pady=1)
                if buttona != None:
                    buttona.bind("<Double-Button-1>", lambda *_: self.w_bu_edit.invoke())
                    buttona.grid(column=missing+2, row=index, sticky="nsew", padx=1, pady=1)
                if buttonb != None:
                    buttonb.bind("<Double-Button-1>", lambda *_: self.w_bu_edit.invoke())
                    if buttonc == None:
                        buttonb.grid(column=4, row=index, sticky="nsew", padx=1, pady=1)
                    else:
                        buttonb.grid(column=3, row=index, sticky="nsew", padx=1, pady=1)
                if buttonc != None:
                    buttonc.bind("<Double-Button-1>", lambda *_: self.w_bu_edit.invoke())
                    buttonc.grid(column=4, row=index, sticky="nsew", padx=1, pady=1)

                self.w_var_data.append(var)
                self.w_la_data.append(label)
                self.w_input_data.append(entry)
                self.w_buttona_data.append(buttona)
                self.w_buttonb_data.append(buttonb)
                self.w_buttonc_data.append(buttonc)
                self.w_hidden_data.append(hidden)

            flags = self.last_doc.get("flags", [])
            flags.sort()
            for index, flag in enumerate(flags):
                self.w_li_flags.insert(index, flag)
            if len(flags) > 0:
                self.w_li_flags.selection_set(0)

            # Correct size and tab order
            for entry, buttona, buttonb, buttonc in zip(self.w_input_data, self.w_buttona_data, self.w_buttonb_data, self.w_buttonc_data):
                if entry != None:
                    entry.lift()
                if buttona != None:
                    buttona.lift()
                if buttonb != None:
                    buttonb.lift()
                if buttonc != None:
                    buttonc.lift()
        
        self.logger.debug("Current show completed")


    @busy
    def showlist(self, event: tk.Event, source: str):
        '''Callback for when the 'show' button is pressed for a given list field.
        
        event: The tkinter event object associated with the callback.
        source: The source to read from.
        '''
        self.logger.debug("Show button activated")
        button = event.widget
        state = str(button.cget("state"))
        if state != "disabled":
            if self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to open a different item?"):
                row = self.w_buttona_data.index(button)
                entry = self.w_input_data[row]
                hidden = self.w_hidden_data[row]
                if source == "IDS":
                    if len(entry['values']) > 0:
                        id = hidden[entry.current()]
                        self._show(id)
            else:
                self.logger.debug("Did not show, as the user declined")
        else:
            self.logger.debug("Did not show, as the state is disabled")


    def __del__(self):
        '''Runs when DataEntry object is deleted.'''
        self.photomanager.destroy()


# ----------------------------------------------------------------------------

class SearchTree(SuperWidget):
    '''A SuperWidget representing a searchable tree.'''

    def __init__(self, master: tk.Misc, db: md.DEHCDatabase, base: dict, *, autoopen: bool = False, cats: list = [], level: str = "NOTSET", prepare: bool = True, readonly: bool = False, select: Callable = None, simple: bool = False, statusbar: StatusBar = None, yesno: Callable = None, hardware: hw.Hardware = None):
        '''Constructs a SearchTree object.
        
        master: The widget that the SearchTree's component widgets will be instantiated under.
        db: The database object which the widget uses for database transactions.
        base: The document of the item upon which the tree is initially based.
        autoopen: The default setting for autoopen.
        cats: The categories of items that can be searched.
        dragstarttree: Stores the origin tree when clicking and dragging.
        dragstartid: Stores the id of the origin item when clicking and dragging between trees.
        last_selector: The most recently used selector for a database search.
        level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
        prepare: If true, automatically prepares widgets for packing.
        select: If present, a callback function that triggers when a tree item is selected.
        simple: If true, the tree is "simplified", removing drag & drop functionality and hiding some controls.
        yesno: If present, a callback function that handles prompting the user with yes/no to proceed.
        '''
        super().__init__(master=master, db=db, level=level)

        self.cats = cats                               # A list of item categories that can be selected
        self.ops = ["=", "<", ">", "≤", "≥", "≠", "≈"] # The operators available to use in searches
        self._select = select                          # A callback which triggers when a tree node is selected
        self.altheld = False                           # Whether or not the alt key is currently being held
        self.ctrlheld = False                          # Whether or not the ctrl key is currently being held
        self.autoopen = autoopen                       # The starting value of autoopen
        self.base = base                               # The current base of the tree
        self.mindragtime = 0.2                         # The minimum time (in seconds) a drag must last to count
        self.dragstarttime = None                      # The time a drag was started
        self.dragstarttree = None                      # The SearchTree a drag and drop originated from
        self.dragstartid = None                        # The ID of the item at the start of a drag and drop
        self.headings = {}                             # The tree headings when summation is turned on
        self.last_selector = {}                        # The previous search selector
        self.readonly = readonly                       # Whether or not the application is in readonly mode
        self.root = self.w_fr.winfo_toplevel()         # The root widget that contains this SuperWidget
        self.selection = None                          # The currently selected item
        self.search_result = None                      # The previous search result
        self.simple = simple                           # Whether or not to hide auto-open and summation
        self.statusbar = statusbar                     # The status bar associated with this object
        self.summables = self.db.schema_sums()         # List of summable fields
        self.summation = False                         # Whether or not summation is currently turned on
        self.yes_no = yesno                            # A callback which leads to a DataEntry's yes_no()
        self.hardware = hardware                       # The hardware manager

        if prepare == True:
            self.prepare()


    def prepare(self):
        '''Constructs the frames and widgets of the SearchTree.'''
        # Frames & Canvas
        self.logger.debug(f"Preparing widgets")
        self.w_fr_search = ttk.Frame(master=self.w_fr)

        self.w_fr.columnconfigure(0, weight=1, minsize=128)
        self.w_fr.columnconfigure(1, weight=1, minsize=16)
        self.w_fr.columnconfigure(2, weight=1000, minsize=48)
        self.w_fr.columnconfigure(3, weight=1000, minsize=48)
        self.w_fr.columnconfigure(4, weight=1, minsize=16)
        self.w_fr.rowconfigure(0, weight=1, minsize=24)
        self.w_fr.rowconfigure(1, weight=1000)
        self.w_fr.rowconfigure(2, weight=1, minsize=17)

        self.w_fr_search.columnconfigure(0, weight=1000)
        self.w_fr_search.columnconfigure(1, weight=1000)
        self.w_fr_search.columnconfigure(2, weight=1000)
        self.w_fr_search.columnconfigure(3, weight=1000)
        self.w_fr_search.columnconfigure(4, weight=1000)
        self.w_fr_search.columnconfigure(5, weight=1000)
        self.w_fr_search.columnconfigure(6, weight=1000)
        self.w_fr_search.rowconfigure(0, weight=1000)

        # Variables
        self.w_var_cat = tk.StringVar()
        self.w_var_cat.trace("w", self.search_cat)
        self.w_var_field = tk.StringVar()
        self.w_var_op = tk.StringVar()
        self.w_var_value = tk.StringVar()
        self.w_var_autoopen = tk.IntVar()
        if self.autoopen == True:
            self.w_var_autoopen.set(1)
        self.w_var_summation = tk.IntVar()
        self.w_var_summation.trace("w", self.summation_toggle)

        # Widgets
        self.w_co_cat = ttk.Combobox(master=self.w_fr_search, values=self.cats, textvariable=self.w_var_cat, state="readonly")
        self.w_co_field = ttk.Combobox(master=self.w_fr_search, textvariable=self.w_var_field, state="readonly")
        self.w_co_op = ttk.Combobox(master=self.w_fr_search, value=self.ops, textvariable=self.w_var_op, state="readonly")
        self.w_en_value = ttk.Entry(master=self.w_fr_search, textvariable=self.w_var_value)
        self.w_bu_search = ttk.Button(master=self.w_fr_search, text="Search", command=lambda *_: self.search())
        self.w_bu_narrow = ttk.Button(master=self.w_fr_search, text="Narrow", command=self.narrow)
        self.w_bu_scan = ttk.Button(master=self.w_fr_search, text="Phys ID Search", command=self.scan)
        self.w_li_search = tk.Listbox(master=self.w_fr, selectmode=tk.SINGLE, relief=tk.GROOVE, exportselection=False)
        self.w_tr_tree = ttk.Treeview(master=self.w_fr, columns=list(range(1,len(self.summables)+2)), show="tree", selectmode="browse", style="unactive.Treeview")
        self.w_tr_tree.SearchTree = self
        self.w_ch_autoopen = ttk.Checkbutton(master=self.w_fr, variable=self.w_var_autoopen, text="Auto Open?")
        self.w_ch_summation = ttk.Checkbutton(master=self.w_fr, variable=self.w_var_summation, text="Show Sums?")

        self.w_en_value.bind("<Return>", self.search, add="+")
        self.w_li_search.bind("<<ListboxSelect>>", self.search_select)

        self.w_tr_tree.bind("<<TreeviewSelect>>", self.tree_select)
        self.w_tr_tree.bind("<<TreeviewOpen>>", lambda *_: self.tree_open())
        self.w_tr_tree.bind("<<TreeviewClose>>", lambda *_: self.tree_close())
        self.w_tr_tree.bind("<Button-3>", self.tree_rebase_mouse)
        self.w_tr_tree.bind("<Control-r>", self.tree_rebase_keyboard)

        self.root.bind("<KeyPress-Alt_L>", self.altpress, add="+")
        self.root.bind("<KeyRelease-Alt_L>", self.altrelease, add="+")
        self.root.bind("<KeyPress-Control_L>", self.ctrlpress, add="+")
        self.root.bind("<KeyRelease-Control_L>", self.ctrlrelease, add="+")

        if self.readonly == False:
            self.w_tr_tree.bind("<ButtonPress-1>", self.dragstart)
            self.w_tr_tree.bind("<B1-Motion>", self.dragmid)
            self.w_tr_tree.bind("<ButtonRelease-1>", self.dragstop)

        self.w_co_cat.current(0)
        self.w_co_field.current(1)
        self.w_co_op.current(0)
        self.w_tr_tree.column(column="#0", anchor=tk.E, stretch=False, minwidth=30)
        self.w_tr_tree.heading("#0", text="Item")
        for index, field in enumerate(self.summables):
            headname = field
            headid = index+1
            self.headings[headname] = index
            self.w_tr_tree.column(column=headid, anchor=tk.E, stretch=False, minwidth=12)
            self.w_tr_tree.heading(headid, text=headname)
        self.w_tr_tree.column(column=len(self.summables)+1, anchor=tk.E, stretch=False, minwidth=12)
        self.w_tr_tree.heading(len(self.summables)+1, text="Flags")

        # Scrollbars
        self.w_sc_tree = ttk.Scrollbar(master=self.w_fr, orient="vertical", command=self.w_tr_tree.yview)
        self.w_tr_tree.config(yscrollcommand=self.w_sc_tree.set)
        self.w_sc_search = ttk.Scrollbar(master=self.w_fr, orient="vertical", command=self.w_li_search.yview)
        self.w_li_search.config(yscrollcommand=self.w_sc_search.set)

        # Misc
        self.tree_refresh()
        self.w_tr_tree.selection_set(self.base["_id"])
        self.w_tr_tree.focus(self.base["_id"])
        self.tree_open(self.base["_id"])
        self.w_tr_tree.see(item=self.base["_id"])


    def _pack_children(self):
        '''Packs & grids children frames and widgets of the SearchTree.'''
        self.logger.debug(f"Packing and gridding widgets")

        # Frames & Canvas
        self.w_fr_search.grid(column=0, row=0, columnspan=5, sticky="nsew")

        # Widgets
        self.w_co_cat.grid(column=0, row=0, sticky="nsew", padx=1, pady=1)
        self.w_co_field.grid(column=1, row=0, sticky="nsew", padx=1, pady=1)
        self.w_co_op.grid(column=2, row=0, sticky="nsew", padx=1, pady=1)
        self.w_en_value.grid(column=3, row=0, sticky="nsew", padx=1, pady=1)
        self.w_bu_search.grid(column=4, row=0, sticky="nsew", padx=1, pady=1)
        self.w_bu_narrow.grid(column=5, row=0, sticky="nsew", padx=1, pady=1)
        self.w_bu_scan.grid(column=6, row=0, sticky="nsew", padx=1, pady=1)
        self.w_li_search.grid(column=0, row=1, rowspan=2, sticky="nsew", padx=1, pady=1)
        self.w_sc_search.grid(column=1, row=1, rowspan=2, sticky="nse", padx=1, pady=1)
        self.w_tr_tree.grid(column=2, row=1, columnspan=2, sticky="nsew", padx=1, pady=1)
        self.w_sc_tree.grid(column=4, row=1, sticky="nse", padx=1, pady=1)

        if self.simple == False:
            self.w_ch_autoopen.grid(column=2, row=2, sticky="nsew", padx=1, pady=1)
            self.w_ch_summation.grid(column=3, row=2, columnspan=2, sticky="nsew", padx=1, pady=1)


    def altpress(self, *args):
        '''Callback for when alt is pressed down.'''
        self.altheld = True

    
    def altrelease(self, *args):
        '''Callback for when alt is released.'''
        self.altheld = False


    def ctrlpress(self, *args):
        '''Callback for when ctrl is pressed down.'''
        self.ctrlheld = True

    
    def ctrlrelease(self, *args):
        '''Callback for when ctrl is released.'''
        self.ctrlheld = False


    def dragstart(self, *args):
        '''Callback for when the mouse is clicked down on the tree.'''
        if self.ctrlheld == True:
            event, = args
            tree = event.widget
            self.dragstarttime = time.time()
            self.dragstartid = tree.identify_row(event.y)
            self.dragstarttree = tree.SearchTree
            self.logger.debug(f"Mouse clicked on tree. Root xy: {tree.winfo_pointerxy()}; Tree: {tree}; Tree xy: {(event.x, event.y)}; Row: {repr(self.dragstartid)}")


    def dragmid(self, *args):
        '''Callback for when the mouse is mid-drag'''
        if self.dragstartid != None:
            self.root.configure(cursor="target")

    @busy
    def dragstop(self, *args):
        '''Callback for when the mouse is released after clicking down on the tree.'''
        if self.root['cursor'] == "target":
            self.root.configure(cursor="")

        if self.ctrlheld == True:
            event, = args
            dragendtime = time.time()
            mx, my = event.widget.winfo_pointerxy()
            tree = self.w_fr.winfo_containing(mx, my)
            dragtime = dragendtime - self.dragstarttime

            if dragtime > self.mindragtime:
                self.logger.debug(f"Mouse released. Time: {dragtime}; Root xy: {(mx, my)}; Target tree: {tree}; Start ID: {repr(self.dragstartid)}")

                if tree != None and tree.winfo_class() == "Treeview" and self.dragstartid not in [None, ""] and self.dragstarttree not in [None, ""]:
                    dragstarttree = self.dragstarttree
                    dragendtree = tree.SearchTree
                    x = mx - tree.winfo_rootx()
                    y = my - tree.winfo_rooty()
                    dragstartid = self.dragstartid
                    dragendid = tree.identify_row(y)
                    self.logger.debug(f"Mouse released cont. Target tree xy: {(x, y)}; Target row: {repr(dragendid)}")
                    
                    if dragstartid != dragendid and dragendid not in [None, ""] and dragendtree not in [None, ""]:
                        if self.yes_no == None or (dragstarttree.w_var_autoopen.get() == 0 and dragendtree.w_var_autoopen.get() == 0):
                            permitted = True
                        else:
                            permitted = self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to move an item?")
                        
                        target = dragstartid
                        target_doc = self.db.item_get(id=target)
                        name = target_doc[self.db.schema_name(id=target)]
                        lock = self.db.schema_lock(id=target)
                        if target_doc.get(lock, 0) == 1:
                            messagebox.showwarning("Locked Item", f"Could not move \"{name}\" ({target}) because item is locked.")
                            self.logger.debug("Did not perform move, as target item is locked")
                            self.dragstartttime = None
                            self.dragstarttree = None
                            self.dragstartid = None
                            return

                        if permitted == True:
                            parents  = self.db.item_parents(item=target)
                            if len(parents) >= 1:
                                source, *_ = parents
                            else:
                                source = None
                            destination = dragendid
                            if source != destination:
                                self.logger.info(f"Moving {target} from {source} to {destination} via D&D")

                                recur_risk_list = [destination]+self.db.item_parents_all(item=destination)
                                self.logger.debug(f"Recursion risk list: {recur_risk_list}")
                                if target not in recur_risk_list:
                                    self.db.container_move(from_con=source, to_con=destination, item=target)
                                    if dragstarttree == dragendtree:
                                        dragendtree.tree_refresh(selection=destination)
                                        dragendtree.tree_focus(goal=source, rebase=True, dragreset=False)
                                        dragendtree.tree_focus(goal=destination, rebase=True, dragreset=False)
                                        dragendtree.tree_open(node=source, dragreset=False)
                                        dragendtree.tree_open(node=destination, dragreset=False)
                                    else:
                                        dragstarttree.tree_refresh(selection=source)
                                        dragendtree.tree_refresh(selection=destination)
                                        dragstarttree.tree_focus(goal=source, rebase=True, dragreset=False)
                                        dragendtree.tree_focus(goal=destination, rebase=True, dragreset=False)
                                        dragstarttree.tree_open(node=source, dragreset=False)
                                        dragendtree.tree_open(node=destination, dragreset=False)
                                    self.logger.debug(f"Move completed")
                                else:
                                    self.logger.warning("Did not perform move, as it would create an infinite loop")
                            else:
                                self.logger.debug(f"Did not perform move, as start and end container were the same")
                        else:
                            self.logger.debug(f"Did not perform move, as user declined")
                    else:
                        self.logger.debug(f"No further action. Drag did not start and end on distinct valid rows")
                else:
                    self.logger.debug(f"No further action. Drag did not start and end on a tree")
            else:
                self.logger.debug(f"Mouse released, but no further action. Drag lasted {dragtime}, which is less than {self.mindragtime}")
        
        self.dragstartttime = None
        self.dragstarttree = None
        self.dragstartid = None


    @busy
    def narrow(self, *args):
        '''Callback for when the narrow button is pressed.'''
        self.logger.info("Narrow button activated")
        self.search(preselector=self.last_selector)


    def scan(self, *args):
        '''Callback for when the scan button is pressed.'''
        self.logger.debug("Scan button activated")
        for child in self.w_bu_scan.winfo_children():
            child.destroy()
        window = tk.Toplevel(master=self.w_bu_scan)
        self.logger.info("Opening scan window")
        window.attributes("-topmost", True)
        window.focus_force()
        window.title("Scan")
        window.configure(background="#DCDAD5")

        def getNFCorBarcode():
            result = ''
            if self.hardware is not None: 
                nfcResult = self.hardware.getCurrentNFCUID()
                barcodeResult = self.hardware.getCurrentBarcode()
                if nfcResult == '':
                    if barcodeResult != '':
                        result = barcodeResult
                if barcodeResult == '':
                    if nfcResult != '':
                        result = nfcResult
            if result != '':
                input_var.set(result)
            window.after(250, getNFCorBarcode)

        def find(*args):
            self.logger.debug("Scan window's find button activated")
            physid = input_var.get()
            ids = self.db.ids_find(physid=physid)
            if len(ids) == 1:
                self.logger.info(f"Search for physical ID {physid} successful")
                id, *_ = ids
                self.tree_focus(goal=id, rebase=True)
                window.destroy()
                self.logger.debug("Closing scan window")
            elif len(ids) == 0:
                self.logger.debug(f"Search for physical ID {physid} failed. No matches")
                feedback.config(text="No matching ID found")
            else:
                self.logger.warning(f"Search for physical ID {physid} failed. Multiple matches")
                feedback.config(text="Multiple matching IDs found")

        self.logger.debug("Preparing scan window widgets")
        input_var = tk.StringVar()
        title = ttk.Label(master=window, text="Phys ID Search")
        input_box = ttk.Entry(master=window, textvariable=input_var)
        feedback = ttk.Label(master=window, text=" ")
        find_button = ttk.Button(master=window, text="Find", command=find)
        input_box.focus_set()
        input_box.bind("<Return>", find, add="+")

        getNFCorBarcode()

        window.columnconfigure(0, weight=1000)
        window.rowconfigure(0, weight=1, minsize=17)
        window.rowconfigure(1, weight=1000)
        window.rowconfigure(2, weight=1, minsize=17)
        window.rowconfigure(3, weight=1000)

        self.logger.debug("Packing and gridding scan window widgets")
        title.grid(column=0, row=0, sticky="nsew", padx=2, pady=2)
        input_box.grid(column=0, row=1, sticky="nsew", padx=2, pady=2)
        feedback.grid(column=0, row=2, sticky="nsew", padx=2, pady=2)
        find_button.grid(column=0, row=3, sticky="nsew", padx=2, pady=2)


    @busy
    def search(self, *args, preselector: dict = {}):
        '''Callback for when the search button is pressed.'''
        self.logger.debug("Search button activated")
        cat = self.w_var_cat.get()
        field = self.w_var_field.get()
        op = self.w_var_op.get()
        value = self.w_var_value.get().strip()
        opvalue = {
            "=": {"$eq": value}, 
            "<": {"$lt": value}, 
            ">": {"$gt": value}, 
            "≤": {"$lte": value},
            "≥": {"$gte": value}, 
            "≠": {"$ne": value},
            "≈": {"$regex": value}
            }[op]
        self.logger.info(f"Searching; Category: {cat}; Field: {field}: Op: {op}; Value: {value}")

        selector = preselector.copy()
        selector[field] = opvalue
        self.last_selector = selector
        
        name = self.db.schema_name(cat=cat)
        fields = ["_id", name]
        sort = [{key: 'asc'} for key in self.db.schema_keys(cat=cat)]
        self.search_result = self.db.items_query(cat=cat, selector=selector, fields=fields, sort=sort)

        self.w_li_search.config(state="normal")
        self.w_li_search.delete(0, "end")
        
        if len(self.search_result) > 0:
            for index, result in enumerate(self.search_result):
                self.w_li_search.insert(index, result[name])
        else:
            self.w_li_search.insert("end", "No results found")
            self.w_li_search.config(state="disabled")

        self.logger.debug(f"Search returned {len(self.search_result)} results")


    def search_cat(self, *args):
        '''Callback for when the search category is changed.'''
        cat = self.w_var_cat.get()
        self.logger.debug(f"Search category changed to {cat}")
        fields = ['_id']+self.db.schema_fields(cat=cat)

        # Searching by IDS and PHYSIDS fields doesn't work, so hide them:
        for field, info in self.db.schema_schema(cat=cat).items():
            if info.get('source','') in ["IDS", "PHYSIDS"]:
                fields.remove(field)

        self.w_co_field['values'] = fields
        self.w_co_field.current(1)


    @busy
    def search_select(self, *args):
        '''Callback for when an item in the search is selected.'''
        event, = args
        selected = event.widget.curselection()
        if len(selected) == 1:
            index, = selected
            id = self.search_result[index]["_id"]
            self.logger.debug(f"Search item {id} was selected")
            self.tree_focus(goal=id, rebase=True)
        else:
            self.logger.warning(f"Multiple search items were selected")


    @busy
    def summation_toggle(self, *args):
        '''Callback for when the summation checkbox is toggled.'''
        state = self.w_var_summation.get()
        if state == 0:
            self.summation = False
            self.logger.debug(f"Summation toggled OFF")
            self.w_tr_tree.config(show="tree")
        elif state == 1:
            self.summation = True
            self.logger.debug(f"Summation toggled ON")
            self.w_tr_tree.config(show="tree headings")
        else:
            self.logger.error(f"Summation toggled to unknown state {state}")
        if self.yes_no == None or self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to open an item?"):
            self.tree_refresh()
        else:
            self.logger.debug(f"Summation was clicked, but user declined.")


    @busy
    def tree_focus(self, goal: str, rebase: bool = False, dragreset: bool = True):
        '''Selects a node in the tree, opening parent nodes as required.
        
        goal: The node to select.
        rebase: If true, will rebase in attempt to find focus item.
        dragreset: If true, invalidates any ongoing drag and drop operations.
        '''
        if dragreset == True:
            self.dragstartid = None
            self.dragstarttree = None
        self.logger.debug(f"Attempting to focus on node {goal}")
        path = self.db.item_parents_all(item=goal)
        path.reverse()
        while True:
            for step in path:
                if self.w_tr_tree.exists(item=step):
                    self.tree_open(node=step, dragreset=dragreset)
            if self.w_tr_tree.exists(item=goal):
                self.w_tr_tree.selection_set(goal)
                self.w_tr_tree.see(item=goal)
                self.w_tr_tree.focus_set()
                self.w_tr_tree.focus(item=goal)
                self.logger.debug(f"Focused on node {goal}")
            elif rebase == True:
                if len(path) > 0:
                    if self.base != path[0]:
                        new_base = self.db.item_get(id=path[0])
                        self.base = new_base
                        self.logger.debug(f"Rebasing to find node {goal}")
                        self.tree_refresh(selection=goal)
                        continue
                    else:
                        new_base = self.db.item_get(id=goal)
                        self.base = new_base
                        self.tree_refresh(selection=goal)
                else:
                    new_base = self.db.item_get(id=goal)
                    self.base = new_base
                    self.tree_refresh(selection=goal)
            break


    def tree_get(self):
        '''Returns a tuple consisting of the currently selected node's id and name.'''
        id, *_ = self.w_tr_tree.selection()
        name = self.w_tr_tree.item(item=id)['text']
        return (id, name)


    def tree_insert(self, parent: str, iid: str, text: str, values: list = []):
        '''Inserts a node into the tree view.
        
        parent: The id of the parent node in the tree.
        iid: The id of the node being inserted.
        text: The text of the node.
        values: The values to put in the nodes's columns.
        '''
        self.w_tr_tree.insert(parent=parent, index=1000000, iid=iid, text=text, values=values)
        #if len(self.db.container_children(container=iid)) > 0:
        self.w_tr_tree.insert(parent=iid, index=1000000, iid=iid+"_stub")


    def tree_rebase_keyboard(self, *args):
        '''Callback for when the tree is rebased using the keyboard.'''
        self.logger.debug(f"Rebase requested using keyboard or event")
        targets = self.w_tr_tree.selection()
        if len(targets) >= 1:
            target, *_ = targets
            self.tree_rebase(target=target)
        else:
            self.logger.debug(f"Did not rebase, as no nodes were selected")


    def tree_rebase_mouse(self, *args):
        '''Callback for when the tree is rebased using right-click.'''
        self.logger.debug(f"Rebase requested using mouse")
        event, = args
        target = event.widget.identify_row(event.y)
        self.tree_rebase(target=target)


    @busy
    def tree_rebase(self, target: str):
        '''Rebase the tree to be based on the target.
        
        The target must be present on the tree.

        target: The item to make the new base.
        '''
        self.logger.info(f"Rebasing to {target}")
        self.w_tr_tree.selection_set(target)
        if self.w_tr_tree.parent(target) == "":
            parents = self.db.item_parents(item=target, result="DOC")
            if len(parents) > 0:
                self.base, *_ = parents
                self.logger.info(f"Previous rebase was top of tree, thus rebasing to {self.base}")
            else:
                self.logger.info(f"Did not rebase, as the tree is already at its highest point")
        else:
            self.base = self.db.item_get(id=target)
        self.tree_refresh()
        self.tree_open(target)
        self.w_tr_tree.see(item=target)


    @busy
    def tree_refresh(self, selection: tuple = None):
        '''Refreshes the tree view.'''
        self.logger.debug(f"Refreshing the tree")
        base_id = self.base["_id"]
        if selection == None:
            self.selection = self.w_tr_tree.selection()
        else:
            self.selection = [selection]
        self.w_tr_tree.delete(*self.w_tr_tree.get_children(item=""))
        if self.db.item_exists(id=base_id):
            base_name = self.base[self.db.schema_name(id=base_id)]
            self.tree_insert(parent="", iid=base_id, text=base_name)
            self.tree_sum(node=base_id)
            if len(self.selection) == 1:
                focus, = self.selection
                self.tree_focus(goal=focus, rebase=True)


    @busy
    def tree_select(self, *args):
        '''Callback for when an item in the tree is selected.'''
        event, = args
        self.selection = event.widget.selection()
        if self._select != None and (self.w_var_autoopen.get() == 1 or self.altheld == True):
            if self.yes_no == None:
                permitted = True
            else:
                permitted = self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to open an item?")
            if permitted == True:
                if len(self.selection) == 1:
                    sid, = self.selection
                    self.logger.debug(f"Node {sid} was selected")
                    doc = self.db.item_get(id=sid, lazy=True)
                    self._select(doc, self)
                else:
                    self.logger.warning(f"Multiple or zero nodes were selected")
            else:
                self.logger.debug(f"Node was selected but item was not opened, as user declined")
        else:
            self.logger.debug(f"Node was selected, but autoopen was disabled.")


    def tree_close(self, *args):
        '''Callback which triggers when a tree node is closed.'''
        self.dragstartid = None
        self.dragstarttree = None


    @busy
    def tree_open(self, node: str = None, dragreset: bool = True):
        '''Open a node on the tree view.
        
        node: The node to open. If omitted, opens currently selected node.
        dragreset: If true, invalidates any ongoing drag and drop operations.
        '''
        if dragreset == True:
            self.dragstartid = None
            self.dragstarttree = None
        self.selection = self.w_tr_tree.selection()
        if node != None:
            id = node
            self.logger.debug(f"Opening requested node {id}")
        elif self.w_tr_tree.focus() != "":
            id = self.w_tr_tree.focus()
            self.logger.debug(f"Opening focused node {id}")
        elif len(self.selection) == 1:
            id, = self.selection
            self.logger.info(f"Opening selected node {id}")
        else:
            self.logger.warning(f"Could not open any nodes, as none were selected")
            return

        # Do not open node if it's already open
        if self.w_tr_tree.item(id, 'open') == 1:
            return

        children = [child for child in self.db.container_children(container=id, result="DOC") if child != None]
        children.sort(key=lambda doc: (doc["category"], doc[self.db.schema_name(cat=doc["category"])]))
        
        # Try/except here prevents strange behavior if the targeted node isn't in the tree
        try:
            self.w_tr_tree.delete(*self.w_tr_tree.get_children(item=id))
            for child in children:
                child_id = child["_id"]
                child_name = child[self.db.schema_name(id=child_id)]
                self.tree_insert(parent=id, iid=child_id, text=child_name)
                self.tree_sum(node=child_id)
            self.w_tr_tree.item(item=id, open=True)
            self.w_tr_tree.see(item=id)
        except Exception as e:
            self.logger.error(f"Unable to open {id}")
            self.logger.error(e)


    @busy
    def tree_sum(self, node: str):
        '''Sums and displays summable fields of a node.
        
        node: The node to display sums of.
        '''
        if self.summation == True:
            self.logger.debug(f"Summing node {node}")
            schema = self.db.schema_schema(id=node)
            values = [""]*(len(self.summables)+1)
            doc = self.db.item_get(id=node)
            all_children = self.db.container_children_all(container=node, result="DOC")
            
            for field, info in schema.items():
                if field in self.summables:
                    defaulted = False
                    
                    # Sum fields
                    if info['type'] == "sum":
                        items = []
                        target = info['target']
                        for child in all_children:
                            child_cat = child['category']
                            if child_cat in info['cat']:
                                child_schema = self.db.schema_schema(cat=child_cat)
                                default = child_schema[target].get('default', 0)
                                value = child.get(target, '')
                                if value == '':
                                    value = default
                                    defaulted = True
                                try:
                                    items.append(float(value))
                                except:
                                    items.append(0.0)
                        itemsum = f"{sum(items):.1f}" if len(items) > 0 else ""
                    
                    # Count fields
                    elif info['type'] == "count":
                        children = [child for child in all_children if child['category'] in info['cat']]
                        itemsum = len(children)
                    
                    # Unknown summations
                    else:
                        value = doc.get(field, "")
                        if value == "":
                            value = info.get('default', 0)
                            defaulted = True
                        itemsum = f"{float(value):.1f}"
                    
                    # Display sum
                    if defaulted == True:
                        itemsum += "*"
                    values[self.headings[field]] = itemsum

            # Flag summation
            all_flags = []
            for child in [doc]+all_children:
                flags = child.get("flags",[])
                all_flags.extend(flags)
            all_flags = list(dict.fromkeys(all_flags))
            minilist = ""
            for flag in all_flags:
                minilist += f"{flag[:2]}"
            values[len(self.summables)] = minilist

            self.w_tr_tree.item(item=node, values=values)


# ----------------------------------------------------------------------------

class ContainerManager(SuperWidget):
    '''A SuperWidget representing a container manager.
    
    bookmarks: Dictionary describing where to base trees when bookmark buttons are pressed.
    bookmarks_path: Relative filepath to the bookmarks definition file.
    cats: The categories which may be searched using this ContainerManager.
    db: The database object which the widget uses for database transactions.
    level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
    logger: The logger object used for logging.
    master: The widget that the ContainerManager's component widgets will be instantiated under.
    ops: The operations that can be used in seraches.
    select: If present, a callback function that triggers when a tree item is selected.
    '''

    def __init__(self, master: tk.Misc, db: md.DEHCDatabase, topbase: dict, botbase: dict,  *, bookmarks: str = "bookmarks.json", cats: list = [], level: str = "NOTSET", prepare: bool = True, readonly: bool = False, select: Callable = None, statusbar: StatusBar = None, yesno: Callable = None, hardware: hw.Hardware = None):
        '''Constructs a ContainerManager object.
        
        master: The widget that the ContainerManager's component widgets will be instantiated under.
        db: The database object which  the widget uses for database transactions.
        topbase: The document of the item upon which the top tree is initially based.
        botbase: The document of the item upon which the bottom tree is initially based.
        bookmarks: Relative filepath to the bookmarks definition file.
        cats: The categories of items that can be searched.
        level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
        ops: The operations that can be used in seraches.
        prepare: If true, automatically prepares widgets for packing.
        select: If present, a callback function that triggers when a tree item is selected.
        yesno: If present, a callback function that handles prompting the user with yes/no to proceed.
        '''
        super().__init__(master=master, db=db, level=level)

        self.topbase = topbase
        self.botbase = botbase
        self.cats = cats
        self.level = level
        self.readonly = readonly
        self.root = self.w_fr.winfo_toplevel()
        self.select = select
        self.statusbar = statusbar
        
        self.yes_no = yesno
        self.hardware = hardware

        self.bookmarks_path = bookmarks
        self.logger.info(f"Loading bookmarks from {self.bookmarks_path}")
        with open(self.bookmarks_path, "r") as f:
            self.bookmarks = json.loads(f.read())
        self.logger.debug(f"Finished loading bookmarks")

        if prepare == True:
            self.prepare()


    def prepare(self):
        '''Constructs the frames and widgets of the ContainerManager.'''
        # Frames
        self.logger.debug(f"Preparing widgets")
        self.w_fr_bookmarks = ttk.Frame(master=self.w_fr)
        
        # Widgets
        self.w_bu_bm1 = ttk.Button(master=self.w_fr_bookmarks, text=self.bookmarks["1"]["name"], command=lambda *_: self.bookmark(preset="1"))
        self.w_bu_bm2 = ttk.Button(master=self.w_fr_bookmarks, text=self.bookmarks["2"]["name"], command=lambda *_: self.bookmark(preset="2"))
        self.w_bu_bm3 = ttk.Button(master=self.w_fr_bookmarks, text=self.bookmarks["3"]["name"], command=lambda *_: self.bookmark(preset="3"))
        self.w_bu_bm4 = ttk.Button(master=self.w_fr_bookmarks, text=self.bookmarks["4"]["name"], command=lambda *_: self.bookmark(preset="4"))
        self.w_se_top = SearchTree(master=self.w_fr, db=self.db, base=self.topbase, autoopen=True, cats=self.cats, level=self.level, prepare=True, select=self.select, statusbar=self.statusbar, yesno=self.yes_no, hardware=self.hardware)
        self.w_bu_move_item = ttk.Button(master=self.w_fr, text="⇓ ⇓ ⇓", style="large.TButton")
        self.w_bu_move_subs = ttk.Button(master=self.w_fr, text="⇑ ⇑ ⇑", style="large.TButton")
        self.w_se_bottom = SearchTree(master=self.w_fr, db=self.db, base=self.botbase, cats=self.cats, level=self.level, prepare=True, select=self.select, statusbar=self.statusbar, yesno=self.yes_no)

        if self.readonly == False:
            self.w_bu_move_item.configure(command=lambda *_: self.move())
            self.w_bu_move_subs.configure(command=lambda *_: self.move(reverse=True))
            self.w_bu_bm1.bind("<Shift-Button-1>", lambda *_: self.bookmark_change(preset="1"), add="+")
            self.w_bu_bm2.bind("<Shift-Button-1>", lambda *_: self.bookmark_change(preset="2"), add="+")
            self.w_bu_bm3.bind("<Shift-Button-1>", lambda *_: self.bookmark_change(preset="3"), add="+")
            self.w_bu_bm4.bind("<Shift-Button-1>", lambda *_: self.bookmark_change(preset="4"), add="+")

        self.w_fr.columnconfigure(0, weight=1000)
        self.w_fr.columnconfigure(1, weight=1000)
        self.w_fr.rowconfigure(0, weight=1, minsize=17)
        self.w_fr.rowconfigure(1, weight=1000)
        self.w_fr.rowconfigure(2, weight=1, minsize=24)
        self.w_fr.rowconfigure(3, weight=1000)

        self.w_fr_bookmarks.columnconfigure(0, weight=1000)
        self.w_fr_bookmarks.columnconfigure(1, weight=1000)
        self.w_fr_bookmarks.columnconfigure(2, weight=1000)
        self.w_fr_bookmarks.columnconfigure(3, weight=1000)
        self.w_fr_bookmarks.rowconfigure(0, weight=1000)

        self.root.bind("<Control-q>", lambda *_: self.w_se_top.w_tr_tree.focus_set(), add="+")
        self.root.bind("<Control-w>", lambda *_: self.w_se_bottom.w_tr_tree.focus_set(), add="+")
        self.root.bind("<Control-Key-1>", lambda *_: self.w_bu_bm1.invoke(), add="+")
        self.root.bind("<Control-Key-2>", lambda *_: self.w_bu_bm2.invoke(), add="+")
        self.root.bind("<Control-Key-3>", lambda *_: self.w_bu_bm3.invoke(), add="+")
        self.root.bind("<Control-Key-4>", lambda *_: self.w_bu_bm4.invoke(), add="+")

        if self.readonly == False:
            self.root.bind("<Control-Down>", lambda *_: self.w_bu_move_item.invoke(), add="+")
            self.root.bind("<Control-Up>", lambda *_: self.w_bu_move_subs.invoke(), add="+")
            self.root.bind("<Control-Shift-KeyPress-!>", lambda *_: self.bookmark_change(preset="1"), add="+")
            self.root.bind("<Control-Shift-KeyPress-@>", lambda *_: self.bookmark_change(preset="2"), add="+")
            self.root.bind("<Control-Shift-KeyPress-#>", lambda *_: self.bookmark_change(preset="3"), add="+")
            self.root.bind("<Control-Shift-KeyPress-$>", lambda *_: self.bookmark_change(preset="4"), add="+")
        
        self.root.bind("<F5>", lambda *_: self.refresh())


    def _pack_children(self):
        '''Packs & grids children frames and widgets of the ContainerManager.'''
        self.logger.debug(f"Packing and gridding widgets")
        self.w_fr_bookmarks.grid(column=0, row=0, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.w_bu_bm1.grid(column=0, row=0, sticky="nsew", padx=2, pady=2)
        self.w_bu_bm2.grid(column=1, row=0, sticky="nsew", padx=2, pady=2)
        self.w_bu_bm3.grid(column=2, row=0, sticky="nsew", padx=2, pady=2)
        self.w_bu_bm4.grid(column=3, row=0, sticky="nsew", padx=2, pady=2)
        self.w_se_top.grid(column=0, row=1, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.w_bu_move_item.grid(column=0, row=2, sticky="nsew", padx=2, pady=4)
        self.w_bu_move_subs.grid(column=1, row=2, sticky="nsew", padx=2, pady=4)
        self.w_se_bottom.grid(column=0, row=3, columnspan=2, sticky="nsew", padx=2, pady=2)


    def base(self, newbase: str = None):
        '''Sets or returns the base of the top tree.
        
        newbase: If specified, rebases the top tree to the new base.
        '''
        if newbase == None:
            return self.w_se_top.base
        else:
            self.w_se_top.base = newbase


    def basebot(self, newbase: str = None):
        '''Sets or returns the base of the bottom tree.
        
        newbase: If specified, rebases the bottom tree to the new base.
        '''
        if newbase == None:
            return self.w_se_bottom.base
        else:
            self.w_se_bottom.base = newbase


    @busy
    def bookmark(self, preset: str):
        '''Sets both trees to the settings described by a bookmark.
        
        preset: Which bookmark to use.
        '''
        self.logger.info(f"Bookmark {preset} activated")
        if self.yes_no == None or (self.w_se_top.w_var_autoopen.get() == 0 and self.w_se_bottom.w_var_autoopen.get() == 0):
            permitted = True
        else:
            permitted = self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to open a bookmark?")

        if permitted == True:
            guide = self.bookmarks.get(preset, None)
            top, bottom = guide.get("top", None), guide.get("bottom", None)
            try:
                items = self.db.items_get(ids=[top, bottom], lazy=True)
                top, bottom = items
                topid, bottomid = top["_id"], bottom["_id"]
                self.logger.info(f"Following bookmark to {topid} and {bottomid}")
                self.basebot(newbase=bottom)
                self.base(newbase=top)
                self.refresh(topselection=topid, bottomselection=bottomid)
                self.highlight(item=topid, botitem=bottomid)
                self.botopen()
                self.open()
            except:
                self.logger.warning(f"Could not open bookmark {preset}")
                self.refresh()
        else:
            self.logger.debug(f"Did not go to bookmark, as user declined")


    @busy
    def bookmark_change(self, preset: str):
        '''Changes a bookmark to match the current top/bottom tree.
        
        preset: Which bookmark to change.
        '''
        self.logger.info(f"Bookmark {preset} change activated")
        topselect = self.w_se_top.base['_id']
        botselect = self.w_se_bottom.base['_id']
        toptext = self.w_se_top.base['Display Name'][:10]
        bottext = self.w_se_bottom.base['Display Name'][:10]
        self.logger.info(f"Bookmark {preset} now goes to {topselect} and {botselect}")
        fulltext = f"{toptext}/{bottext}"
        if preset == "1":
            self.w_bu_bm1.config(text=fulltext)
        elif preset == "2":
            self.w_bu_bm2.config(text=fulltext)
        elif preset == "3":
            self.w_bu_bm3.config(text=fulltext)
        elif preset == "4":
            self.w_bu_bm4.config(text=fulltext)
        self.bookmarks[preset]["name"] = fulltext
        self.bookmarks[preset]["top"] = topselect
        self.bookmarks[preset]["bottom"] = botselect

        self.logger.info(f"Saving new bookmarks to {self.bookmarks_path}")
        with open(self.bookmarks_path, "w") as f:
            f.write(json.dumps(self.bookmarks))
        self.logger.debug(f"Done saving new bookmarks")


    def highlight(self, item: str = None, botitem: str = None):
        '''Selects an item in the top and/or bottom tree with the matching id.
        
        Note: requires item to already exist in the tree.
        '''
        if botitem != None:
            self.w_se_bottom.tree_focus(goal=botitem, rebase=True)
        if item != None:
            self.w_se_top.tree_focus(goal=item, rebase=True)


    @busy
    def move(self, reverse: bool = False):
        '''Callback for when the item move button is pressed.
        
        reverse: If true, container movement is bottom to top.
        '''
        self.logger.debug(f"Move {'down' if reverse == False else 'up'} button activated")

        if reverse == False:
            target, *_ = self.w_se_top.selection
        else:
            target, *_ = self.w_se_bottom.selection

        target_doc = self.db.item_get(id=target)
        name = target_doc[self.db.schema_name(id=target)]
        lock = self.db.schema_lock(id=target)
        if target_doc.get(lock, 0) == 1:
            messagebox.showwarning("Locked Item", f"Could not move \"{name}\" ({target}) because item is locked.")
            self.logger.debug("Did not perform move, as target item is locked")
            return

        if self.yes_no == None or (self.w_se_top.w_var_autoopen.get() == 0 and self.w_se_bottom.w_var_autoopen.get() == 0):
            permitted = True
        else:
            permitted = self.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to move an item?")

        if permitted == True:
            parents  = self.db.item_parents(item=target)
            if len(parents) >= 1:
                source, *_ = parents
            else:
                source = None
            if reverse == False:
                destination, *_ = self.w_se_bottom.selection
            else:
                destination, *_ = self.w_se_top.selection
            
            if source != destination:
                self.logger.info(f"Moving {target} from {source} to {destination} via button")

                recur_risk_list = [destination]+self.db.item_parents_all(item=destination)
                self.logger.debug(f"Recursion risk list: {recur_risk_list}")
                if target not in recur_risk_list:
                    self.db.container_move(from_con=source, to_con=destination, item=target)

                    if reverse == False:
                        self.refresh(topselection=source, bottomselection=destination)
                        self.highlight(botitem=destination)
                        self.highlight(item=source)
                    else:
                        self.refresh(topselection=destination, bottomselection=source)
                        self.highlight(botitem=source)
                        self.highlight(item=destination)
                    self.open()
                    self.botopen()
                    self.logger.debug(f"Move completed")
                else:
                    self.logger.warning("Did not perform move, as it would create an infinite loop")
            else:
                self.logger.debug("Did not perform move, as source and destination were the same")
        else:
            self.logger.debug("Did not perform move, as user declined")


    # This functionality is currently inaccessible since there's no button tied to it
    #def submove(self, *args):
    #    '''Callback for when the sub-item move button is pressed.'''
    #    source, *_ = self.w_se_top.selection
    #    targets = self.db.container_children(container=source)
    #    destination, *_ = self.w_se_bottom.selection
    #    self.db.container_moves(from_con=source, to_con=destination, items=targets)
    #    self.highlight(item=source)
    #    self.refresh()
    #    self.highlight(botitem=destination)
    #    self.botopen()


    def botopen(self):
        '''Opens the bottom tree's currently selected container.'''
        self.w_se_bottom.tree_open()


    def open(self):
        '''Opens the top tree's currently selected container.'''
        self.w_se_top.tree_open()


    def refresh(self, topselection: tuple = None, bottomselection: tuple = None, active: SearchTree = None):
        '''Refreshes both trees.
        
        topselection: If present, what to select while refreshing the top tree.
        bottomselection: If present, what to select while refreshing the bottom tree.
        active: If present, refreshes such that the active tree is the one provided.
        '''
        if active == self.w_se_top:
            self.logger.debug(f"Refreshing both trees with priority to top")
            self.w_se_bottom.tree_refresh(selection=bottomselection)
            self.w_se_top.tree_refresh(selection=topselection)
        else:
            self.logger.debug(f"Refreshing both trees with priority to bottom")
            self.w_se_top.tree_refresh(selection=topselection)
            self.w_se_bottom.tree_refresh(selection=bottomselection)


    def selections(self):
        '''Returns a tuple containing the IDs of the selected items in the top and bottom tree respectively.'''
        top, *_ = self.w_se_top.selection
        bot, *_ = self.w_se_bottom.selection
        return (top, bot)
