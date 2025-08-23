import os

import psutil

# Get memory information
process = psutil.Process(os.getpid())
memory_info = process.memory_info()
print(f"Current memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")

# Get system memory information
virtual_memory = psutil.virtual_memory()
print(f"Available system memory: {virtual_memory.available / 1024 / 1024:.2f} MB")
print(f"Total system memory: {virtual_memory.total / 1024 / 1024:.2f} MB")
print(f"Memory usage percentage: {virtual_memory.percent}%")
