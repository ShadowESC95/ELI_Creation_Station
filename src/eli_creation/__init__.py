"""ELI Creation Station: ELI's local studio for socials, images, video, games, editing and code.

It is an official ELI bundle (product id ``creation``): an application of its own that ELI v3 can
open in place of its window, or that runs on its own with its own licence key. One main model
(the language model) stays loaded while it runs; every specialist model (images, video, music,
3D, upscaling) is loaded in a worker process of its own when a job needs it, and unloaded again.
"""

__version__ = "0.2.1"
PRODUCT = "creation"
TITLE = "ELI Creation Station"
