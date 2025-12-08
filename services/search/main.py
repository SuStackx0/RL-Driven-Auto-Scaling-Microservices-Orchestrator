from fastapi import FastAPI,Query
import random
import time

app = FastAPI(title="Search service")

def cpu_heavy_operation(size:int):
    x=0
    for i in range(size* 10000):
        x+= (i%10)*random.randint(1,5)
    return x


@app.get("/search")
def search(query: str = Query(..., min_length=1)):
    # simulate variable work based on query size
    base_work = len(query)


    if random.random() < 0.10:
        base_work *= 4

    start = time.time()
    cpu_heavy_operation(base_work)
    end = time.time()

    return {
        "query": query,
        "latency_ms": round((end - start) * 1000, 2),
        "spike": "yes" if base_work > len(query) else "no"
    }
