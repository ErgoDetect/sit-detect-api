import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, workers=2, log_level="info", reload=True
    )
