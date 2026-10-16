from fastapi import FastAPI, HTTPException

app = FastAPI(title="SentinelOS disposable demo")


@app.get("/profile/{user_id}")
def get_profile(user_id: str, email: str | None = None) -> dict[str, str]:
    return {"user_id": user_id, "email": email.lower()}
