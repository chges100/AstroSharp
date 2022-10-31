### AstroSharp

AstroSharp is a small tool that can be used for sharpening and denoising astronomical images. 
It is still in early alpha, meaning the denoising algorithm has not to be considered for productive use right now and there can be bugs and inconsistencies.

AstroSharp makes use of multiscale methods, decomposing the original image into different scales representing fine to coarse details and image structures. A modified median filtering is used to extract the different scales. For more detail regarding this approach we refer to

"Image Processing and Data Analysis - The Multiscale Approach" by J.L. Starck, F. Murtagh and A. Bijaoui.

Credits go to the [GraXpert](https://github.com/Steffenhir/GraXpert)-project, from which the GUI and application structure is taken.


