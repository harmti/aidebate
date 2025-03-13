import asyncio
import base64
import json
import logging
import os
import platform
import secrets
import sys
import time
import uuid
from datetime import datetime

import psutil
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.debate_engine import LLM_OPTIONS, get_llm_function

# Ensure logs directory exists with proper permissions
try:
    os.makedirs("logs", exist_ok=True)
    # Try to create a test file to verify write permissions
    test_file_path = os.path.join("logs", "test_permissions.txt")
    with open(test_file_path, "w") as f:
        f.write("Testing write permissions")
    os.remove(test_file_path)
except PermissionError:
    print("WARNING: Permission denied when trying to write to logs directory.")
    print("Redirecting logs to stdout only.")
    # Configure logging to stdout only
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
else:
    # Configure logging to both stdout and file
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("logs/aidebate.log")],
    )

logger = logging.getLogger("aidebate")

# Store for debate progress
debate_progress = {}

# Get credentials from environment variables or use defaults
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "debate123")


# Custom authentication middleware
class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Paths that don't require authentication
        excluded_paths = ["/favicon.ico", "/static", "/health"]

        # Check if the path is excluded from authentication
        for path in excluded_paths:
            if request.url.path.startswith(path):
                return await call_next(request)

        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # No auth header, return 401
            return self._unauthorized_response()

        # Parse the Authorization header
        try:
            scheme, credentials = auth_header.split()
            if scheme.lower() != "basic":
                return self._unauthorized_response()

            decoded = base64.b64decode(credentials).decode("utf-8")
            username, password = decoded.split(":")

            # Validate credentials
            if not (
                secrets.compare_digest(username, ADMIN_USERNAME) and secrets.compare_digest(password, ADMIN_PASSWORD)
            ):
                return self._unauthorized_response()

            # Add username to request state for logging
            request.state.username = username

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return self._unauthorized_response()

        # If we get here, authentication was successful
        return await call_next(request)

    def _unauthorized_response(self):
        from starlette.responses import Response

        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
            content="Unauthorized",
        )


# HTTPS URL rewriting middleware
class HTTPSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Store original base URL
        request.state.base_url = str(request.base_url)

        # Check if we're running on Railway with HTTPS
        is_railway = "RAILWAY_PUBLIC_DOMAIN" in os.environ
        is_https = request.headers.get("x-forwarded-proto") == "https"

        # Log the protocol information
        logger.info(
            f"""Request protocol: {request.url.scheme},
            X-Forwarded-Proto: {request.headers.get("x-forwarded-proto", "not set")}"""
        )

        # Process the request
        response = await call_next(request)

        # If we're on Railway and using HTTPS, ensure all URLs are HTTPS
        if is_railway and is_https:
            # Add security headers
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"

        return response


app = FastAPI(title="AI Debate")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add HTTPS middleware (must be before authentication middleware)
app.add_middleware(HTTPSMiddleware)

# Add authentication middleware
app.add_middleware(BasicAuthMiddleware)

# Mount static files with custom URL generation
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up Jinja2 templates with custom URL generation
templates = Jinja2Templates(directory="app/templates")

# Override the url_for method to ensure HTTPS URLs in Railway environment
original_url_for = templates.env.globals["url_for"]


def secure_url_for(name, **path_params):
    url = original_url_for(name, **path_params)
    if url.startswith("http:") and "RAILWAY_PUBLIC_DOMAIN" in os.environ:
        url = url.replace("http:", "https:", 1)
    return url


templates.env.globals["url_for"] = secure_url_for


