import logging
import os
import time
from typing import Any, Callable, Dict, Optional

import anthropic
import google.generativeai as genai
import openai
import requests

# Get logger
logger = logging.getLogger("aidebate")

# Set up API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = os.getenv("GROK_API_URL", "https://api.grok.ai/v1")

# Initialize clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Configure Gemini
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")


# Function to get response from ChatGPT
def chatgpt_response(prompt: str) -> str:
    start_time = time.time()
    logger.info("Requesting response from ChatGPT")

    try:
        response = openai_client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": prompt}])
        result = response.choices[0].message.content

        elapsed_time = time.time() - start_time
        logger.info(f"ChatGPT response received in {elapsed_time:.2f} seconds")

        return result
    except Exception as e:
        logger.error(f"Error getting ChatGPT response: {str(e)}")
        raise


# Function to get response from Claude
def claude_response(prompt: str) -> str:
    start_time = time.time()
    logger.info("Requesting response from Claude")

    try:
        response = anthropic_client.messages.create(
            model="claude-3-opus-20240229", max_tokens=1024, messages=[{"role": "user", "content": prompt}]
        )
        result = response.content[0].text

        elapsed_time = time.time() - start_time
        logger.info(f"Claude response received in {elapsed_time:.2f} seconds")

        return result
    except Exception as e:
        logger.error(f"Error getting Claude response: {str(e)}")
        raise


# Function to get response from Gemini
def gemini_response(prompt: str) -> str:
    start_time = time.time()
    logger.info("Requesting response from Gemini")

    try:
        response = gemini_model.generate_content(prompt)
        if response.text:
            result = response.text
            elapsed_time = time.time() - start_time
            logger.info(f"Gemini response received in {elapsed_time:.2f} seconds")
            return result
        else:
            logger.warning("Gemini returned empty response")
            return "I apologize, but I couldn't generate a response at this time."
    except Exception as e:
        logger.error(f"Error with Gemini response: {str(e)}")
        return "I apologize, but I encountered an error while generating a response."


# Function to get response from Grok
def grok_response(prompt: str) -> str:
    start_time = time.time()
    logger.info("Requesting response from Grok")

    try:
        headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}

        payload = {"messages": [{"role": "user", "content": prompt}], "model": "grok-1"}

        response = requests.post(f"{GROK_API_URL}/chat/completions", headers=headers, json=payload)

        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"]

        elapsed_time = time.time() - start_time
        logger.info(f"Grok response received in {elapsed_time:.2f} seconds")

        return result
    except Exception as e:
        logger.error(f"Error getting Grok response: {str(e)}")
        return "I apologize, but I encountered an error while generating a response."


# Function to select LLM
def get_llm_function(name: str) -> Optional[Callable[[str], str]]:
    # Make case insensitive by converting to lowercase
    name_lower = name.lower() if name else ""

    llm_map = {"chatgpt": chatgpt_response, "claude": claude_response, "gemini": gemini_response, "grok": grok_response}
    return llm_map.get(name_lower, None)


# Available LLMs
LLM_OPTIONS = ["ChatGPT", "Claude", "Gemini", "Grok"]


# Run debate and capture results
def run_debate(
    topic: str,
    pro_llm: str,
    con_llm: str,
    judge_llm: str,
    rounds: int = 2,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """
    Run the debate and capture the output.

    Args:
        topic: The debate topic
        pro_llm: The LLM to use for the pro side
        con_llm: The LLM to use for the con side
        judge_llm: The LLM to use for the judge
        rounds: Number of debate rounds
        progress_callback: Optional callback function for progress updates
                          Takes (stage, message) parameters

    Returns:
        Dictionary with debate results
    """
    logger.info(f"Starting debate on topic: '{topic}'")

    results = {"rounds": [], "summary": ""}

    pro_model = get_llm_function(pro_llm)
    con_model = get_llm_function(con_llm)
    judge_model = get_llm_function(judge_llm)

    if not pro_model or not con_model or not judge_model:
        logger.error(f"Invalid LLM selection: Pro={pro_llm}, Con={con_llm}, Judge={judge_llm}")
        raise ValueError("Invalid LLM selection. Please use 'ChatGPT', 'Claude', 'Gemini', or 'Grok'.")

    # Initial arguments - Pro side
    if progress_callback:
        progress_callback("pro_initial", f"Getting initial argument from {pro_llm}...")

    logger.info(f"Getting initial pro argument from {pro_llm}")
    try:
        pro_argument = pro_model(f"Argue in favor of: {topic}")
        logger.info(f"Received initial pro argument ({len(pro_argument)} chars)")
    except Exception as e:
        logger.error(f"Error getting pro argument: {str(e)}")
        raise ValueError(f"Error getting response from {pro_llm}: {str(e)}")

    # Initial arguments - Con side
    if progress_callback:
        progress_callback("con_initial", f"Getting initial argument from {con_llm}...")

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
            if progress_callback:
                progress_callback(
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
            if progress_callback:
                progress_callback(
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
    if progress_callback:
        progress_callback("judging", f"Getting final summary from {judge_llm}...")

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

    if progress_callback:
        progress_callback("completed", "Debate completed successfully!")

    logger.info("Debate completed successfully")
    return results
