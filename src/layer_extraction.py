import multiprocessing
multiprocessing.freeze_support()

import logging
from concurrent.futures import wait
# from gpr_cuda import GPRegression
from multiprocessing import shared_memory

import numpy as np
from astropy.stats import sigma_clipped_stats
from pykrige.ok import OrdinaryKriging
from scipy import interpolate, linalg
from skimage.transform import resize

from mp_logging import get_logging_queue, worker_configurer
from parallel_processing import executor

import cv2

def extract_layers(in_imarray):

    shm_imarray = shared_memory.SharedMemory(create=True, size=in_imarray.nbytes)
    shm_layer = shared_memory.SharedMemory(create=True, size=in_imarray.nbytes)

    imarray = np.ndarray(in_imarray.shape, dtype=np.float32, buffer=shm_imarray.buf)
    layer = np.ndarray(in_imarray.shape, dtype=np.float32, buffer=shm_layer.buf)
    np.copyto(imarray, in_imarray)

    num_colors = imarray.shape[2]

    return cv2.GaussianBlur(imarray, (15,15), cv2.BORDER_DEFAULT) 