# Serve favicon.ico - excluded from authentication by middleware
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon without authentication."""
    logger.debug("Serving favicon.ico")
    return FileResponse("app/static/favicon.ico")


# Health check endpoint for Railway - excluded from authentication by middleware
@app.get("/health", include_in_schema=False)
async def health_check():
    """Health check endpoint for Railway."""
    logger.debug("Health check requested")
    return JSONResponse(content={"status": "healthy"}, status_code=200)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with the debate form."""
    username = getattr(request.state, "username", "unknown")
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
):
    """Start a debate in the background and redirect to results page."""
    username = getattr(request.state, "username", "unknown")

    # Log the debate request
    logger.info(
        f"Debate requested by {username} - Topic: '{topic}', "
        f"Pro: {pro_llm}, Con: {con_llm}, Judge: {judge_llm}, Rounds: {rounds}"
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
async def get_debate_progress(debate_id: str, request: Request):
    """Stream debate progress as server-sent events."""
    try:
        if debate_id not in debate_progress:
            logger.error(f"Debate {debate_id} not found in progress dictionary")
            return JSONResponse(status_code=404, content={"error": "Debate not found", "debate_id": debate_id})

        username = getattr(request.state, "username", "unknown")
        client_host = request.client.host if request.client else "unknown"
        headers = dict(request.headers)

        logger.info(f"Progress stream requested by {username} from {client_host} for debate {debate_id}")
        logger.info(f"Request headers: {headers}")
        logger.info(f"Available debates: {list(debate_progress.keys())}")

        async def event_generator():
            try:
                # Send initial state immediately
                initial_data = json.dumps(debate_progress[debate_id])
                logger.info(f"Sending initial state for debate {debate_id}: {initial_data}")
                yield f"data: {initial_data}\n\n"

                # Keep track of last sent data to avoid sending duplicates
                last_data = debate_progress[debate_id].copy()
                last_heartbeat = time.time()
                connection_start = time.time()

                # Continue sending updates until debate is completed or errored
                while True:
                    current_time = time.time()
                    connection_duration = current_time - connection_start

                    # Log connection duration every 15 seconds
                    if int(connection_duration) % 15 == 0 and int(connection_duration) > 0:
                        logger.info(
                            f"SSE connection for debate {debate_id} active for {int(connection_duration)} seconds"
                        )

                    # If debate is completed or errored, send final update and stop
                    if debate_progress[debate_id]["completed"] or debate_progress[debate_id].get("error"):
                        # Only send if there's been a change
                        if debate_progress[debate_id] != last_data:
                            final_data = json.dumps(debate_progress[debate_id])
                            logger.info(
                                f"Sending final update for debate {debate_id}: {debate_progress[debate_id]['status']}"
                            )
                            yield f"data: {final_data}\n\n"
                        logger.info(
                            f"SSE connection for debate {debate_id} closing after {int(connection_duration)} seconds"
                        )
                        break

                    # Check if there's been a change
                    if debate_progress[debate_id] != last_data:
                        update_data = json.dumps(debate_progress[debate_id])
                        last_data = debate_progress[debate_id].copy()
                        last_heartbeat = current_time
                        logger.info(
                            f"Sending progress update for debate {debate_id}: "
                            f"{debate_progress[debate_id]['status']} - {debate_progress[debate_id]['progress']}%"
                        )
                        yield f"data: {update_data}\n\n"
                    # Send heartbeat every 5 seconds to keep connection alive (reduced from 15)
                    elif current_time - last_heartbeat > 5:
                        logger.info(
                            f"Sending heartbeat for debate {debate_id} after "
                            f"{int(current_time - last_heartbeat)} seconds"
                        )
                        yield ": heartbeat\n\n"
                        last_heartbeat = current_time

                    # Wait before checking again (reduced from 0.5)
                    await asyncio.sleep(0.2)
            except Exception as e:
                logger.exception(f"Error in SSE event generator for debate {debate_id}: {str(e)}")
                error_data = json.dumps({"error": f"Server error: {str(e)}", "debate_id": debate_id})
                yield f"data: {error_data}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Transfer-Encoding": "chunked",
            },
        )
    except Exception as e:
        logger.exception(f"Error setting up SSE for debate {debate_id}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}", "debate_id": debate_id})


@app.get("/debate/{debate_id}/progress/json")
async def get_debate_progress_json(debate_id: str, request: Request):
    """Get debate progress as JSON (non-streaming fallback)."""
    try:
        if debate_id not in debate_progress:
            logger.error(f"Debate {debate_id} not found in progress dictionary for JSON request")
            return JSONResponse(status_code=404, content={"error": "Debate not found", "debate_id": debate_id})

        username = getattr(request.state, "username", "unknown")
        client_host = request.client.host if request.client else "unknown"
        headers = dict(request.headers)

        # Log more detailed information
        logger.info(f"JSON progress requested by {username} from {client_host} for debate {debate_id}")
        logger.info(f"JSON request headers: {headers}")
        logger.info(f"Available debates: {list(debate_progress.keys())}")
        logger.info(f"Returning progress data: {debate_progress[debate_id]}")

        # Add CORS headers for Railway
        response = JSONResponse(content=debate_progress[debate_id])
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Cache-Control"] = "no-cache"

        return response
    except Exception as e:
        logger.exception(f"Error in get_debate_progress_json: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}", "debate_id": debate_id})


