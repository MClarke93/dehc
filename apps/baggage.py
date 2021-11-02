'''The module containing the pallet builder application.'''

import math

from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk

import mods.log as ml
import mods.database as md

# ----------------------------------------------------------------------------

class PB():
    '''A class which represents the Pallet Builder application.'''

    def __init__(self, db: md.DEHCDatabase, baghold: str, pallet: str, *, level: str = "NOTSET", autorun: bool = False):
        '''Constructs a PB object.'''
        self.level = level
        self.logger = ml.get("GC", level=self.level)
        self.logger.debug("GC object instantiated")

        self.blank = Image.new("RGB", (512, 512), (240, 240, 240))
        self.db = db
        self.baghold = baghold
        self.pallet = pallet
        self.bagholdname = self.db.item_get(id=self.baghold)[self.db.schema_name(id=self.baghold)]
        self.palletname = self.db.item_get(id=self.pallet)[self.db.schema_name(id=self.pallet)]

        self.root = tk.Tk()
        self.root.title(f"PB ({self.db.namespace} @ {self.db.db.data['url']})")
        self.root.state('zoomed')
        self.root.configure(background="#DCDAD5")

        if autorun == True:
            self.logger.info(f"Performing autorun")
            self.prepare()
            self.pack()
            self.run()


    def prepare(self):
        '''Constructs the frames and widgets of the PB.'''
        self.logger.debug(f"Preparing widgets")

        self.w_var_search = tk.StringVar()

        self.w_la_title = tk.Label(master=self.root, text=f"Loading {self.palletname}", font="Arial 48 bold")
        self.w_la_name = tk.Label(master=self.root, text=f"", font="Arial 48 bold")
        self.w_bu_photo = tk.Button(master=self.root, highlightthickness=0, bd=0)
        self.newphoto(img=self.blank)
        self.w_la_result = tk.Label(master=self.root, text="", font="Arial 48")
        self.w_en_search = tk.Entry(master=self.root, textvariable=self.w_var_search, font="Arial 16")
        self.w_bu_search = tk.Button(master=self.root, text="Search", command=self.search, font="Arial 16")

        self.root.bind("<Return>", lambda *_: self.w_bu_search.invoke())
        self.w_en_search.focus_set()

        self.root.columnconfigure(index=0, weight=1000)
        self.root.rowconfigure(index=0, weight=1, minsize=70)
        self.root.rowconfigure(index=1, weight=1, minsize=70)
        self.root.rowconfigure(index=2, weight=1000)
        self.root.rowconfigure(index=3, weight=1, minsize=70)
        self.root.rowconfigure(index=4, weight=1, minsize=48)
        self.root.rowconfigure(index=5, weight=1, minsize=48)


    def pack(self):
        '''Packs & grids children frames and widgets of the PB.'''
        self.logger.debug(f"Packing and gridding widgets")

        self.w_la_title.grid(column=0, row=0, sticky="nsew", padx=6, pady=(6,3))
        self.w_la_name.grid(column=0, row=1, sticky="nsew", padx=6, pady=3)
        self.w_bu_photo.grid(column=0, row=2, sticky="nsew", padx=6, pady=3)
        self.w_la_result.grid(column=0, row=3, sticky="nsew", padx=6, pady=3)
        self.w_en_search.grid(column=0, row=4, sticky="nsew", padx=6, pady=3)
        self.w_bu_search.grid(column=0, row=5, sticky="nsew", padx=6, pady=(3,6))


    def run(self):
        '''Enters the root's main loop, drawing the app screen.'''
        self.logger.info(f"Starting main UI loop")
        self.root.mainloop()
        self.logger.info(f"Ending main UI loop")


    def accept(self, who: str):
        '''Changes app appearence to be green'''
        color = "#70FF70"
        self.root.configure(background=color)
        self.w_la_title.configure(background=color)
        self.w_la_name.configure(background=color, text=who)
        self.w_bu_photo.configure(background=color)
        self.w_la_result.configure(background=color)
        self.w_bu_search.configure(background=color)
        self.w_la_result.configure(text=f"Moved to {self.palletname}")


    def deny(self, who: str, reason: str):
        '''Changes app appearence to be red'''
        color = "#FF7070"
        self.root.configure(background=color)
        self.w_la_title.configure(background=color)
        self.w_la_name.configure(background=color, text=who)
        self.w_bu_photo.configure(background=color)
        self.w_la_result.configure(background=color)
        self.w_bu_search.configure(background=color)
        self.w_la_result.configure(text=f"Denied ({reason})")


    def newphoto(self, img: Image):
        '''Changes the photo to be the one specified.'''
        target_width, target_height = (500, 500)
        width, height = img.size
        
        if width > height:
            ratio = target_width/width
        else:
            ratio = target_height/height

        img = img.resize((math.floor(width*ratio), math.floor(height*ratio)))
        img = ImageTk.PhotoImage(image=img)
        self.w_bu_photo.configure(image=img)
        self.w_bu_photo.image = img


    def search(self):
        '''Callback for when the search button is pressed.'''
        self.logger.debug(f"Search button activated")

        value = self.w_var_search.get()
        self.w_var_search.set("")
        
        # Guard against empty searches
        if value == "":
            return

        bag_doc = self.db.get_item_by_any_id(value)
        
        if bag_doc == False:
            self.newphoto(img=self.blank)
            self.deny(who="", reason="Unknown ID")
            self.logger.debug(f"Bag \"{value}\" rejected, unknown ID")
        else:
            bag = bag_doc['_id']
            bag_name = bag_doc[self.db.schema_name(id=bag)]
            bag_photo = self.db.photo_load(item=bag)

            if bag_photo != None:
                self.newphoto(img=bag_photo)
            else:
                self.newphoto(img=self.blank)

            self.logger.debug(f"Verifying bag {bag}")

            baghold_children = self.db.container_children_all(container=self.baghold, cat="Baggage")
            if bag in baghold_children:
                self.db.container_move(from_con=self.baghold, to_con=self.pallet, item=bag, lazy=True)
                self.accept(who=bag_name)
                self.logger.debug(f"Bag {bag_name} ({bag}) is acceptable")
            else:
                self.deny(who=bag_name, reason=f"Bag not in {self.bagholdname}")
                self.logger.debug(f"Bag {bag_name} ({bag}) rejected, bag not in {self.bagholdname}")
