"""Worker processes: where specialist models run.

A specialist model is never loaded into Creation Station's own process. It is loaded in a worker
process of its own, spoken to over its standard input and output (one JSON message per line), and
unloaded by ending that process. Ending the process is the one way of giving all of a model's
memory back that works the same with every vendor's driver: a CUDA, ROCm, Metal or DirectML
context goes with its process, where unloading inside a long-lived process leaves caches and
fragments behind. A model that crashes or runs out of memory takes its worker with it, never the
window.

Each engine family can run in an environment of its own (``runtimes/<name>`` in the data
folder: PyTorch for diffusers, stable-diffusion.cpp, ONNX Runtime), built for the accelerator this
machine has, so the application itself ships no PyTorch and each family pins its own libraries.
"""
