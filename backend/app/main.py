from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.finance import router as finance_router


app = FastAPI(title="Paytm Sense Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://paytm-sense-ai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Paytm Sense backend is running"}


app.include_router(finance_router)
