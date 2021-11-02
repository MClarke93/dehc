'''The module containing the evacuation management system, used for ingest, etc.'''

import json

import tkinter as tk
from tkinter import ttk

import mods.log as ml
import mods.database as md
import mods.widgets as mw
import mods.dehc_hardware as hw

# ----------------------------------------------------------------------------

class EMS():
    '''A class which represents the EMS application.'''

    def __init__(self, db: md.DEHCDatabase, *, bookmarks: str = "bookmarks.json", godmode: bool = False, level: str = "NOTSET", readonly: bool = False, web: str = "web_auth.json", autorun: bool = False, hardware: hw.Hardware = None):
        '''Constructs an EMS object.
        
        db: The database object which the app uses for database transactions.
        bookmarks: Relative filepath to the bookmark definition file.
        level: Minimum level of logging messages to report; "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NONE".
        prepare: If true, automatically prepares widgets for packing.
        '''
        self.level = level                # The minimum level of logging messages to report
        self.logger = ml.get("EMS", level=self.level)
        self.logger.debug("EMS object instantiated")

        self.active = None                # The source of the last selected data pane item.
        self.bookmarks = bookmarks        # The filepath to the bookmarks.json file
        self.db = db                      # The associated DEHCDatabase object
        self.cats = self.db.schema_cats() # The item categories available to the EMS application
        self.godmode = godmode            # Whether or not the application is in 'god mode' (admin mode)
        self.hardware = hardware          # The associated hardware manager
        self.readonly = readonly          # Whether the app is in readonly or not
        self.web = web                    # The filepath to the web server authentication file

        self.cats.remove("Evacuation")
        self.cats.remove("Trash")
        if self.godmode == False:
            self.cats.remove("Station")
            self.cats.remove("Lane")
            self.cats.remove("Vessel")

        self.root = tk.Tk()
        self.root.title(f"EMS ({self.db.namespace} @ {self.db.db.data['url']})")
        self.root.state('zoomed')
        self.root.configure(background="#dcdad5")

        if autorun == True:
            self.logger.info(f"Performing autorun")
            self.prepare()
            self.pack()
            self.run()


    def prepare(self):
        '''Constructs the frames and widgets of the EMS.'''
        self.logger.debug(f"Preparing widgets")

        evacuations = self.db.items_query(cat="Evacuation", fields=["_id", "Display Name"])
        if len(evacuations) == 1:
            self.logger.debug(f"Found 1 Evacuation.")
            base, = evacuations
        else:
            self.logger.error(f"Found {len(evacuations)} Evacuations.")
            raise RuntimeError("Expected one Evacuation in the database.")
        
        trashes = self.db.items_query(cat="Trash", fields=["_id", "Display Name"])
        if len(trashes) == 1:
            self.logger.debug(f"Found 1 Trash.")
            trash, = trashes
        else:
            self.logger.error(f"Found {len(trashes)} Trashes.")
            raise RuntimeError(f"Expected one Trash in the database.")

        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure('.', font=('Arial', 9))
        self.style.map('TEntry', foreground=[('readonly', 'black')])
        self.style.map('TCombobox', fieldbackground=[('readonly', 'white')])

        self.style.configure("unactive.Treeview", fieldbackground="white", background="white", foreground="black")
        self.style.map('unactive.Treeview', background=[('selected', 'blue')], foreground=[('selected', 'white')])
        self.style.configure("active.Treeview", fieldbackground="#fcf0cf", background="#fcf0cf", foreground="black")
        self.style.map('active.Treeview', background=[('selected', 'blue')], foreground=[('selected', '#fcf0cf')])
        self.style.configure('large.TButton', font=('Arial', 14))

        self.root.bind_class("TButton", "<Return>", lambda event: event.widget.invoke(), add="+")
        self.root.bind_class("TCheckbutton", "<Return>", lambda event: event.widget.invoke(), add="+")

        self.sb = mw.StatusBar(master=self.root, db=self.db, level=self.level, prepare=True)
        self.de = mw.DataEntry(master=self.root, db=self.db, cats=self.cats, delete=self.delete, godmode=self.godmode, level=self.level, newchild=self.new_child, prepare=True, readonly=self.readonly, save=self.save, show=self.show, statusbar=self.sb, trash=trash, web=self.web, hardware=self.hardware)
        self.cm = mw.ContainerManager(master=self.root, db=self.db, topbase=base, botbase=base, bookmarks=self.bookmarks, cats=self.cats, level=self.level, prepare=True, readonly=self.readonly, select=self.item_select, statusbar=self.sb, yesno=self.de.yes_no, hardware=self.hardware)
        self.bu_refresh = ttk.Button(master=self.root, text="Refresh", command=self.refresh_button)
        
        self.root.rowconfigure(0, weight=10000)
        self.root.rowconfigure(1, weight=1, minsize=16)
        self.root.columnconfigure(0, weight=1, minsize=16)
        self.root.columnconfigure(1, weight=2500, minsize=232)
        self.root.columnconfigure(2, weight=1000)


    def pack(self):
        '''Packs & grids children frames and widgets of the EMS.'''
        self.logger.debug(f"Packing and gridding widgets")
        self.cm.grid(column=0, row=0, columnspan=2, sticky="nsew", padx=2, pady=2)
        self.de.grid(column=2, row=0, sticky="nsew", padx=2, pady=2)
        self.bu_refresh.grid(column=0, row=1, sticky="nsew", padx=2, pady=2)
        self.sb.grid(column=1, row=1, columnspan=2, sticky="nsew", padx=2, pady=2)


    def run(self):
        '''Enters the root's main loop, drawing the app screen.'''
        self.logger.info(f"Starting main UI loop")
        self.root.mainloop()
        self.logger.info(f"Ending main UI loop")


    def new_child(self, target: str):
        '''Callback for when new child is pressed in the data pane.'''
        parents = self.db.item_parents(item=target)
        if len(parents) == 1:
            parent, = parents
            if target == self.active.base:
                self.active.tree_rebase(target=target)
                parent = self.active.w_tr_tree.parent(target)
            self.active.tree_focus(goal=parent, rebase=True)
            self.active.tree_open()


    def refresh_button(self, *args):
        '''Callback for when the refresh button is pressed.'''
        if self.de.yes_no("Unsaved Changes","There are unsaved changes. Are you sure you want to refresh?"):
            autoopen = self.active.w_var_autoopen.get()
            if autoopen == 0:
                self.active.w_var_autoopen.set(1)
            self.refresh()
            self.root.after(ms=1, func=lambda *_: self.active.w_var_autoopen.set(autoopen)) # .after is required to make this trigger after <<TreeviewSelect>>


    def refresh(self):
        '''Refreshes the trees.'''
        self.cm.refresh(active=self.active)


    def item_select(self, *args):
        '''Callback for when an item is selected in a tree.'''
        doc, tree = args
        if self.active != None:
            self.active.w_tr_tree.configure(style="unactive.Treeview")
        self.active = tree
        self.active.w_tr_tree.configure(style="active.Treeview")
        self.logger.info(f"Item {doc.get('_id','_')} was selected")
        self.de.show(doc, summation=bool(self.active.w_var_sumdata.get()))


    def delete(self, *args):
        '''Callback for when the delete button is pressed in the data pane.'''
        id, parents, *_ = args
        if len(parents) > 0:
            parent, *_ = parents
            if id == self.cm.w_se_top.base["_id"]:
                self.cm.w_se_top.base = self.db.item_get(id=parent, fields=["_id", "Display Name"])
            if id == self.cm.w_se_bottom.base["_id"]:
                self.cm.w_se_bottom.base = self.db.item_get(id=parent, fields=["_id", "Display Name"])
            self.active.w_tr_tree.selection_set(parent)
            self.refresh()
            self.active.tree_focus(goal=parent, rebase=True)
            self.active.tree_open()
        else:
            self.refresh()


    def save(self, *args):
        '''Callback for when the save button is pressed in the data pane.'''
        id, *_ = args
        if id != None:
            container, *_ = self.active.selection
            self.db.container_add(container=container, item=id)
        self.refresh()
        if id != None:
            self.active.tree_focus(goal=container, rebase=True)
            self.active.tree_open()


    def show(self, *args):
        '''Callback for when the show button is pressed in the data pane.'''
        id, *_ = args
        if id != None:
            autoopen = self.active.w_var_autoopen.get()
            if autoopen == 0:
                self.active.w_var_autoopen.set(1)
            self.refresh()
            self.active.tree_focus(goal=id, rebase=True)
            self.root.after(ms=1, func=lambda *_: self.active.w_var_autoopen.set(autoopen)) # .after is required to make this trigger after <<TreeviewSelect>>


# ----------------------------------------------------------------------------