from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
import time
import os
import json
import asyncio
from datetime import datetime
import uuid
import sys
import secrets

from app.debate_engine import get_llm_function, LLM_OPTIONS

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/aidebate.log")],
)
logger = logging.getLogger("aidebate")

# Store for debate progress
debate_progress = {}

# Initialize security
security = HTTPBasic()

# Get credentials from environment variables or use defaults
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "debate123")

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate credentials and return username if valid."""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app = FastAPI(title="AI Debate")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Serve favicon.ico
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, username: str = Depends(get_current_username)):
    """Render the home page with the debate form."""
    logger.info(f"Home page accessed by {username} from {request.client.host}")
    return templates.TemplateResponse("index.html", {"request": request, "llm_options": LLM_OPTIONS})


@app.post("/debate", response_class=HTMLResponse)
async def create_debate(
    request: Request,
    background_tasks: BackgroundTasks,
    topic: str = Form(...),
    pro_llm: str = Form("ChatGPT"),
    con_llm: str = Form("Claude"),
    judge_llm: str = Form("Gemini"),
    rounds: int = Form(2),
    username: str = Depends(get_current_username),
):
    """Start a debate in the background and redirect to results page."""
    # Log the debate request
    logger.info(
        f"Debate requested by {username} - Topic: '{topic}', Pro: {pro_llm}, Con: {con_llm}, Judge: {judge_llm}, Rounds: {rounds}"
    )

    # Validate inputs
    if not topic:
        logger.warning("Empty topic submitted")
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    if rounds < 1 or rounds > 5:
        logger.warning(f"Invalid number of rounds: {rounds}")
        raise HTTPException(status_code=400, detail="Rounds must be between 1 and 5")

    # Generate a unique ID for this debate
    debate_id = str(uuid.uuid4())

    # Initialize progress tracking
    debate_progress[debate_id] = {
        "status": "starting",
        "message": "Initializing debate...",
        "progress": 0,
        "started_at": datetime.now().isoformat(),
        "topic": topic,
        "pro_llm": pro_llm,
        "con_llm": con_llm,
        "judge_llm": judge_llm,
        "rounds": rounds,
        "results": None,
        "completed": False,
        "error": None,
    }

    # Start the debate in the background
    background_tasks.add_task(run_debate_background, debate_id, topic, pro_llm, con_llm, judge_llm, rounds)

    # Redirect to the results page, which will show progress and then results
    return templates.TemplateResponse(
        "progress.html",
        {
            "request": request,
            "debate_id": debate_id,
            "topic": topic,
            "pro_llm": pro_llm,
            "con_llm": con_llm,
            "judge_llm": judge_llm,
            "rounds": rounds,
        },
    )


@app.get("/debate/{debate_id}/progress")
async def get_debate_progress(debate_id: str, username: str = Depends(get_current_username)):
    """Stream debate progress as server-sent events."""
    if debate_id not in debate_progress:
        raise HTTPException(status_code=404, detail="Debate not found")

    logger.info(f"Progress stream requested by {username} for debate {debate_id}")

    async def event_generator():
        # Send initial state immediately
        initial_data = json.dumps(debate_progress[debate_id])
        logger.info(f"Sending initial state: {initial_data}")
        yield f"data: {initial_data}\n\n"

        # Keep track of last sent data to avoid sending duplicates
        last_data = debate_progress[debate_id].copy()
        last_heartbeat = time.time()

        # Continue sending updates until debate is completed or errored
        while True:
            current_time = time.time()

            # If debate is completed or errored, send final update and stop
            if debate_progress[debate_id]["completed"] or debate_progress[debate_id].get("error"):
                # Only send if there's been a change
                if debate_progress[debate_id] != last_data:
                    final_data = json.dumps(debate_progress[debate_id])
                    logger.info(f"Sending final update: {debate_progress[debate_id]['status']}")
                    yield f"data: {final_data}\n\n"
                break

            # Check if there's been a change
            if debate_progress[debate_id] != last_data:
                update_data = json.dumps(debate_progress[debate_id])
                last_data = debate_progress[debate_id].copy()
                last_heartbeat = current_time
                logger.info(
                    f"Sending progress update: {debate_progress[debate_id]['status']} - {debate_progress[debate_id]['progress']}%"
                )
                yield f"data: {update_data}\n\n"
            # Send heartbeat every 15 seconds to keep connection alive
            elif current_time - last_heartbeat > 15:
                logger.debug("Sending heartbeat")
                yield ": heartbeat\n\n"
                last_heartbeat = current_time

            # Wait before checking again
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/debate/{debate_id}/results", response_class=HTMLResponse)
async def get_debate_results(request: Request, debate_id: str, username: str = Depends(get_current_username)):
    """Get the results of a completed debate."""
    if debate_id not in debate_progress:
        raise HTTPException(status_code=404, detail="Debate not found")

    logger.info(f"Results requested by {username} for debate {debate_id}")
    
    debate_data = debate_progress[debate_id]

    if not debate_data["completed"]:
        # If debate is not completed, redirect to progress page
        return templates.TemplateResponse(
            "progress.html",
            {
                "request": request,
                "debate_id": debate_id,
                "topic": debate_data["topic"],
                "pro_llm": debate_data["pro_llm"],
                "con_llm": debate_data["con_llm"],
                "judge_llm": debate_data["judge_llm"],
                "rounds": debate_data["rounds"],
            },
        )

    if debate_data["error"]:
        # If there was an error, show error page
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error_message": debate_data["error"], "topic": debate_data["topic"]},
        )

    # Show results
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "topic": debate_data["topic"],
            "pro_llm": debate_data["pro_llm"],
            "con_llm": debate_data["con_llm"],
            "judge_llm": debate_data["judge_llm"],
            "rounds": debate_data["rounds"],
            "results": debate_data["results"],
        },
    )


async def run_debate_background(
    debate_id: str, topic: str, pro_llm: str, con_llm: str, judge_llm: str, rounds: int
):
    """Run the debate in the background and update progress."""
    start_time = time.time()

    try:
        # Define the step sequence to ensure correct order
        step_sequence = ["starting", "pro_initial", "con_initial"]

        # Add round steps
        for r in range(2, rounds + 1):
            step_sequence.extend([f"pro_round_{r}", f"con_round_{r}"])

        step_sequence.extend(["judging", "completed"])

        logger.info(f"Debate {debate_id} step sequence: {step_sequence}")

        # Track current step index
        current_step_index = 0

        # Update status to processing
        debate_progress[debate_id]["status"] = step_sequence[current_step_index]  # 'starting'
        debate_progress[debate_id]["message"] = "Initializing debate..."
        debate_progress[debate_id]["progress"] = 5

        # Add a small delay to ensure the initial progress update is sent
        await asyncio.sleep(1)
        current_step_index += 1

        # Calculate total steps (initial arguments + rounds + summary)
        total_steps = 2 + (rounds * 2) + 1
        current_step = 0

        # Custom progress callback
        async def update_progress(stage: str, message: str):
            nonlocal current_step, current_step_index

            # Ensure we're following the step sequence
            expected_stage = step_sequence[current_step_index]
            if stage != expected_stage:
                logger.warning(f"Step out of sequence: got {stage}, expected {expected_stage}")
                # Use the expected stage instead
                stage = expected_stage

            current_step += 1
            current_step_index += 1

            # Calculate progress percentage - leave room for completion
            progress_percent = min(95, int((current_step / total_steps) * 100))

            logger.info(f"Debate {debate_id} progress: {progress_percent}% - {message} (step: {stage})")

            # Update progress data atomically
            debate_progress[debate_id] = {
                **debate_progress[debate_id],
                "status": stage,
                "message": message,
                "progress": progress_percent,
            }

            # Add a small delay to ensure the update is processed
            await asyncio.sleep(0.5)

        # Run the debate with progress updates
        logger.info(f"Starting debate {debate_id} with topic: '{topic}'")

        # Get the LLM functions
        pro_model = get_llm_function(pro_llm)
        con_model = get_llm_function(con_llm)
        judge_model = get_llm_function(judge_llm)

        if not pro_model or not con_model or not judge_model:
            logger.error(f"Invalid LLM selection: Pro={pro_llm}, Con={con_llm}, Judge={judge_llm}")
            raise ValueError("Invalid LLM selection. Please use 'ChatGPT', 'Claude', or 'Gemini'.")

        # Initialize results
        results = {"rounds": [], "summary": ""}

        # Initial arguments - Pro side
        await update_progress("pro_initial", f"Getting initial argument from {pro_llm}...")
        logger.info(f"Getting initial pro argument from {pro_llm}")
        try:
            pro_argument = pro_model(f"Argue in favor of: {topic}")
            logger.info(f"Received initial pro argument ({len(pro_argument)} chars)")
        except Exception as e:
            logger.error(f"Error getting pro argument: {str(e)}")
            raise ValueError(f"Error getting response from {pro_llm}: {str(e)}")

        # Initial arguments - Con side
        await update_progress("con_initial", f"Getting initial argument from {con_llm}...")
        logger.info(f"Getting initial con argument from {con_llm}")
        try:
            con_argument = con_model(f"Argue against: {topic}")
            logger.info(f"Received initial con argument ({len(con_argument)} chars)")
        except Exception as e:
            logger.error(f"Error getting con argument: {str(e)}")
            raise ValueError(f"Error getting response from {con_llm}: {str(e)}")

        for round_num in range(1, rounds + 1):
            logger.info(f"Starting round {round_num} of {rounds}")

            # Store the current round's arguments
            results["rounds"].append(
                {"round_number": round_num, "pro_argument": pro_argument, "con_argument": con_argument}
            )

            # Generate counter-arguments for the next round
            if round_num < rounds:
                # Pro counter-argument
                await update_progress(
                    f"pro_round_{round_num + 1}", f"Round {round_num + 1}: Getting response from {pro_llm}..."
                )

                logger.info(f"Getting pro counter-argument for round {round_num + 1}")
                try:
                    pro_counter_prompt = f"Your opponent argued: {con_argument}\n\nCounter their argument while supporting: {topic}."
                    pro_argument = pro_model(pro_counter_prompt)
                    logger.info(
                        f"Received pro counter-argument for round {round_num + 1} ({len(pro_argument)} chars)"
                    )
                except Exception as e:
                    logger.error(f"Error getting pro counter-argument: {str(e)}")
                    raise ValueError(f"Error getting response from {pro_llm}: {str(e)}")

                # Con counter-argument
                await update_progress(
                    f"con_round_{round_num + 1}", f"Round {round_num + 1}: Getting response from {con_llm}..."
                )

                logger.info(f"Getting con counter-argument for round {round_num + 1}")
                try:
                    con_counter_prompt = f"Your opponent argued: {pro_argument}\n\nCounter their argument while opposing: {topic}."
                    con_argument = con_model(con_counter_prompt)
                    logger.info(
                        f"Received con counter-argument for round {round_num + 1} ({len(con_argument)} chars)"
                    )
                except Exception as e:
                    logger.error(f"Error getting con counter-argument: {str(e)}")
                    raise ValueError(f"Error getting response from {con_llm}: {str(e)}")

        # Judge LLM summarizes the debate
        await update_progress("judging", f"Getting final summary from {judge_llm}...")

        logger.info(f"Getting debate summary from {judge_llm}")
        try:
            judge_prompt = f"Summarize the key points of the debate on '{topic}', highlighting the strongest arguments for and against. Provide a balanced conclusion."
            summary = judge_model(judge_prompt)
            logger.info(f"Received judge summary ({len(summary)} chars)")
            results["summary"] = summary
        except Exception as e:
            logger.error(f"Error getting judge summary: {str(e)}")
            raise ValueError(f"Error getting response from {judge_llm}: {str(e)}")

        await update_progress("completed", "Debate completed successfully!")

        # Final update - mark as completed
        debate_progress[debate_id] = {
            **debate_progress[debate_id],
            "status": "completed",
            "message": f"Debate completed in {time.time() - start_time:.2f} seconds",
            "progress": 100,
            "results": results,
            "completed": True,
        }

        logger.info(f"Debate {debate_id} completed in {time.time() - start_time:.2f} seconds")

    except Exception as e:
        # Update with error status
        logger.error(f"Error in debate {debate_id}: {str(e)}", exc_info=True)

        # Error update
        debate_progress[debate_id] = {
            **debate_progress[debate_id],
            "status": "error",
            "message": f"Error: {str(e)}",
            "error": str(e),
            "completed": True,
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
