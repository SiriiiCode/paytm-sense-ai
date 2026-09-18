from fastapi import FastAPI

from .routes.finance import router as finance_router


app = FastAPI()


@app.get("/")
def root():
    return {"message": "Paytm Sense backend is running"}


app.include_router(finance_router)