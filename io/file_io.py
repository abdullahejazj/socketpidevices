# Python
import os, time

os.makedirs('py_files', exist_ok=True)
start = time.time()

# Write 1,000 files
for i in range(1000):
    with open(f'py_files/file_{i}.txt', 'w') as f:
        f.write('A' * 1048576)  # 1MB

# Read 1,000 files
for i in range(1000):
    with open(f'py_files/file_{i}.txt', 'r') as f:
        f.read()

print(f"Time: {time.time() - start:.3f}s")