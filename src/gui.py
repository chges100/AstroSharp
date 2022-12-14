# -*- coding: utf-8 -*-
"""
Created on Sun Feb 13 10:05:08 2022
@author: steff
"""

import multiprocessing

multiprocessing.freeze_support()

from mp_logging import configure_logging, initialize_logging, shutdown_logging

configure_logging()

import logging
import os
import sys
import tkinter as tk
from colorsys import hls_to_rgb
from tkinter import filedialog, messagebox, ttk

import hdpitkinter as hdpitk
import numpy as np
from appdirs import user_config_dir
from PIL import Image, ImageTk
from skimage import io
from skimage.transform import resize

import multiscale_image
import tooltip
from astroimage import AstroImage
from collapsible_frame import CollapsibleFrame
from help_panel import Help_Panel
from loadingframe import LoadingFrame
from localization import _
from parallel_processing import executor
from preferences import (get_default_prefs, load_preferences, save_preferences)
from stretch import stretch_all
from ui_scaling import get_scaling_factor


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = os.path.abspath(os.path.dirname(__file__))
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    return os.path.join(base_path, relative_path)



class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)

        self.master.geometry("1920x1080")
        self.master.minsize(height=768 ,width=1024)
        
        try:
            self.master.state("zoomed")
        except:
            self.master.state("normal")
        
        self.filename = ""
        self.data_type = ""

        self.images_full = {
            "Original": None,
            "Processed": None,
            "Scale": None,
            "Residual": None
        }

        self.images_preview = {
            "Original": None,
            "Processed": None,
            "Scale": None,
            "Residual": None
        }
        
        self.images = self.images_full

        self.multiscale_img = None


        self.preview_mode = False
        self.preview_select_mode = False
        self.preview_changed = False
        self.num_scales = 7
        
        self.my_title = "AstroSharp"
        self.master.title(self.my_title)

        prefs_filename = os.path.join(user_config_dir(appname="AstroSharp"), "preferences.json")
        self.prefs = load_preferences(prefs_filename)

        self.create_widget()
        self.sharp_menu.show.set(1)
        self.sharp_menu.toggle()

        self.scale_img_to_show = AstroImage(self.stretch_option_current, self.saturation)

        self.reset_transform()
        

    def create_widget(self):
        

        frame_statusbar = tk.Frame(self.master, bd=1, relief = tk.SUNKEN)
        self.label_image_info = ttk.Label(frame_statusbar, text="image info", anchor=tk.E)
        self.label_image_pixel = ttk.Label(frame_statusbar, text="(x, y)", anchor=tk.W)
        self.label_image_info.pack(side=tk.RIGHT)
        self.label_image_pixel.pack(side=tk.LEFT)
        frame_statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        
        self.master.grid_columnconfigure(2)

        #Right help panel
        
        self.canvas = tk.Canvas(self.master, background="black", name="picture")
        
        self.help_panel = Help_Panel(self.master, self.canvas, self)
        
       
        # Canvas
        
        self.canvas.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        
        self.display_options = ["Original","Processed","Scale", "Residual"]
        self.display_type = tk.StringVar()
        self.display_type.set(self.display_options[0])
        self.display_menu = ttk.OptionMenu(self.canvas, self.display_type, self.display_type.get(), *self.display_options, command=self.switch_display)
        self.display_menu.place(relx=0.5, rely=0.01)
        tt_display_type = tooltip.Tooltip(self.display_menu, text=tooltip.display_text, wraplength=500)
        
        self.loading_frame = LoadingFrame(self.canvas, self.master)

        self.left_drag_timer = -1 
        self.clicked_inside_pt = False
        self.clicked_inside_pt_idx = 0
        self.clicked_inside_pt_coord = None
        
        self.preview_select_mode = False
        
        self.master.bind("<Button-1>", self.mouse_down_left)  
        self.master.bind("<ButtonRelease-1>", self.mouse_release_left)         # Left Mouse Button
        self.master.bind("<B1-Motion>", self.mouse_move_left)                  # Left Mouse Button Drag
        self.master.bind("<Motion>", self.mouse_move)                          # Mouse move
        self.master.bind("<Double-Button-1>", self.mouse_double_click_left)    # Left Button Double Click
        self.master.bind("<MouseWheel>", self.mouse_wheel)                     # Mouse Wheel
        self.master.bind("<Button-4>", self.mouse_wheel)                       # Mouse Wheel Linux
        self.master.bind("<Button-5>", self.mouse_wheel)                       # Mouse Wheel Linux
        self.master.bind("<Return>", self.enter_key)                           # Enter Key
        
        
        #Side menu
        heading_font = "Verdana 10 bold"
        
        self.side_canvas = tk.Canvas(self.master, borderwidth=0,  bd=0, highlightthickness=0, name="left_panel")
        self.side_canvas.pack(side=tk.TOP, fill=tk.Y, expand=True)
        
        self.scrollbar = ttk.Scrollbar(self.canvas, orient=tk.VERTICAL, command=self.side_canvas.yview)
        self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        
        scal = get_scaling_factor()*0.75
        self.side_menu = tk.Frame(self.side_canvas, borderwidth=0)
        
        #Crop menu
        self.preview_menu = CollapsibleFrame(self.side_menu, text=_("Create Preview") + " ")
        self.preview_menu.grid(column=0, row=0, pady=(20*scal,5*scal), padx=15*scal, sticky="news")
        self.preview_menu.sub_frame.grid_columnconfigure(0, weight=1)
        
        for i in range(2):
            self.preview_menu.sub_frame.grid_rowconfigure(i, weight=1)
            
        self.preview_mode_button = ttk.Button(self.preview_menu.sub_frame, 
                          text=_("Select preview"),
                          command=self.toggle_preview_select_mode,
        )
        self.preview_mode_button.grid(column=0, row=0, pady=(20*scal,5*scal), padx=15*scal, sticky="news")
        
        self.preview_apply_button = ttk.Button(self.preview_menu.sub_frame, 
                          text=_("Apply preview"),
                          command=self.preview_apply,
        )
        self.preview_apply_button.grid(column=0, row=1, pady=(5*scal,20*scal), padx=15*scal, sticky="news")

        
        #Background extraction menu
        self.sharp_menu = CollapsibleFrame(self.side_menu, text=_("Sharpen and Denoise") + " ")
        self.sharp_menu.grid(column=0, row=1, pady=(20*scal,5*scal), padx=15*scal, sticky="news")
        self.sharp_menu.sub_frame.grid_columnconfigure(0, weight=1)
        
        for i in range(22):
            self.sharp_menu.sub_frame.grid_rowconfigure(i, weight=1)
        
        #---Open Image---
        num_pic = ImageTk.PhotoImage(file=resource_path("img/gfx_number_1-scaled.png"))
        text = tk.Label(self.sharp_menu.sub_frame, text=_(" Loading"), image=num_pic, font=heading_font, compound="left")
        text.image = num_pic
        text.grid(column=0, row=0, pady=(20*scal,5*scal), padx=0, sticky="w")
        
        self.load_image_button = ttk.Button(self.sharp_menu.sub_frame, 
                         text=_("Load Image"),
                         command=self.menu_open_clicked,
        )
        tt_load = tooltip.Tooltip(self.load_image_button, text=tooltip.load_text)
        self.load_image_button.grid(column=0, row=1, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        
        #--Stretch Options--
        num_pic = ImageTk.PhotoImage(file=resource_path("img/gfx_number_2-scaled.png"))
        text = tk.Label(self.sharp_menu.sub_frame, text=_(" Stretch Options"), image=num_pic, font=heading_font, compound="left")
        text.image = num_pic
        text.grid(column=0, row=2, pady=5*scal, padx=0, sticky="w")
        
        self.stretch_options = ["No Stretch", "10% Bg, 3 sigma", "15% Bg, 3 sigma", "20% Bg, 3 sigma", "30% Bg, 2 sigma"]
        self.stretch_option_current = tk.StringVar()
        self.stretch_option_current.set(self.stretch_options[0])
        if "stretch_option" in self.prefs:
            self.stretch_option_current.set(self.prefs["stretch_option"])
        self.stretch_menu = ttk.OptionMenu(self.sharp_menu.sub_frame, self.stretch_option_current, self.stretch_option_current.get(), *self.stretch_options, command=self.change_stretch)
        self.stretch_menu.grid(column=0, row=3, pady=(5*scal,5*scal), padx=15*scal, sticky="news")
        tt_stretch= tooltip.Tooltip(self.stretch_menu, text=tooltip.stretch_text)
        
        self.saturation = tk.DoubleVar()
        self.saturation.set(1.0)
        if "saturation" in self.prefs:
            self.saturation.set(self.prefs["saturation"])
        
        self.saturation_text = tk.Message(self.sharp_menu.sub_frame, text=_("Saturation") + ": {:.1f}".format(self.saturation.get()))
        self.saturation_text.config(width=500 * scal)
        self.saturation_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_saturation_slider(saturation):
            self.saturation.set(saturation)
            self.saturation_text.configure(text=_("Saturation") + ": {:.1f}".format(self.saturation.get()))
                

        self.saturation_slider = ttk.Scale(
            self.sharp_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0,
            to=3,
            var=self.saturation,
            command=on_saturation_slider,
            length=240
            )
        
        self.saturation_slider.bind("<ButtonRelease-1>", self.update_saturation)
        self.saturation_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")
      
        #---Scale extraction---
        num_pic = ImageTk.PhotoImage(file=resource_path("img/gfx_number_3-scaled.png"))
        text = tk.Label(self.sharp_menu.sub_frame, text=_(" Scale extraction"), image=num_pic, font=heading_font, compound="left")
        text.image = num_pic
        text.grid(column=0, row=6, pady=5*scal, padx=0, sticky="w")

        self.extract_button = ttk.Button(self.sharp_menu.sub_frame, 
                         text=_("Extract Scales"),
                         command=self.extract)
        self.extract_button.grid(column=0, row=7, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_calculate= tooltip.Tooltip(self.extract_button, text=tooltip.extract_text)

        #---Scales editor---
        text = tk.Label(self.sharp_menu.sub_frame, text=_(" Adjust Scales"), font=heading_font, compound="left")
        text.grid(column=0, row=8, pady=5*scal, padx=5*scal, sticky="w")


        #---Scale 1 menu---

        self.scale1_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Scale 1") + " ", nested=True)
        self.scale1_menu.grid(column=0, row=9, pady=(10*scal,20*scal), padx=15*scal, sticky="news")
        self.scale1_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(7):
            self.scale1_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.scale1_detail = tk.DoubleVar()
        self.scale1_detail.set(1.0)
        if "scale1_detail" in self.prefs:
            self.scale1_detail.set(self.prefs["scale1_detail"])

        self.scale1_detail_text = tk.Message(self.scale1_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale1_detail.get()))
        self.scale1_detail_text.config(width=500 * scal)
        self.scale1_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale1_detail_slider(scale_detail):
            self.scale1_detail.set(scale_detail)
            self.scale1_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale1_detail.get()))
                

        self.scale1_detail_slider = ttk.Scale(
            self.scale1_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale1_detail,
            command=on_scale1_detail_slider,
            length=110
            )
        
        self.scale1_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale1_denoise_thr = tk.DoubleVar()
        self.scale1_denoise_thr.set(0.05)
        if "scale1_denoise_thr" in self.prefs:
            self.scale1_denoise_thr.set(self.prefs["scale1_denoise_thr"])

        self.scale1_denoise_thr_text = tk.Message(self.scale1_menu.sub_frame, text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale1_denoise_thr.get()))
        self.scale1_denoise_thr_text.config(width=500 * scal)
        self.scale1_denoise_thr_text.grid(column=0, row=2, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale1_denoise_thr_slider(denoise_thr):
            self.scale1_denoise_thr.set(denoise_thr)
            self.scale1_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale1_denoise_thr.get()))
                

        self.scale1_denoise_thr_slider = ttk.Scale(
            self.scale1_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=0.2,
            var=self.scale1_denoise_thr,
            command=on_scale1_denoise_thr_slider,
            length=110
            )
        
        self.scale1_denoise_thr_slider.grid(column=0, row=3, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale1_denoise_amount = tk.DoubleVar()
        self.scale1_denoise_amount.set(0.0)
        if "scale1_denoise_amount" in self.prefs:
            self.scale1_denoise_amount.set(self.prefs["scale1_denoise_amount"])

        self.scale1_denoise_amount_text = tk.Message(self.scale1_menu.sub_frame, text=_("Denoise amount") + ": {:.2f}".format(self.scale1_denoise_amount.get()))
        self.scale1_denoise_amount_text.config(width=500 * scal)
        self.scale1_denoise_amount_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale1_denoise_amount_slider(denoise_amount):
            self.scale1_denoise_amount.set(denoise_amount)
            self.scale1_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(self.scale1_denoise_amount.get()))
                

        self.scale1_denoise_amount_slider = ttk.Scale(
            self.scale1_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=1.0,
            var=self.scale1_denoise_amount,
            command=on_scale1_denoise_amount_slider,
            length=110
            )
        
        self.scale1_denoise_amount_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale1_show_button = ttk.Button(self.scale1_menu.sub_frame, 
                         text=_("Show Scale"),
                         command=self.show_scale1)
        self.scale1_show_button.grid(column=0, row=6, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_scale1 = tooltip.Tooltip(self.scale1_show_button, text=tooltip.show_scale_text)


        #---Scale 2 menu---

        self.scale2_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Scale 2") + " ", nested=True)
        self.scale2_menu.grid(column=0, row=10, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        self.scale2_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(7):
            self.scale2_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.scale2_detail = tk.DoubleVar()
        self.scale2_detail.set(1.0)
        if "scale2_detail" in self.prefs:
            self.scale2_detail.set(self.prefs["scale2_detail"])

        self.scale2_detail_text = tk.Message(self.scale2_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale2_detail.get()))
        self.scale2_detail_text.config(width=500 * scal)
        self.scale2_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale2_detail_slider(scale_detail):
            self.scale2_detail.set(scale_detail)
            self.scale2_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale2_detail.get()))
                

        self.scale2_detail_slider = ttk.Scale(
            self.scale2_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale2_detail,
            command=on_scale2_detail_slider,
            length=110
            )
        
        self.scale2_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale2_denoise_thr = tk.DoubleVar()
        self.scale2_denoise_thr.set(0.05)
        if "scale2_denoise_thr" in self.prefs:
            self.scale2_denoise_thr.set(self.prefs["scale2_denoise_thr"])

        self.scale2_denoise_thr_text = tk.Message(self.scale2_menu.sub_frame, text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale2_denoise_thr.get()))
        self.scale2_denoise_thr_text.config(width=500 * scal)
        self.scale2_denoise_thr_text.grid(column=0, row=2, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale2_denoise_thr_slider(denoise_thr):
            self.scale2_denoise_thr.set(denoise_thr)
            self.scale2_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale2_denoise_thr.get()))
                

        self.scale2_denoise_thr_slider = ttk.Scale(
            self.scale2_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=0.2,
            var=self.scale2_denoise_thr,
            command=on_scale2_denoise_thr_slider,
            length=110
            )
        
        self.scale2_denoise_thr_slider.grid(column=0, row=3, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale2_denoise_amount = tk.DoubleVar()
        self.scale2_denoise_amount.set(0.0)
        if "scale2_denoise_amount" in self.prefs:
            self.scale2_denoise_amount.set(self.prefs["scale2_denoise_amount"])

        self.scale2_denoise_amount_text = tk.Message(self.scale2_menu.sub_frame, text=_("Denoise amount") + ": {:.2f}".format(self.scale2_denoise_amount.get()))
        self.scale2_denoise_amount_text.config(width=500 * scal)
        self.scale2_denoise_amount_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale2_denoise_amount_slider(denoise_amount):
            self.scale2_denoise_amount.set(denoise_amount)
            self.scale2_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(self.scale2_denoise_amount.get()))
                

        self.scale2_denoise_amount_slider = ttk.Scale(
            self.scale2_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=1.0,
            var=self.scale2_denoise_amount,
            command=on_scale2_denoise_amount_slider,
            length=110
            )
        
        self.scale2_denoise_amount_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale2_show_button = ttk.Button(self.scale2_menu.sub_frame, 
                         text=_("Show Scale"),
                         command=self.show_scale2)
        self.scale2_show_button.grid(column=0, row=6, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_scale2 = tooltip.Tooltip(self.scale2_show_button, text=tooltip.show_scale_text)


        #---Scale 3 menu---

        self.scale3_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Scale 3") + " ", nested=True)
        self.scale3_menu.grid(column=0, row=11, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        self.scale3_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(7):
            self.scale3_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.scale3_detail = tk.DoubleVar()
        self.scale3_detail.set(1.0)
        if "scale3_detail" in self.prefs:
            self.scale3_detail.set(self.prefs["scale3_detail"])

        self.scale3_detail_text = tk.Message(self.scale3_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale3_detail.get()))
        self.scale3_detail_text.config(width=500 * scal)
        self.scale3_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale3_detail_slider(scale_detail):
            self.scale3_detail.set(scale_detail)
            self.scale3_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale3_detail.get()))
                

        self.scale3_detail_slider = ttk.Scale(
            self.scale3_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale3_detail,
            command=on_scale3_detail_slider,
            length=110
            )
        
        self.scale3_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale3_denoise_thr = tk.DoubleVar()
        self.scale3_denoise_thr.set(0.05)
        if "scale3_denoise_thr" in self.prefs:
            self.scale3_denoise_thr.set(self.prefs["scale3_denoise_thr"])

        self.scale3_denoise_thr_text = tk.Message(self.scale3_menu.sub_frame, text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale3_denoise_thr.get()))
        self.scale3_denoise_thr_text.config(width=500 * scal)
        self.scale3_denoise_thr_text.grid(column=0, row=2, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale3_denoise_thr_slider(denoise_thr):
            self.scale3_denoise_thr.set(denoise_thr)
            self.scale3_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale3_denoise_thr.get()))
                

        self.scale3_denoise_thr_slider = ttk.Scale(
            self.scale3_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=0.2,
            var=self.scale3_denoise_thr,
            command=on_scale3_denoise_thr_slider,
            length=110
            )
        
        self.scale3_denoise_thr_slider.grid(column=0, row=3, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale3_denoise_amount = tk.DoubleVar()
        self.scale3_denoise_amount.set(0.0)
        if "scale3_denoise_amount" in self.prefs:
            self.scale3_denoise_amount.set(self.prefs["scale3_denoise_amount"])

        self.scale3_denoise_amount_text = tk.Message(self.scale3_menu.sub_frame, text=_("Denoise amount") + ": {:.2f}".format(self.scale3_denoise_amount.get()))
        self.scale3_denoise_amount_text.config(width=500 * scal)
        self.scale3_denoise_amount_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale3_denoise_amount_slider(denoise_amount):
            self.scale3_denoise_amount.set(denoise_amount)
            self.scale3_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(self.scale3_denoise_amount.get()))
                

        self.scale3_denoise_amount_slider = ttk.Scale(
            self.scale3_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=1.0,
            var=self.scale3_denoise_amount,
            command=on_scale3_denoise_amount_slider,
            length=110
            )
        
        self.scale3_denoise_amount_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale3_show_button = ttk.Button(self.scale3_menu.sub_frame, 
                         text=_("Show Scale"),
                         command=self.show_scale3)
        self.scale3_show_button.grid(column=0, row=6, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_scale3 = tooltip.Tooltip(self.scale3_show_button, text=tooltip.show_scale_text)


        #---Scale 4 menu---

        self.scale4_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Scale 4") + " ", nested=True)
        self.scale4_menu.grid(column=0, row=12, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        self.scale4_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(7):
            self.scale4_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.scale4_detail = tk.DoubleVar()
        self.scale4_detail.set(1.0)
        if "scale4_detail" in self.prefs:
            self.scale4_detail.set(self.prefs["scale4_detail"])

        self.scale4_detail_text = tk.Message(self.scale4_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale4_detail.get()))
        self.scale4_detail_text.config(width=500 * scal)
        self.scale4_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale4_detail_slider(scale_detail):
            self.scale4_detail.set(scale_detail)
            self.scale4_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale4_detail.get()))
                

        self.scale4_detail_slider = ttk.Scale(
            self.scale4_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale4_detail,
            command=on_scale4_detail_slider,
            length=110
            )
        
        self.scale4_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale4_denoise_thr = tk.DoubleVar()
        self.scale4_denoise_thr.set(0.05)
        if "scale4_denoise_thr" in self.prefs:
            self.scale4_denoise_thr.set(self.prefs["scale4_denoise_thr"])

        self.scale4_denoise_thr_text = tk.Message(self.scale4_menu.sub_frame, text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale4_denoise_thr.get()))
        self.scale4_denoise_thr_text.config(width=500 * scal)
        self.scale4_denoise_thr_text.grid(column=0, row=2, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale4_denoise_thr_slider(denoise_thr):
            self.scale4_denoise_thr.set(denoise_thr)
            self.scale4_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale4_denoise_thr.get()))
                

        self.scale4_denoise_thr_slider = ttk.Scale(
            self.scale4_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=0.2,
            var=self.scale4_denoise_thr,
            command=on_scale4_denoise_thr_slider,
            length=110
            )
        
        self.scale4_denoise_thr_slider.grid(column=0, row=3, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale4_denoise_amount = tk.DoubleVar()
        self.scale4_denoise_amount.set(0.0)
        if "scale4_denoise_amount" in self.prefs:
            self.scale4_denoise_amount.set(self.prefs["scale4_denoise_amount"])

        self.scale4_denoise_amount_text = tk.Message(self.scale4_menu.sub_frame, text=_("Denoise amount") + ": {:.2f}".format(self.scale4_denoise_amount.get()))
        self.scale4_denoise_amount_text.config(width=500 * scal)
        self.scale4_denoise_amount_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale4_denoise_amount_slider(denoise_amount):
            self.scale4_denoise_amount.set(denoise_amount)
            self.scale4_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(self.scale4_denoise_amount.get()))
                

        self.scale4_denoise_amount_slider = ttk.Scale(
            self.scale4_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=1.0,
            var=self.scale4_denoise_amount,
            command=on_scale4_denoise_amount_slider,
            length=110
            )
        
        self.scale4_denoise_amount_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale4_show_button = ttk.Button(self.scale4_menu.sub_frame, 
                         text=_("Show Scale"),
                         command=self.show_scale4)
        self.scale4_show_button.grid(column=0, row=6, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_scale4 = tooltip.Tooltip(self.scale4_show_button, text=tooltip.show_scale_text)


        #---Scale 5 menu---

        self.scale5_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Scale 5") + " ", nested=True)
        self.scale5_menu.grid(column=0, row=13, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        self.scale5_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(7):
            self.scale5_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.scale5_detail = tk.DoubleVar()
        self.scale5_detail.set(1.0)
        if "scale5_detail" in self.prefs:
            self.scale5_detail.set(self.prefs["scale5_detail"])

        self.scale5_detail_text = tk.Message(self.scale5_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale5_detail.get()))
        self.scale5_detail_text.config(width=500 * scal)
        self.scale5_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale5_detail_slider(scale_detail):
            self.scale5_detail.set(scale_detail)
            self.scale5_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale5_detail.get()))
                

        self.scale5_detail_slider = ttk.Scale(
            self.scale5_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale5_detail,
            command=on_scale5_detail_slider,
            length=110
            )
        
        self.scale5_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale5_denoise_thr = tk.DoubleVar()
        self.scale5_denoise_thr.set(0.05)
        if "scale5_denoise_thr" in self.prefs:
            self.scale5_denoise_thr.set(self.prefs["scale5_denoise_thr"])

        self.scale5_denoise_thr_text = tk.Message(self.scale5_menu.sub_frame, text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale5_denoise_thr.get()))
        self.scale5_denoise_thr_text.config(width=500 * scal)
        self.scale5_denoise_thr_text.grid(column=0, row=2, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale5_denoise_thr_slider(denoise_thr):
            self.scale5_denoise_thr.set(denoise_thr)
            self.scale5_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale5_denoise_thr.get()))
                

        self.scale5_denoise_thr_slider = ttk.Scale(
            self.scale5_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=0.2,
            var=self.scale5_denoise_thr,
            command=on_scale5_denoise_thr_slider,
            length=110
            )
        
        self.scale5_denoise_thr_slider.grid(column=0, row=3, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale5_denoise_amount = tk.DoubleVar()
        self.scale5_denoise_amount.set(0.0)
        if "scale5_denoise_amount" in self.prefs:
            self.scale5_denoise_amount.set(self.prefs["scale5_denoise_amount"])

        self.scale5_denoise_amount_text = tk.Message(self.scale5_menu.sub_frame, text=_("Denoise amount") + ": {:.2f}".format(self.scale5_denoise_amount.get()))
        self.scale5_denoise_amount_text.config(width=500 * scal)
        self.scale5_denoise_amount_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale5_denoise_amount_slider(denoise_amount):
            self.scale5_denoise_amount.set(denoise_amount)
            self.scale5_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(self.scale5_denoise_amount.get()))
                

        self.scale5_denoise_amount_slider = ttk.Scale(
            self.scale5_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=1.0,
            var=self.scale5_denoise_amount,
            command=on_scale5_denoise_amount_slider,
            length=110
            )
        
        self.scale5_denoise_amount_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale5_show_button = ttk.Button(self.scale5_menu.sub_frame, 
                         text=_("Show Scale"),
                         command=self.show_scale5)
        self.scale5_show_button.grid(column=0, row=6, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_scale5 = tooltip.Tooltip(self.scale5_show_button, text=tooltip.show_scale_text)


        #---Scale 6 menu---

        self.scale6_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Scale 6") + " ", nested=True)
        self.scale6_menu.grid(column=0, row=14, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        self.scale6_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(7):
            self.scale6_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.scale6_detail = tk.DoubleVar()
        self.scale6_detail.set(1.0)
        if "scale6_detail" in self.prefs:
            self.scale6_detail.set(self.prefs["scale6_detail"])

        self.scale6_detail_text = tk.Message(self.scale6_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale6_detail.get()))
        self.scale6_detail_text.config(width=500 * scal)
        self.scale6_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale6_detail_slider(scale_detail):
            self.scale6_detail.set(scale_detail)
            self.scale6_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale6_detail.get()))
                

        self.scale6_detail_slider = ttk.Scale(
            self.scale6_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale6_detail,
            command=on_scale6_detail_slider,
            length=110
            )
        
        self.scale6_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale6_denoise_thr = tk.DoubleVar()
        self.scale6_denoise_thr.set(0.05)
        if "scale6_denoise_thr" in self.prefs:
            self.scale6_denoise_thr.set(self.prefs["scale6_denoise_thr"])

        self.scale6_denoise_thr_text = tk.Message(self.scale6_menu.sub_frame, text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale6_denoise_thr.get()))
        self.scale6_denoise_thr_text.config(width=500 * scal)
        self.scale6_denoise_thr_text.grid(column=0, row=2, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale6_denoise_thr_slider(denoise_thr):
            self.scale6_denoise_thr.set(denoise_thr)
            self.scale6_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale6_denoise_thr.get()))
                

        self.scale6_denoise_thr_slider = ttk.Scale(
            self.scale6_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=0.2,
            var=self.scale6_denoise_thr,
            command=on_scale6_denoise_thr_slider,
            length=110
            )
        
        self.scale6_denoise_thr_slider.grid(column=0, row=3, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale6_denoise_amount = tk.DoubleVar()
        self.scale6_denoise_amount.set(0.0)
        if "scale6_denoise_amount" in self.prefs:
            self.scale6_denoise_amount.set(self.prefs["scale6_denoise_amount"])

        self.scale6_denoise_amount_text = tk.Message(self.scale6_menu.sub_frame, text=_("Denoise amount") + ": {:.2f}".format(self.scale6_denoise_amount.get()))
        self.scale6_denoise_amount_text.config(width=500 * scal)
        self.scale6_denoise_amount_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale6_denoise_amount_slider(denoise_amount):
            self.scale6_denoise_amount.set(denoise_amount)
            self.scale6_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(self.scale6_denoise_amount.get()))
                

        self.scale6_denoise_amount_slider = ttk.Scale(
            self.scale6_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=1.0,
            var=self.scale6_denoise_amount,
            command=on_scale6_denoise_amount_slider,
            length=110
            )
        
        self.scale6_denoise_amount_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale6_show_button = ttk.Button(self.scale6_menu.sub_frame, 
                         text=_("Show Scale"),
                         command=self.show_scale6)
        self.scale6_show_button.grid(column=0, row=6, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_scale6 = tooltip.Tooltip(self.scale6_show_button, text=tooltip.show_scale_text)

        #---Scale 7 menu---

        self.scale7_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Scale 7") + " ", nested=True)
        self.scale7_menu.grid(column=0, row=15, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        self.scale7_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(7):
            self.scale7_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.scale7_detail = tk.DoubleVar()
        self.scale7_detail.set(1.0)
        if "scale7_detail" in self.prefs:
            self.scale7_detail.set(self.prefs["scale7_detail"])

        self.scale7_detail_text = tk.Message(self.scale7_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale7_detail.get()))
        self.scale7_detail_text.config(width=500 * scal)
        self.scale7_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale7_detail_slider(scale_detail):
            self.scale7_detail.set(scale_detail)
            self.scale7_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale7_detail.get()))
                

        self.scale7_detail_slider = ttk.Scale(
            self.scale7_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale7_detail,
            command=on_scale7_detail_slider,
            length=110
            )
        
        self.scale7_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale7_denoise_thr = tk.DoubleVar()
        self.scale7_denoise_thr.set(0.05)
        if "scale7_denoise_thr" in self.prefs:
            self.scale7_denoise_thr.set(self.prefs["scale7_denoise_thr"])

        self.scale7_denoise_thr_text = tk.Message(self.scale7_menu.sub_frame, text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale7_denoise_thr.get()))
        self.scale7_denoise_thr_text.config(width=500 * scal)
        self.scale7_denoise_thr_text.grid(column=0, row=2, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale7_denoise_thr_slider(denoise_thr):
            self.scale7_denoise_thr.set(denoise_thr)
            self.scale7_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(self.scale7_denoise_thr.get()))
                

        self.scale7_denoise_thr_slider = ttk.Scale(
            self.scale7_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=0.2,
            var=self.scale7_denoise_thr,
            command=on_scale7_denoise_thr_slider,
            length=110
            )
        
        self.scale7_denoise_thr_slider.grid(column=0, row=3, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale7_denoise_amount = tk.DoubleVar()
        self.scale7_denoise_amount.set(0.0)
        if "scale7_denoise_amount" in self.prefs:
            self.scale7_denoise_amount.set(self.prefs["scale7_denoise_amount"])

        self.scale7_denoise_amount_text = tk.Message(self.scale7_menu.sub_frame, text=_("Denoise amount") + ": {:.2f}".format(self.scale7_denoise_amount.get()))
        self.scale7_denoise_amount_text.config(width=500 * scal)
        self.scale7_denoise_amount_text.grid(column=0, row=4, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_scale7_denoise_amount_slider(denoise_amount):
            self.scale7_denoise_amount.set(denoise_amount)
            self.scale7_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(self.scale7_denoise_amount.get()))
                

        self.scale7_denoise_amount_slider = ttk.Scale(
            self.scale7_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=1.0,
            var=self.scale7_denoise_amount,
            command=on_scale7_denoise_amount_slider,
            length=110
            )
        
        self.scale7_denoise_amount_slider.grid(column=0, row=5, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.scale7_show_button = ttk.Button(self.scale7_menu.sub_frame, 
                         text=_("Show Scale"),
                         command=self.show_scale7)
        self.scale7_show_button.grid(column=0, row=6, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_scale7 = tooltip.Tooltip(self.scale7_show_button, text=tooltip.show_scale_text)

        #---Residual menu---

        self.residual_menu = CollapsibleFrame(self.sharp_menu.sub_frame, text=_("Residual") + " ", nested=True)
        self.residual_menu.grid(column=0, row=16, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        self.residual_menu.sub_frame.grid_columnconfigure(0, weight=1)

        for i in range(3):
            self.residual_menu.sub_frame.grid_rowconfigure(i, weight=1)

        self.residual_detail = tk.DoubleVar()
        self.residual_detail.set(1.0)
        if "residual_detail" in self.prefs:
            self.residual_detail.set(self.prefs["residual_detail"])

        self.residual_detail_text = tk.Message(self.residual_menu.sub_frame, text=_("Detail Enhancement") + ": {:.1f}".format(self.scale7_detail.get()))
        self.residual_detail_text.config(width=500 * scal)
        self.residual_detail_text.grid(column=0, row=0, pady=(5*scal,5*scal), padx=15*scal, sticky="ews")
        
        def on_residual_detail_slider(scale_detail):
            self.residual_detail.set(scale_detail)
            self.residual_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(self.scale7_detail.get()))
                

        self.residual_detail_slider = ttk.Scale(
            self.residual_menu.sub_frame,
            orient=tk.HORIZONTAL,
            from_=1.0,
            to=4.0,
            var=self.scale7_detail,
            command=on_residual_detail_slider,
            length=110
            )
        
        self.residual_detail_slider.grid(column=0, row=1, pady=(0,30*scal), padx=15*scal, sticky="ew")

        self.residual_show_button = ttk.Button(self.residual_menu.sub_frame, 
                         text=_("Show Residual"),
                         command=self.show_residual)
        self.residual_show_button.grid(column=0, row=2, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_show_residual = tooltip.Tooltip(self.residual_show_button, text=tooltip.show_scale_text)

        #---Load default values---
        self.default_val_button = ttk.Button(self.sharp_menu.sub_frame, 
                         text=_("Set default values"),
                         command=self.set_default_values)
        self.default_val_button.grid(column=0, row=17, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_calculate= tooltip.Tooltip(self.default_val_button, text=tooltip.load_default_val_text)
        
        
        #---Calculation---
        num_pic = ImageTk.PhotoImage(file=resource_path("img/gfx_number_4-scaled.png"))
        text = tk.Label(self.sharp_menu.sub_frame, text=_(" Process Image"), image=num_pic, font=heading_font, compound="left")
        text.image = num_pic
        text.grid(column=0, row=18, pady=5*scal, padx=0, sticky="w")
        
        
        self.calculate_button = ttk.Button(self.sharp_menu.sub_frame, 
                         text=_("Process Image"),
                         command=self.calculate)
        self.calculate_button.grid(column=0, row=19, pady=(5*scal,30*scal), padx=15*scal, sticky="news")
        tt_calculate= tooltip.Tooltip(self.calculate_button, text=tooltip.calculate_text)
        
        #---Saving---  
        num_pic = ImageTk.PhotoImage(file=resource_path("img/gfx_number_5-scaled.png"))
        self.saveas_text = tk.Label(self.sharp_menu.sub_frame, text=_(" Saving"), image=num_pic, font=heading_font, compound="left")
        self.saveas_text.image = num_pic
        self.saveas_text.grid(column=0, row=20, pady=5*scal, padx=0, sticky="w")
        
        self.saveas_options = ["16 bit Tiff", "32 bit Tiff", "16 bit Fits", "32 bit Fits", "16 bit XISF", "32 bit XISF"]
        self.saveas_type = tk.StringVar()
        self.saveas_type.set(self.saveas_options[0])
        if "saveas_option" in self.prefs:
            self.saveas_type.set(self.prefs["saveas_option"])
        self.saveas_menu = ttk.OptionMenu(self.sharp_menu.sub_frame, self.saveas_type, self.saveas_type.get(), *self.saveas_options)
        self.saveas_menu.grid(column=0, row=21, pady=(5*scal,20*scal), padx=15*scal, sticky="news")
        tt_interpol_type= tooltip.Tooltip(self.saveas_menu, text=tooltip.saveas_text)
              
        
        self.save_button = ttk.Button(self.sharp_menu.sub_frame, 
                         text=_("Save Processed"),
                         command=self.save_image)
        self.save_button.grid(column=0, row=22, pady=(5*scal,10*scal), padx=15*scal, sticky="news")
        tt_save_pic= tooltip.Tooltip(self.save_button, text=tooltip.save_pic_text)
        

        self.side_canvas.create_window((0,0), window=self.side_menu)
        self.side_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.side_canvas.bind('<Configure>', lambda e: self.side_canvas.configure(scrollregion=self.side_canvas.bbox("all")))
        self.side_menu.update()
        width = self.side_menu.winfo_width()
        self.side_canvas.configure(width=width)
        self.side_canvas.yview_moveto("0.0")

    
    def menu_open_clicked(self, event=None):

        if self.prefs["working_dir"] != "" and os.path.exists(self.prefs["working_dir"]):
            initialdir = self.prefs["working_dir"]
        else:
            initialdir = os.getcwd()
        
        filename = tk.filedialog.askopenfilename(
            filetypes = [("Image file", ".bmp .png .jpg .tif .tiff .fit .fits .fts .xisf"),
                         ("Bitmap", ".bmp"), ("PNG", ".png"), ("JPEG", ".jpg"), ("Tiff", ".tif .tiff"), ("Fits", ".fit .fits .fts"), ("XISF", ".xisf")],
            initialdir = initialdir
            )
        
        if filename == "":
            return
        
        self.loading_frame.start()
        self.data_type = os.path.splitext(filename)[1]
        
        try:
            image = AstroImage(self.stretch_option_current, self.saturation)
            image.set_from_file(filename)
            self.images["Original"] = image
            self.prefs["working_dir"] = os.path.dirname(filename)
            
        except Exception as e:
            msg = _("An error occurred while loading your picture.")
            logging.exception(msg)
            messagebox.showerror("Error", _(msg))

        
        self.display_type.set("Original")
        self.images["Processed"] = None
        self.images["Scale"] = None
        
        self.master.title(self.my_title + " - " + os.path.basename(filename))
        self.filename = os.path.splitext(os.path.basename(filename))[0]
        
        width = self.images["Original"].img_display.width
        height = self.images["Original"].img_display.height
        mode = self.images["Original"].img_display.mode
        self.label_image_info["text"] = f"{self.data_type} : {width} x {height} {mode}"

        os.chdir(os.path.dirname(filename))

        self.prefs["width"] = width
        self.prefs["height"] = height
        
        self.zoom_fit(width, height)
        self.redraw_image()
        self.loading_frame.end()
        return
    
    def toggle_preview_select_mode(self):
        
        if self.images["Original"] is None:
            messagebox.showerror("Error", _("Please load your picture first."))
            return

        if self.preview_mode == True:
            messagebox.showerror("Error", _("Cannot select preview in preview mode"))
            return

        self.preview_changed = True

        if(self.preview_select_mode):
            self.preview_select_mode = False
        else:
            self.startx = 0
            self.starty = 0
            self.endx = self.images["Original"].width
            self.endy = self.images["Original"].height
            self.preview_select_mode = True

        self.redraw_preview_rect()

        
    def preview_apply(self):
        if self.images["Original"] is None:
            messagebox.showerror("Error", _("Please load your picture first."))
            return

        self.preview_select_mode = False

        if self.preview_mode == True:
            self.images = self.images_full
            self.preview_mode = False
            self.preview_apply_button["text"] = "Apply Preview"
        else:
            if self.preview_changed == True:
                preview_img = AstroImage(self.images["Original"].stretch_option, self.images["Original"].saturation)
                preview_img.set_from_array(self.images["Original"].img_array[self.starty:self.endy,self.startx:self.endx,:])
                preview_img.stretch()
                preview_img.update_display()
                self.images_preview["Original"] = preview_img

                self.preview_changed = False
            else:
                if self.images_preview["Original"] is None:
                    messagebox.showerror("Error", _("Please select a preview area first."))
                    return
            
            self.preview_apply_button["text"] = "End preview"
            self.images = self.images_preview
            self.preview_mode = True

        self.preview_select_mode = False
        self.multiscale_img = None
        self.zoom_fit(self.images[self.display_type.get()].width, self.images[self.display_type.get()].height)
        self.redraw_image()
        self.redraw_preview_rect()
        return
        

    def change_stretch(self,event=None):
        self.loading_frame.start()
        
        all_images = []
        stretches = []
        for img in self.images.values():    
            if(img is not None):
                all_images.append(img.img_array)
        if len(all_images) > 0:
            stretch_params = self.images["Original"].get_stretch()
            stretches = stretch_all(all_images, stretch_params)

        i = 0
        for idx, img in enumerate(self.images.values()):
            if(img is not None):
                img.update_display_from_array(stretches[i])
                i = i+1
        self.loading_frame.end()
        
        self.redraw_image()
        return


    def update_saturation(self, event=None):
        for img in self.images.values():
            if img is not None:
                img.update_saturation()
        
        self.redraw_image()

   
    def save_image(self):
       
       
       if(self.saveas_type.get() == "16 bit Tiff" or self.saveas_type.get() == "32 bit Tiff"):
           dir = tk.filedialog.asksaveasfilename(
               initialfile = self.filename + "_AstroSharp.tiff",
               filetypes = [("Tiff", ".tiff")],
               defaultextension = ".tiff",
               initialdir = self.prefs["working_dir"]
               )         
       elif(self.saveas_type.get() == "16 bit XISF" or self.saveas_type.get() == "32 bit XISF"):       
            dir = tk.filedialog.asksaveasfilename(
                initialfile = self.filename + "_AstroSharp.xisf",
                filetypes = [("XISF", ".xisf")],
                defaultextension = ".xisf",
                initialdir = self.prefs["working_dir"]
                )           
       else:
           dir = tk.filedialog.asksaveasfilename(
               initialfile = self.filename + "_AstroSharp.fits",
               filetypes = [("Fits", ".fits")],
               defaultextension = ".fits",
               initialdir = self.prefs["working_dir"]
               )
                           
       if(dir == ""):
           return
        
       self.loading_frame.start()
       
       try:
           self.images["Processed"].save(dir, self.saveas_type.get())
       except:
           messagebox.showerror("Error", _("Error occured when saving the image."))
           
       self.loading_frame.end()
        
    def extract(self):

        if self.images["Original"] is None:
            messagebox.showerror("Error", _("Please load your picture first."))
            return

        self.loading_frame.start()

        self.multiscale_img = multiscale_image.MultiScaleImage.decompose_image(self.images["Original"].img_array, self.num_scales)

        self.loading_frame.end()

    def calculate(self):

        if self.images["Original"] is None:
            messagebox.showerror("Error", _("Please load your picture first."))
            return

        if self.multiscale_img is None:
            messagebox.showerror("Error", _("Please extract layers first"))

        
        self.loading_frame.start()

        self.multiscale_img.set_residual_detail_boost(self.residual_detail.get())
        self.multiscale_img.set_detail_boost(np.array([self.scale1_detail.get(), self.scale2_detail.get(), self.scale3_detail.get(), self.scale4_detail.get(), self.scale5_detail.get(), self.scale6_detail.get(), self.scale7_detail.get()]))
        self.multiscale_img.set_denoise_amount(np.array([self.scale1_denoise_amount.get(), self.scale2_denoise_amount.get(), self.scale3_denoise_amount.get(), self.scale4_denoise_amount.get(), self.scale5_denoise_amount.get(), self.scale6_denoise_amount.get(), self.scale7_denoise_amount.get()]))
        self.multiscale_img.set_denoise_threshold(np.array([self.scale1_denoise_thr.get(), self.scale2_denoise_thr.get(), self.scale3_denoise_thr.get(), self.scale4_denoise_thr.get(), self.scale5_denoise_thr.get(), self.scale6_denoise_thr.get(), self.scale7_denoise_thr.get()]))
        
        self.images["Processed"] = AstroImage(self.stretch_option_current, self.saturation)
        self.images["Processed"].set_from_array(self.multiscale_img.recompose_image())
 
        # Update fits header and metadata
        all_images = [self.images["Original"].img_array, self.images["Processed"].img_array]
        stretches = stretch_all(all_images, self.images["Original"].get_stretch())
        self.images["Original"].update_display_from_array(stretches[0])
        self.images["Processed"].update_display_from_array(stretches[1])
        
        self.display_type.set("Processed")
        self.redraw_image()
        
        self.loading_frame.end()

        return

    def show_scale1(self):
        self.show_scale(1)
        return

    def show_scale2(self):
        self.show_scale(2)
        return

    def show_scale3(self):
        self.show_scale(3)
        return

    def show_scale4(self):
        self.show_scale(4)
        return

    def show_scale5(self):
        self.show_scale(5)
        return

    def show_scale6(self):
        self.show_scale(6)
        return

    def show_scale7(self):
        self.show_scale(7)
        return

    def show_scale(self, num):
        if self.multiscale_img is None:
            messagebox.showerror("Error", _("Please extract scales first."))
            return
        
        self.scale_img_to_show.set_from_array(self.multiscale_img.img_scales[num-1,:,:,:])
        self.scale_img_to_show.set_boost(0.5)
        self.scale_img_to_show.update_display()

        self.images["Scale"] = self.scale_img_to_show
        self.display_type.set("Scale")

        self.redraw_image()

        return

    def show_residual(self):
        if self.multiscale_img is None:
            messagebox.showerror("Error", _("Please extract scales first."))
            return
        
        self.scale_img_to_show.set_from_array(self.multiscale_img.img_residual)
        self.scale_img_to_show.set_boost(0.0)
        self.scale_img_to_show.update_display()

        self.images["Residual"] = self.scale_img_to_show
        self.display_type.set("Residual")

        self.redraw_image()

        return

    
    def enter_key(self,enter):
        
        self.calculate()

    def set_default_values(self):
        default_prefs = get_default_prefs()

        self.scale1_detail.set(default_prefs["scale1_detail"])
        self.scale1_detail_slider.set(default_prefs["scale1_detail"])
        self.scale1_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["scale1_detail"]))
        self.scale2_detail.set(default_prefs["scale2_detail"])
        self.scale2_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["scale2_detail"]))
        self.scale3_detail.set(default_prefs["scale3_detail"])
        self.scale3_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["scale3_detail"]))
        self.scale4_detail.set(default_prefs["scale4_detail"])
        self.scale4_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["scale4_detail"]))
        self.scale5_detail.set(default_prefs["scale5_detail"])
        self.scale5_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["scale5_detail"]))
        self.scale6_detail.set(default_prefs["scale6_detail"])
        self.scale6_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["scale6_detail"]))
        self.scale7_detail.set(default_prefs["scale7_detail"])
        self.scale7_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["scale7_detail"]))
        self.residual_detail.set(default_prefs["residual_detail"])
        self.residual_detail_text.configure(text=_("Detail Enhancement") + ": {:.1f}".format(default_prefs["residual_detail"]))

        self.scale1_denoise_amount.set(default_prefs["scale1_denoise_amount"])
        self.scale1_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(default_prefs["scale1_denoise_amount"]))
        self.scale2_denoise_amount.set(default_prefs["scale2_denoise_amount"])
        self.scale2_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(default_prefs["scale2_denoise_amount"]))
        self.scale3_denoise_amount.set(default_prefs["scale3_denoise_amount"])
        self.scale3_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(default_prefs["scale3_denoise_amount"]))
        self.scale4_denoise_amount.set(default_prefs["scale4_denoise_amount"])
        self.scale4_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(default_prefs["scale4_denoise_amount"]))
        self.scale5_denoise_amount.set(default_prefs["scale5_denoise_amount"])
        self.scale5_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(default_prefs["scale5_denoise_amount"]))
        self.scale6_denoise_amount.set(default_prefs["scale6_denoise_amount"])
        self.scale6_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(default_prefs["scale6_denoise_amount"]))
        self.scale7_denoise_amount.set(default_prefs["scale7_denoise_amount"])
        self.scale7_denoise_amount_text.configure(text=_("Denoise amount") + ": {:.2f}".format(default_prefs["scale7_denoise_amount"]))

        self.scale1_denoise_thr.set(default_prefs["scale1_denoise_thr"])
        self.scale1_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(default_prefs["scale1_denoise_thr"]))
        self.scale2_denoise_thr.set(default_prefs["scale2_denoise_thr"])
        self.scale2_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(default_prefs["scale2_denoise_thr"]))
        self.scale3_denoise_thr.set(default_prefs["scale3_denoise_thr"])
        self.scale3_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(default_prefs["scale3_denoise_thr"]))
        self.scale4_denoise_thr.set(default_prefs["scale4_denoise_thr"])
        self.scale4_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(default_prefs["scale4_denoise_thr"]))
        self.scale5_denoise_thr.set(default_prefs["scale5_denoise_thr"])
        self.scale5_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(default_prefs["scale5_denoise_thr"]))
        self.scale6_denoise_thr.set(default_prefs["scale6_denoise_thr"])
        self.scale6_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(default_prefs["scale6_denoise_thr"]))
        self.scale7_denoise_thr.set(default_prefs["scale7_denoise_thr"])
        self.scale7_denoise_thr_text.configure(text=_("Denoise detail threshold") + ": {:.3f}".format(default_prefs["scale7_denoise_thr"]))
        
    
    def mouse_down_left(self,event):
        
        self.left_drag_timer = -1
        if(str(event.widget).split(".")[-1] != "picture" or self.images["Original"] is None):
            return
        
        if(self.preview_select_mode):
            #Check if inside circles to move crop corners
            corner1 = self.to_canvas_point(self.startx, self.starty)
            corner2 = self.to_canvas_point(self.endx, self.endy)
            if((event.x - corner1[0])**2 + (event.y - corner1[1])**2 < 15**2 or (event.x - corner2[0])**2 + (event.y - corner2[1])**2 < 15**2):
                self.clicked_inside_pt = True
                
        self.__old_event = event

        
    def mouse_release_left(self,event):
        
        if(str(event.widget).split(".")[-1] != "picture" or self.images["Original"] is None):
            return
        
        self.__old_event = event
        self.left_drag_timer = -1

        self.redraw_preview_rect()
        
    def mouse_move_left(self, event):
        
        if(str(event.widget).split(".")[-1] != "picture" or self.images["Original"] is None):
            return
        
        if (self.images[self.display_type.get()] is None):
            return

        if(self.left_drag_timer == -1):
            self.left_drag_timer = event.time

        elif(self.clicked_inside_pt and self.preview_select_mode):
            new_point = self.to_image_point_pinned(event.x, event.y)
            corner1_canvas = self.to_canvas_point(self.startx, self.starty)
            corner2_canvas = self.to_canvas_point(self.endx, self.endy)
            
            dist1 = (event.x - corner1_canvas[0])**2 + (event.y - corner1_canvas[1])**2
            dist2 = (event.x - corner2_canvas[0])**2 + (event.y - corner2_canvas[1])**2
            if(dist1 < dist2):
                self.startx = int(new_point[0])
                self.starty = int(new_point[1])
            else:
                self.endx = int(new_point[0])
                self.endy = int(new_point[1])

            self.redraw_preview_rect()                      
        else:
            if(event.time - self.left_drag_timer >= 100):            
                self.translate(event.x - self.__old_event.x, event.y - self.__old_event.y)
                self.redraw_image()
        
        
        self.mouse_move(event)
        self.__old_event = event
        return

    def mouse_move(self, event):

        if (self.images[self.display_type.get()] is None):
            return
        
        image_point = self.to_image_point(event.x, event.y)
        if len(image_point) != 0:
            text = "x=" + f"{image_point[0]:.2f}" + ",y=" + f"{image_point[1]:.2f}  "
            if(self.images[self.display_type.get()].img_array.shape[2] == 3):
                R, G, B = self.images[self.display_type.get()].get_local_median(image_point)            
                text = text + "RGB = (" + f"{R:.4f}," + f"{G:.4f}," + f"{B:.4f})"
            
            if(self.images[self.display_type.get()].img_array.shape[2] == 1):
                L = self.images[self.display_type.get()].get_local_median(image_point)
                text = text + "L= " + f"{L:.4f}"
            
            self.label_image_pixel["text"] = text
        else:
            self.label_image_pixel["text"] = ("(--, --)")


    def mouse_double_click_left(self, event):
        
        if(str(event.widget).split(".")[-1] != "picture"):
            return
        
        if self.images[self.display_type.get()] is None:
            return
        self.zoom_fit(self.images[self.display_type.get()].width, self.images[self.display_type.get()].height)
        self.redraw_preview_rect()
        self.redraw_image()


    def mouse_wheel(self, event):

        if "help_canvas" in str(event.widget):
            if self.help_panel.help_canvas.yview() == (0.0,1.0):
                return
            
            if (event.delta > 0 or event.num == 4):
                self.help_panel.help_canvas.yview_scroll(-1, "units")
            else:
                self.help_panel.help_canvas.yview_scroll(1, "units")       
                
        elif "advanced_canvas" in str(event.widget):
            if self.help_panel.advanced_canvas.yview() == (0.0,1.0):
                return
            
            if (event.delta > 0 or event.num == 4):
                self.help_panel.advanced_canvas.yview_scroll(-1, "units")
            else:
                self.help_panel.advanced_canvas.yview_scroll(1, "units") 
        
        elif "left_panel" in str(event.widget):
            if self.side_canvas.yview() == (0.0,1.0):
                return
            
            if (event.delta > 0 or event.num == 4):
                self.side_canvas.yview_scroll(-1, "units")
            else:
                self.side_canvas.yview_scroll(1, "units")
                
        elif "picture" in str(event.widget):
            if self.images[self.display_type.get()] is None:
                return    
    
            if (event.delta > 0 or event.num == 4):
    
                self.scale_at(6/5, event.x, event.y)
            else:
    
                self.scale_at(5/6, event.x, event.y)
       
            self.redraw_image()


    def redraw_preview_rect(self):
        
        if self.images["Original"] is None:
            return
    
        color = hls_to_rgb(self.sample_color.get()/360, 0.5, 1.0)
        color = (int(color[0]*255), int(color[1]*255), int(color[2]*255))
        color = '#%02x%02x%02x' % color
        
        self.canvas.delete("crop") 
        
        
        if self.preview_select_mode:
            corner1 = self.to_canvas_point(self.startx, self.starty)
            corner2 = self.to_canvas_point(self.endx, self.endy)
            self.canvas.create_rectangle(corner1[0],corner1[1], corner2[0],corner2[1], outline=color, width=2, tags="crop")
            self.canvas.create_oval(corner1[0]-15,corner1[1]-15, corner1[0]+15,corner1[1]+15, outline=color, width=2, tags="crop")
            self.canvas.create_oval(corner2[0]-15,corner2[1]-15, corner2[0]+15,corner2[1]+15, outline=color, width=2, tags="crop")
        return  



    def reset_transform(self):

        self.mat_affine = np.eye(3)

    def translate(self, offset_x, offset_y):

        mat = np.eye(3)
        mat[0, 2] = float(offset_x)
        mat[1, 2] = float(offset_y)

        self.mat_affine = np.dot(mat, self.mat_affine)

    def scale(self, scale:float):

        mat = np.eye(3)
        mat[0, 0] = scale
        mat[1, 1] = scale

        self.mat_affine = np.dot(mat, self.mat_affine)

    def scale_at(self, scale:float, cx:float, cy:float):



        self.translate(-cx, -cy)
        self.scale(scale)
        self.translate(cx, cy)



    def zoom_fit(self, image_width, image_height):


        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if (image_width * image_height <= 0) or (canvas_width * canvas_height <= 0):
            return


        self.reset_transform()

        scale = 1.0
        offsetx = 0.0
        offsety = 0.0

        if (canvas_width * image_height) > (image_width * canvas_height):

            scale = canvas_height / image_height
            offsetx = (canvas_width - image_width * scale) / 2
        else:

            scale = canvas_width / image_width
            offsety = (canvas_height - image_height * scale) / 2


        self.scale(scale)
        self.translate(offsetx, offsety)

    def to_image_point(self, x, y):

        if self.images[self.display_type.get()] is None:
            return []

        mat_inv = np.linalg.inv(self.mat_affine)
        image_point = np.dot(mat_inv, (x, y, 1.))
        
        width = self.images[self.display_type.get()].width
        height = self.images[self.display_type.get()].height
        
        if  image_point[0] < 0 or image_point[1] < 0 or image_point[0] > width or image_point[1] > height:
            return []

        return image_point

    def to_image_point_pinned(self, x, y):
        
        if self.images[self.display_type.get()] is None:
            return []

        mat_inv = np.linalg.inv(self.mat_affine)
        image_point = np.dot(mat_inv, (x, y, 1.))
        
        width = self.images[self.display_type.get()].width
        height = self.images[self.display_type.get()].height
        
        if image_point[0] < 0:
            image_point[0] = 0
        if image_point[1] < 0:
            image_point[1] = 0
        if image_point[0] > width:
            image_point[0] = width
        if image_point[1] > height:
            image_point[1] = height

        return image_point
    
    def to_canvas_point(self, x, y):
        
        return np.dot(self.mat_affine,(x,y,1.))

    def draw_image(self, pil_image):

        if pil_image is None:
            return


        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()


        mat_inv = np.linalg.inv(self.mat_affine)


        affine_inv = (
            mat_inv[0, 0], mat_inv[0, 1], mat_inv[0, 2],
            mat_inv[1, 0], mat_inv[1, 1], mat_inv[1, 2]
            )


        dst = pil_image.transform(
                    (canvas_width, canvas_height),
                    Image.AFFINE,
                    affine_inv,
                    Image.BILINEAR  
                    )

        im = ImageTk.PhotoImage(image=dst)


        item = self.canvas.create_image(
                0, 0,           
                anchor='nw',    
                image=im        
                )

        self.image = im
        self.redraw_preview_rect()
        return

    def redraw_image(self):

        if self.images[self.display_type.get()] is None:
            return
        self.draw_image(self.images[self.display_type.get()].img_display_saturated)
            
    def switch_display(self, event):
        if(self.images["Processed"] is None and self.display_type.get() == "Processed"):
            self.display_type.set("Original")
            messagebox.showerror("Error", _("Please process image first"))         
            return

        if(self.images["Scale"] is None and self.display_type.get() == "Scale"):
            self.show_scale1()     
            return

        if(self.images["Residual"] is None and self.display_type.get() == "Residual"):
            self.show_residual()     
            return
        
        self.loading_frame.start()
        self.redraw_image()
        self.loading_frame.end()
    
    def on_closing(self, logging_thread):
        self.prefs["stretch_option"] = self.stretch_option_current.get()
        self.prefs["saturation"] = self.saturation.get()
        self.prefs["saveas_option"] = self.saveas_type.get()
        self.prefs["sample_color"] = self.sample_color.get()
        self.prefs["scale1_detail"] = self.scale1_detail.get()
        self.prefs["scale1_denoise_amount"] = self.scale1_denoise_amount.get()
        self.prefs["scale1_denoise_thr"] = self.scale1_denoise_thr.get()
        self.prefs["scale2_detail"] = self.scale2_detail.get()
        self.prefs["scale2_denoise_amount"] = self.scale2_denoise_amount.get()
        self.prefs["scale2_denoise_thr"] = self.scale2_denoise_thr.get()
        self.prefs["scale3_detail"] = self.scale3_detail.get()
        self.prefs["scale3_denoise_amount"] = self.scale3_denoise_amount.get()
        self.prefs["scale3_denoise_thr"] = self.scale3_denoise_thr.get()
        self.prefs["scale4_detail"] = self.scale4_detail.get()
        self.prefs["scale4_denoise_amount"] = self.scale4_denoise_amount.get()
        self.prefs["scale4_denoise_thr"] = self.scale4_denoise_thr.get()
        self.prefs["scale5_detail"] = self.scale5_detail.get()
        self.prefs["scale5_denoise_amount"] = self.scale5_denoise_amount.get()
        self.prefs["scale5_denoise_thr"] = self.scale5_denoise_thr.get()
        self.prefs["scale6_detail"] = self.scale6_detail.get()
        self.prefs["scale6_denoise_amount"] = self.scale6_denoise_amount.get()
        self.prefs["scale6_denoise_thr"] = self.scale6_denoise_thr.get()
        self.prefs["scale7_detail"] = self.scale7_detail.get()
        self.prefs["scale7_denoise_amount"] = self.scale7_denoise_amount.get()
        self.prefs["scale7_denoise_thr"] = self.scale7_denoise_thr.get()
        self.prefs["residual_detail"] = self.residual_detail.get()
        #self.prefs["lang"] = self.lang.get()
        prefs_filename = os.path.join(user_config_dir(appname="AstroSharp"), "preferences.json")
        save_preferences(prefs_filename, self.prefs)
        try:
            executor.shutdown(cancel_futures=True)
        except Exception as e:
            logging.exception("error shutting down ProcessPoolExecutor")
        shutdown_logging(logging_thread)
        root.destroy()

