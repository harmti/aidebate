from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import logging
import time
import os

from app.debate_engine import run_debate, LLM_OPTIONS

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/aidebate.log")],
)
logger = logging.getLogger("aidebate")

app = FastAPI(title="AI Debate")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with the debate form."""
    logger.info(f"Home page accessed from {request.client.host}")
    return templates.TemplateResponse("index.html", {"request": request, "llm_options": LLM_OPTIONS})


@app.post("/debate", response_class=HTMLResponse)
async def create_debate(
    request: Request,
    topic: str = Form(...),
    pro_llm: str = Form("ChatGPT"),
    con_llm: str = Form("Claude"),
    judge_llm: str = Form("Gemini"),
    rounds: int = Form(2),
):
    """Run a debate and display the results."""
    # Log the debate request
    logger.info(
        f"Debate requested - Topic: '{topic}', Pro: {pro_llm}, Con: {con_llm}, Judge: {judge_llm}, Rounds: {rounds}"
    )
    start_time = time.time()

    # Validate inputs
    if not topic:
        logger.warning("Empty topic submitted")
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    if rounds < 1 or rounds > 5:
        logger.warning(f"Invalid number of rounds: {rounds}")
        raise HTTPException(status_code=400, detail="Rounds must be between 1 and 5")

    try:
        # Run the debate
        debate_results = run_debate(topic, pro_llm, con_llm, judge_llm, rounds)

        # Log completion time
        elapsed_time = time.time() - start_time
        logger.info(f"Debate completed in {elapsed_time:.2f} seconds")

        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "topic": topic,
                "pro_llm": pro_llm,
                "con_llm": con_llm,
                "judge_llm": judge_llm,
                "rounds": rounds,
                "results": debate_results,
            },
        )
    except ValueError as e:
        logger.error(f"Error running debate: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
