from fastapi import FastAPI,Query
import time
import random
import math

app=FastAPI(title="recommendation")


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b + 1e-8)

def generate_embedding(size=128):
    return [random.random() for _ in range(size)]

@app.get("/recommend")
def recommend(user_id: int= Query(...,description="user id")):
    user_emb= generate_embedding()
    
    scores=[]
    for _ in range(1000):
        prod_emb=generate_embedding()
        score=cosine_similarity(prod_emb,user_emb)
        scores.append(score)
    scores.sort(reverse=True)
    top_scores=scores[:10]
    
    #adding latency
    time.sleep(random.uniform(0.001,0.025))
    return {
        "user_id": user_id,
        "top_scores": top_scores,
        "latency_ms": round(random.uniform(15, 40), 2)
    }