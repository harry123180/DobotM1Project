import multiprocessing as mp
import time
import math
import os

def stress_worker(duration_sec):
    start = time.time()
    x = 0.0001
    while time.time() - start < duration_sec:
        for i in range(10000):
            x += math.sqrt(x * i % 1000)
    return os.getpid()

if __name__ == "__main__":
    duration = 60  # 測試時間（秒）
    cpu_count = mp.cpu_count()  # 使用可用核心
    print(f"Spawning {cpu_count} workers for {duration} seconds")

    with mp.Pool(processes=cpu_count) as pool:
        pool.map(stress_worker, [duration] * cpu_count)
