import logging
import multiprocessing
multiprocessing.freeze_support()
from multiprocessing import shared_memory


from concurrent.futures import wait
from parallel_processing import executor

from mp_logging import get_logging_queue, worker_configurer


import numpy as np
import scipy as sp
import astroimage

class MultiScaleImage:

    def __init__(self, num_scales):
        self.img_scales = None
        self.img_residual = None
        self.num_scales = num_scales
        self.detail_boost = np.ones(num_scales)

    def set_scales(self, img_scales):
        self.img_scales = img_scales

    def set_residual(self, img_residual):
        self.img_residual = img_residual

    def set_detail_boost(self, detail_boost):
        self.detail_boost = detail_boost

    @staticmethod
    def decompose_image(img_orig, num_scales):
        shm_img_scales = shared_memory.SharedMemory(create=True, size=img_orig.nbytes*num_scales)
        # First image should be original, last image the residual
        shm_img_filtered = shared_memory.SharedMemory(create=True, size=img_orig.nbytes*(num_scales+1))

        img_scales_array = np.ndarray(np.concatenate([[num_scales], img_orig.shape]), dtype=np.float32, buffer=shm_img_scales.buf)
        img_filtered_array = np.ndarray(np.concatenate([[num_scales+1], img_orig.shape]), dtype=np.float32, buffer=shm_img_filtered.buf)

        np.copyto(img_filtered_array[0,:,:,:], img_orig)

        num_colors = img_filtered_array.shape[3]

        futures_median_filtering = []
        logging_queue = get_logging_queue()

        for color_channel in range(num_colors):
            for layer in range(num_scales):
                futures_median_filtering.insert(color_channel*num_scales + layer, executor.submit(MultiScaleImage.apply_median_filters, shm_img_filtered.name, np.float32, img_orig.shape, color_channel, layer, num_scales, logging_queue, worker_configurer))

        wait(futures_median_filtering)

        futures_layer_extraction = []

        for color_channel in range(num_colors):
            futures_layer_extraction.insert(color_channel, executor.submit(MultiScaleImage.extract_layers, shm_img_filtered.name, shm_img_scales.name, np.float32, img_orig.shape, color_channel, num_scales, logging_queue, worker_configurer))

        wait(futures_layer_extraction)

        img_scales = np.copy(img_scales_array)
        img_residual = np.copy(img_filtered_array[num_scales,:,:,:])

        shm_img_filtered.close()
        shm_img_scales.close()
        shm_img_filtered.unlink()
        shm_img_scales.unlink()

        multiscale_image = MultiScaleImage(num_scales)
        multiscale_image.set_scales(img_scales)
        multiscale_image.set_residual(img_residual)

        return multiscale_image

    def recompose_image(self):
        logging.info("Recompose image")
        img_processed = np.copy(self.img_residual)

        for i in range(self.num_scales):
            logging.info("Add layer {}".format(i))
            img_processed = img_processed + self.img_scales[i,:,:,:]

        return img_processed

    @staticmethod
    def extract_layers(shm_img_filtered_name, shm_img_scales_name, dtype, shape, color_channel, num_scales, logging_queue, logging_configurer):

        logging_configurer(logging_queue)
        logging.info("layer extraction started for color channel {}".format(color_channel))

        try:
            ex_shm_img_filtered = shared_memory.SharedMemory(name=shm_img_filtered_name)
            ex_shm_img_scales = shared_memory.SharedMemory(name=shm_img_scales_name)

            img_filtered_array = np.ndarray(np.concatenate([[num_scales+1], shape]), dtype, buffer=ex_shm_img_filtered.buf)
            img_scales_array = np.ndarray(np.concatenate([[num_scales], shape]), dtype=np.float32, buffer=ex_shm_img_scales.buf)

            img_filtered_array = img_filtered_array[:,:,:,color_channel]
            img_scales_array = img_scales_array[:,:,:,color_channel]

            for i in range(num_scales):
                img_scales_array[i,:,:] = img_filtered_array[i,:,:] - img_filtered_array[i+1,:,:]
        except:
            logging.exception("Error during image decomposition")

        ex_shm_img_filtered.close()
        ex_shm_img_scales.close()

        logging.info("layer extraction finished for color channel {}".format(color_channel))

    def apply_median_filters(shm_img_filtered_name, dtype, shape, color_channel, selected_scale, num_scales, logging_queue, logging_configurer):

        logging_configurer(logging_queue)
        logging.info("median filtering of level {} started for color channel {} started".format(selected_scale, color_channel))

        try:
            ex_shm_img_filtered = shared_memory.SharedMemory(name=shm_img_filtered_name)

            img_filtered_array = np.ndarray(np.concatenate([[num_scales+1], shape]), dtype, buffer=ex_shm_img_filtered.buf)
            img_filtered_array = img_filtered_array[:,:,:,color_channel]

            img_filtered_array[selected_scale+1,:,:] = sp.signal.medfilt2d(img_filtered_array[0,:,:], 2**(selected_scale + 1) + 1)


        except:
            logging.exception("Error during median filtering")

        ex_shm_img_filtered.close()
        logging.info("median filtering of level {} started for color channel {} finished".format(selected_scale, color_channel))
        


    

    