def scale_img(path, scaling, shape):
    img = io.imread(resource_path(path))
    img = resize(img, (int(shape[0]*scaling),int(shape[1]*scaling)))
    img = img*255
    img = img.astype(dtype=np.uint8)
    io.imsave(resource_path(resource_path(path.replace('.png', '-scaled.png'))), img, check_contrast=False)

if __name__ == "__main__":

    logging_thread = initialize_logging()

    root = hdpitk.HdpiTk()
    scaling = get_scaling_factor()
    
    scale_img("./forest-dark/vert-hover.png", scaling*0.9, (20,10))
    scale_img("./forest-dark/vert-basic.png", scaling*0.9, (20,10))
    
    scale_img("./forest-dark/thumb-hor-accent.png", scaling*0.9, (20,8))
    scale_img("./forest-dark/thumb-hor-hover.png", scaling*0.9, (20,8))
    scale_img("./forest-dark/thumb-hor-basic.png", scaling*0.9, (20,8))
    scale_img("./forest-dark/scale-hor.png", scaling, (20,20))
    
    scale_img("./forest-dark/check-accent.png", scaling*0.8, (20,20))
    scale_img("./forest-dark/check-basic.png", scaling*0.8, (20,20))
    scale_img("./forest-dark/check-hover.png", scaling*0.8, (20,20))
    scale_img("./forest-dark/check-unsel-accent.png", scaling*0.8, (20,20))
    scale_img("./forest-dark/check-unsel-basic.png", scaling*0.8, (20,20))
    scale_img("./forest-dark/check-unsel-hover.png", scaling*0.8, (20,20))
    scale_img("./forest-dark/check-unsel-pressed.png", scaling*0.8, (20,20))
    
    scale_img("./img/gfx_number_1.png", scaling*0.7, (25,25))
    scale_img("./img/gfx_number_2.png", scaling*0.7, (25,25))
    scale_img("./img/gfx_number_3.png", scaling*0.7, (25,25))
    scale_img("./img/gfx_number_4.png", scaling*0.7, (25,25))
    scale_img("./img/gfx_number_5.png", scaling*0.7, (25,25))
    scale_img("./img/hourglass.png", scaling, (25,25))
    
    root.tk.call("source", resource_path("forest-dark.tcl"))   
    style = ttk.Style(root)
    style.theme_use("forest-dark")
    style.configure("TButton", padding=(8*scaling, 12*scaling, 8*scaling, 12*scaling))
    style.configure("TMenubutton", padding=(8*scaling, 4*scaling, 4*scaling, 4*scaling))
    root.tk.call("wm", "iconphoto", root._w, tk.PhotoImage(file=resource_path("img/Icon.png")))
    root.tk.call('tk', 'scaling', scaling)
    root.option_add("*TkFDialog*foreground", "black")
    app = Application(master=root)
    root.protocol("WM_DELETE_WINDOW", lambda: app.on_closing(logging_thread))
    root.createcommand("::tk::mac::Quit", lambda: app.on_closing(logging_thread))

    app.mainloop()
    