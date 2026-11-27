"""Models: what is known (catalogue), what may be fetched (licences), and what is loaded (manager).

One main model stays loaded while Creation Station runs. Every specialist model is loaded in a
worker process of its own when a job needs it and unloaded when it has been idle, so a machine
holds only what the work in front of it needs.
"""