@app.get("/debug/connection")
async def debug_connection(request: Request):
    """Debug endpoint to check connection details."""
    try:
        headers = dict(request.headers)
        client_host = request.client.host if request.client else "unknown"

        # Log the connection details
        logger.info(f"Debug connection from {client_host}")
        logger.info(f"Headers: {headers}")

        # Get active debates
        active_debates = list(debate_progress.keys())

        # Return connection details
        response_data = {
            "client_ip": client_host,
            "headers": headers,
            "server_time": datetime.now().isoformat(),
            "railway_env": os.environ.get("RAILWAY_ENVIRONMENT", "not_set"),
            "railway_service": os.environ.get("RAILWAY_SERVICE_NAME", "not_set"),
            "railway_project": os.environ.get("RAILWAY_PROJECT_NAME", "not_set"),
            "railway_domain": os.environ.get("RAILWAY_PUBLIC_DOMAIN", "not_set"),
            "active_debates": active_debates,
            "app_version": "1.1.0",  # Add version for tracking
        }

        # Add CORS headers
        response = JSONResponse(content=response_data)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

        return response
    except Exception as e:
        logger.exception(f"Error in debug_connection: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


@app.get("/debate/{debate_id}/results", response_class=HTMLResponse)
async def get_debate_results(request: Request, debate_id: str):
    """Get the results of a completed debate."""
    if debate_id not in debate_progress:
        raise HTTPException(status_code=404, detail="Debate not found")

    username = getattr(request.state, "username", "unknown")
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


@app.get("/railway/debug", include_in_schema=False)
async def railway_debug(request: Request):
    """Special debug endpoint for Railway deployments."""
    try:
        # Get basic request info
        client_host = request.client.host if request.client else "unknown"
        headers = dict(request.headers)

        # Get Railway environment variables
        railway_vars = {k: v for k, v in os.environ.items() if k.startswith("RAILWAY_")}

        # Get active debates
        active_debates = list(debate_progress.keys())
        debate_details = {}

        # Get details for each active debate
        for debate_id in active_debates:
            debate_details[debate_id] = {
                "status": debate_progress[debate_id]["status"],
                "progress": debate_progress[debate_id]["progress"],
                "completed": debate_progress[debate_id]["completed"],
                "error": debate_progress[debate_id].get("error", None),
            }

        # Collect system info
        system_info = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "memory": psutil.virtual_memory()._asdict() if "psutil" in sys.modules else "psutil not available",
            "cpu_count": os.cpu_count(),
            "process_id": os.getpid(),
            "working_directory": os.getcwd(),
        }

        # Log the request
        logger.info(f"Railway debug request from {client_host}")

        # Return comprehensive debug info
        response_data = {
            "timestamp": datetime.now().isoformat(),
            "client_ip": client_host,
            "headers": headers,
            "railway_environment": railway_vars,
            "active_debates": active_debates,
            "debate_details": debate_details,
            "system_info": system_info,
            "app_version": "1.1.0",
        }

        # Add CORS headers
        response = JSONResponse(content=response_data)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

        return response
    except Exception as e:
        logger.exception(f"Error in railway_debug: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Server error: {str(e)}"})


@app.get("/debug/https", response_class=HTMLResponse)
async def https_debug(request: Request):
    """Debug page for HTTPS and mixed content issues."""
    client_host = request.client.host if request.client else "unknown"
    headers = dict(request.headers)

    # Log the request
    logger.info(f"HTTPS debug page requested from {client_host}")
    logger.info(f"Headers: {headers}")

    # Get active debates
    active_debates = list(debate_progress.keys())

    # Return the debug page
    return templates.TemplateResponse(
        "https_debug.html",
        {
            "request": request,
            "client_ip": client_host,
            "protocol": request.url.scheme,
            "x_forwarded_proto": headers.get("x-forwarded-proto", "not set"),
            "host": headers.get("host", "not set"),
            "railway_env": os.environ.get("RAILWAY_ENVIRONMENT", "not set"),
            "railway_domain": os.environ.get("RAILWAY_PUBLIC_DOMAIN", "not set"),
            "active_debates": active_debates,
        },
    )


async def run_debate_background(debate_id: str, topic: str, pro_llm: str, con_llm: str, judge_llm: str, rounds: int):
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
                    pro_counter_prompt = (
                        f"Your opponent argued: {con_argument}\n\nCounter their argument while supporting: {topic}."
                    )
                    pro_argument = pro_model(pro_counter_prompt)
                    logger.info(f"Received pro counter-argument for round {round_num + 1} ({len(pro_argument)} chars)")
                except Exception as e:
                    logger.error(f"Error getting pro counter-argument: {str(e)}")
                    raise ValueError(f"Error getting response from {pro_llm}: {str(e)}")

                # Con counter-argument
                await update_progress(
                    f"con_round_{round_num + 1}", f"Round {round_num + 1}: Getting response from {con_llm}..."
                )

                logger.info(f"Getting con counter-argument for round {round_num + 1}")
                try:
                    con_counter_prompt = (
                        f"Your opponent argued: {pro_argument}\n\nCounter their argument while opposing: {topic}."
                    )
                    con_argument = con_model(con_counter_prompt)
                    logger.info(f"Received con counter-argument for round {round_num + 1} ({len(con_argument)} chars)")
                except Exception as e:
                    logger.error(f"Error getting con counter-argument: {str(e)}")
                    raise ValueError(f"Error getting response from {con_llm}: {str(e)}")

        # Judge LLM summarizes the debate
        await update_progress("judging", f"Getting final summary from {judge_llm}...")

        logger.info(f"Getting debate summary from {judge_llm}")
        try:
            judge_prompt = (
                f"Summarize the key points of the debate on '{topic}', "
                "highlighting the strongest arguments for and against. "
                "Provide a balanced conclusion."
            )
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
