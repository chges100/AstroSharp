import tkinter as tk
from tkinter import ttk 

from mp_logging import configure_logging, initialize_logging, shutdown_logging

configure_logging()

import logging

class CollapsibleFrame(tk.Frame):

    def __init__(self, parent, text="", nested = False, *args, **options):
        tk.Frame.__init__(self, parent, *args, **options)

        self.show = tk.IntVar()
        self.show.set(0)

        self.title_frame = ttk.Frame(self)
        self.title_frame.pack(fill="x", expand=1)

        self.nested = nested

        ttk.Label(self.title_frame, text=text, font="Verdana 10 bold").pack(side="left", fill="x", expand=1)

        self.toggle_button = ttk.Checkbutton(self.title_frame, width=2, text='+', command=self.toggle,
                                            variable=self.show, style='Toolbutton')
        self.toggle_button.pack(side="left")

        self.sub_frame = tk.Frame(self, relief="sunken", borderwidth=0)

    def toggle(self):
        if bool(self.show.get()):
            self.sub_frame.pack(fill="x", expand=1)
            self.toggle_button.configure(text='-')
        else:
            self.sub_frame.forget()
            self.toggle_button.configure(text='+')
        
        self.update()
        self.master.update()

        # use nested option only if collapsible frame is embedded into other collapsible frame 
        if self.nested is True:
            self.master.master.master.update()
            width = self.master.master.master.winfo_width()
            self.master.master.master.master.configure(width=width)
            self.master.master.master.master.configure(scrollregion=self.master.master.master.master.bbox("all"))
            self.master.master.master.master.yview_moveto("0.0")
        else:
            width = self.master.winfo_width()
            self.master.master.configure(width=width)
            self.master.master.configure(scrollregion=self.master.master.bbox("all"))
            self.master.master.yview_moveto("0.0")
        