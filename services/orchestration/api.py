from fastapi import FastAPI

app = FastAPI(title="Culinary AI")

@app.get("/health")
def health_check():
    return {"status": "ok"}
