import time
from multiprocessing import Pool

def calculate_pi(start_end):
    start, end = start_end
    return sum((-1)**k / (2*k + 1) for k in range(start, end))

def main():
    start = time.time()
    with Pool(4) as p:
        results = p.map(calculate_pi, [(i*2_500_000, (i+1)*2_500_000) for i in range(4)])
    pi = sum(results) * 4
    print(f"Time: {time.time() - start:.3f}s")

if __name__ == '__main__':
    main()