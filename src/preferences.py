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
    sample_color: int
    lang: AnyStr
    scale1_detail: float
    scale1_denoise_amount: float
    scale1_denoise_thr: float
    scale2_detail: float
    scale2_denoise_amount: float
    scale2_denoise_thr: float
    scale3_detail: float
    scale3_denoise_amount: float
    scale3_denoise_thr: float
    scale4_detail: float
    scale4_denoise_amount: float
    scale4_denoise_thr: float
    scale5_detail: float
    scale5_denoise_amount: float
    scale5_denoise_thr: float
    scale6_detail: float
    scale6_denoise_amount: float
    scale6_denoise_thr: float

DEFAULT_PREFS: Prefs = {
    "working_dir": os.getcwd(),
    "width": None,
    "height": None,
    "stretch_option": "No Stretch",
    "saturation": 1.0,
    "saveas_option": "32 bit Tiff",
    "sample_color": 55,
    "lang": None,
    "scale1_detail": 1.0,
    "scale1_denoise_amount": 0.0,
    "scale1_denoise_thr": 0.05,
    "scale2_detail": 1.0,
    "scale2_denoise_amount": 0.0,
    "scale2_denoise_thr": 0.05,
    "scale3_detail": 1.0,
    "scale3_denoise_amount": 0.0,
    "scale3_denoise_thr": 0.05,
    "scale4_detail": 1.0,
    "scale4_denoise_amount": 0.0,
    "scale4_denoise_thr": 0.05,
    "scale5_detail": 1.0,
    "scale5_denoise_amount": 0.0,
    "scale5_denoise_thr": 0.05,
    "scale6_detail": 1.0,
    "scale6_denoise_amount": 0.0,
    "scale6_denoise_thr": 0.05,
}

def get_default_prefs() -> Prefs:
    return DEFAULT_PREFS


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
    if "sample_color" in json:
        prefs["sample_color"] = json["sample_color"]
    if "lang" in json:
        prefs["lang"] = json["lang"]
    if "scale1_detail" in json:
        prefs["scale1_detail"] = json["scale1_detail"]
    if "scale1_denoise_amount" in json:
        prefs["scale1_denoise_amount"] = json["scale1_denoise_amount"]
    if "scale1_denoise_thr" in json:
        prefs["scale1_denoise_thr"] = json["scale1_denoise_thr"]
    if "scale2_detail" in json:
        prefs["scale2_detail"] = json["scale2_detail"]
    if "scale2_denoise_amount" in json:
        prefs["scale2_denoise_amount"] = json["scale2_denoise_amount"]
    if "scale2_denoise_thr" in json:
        prefs["scale2_denoise_thr"] = json["scale2_denoise_thr"]
    if "scale3_detail" in json:
        prefs["scale3_detail"] = json["scale3_detail"]
    if "scale3_denoise_amount" in json:
        prefs["scale3_denoise_amount"] = json["scale3_denoise_amount"]
    if "scale3_denoise_thr" in json:
        prefs["scale3_denoise_thr"] = json["scale3_denoise_thr"]
    if "scale4_detail" in json:
        prefs["scale4_detail"] = json["scale4_detail"]
    if "scale4_denoise_amount" in json:
        prefs["scale4_denoise_amount"] = json["scale4_denoise_amount"]
    if "scale4_denoise_thr" in json:
        prefs["scale4_denoise_thr"] = json["scale4_denoise_thr"]
    if "scale5_detail" in json:
        prefs["scale5_detail"] = json["scale5_detail"]
    if "scale5_denoise_amount" in json:
        prefs["scale5_denoise_amount"] = json["scale5_denoise_amount"]
    if "scale5_denoise_thr" in json:
        prefs["scale5_denoise_thr"] = json["scale5_denoise_thr"]
    if "scale6_detail" in json:
        prefs["scale6_detail"] = json["scale6_detail"]
    if "scale6_denoise_amount" in json:
        prefs["scale6_denoise_amount"] = json["scale6_denoise_amount"]
    if "scale6_denoise_thr" in json:
        prefs["scale6_denoise_thr"] = json["scale6_denoise_thr"]
    return prefs


def load_preferences(prefs_filename) -> Prefs:
    prefs = DEFAULT_PREFS.copy()
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
