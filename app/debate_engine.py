import openai
import anthropic
import os
import google.generativeai as genai
import logging
import time
from typing import Dict, Callable, Any, Optional

# Get logger
logger = logging.getLogger("aidebate")

# Set up API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

# Initialize clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Configure Gemini
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flas")


# Function to get response from ChatGPT
def chatgpt_response(prompt: str) -> str:
    start_time = time.time()
    logger.info("Requesting response from ChatGPT")

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": prompt}]
        )
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


# Function to select LLM
def get_llm_function(name: str) -> Optional[Callable[[str], str]]:
    # Make case insensitive by converting to lowercase
    name_lower = name.lower() if name else ""

    llm_map = {"chatgpt": chatgpt_response, "claude": claude_response, "gemini": gemini_response}
    return llm_map.get(name_lower, None)


# Available LLMs
LLM_OPTIONS = ["ChatGPT", "Claude", "Gemini"]


# Run debate and capture results
def run_debate(topic: str, pro_llm: str, con_llm: str, judge_llm: str, rounds: int = 2) -> Dict[str, Any]:
    """Run the debate and capture the output."""
    logger.info(f"Starting debate on topic: '{topic}'")

    results = {"rounds": [], "summary": ""}

    pro_model = get_llm_function(pro_llm)
    con_model = get_llm_function(con_llm)
    judge_model = get_llm_function(judge_llm)

    if not pro_model or not con_model or not judge_model:
        logger.error(f"Invalid LLM selection: Pro={pro_llm}, Con={con_llm}, Judge={judge_llm}")
        raise ValueError("Invalid LLM selection. Please use 'ChatGPT', 'Claude', or 'Gemini'.")

    # Initial arguments
    logger.info(f"Getting initial pro argument from {pro_llm}")
    pro_argument = pro_model(f"Argue in favor of: {topic}")

    logger.info(f"Getting initial con argument from {con_llm}")
    con_argument = con_model(f"Argue against: {topic}")

    for round_num in range(1, rounds + 1):
        logger.info(f"Starting round {round_num} of {rounds}")

        # Store the current round's arguments
        results["rounds"].append(
            {"round_number": round_num, "pro_argument": pro_argument, "con_argument": con_argument}
        )

        # Generate counter-arguments for the next round
        if round_num < rounds:
            logger.info(f"Getting pro counter-argument for round {round_num + 1}")
            pro_counter_prompt = (
                f"Your opponent argued: {con_argument}\n\nCounter their argument while supporting: {topic}."
            )
            pro_argument = pro_model(pro_counter_prompt)

            logger.info(f"Getting con counter-argument for round {round_num + 1}")
            con_counter_prompt = (
                f"Your opponent argued: {pro_argument}\n\nCounter their argument while opposing: {topic}."
            )
            con_argument = con_model(con_counter_prompt)

    # Judge LLM summarizes the debate
    logger.info(f"Getting debate summary from {judge_llm}")
    judge_prompt = f"Summarize the key points of the debate on '{topic}', highlighting the strongest arguments for and against. Provide a balanced conclusion."
    summary = judge_model(judge_prompt)
    results["summary"] = summary

    logger.info("Debate completed successfully")
    return results
