# Python
import time

def fib(n):
    return fib(n-1) + fib(n-2) if n > 1 else n

start = time.time()
fib(40)
print(f"Time: {time.time() - start:.3f}s")