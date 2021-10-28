'''The module containing the timetable application.'''

from PIL import Image, ImageTk

import tkinter as tk

import mods.log as ml
import mods.database as md

# ----------------------------------------------------------------------------

SCROLLRATE = 33        # in ms
SCROLLDIST = 3         # in px
STARTWAIT  = 6000      # in ms
ENDWAIT    = 6000      # in ms
RETRYWAIT  = 15000     # in ms
FORECOLOR  = "#ffffff" # in rgb hex
TOPCOLOR   = "#0000c3" # in rgb hex
BOTCOLOR   = "#00003f" # in rgb hex
TEXTFONT   = "Arial"   # tkinter font

class TT():
    '''A class which represents the Timetable application.'''

    def __init__(self, db: md.DEHCDatabase, container: str, *, level: str = "NOTSET", autorun: bool = False):
        '''Constructs a GC object.'''
        self.level = level
        self.logger = ml.get("TT", level=self.level)
        self.logger.debug("TT object instantiated")

        self.db = db
        self.container = container
        self.scroll = 0
        self.queue = []

        self.root = tk.Tk()
        self.root.title(f"TT ({self.db.namespace} @ {self.db.db.data['url']})")
        self.root.attributes("-fullscreen", True)
        self.root.geometry("1080x900")
        self.root.configure(background="#FFFFFF")
        self.root.bind('<Escape>', lambda *_: self.root.destroy())

        if autorun == True:
            self.logger.info(f"Performing autorun")
            self.prepare()
            self.pack()
            self.run()


    def prepare(self):
        '''Constructs the frames and widgets of the TT.'''
        self.logger.debug(f"Preparing widgets")

        self.w_la_vessel = tk.Label(master=self.root, text="", font=f"{TEXTFONT} 50 bold", anchor="w", justify="left", background=TOPCOLOR, foreground=FORECOLOR)
        self.w_la_arrives = tk.Label(master=self.root, text="Arrives", font=f"{TEXTFONT} 30 bold", anchor="w", justify="left", background=TOPCOLOR, foreground=FORECOLOR)
        self.w_la_arrtime = tk.Label(master=self.root, text="", font=f"{TEXTFONT} 30 bold", anchor="w", justify="left", background=TOPCOLOR, foreground=FORECOLOR)
        self.w_la_departs = tk.Label(master=self.root, text="Departs", font=f"{TEXTFONT} 30 bold", anchor="w", justify="left", background=TOPCOLOR, foreground=FORECOLOR)
        self.w_la_deptime = tk.Label(master=self.root, text="", font=f"{TEXTFONT} 30 bold", anchor="w", justify="left", background=TOPCOLOR, foreground=FORECOLOR)
        self.w_bu_photo = tk.Button(master=self.root, image="", background=TOPCOLOR, activebackground=TOPCOLOR, highlightthickness = 0, bd = 0)

        def redraw_canvas_window(*args):
            self.w_ca.itemconfig('frame', width=self.w_ca.winfo_width())

        self.w_ca = tk.Canvas(master=self.root, yscrollincrement=1, border=0, borderwidth=0, highlightthickness=0, background=TOPCOLOR, selectbackground=TOPCOLOR)
        self.w_fr_scrollable = tk.Frame(master=self.w_ca, background=TOPCOLOR)
        self.w_ca.create_window((0, 0), window=self.w_fr_scrollable, anchor="nw", tags="frame")
        self.w_ca.bind("<Configure>", redraw_canvas_window)

        self.root.columnconfigure(index=0, weight=1000)
        self.root.columnconfigure(index=1, weight=1000)
        self.root.columnconfigure(index=2, weight=1, minsize=266)
        self.root.rowconfigure(index=0, weight=1, minsize=1)
        self.root.rowconfigure(index=1, weight=1, minsize=1)
        self.root.rowconfigure(index=2, weight=1, minsize=1)
        self.root.rowconfigure(index=3, weight=1000)
        self.w_fr_scrollable.columnconfigure(index=0, weight=1000)

        self.reset_canvas()


    def pack(self):
        '''Packs & grids children frames and widgets of the TT.'''
        self.logger.debug(f"Packing and gridding widgets")

        self.w_la_vessel.grid(column=0, row=0, columnspan=2, sticky="nsew", padx=(4,2), pady=2)
        self.w_la_arrives.grid(column=0, row=1, sticky="nsew", padx=(4,2), pady=2)
        self.w_la_arrtime.grid(column=1, row=1, sticky="nsew", padx=2, pady=2)
        self.w_la_departs.grid(column=0, row=2, sticky="nsew", padx=(4,2), pady=2)
        self.w_la_deptime.grid(column=1, row=2, sticky="nsew", padx=2, pady=2)
        self.w_bu_photo.grid(column=2, row=0, rowspan=3, sticky="nsew", padx=(2,4), pady=2)
        self.w_ca.grid(column=0, row=3, columnspan=3, sticky="nsew", padx=2, pady=2)


    def get_vessels(self, container: str):
        children = self.db.container_children_all(container=container, cat="Vessel", result="DOC")
        response = []
        for child in children:
            id = child['_id']
            dn = child['Display Name']
            ea = child['Estimated Arrival']
            ed = child['Estimated Departure']
            img = self.db.photo_load(item=id)
            response.append((id, dn, ea, ed, img))
        return response


    def get_people(self, vessel: str):
        children = self.db.container_children_all(container=vessel, cat="Person", result="DOC")
        response = []
        for child in children:
            response.append(child['Display Name'])
        response.sort()
        return response


    def scroll_canvas(self, *args):
        list_height = self.w_li_names.winfo_height()
        canvas_height = self.w_ca.winfo_height()
        if self.scroll <= list_height-canvas_height:
            self.w_ca.yview_scroll(SCROLLDIST, "units")
            self.scroll += SCROLLDIST
            self.root.after(ms=SCROLLRATE, func=self.scroll_canvas)
        else:
            self.root.after(ms=ENDWAIT, func=self.reset_canvas)


    def reset_canvas(self):
        if len(self.queue) > 0:
            vessel_uuid, vessel_name, vessel_arr, vessel_dep, vessel_photo = self.queue.pop()
            print(vessel_uuid, vessel_name, vessel_arr, vessel_dep)

            self.w_la_vessel.config(text=vessel_name)
            self.w_la_arrtime.config(text=vessel_arr)
            self.w_la_deptime.config(text=vessel_dep)
            if vessel_photo != None:
                vessel_photo = ImageTk.PhotoImage(vessel_photo)
                self.w_bu_photo.config(image=vessel_photo)
                self.w_bu_photo.image = vessel_photo
            else:
                self.w_bu_photo.config(image="")
                self.w_bu_photo.image = ""

            self.w_ca.yview_scroll(-self.scroll, "units")
            self.scroll = 0
            for child in self.w_fr_scrollable.winfo_children():
                child.destroy()
            
            people_names = self.get_people(vessel=vessel_uuid)
            self.w_li_names = tk.Listbox(master=self.w_fr_scrollable, height=len(people_names), justify="center", font=f"{TEXTFONT} 24 bold", relief="flat", border=0, borderwidth=0, highlightthickness=0, background=BOTCOLOR, selectbackground=BOTCOLOR, foreground=FORECOLOR, selectforeground=FORECOLOR, activestyle='none')
            for row in people_names:
                self.w_li_names.insert("end", row)
            self.w_li_names.grid(column=0, row=0, sticky="nsew", padx=0, pady=0)

            self.root.after(ms=STARTWAIT, func=self.scroll_canvas)
        else:
            self.timetable_run()


    def timetable_run(self):
        self.queue += self.get_vessels(container=self.container)
        if len(self.queue) > 0:
            self.reset_canvas()
        else:
            self.w_la_vessel.configure(text="Waiting for data...")
            self.root.after(ms=RETRYWAIT, func=lambda *_: self.timetable_run())


    def run(self):
        '''Enters the root's main loop, drawing the app screen.'''
        self.logger.info(f"Starting main UI loop")
        self.root.mainloop()
        self.logger.info(f"Ending main UI loop")