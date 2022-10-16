import json
import logging
import os
import shutil
from datetime import datetime
from typing import AnyStr, List, TypedDict

import numpy as np


class Prefs(TypedDict):
    working_dir: AnyStr
    width: int
    height: int
    stretch_option: AnyStr
    saturation: float
    saveas_option: AnyStr
    lang: AnyStr

DEFAULT_PREFS: Prefs = {
    "working_dir": os.getcwd(),
    "width": None,
    "height": None,
    "stretch_option": "No Stretch",
    "saturation": 1.0,
    "saveas_option": "32 bit Tiff",
    "lang": None,
}


def merge_json(prefs: Prefs, json) -> Prefs:
    if "working_dir" in json:
        prefs["working_dir"] = json["working_dir"]
    if "width" in json:
        prefs["width"] = json["width"]
    if "height" in json:
        prefs["height"] = json["height"]
    if "stretch_option" in json:
        prefs["stretch_option"] = json["stretch_option"]
    if "saturation" in json:
        prefs["saturation"] = json["saturation"]
    if "saveas_option" in json:
        prefs["saveas_option"] = json["saveas_option"]
    if "lang" in json:
        prefs["lang"] = json["lang"]
    return prefs


def load_preferences(prefs_filename) -> Prefs:
    prefs = DEFAULT_PREFS
    try:
        if os.path.isfile(prefs_filename):
            with open(prefs_filename) as f:
                    json_prefs: Prefs = json.load(f)
                    prefs = merge_json(prefs, json_prefs)
        else:
            logging.info("{} appears to be missing. it will be created after program shutdown".format(prefs_filename))
    except:
        logging.exception("could not load preferences.json from {}".format(prefs_filename))
        if os.path.isfile(prefs_filename):
            # make a backup of the old preferences file so we don't loose it
            backup_filename = os.path.join(os.path.dirname(prefs_filename), datetime.now().strftime("%m-%d-%Y_%H-%M-%S_{}".format(os.path.basename(prefs_filename))))
            shutil.copyfile(prefs_filename, backup_filename)
    return prefs


def save_preferences(prefs_filename, prefs):
    try:
        os.makedirs(os.path.dirname(prefs_filename), exist_ok=True)
        with open(prefs_filename, "w") as f:
            json.dump(prefs, f)
    except OSError as err:
        logging.exception("error serializing preferences")
