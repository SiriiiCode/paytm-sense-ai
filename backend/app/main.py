from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Paytm Sense backend is running"}