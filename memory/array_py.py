# Python
import time

start = time.time()
arr = [i * 2 for i in range(25_000_000)]  # ~100MB (4 bytes per int)
sum_val = sum(arr)
print(f"Time: {time.time() - start:.3f}s")