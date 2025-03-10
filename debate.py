import openai
import anthropic
import os
import google.generativeai as genai
from langchain_community.chat_models import ChatOpenAI
from langchain.schema import HumanMessage

# Set up API keys (Replace with your own keys)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

# Initialize clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Configure Gemini
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.0-pro-exp')

# Function to get response from ChatGPT
def chatgpt_response(prompt):
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Function to get response from Claude
def claude_response(prompt):
    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Function to get response from Gemini
def gemini_response(prompt):
    try:
        response = gemini_model.generate_content(prompt)
        if response.text:
            return response.text
        else:
            return "I apologize, but I couldn't generate a response at this time."
    except Exception as e:
        print(f"Error with Gemini response: {str(e)}")
        return "I apologize, but I encountered an error while generating a response."

# Function to select LLM
def get_llm_function(name):
    # Make case insensitive by converting to lowercase
    name_lower = name.lower() if name else ""

    llm_map = {
        "chatgpt": chatgpt_response,
        "claude": claude_response,
        "gemini": gemini_response
    }
    return llm_map.get(name_lower, None)

# Debate function
def debate(topic, pro_llm, con_llm, judge_llm, rounds=2):
    """Facilitates a debate between two LLMs and uses a third as a judge."""

    pro_model = get_llm_function(pro_llm)
    con_model = get_llm_function(con_llm)
    judge_model = get_llm_function(judge_llm)

    if not pro_model or not con_model or not judge_model:
        print("Invalid LLM selection. Please use 'ChatGPT', 'Claude', or 'Gemini'.")
        return

    print(f"\n🔷 Starting Debate on: {topic}")
    print(f"⚖️ {pro_llm} argues **FOR** the topic.")
    print(f"⚖️ {con_llm} argues **AGAINST** the topic.")
    print(f"👨‍⚖️ {judge_llm} will summarize the debate.\n")

    # Initial arguments
    pro_argument = pro_model(f"Argue in favor of: {topic}")
    con_argument = con_model(f"Argue against: {topic}")

    for round in range(1, rounds + 1):
        print(f"\n=== Round {round} ===\n")
        print(f"🟢 {pro_llm} (Pro):\n{pro_argument}\n")
        print(f"🔴 {con_llm} (Con):\n{con_argument}\n")

        # Generate counter-arguments
        pro_counter_prompt = f"Your opponent argued: {con_argument}\n\nCounter their argument while supporting: {topic}."
        con_counter_prompt = f"Your opponent argued: {pro_argument}\n\nCounter their argument while opposing: {topic}."

        pro_argument = pro_model(pro_counter_prompt)
        con_argument = con_model(con_counter_prompt)

    # Judge LLM summarizes the debate
    judge_prompt = f"Summarize the key points of the debate on '{topic}', highlighting the strongest arguments for and against. Provide a balanced conclusion."
    summary = judge_model(judge_prompt)

    print("\n=== 🔍 Summary & Verdict ===\n")
    print(summary)

# User input for debate setup
topic = input("Enter debate topic: ")

# Set defaults with optional override
pro_llm = input("Choose LLM for Pro side (ChatGPT, Claude, Gemini) [default: ChatGPT]: ") or "ChatGPT"
con_llm = input("Choose LLM for Con side (ChatGPT, Claude, Gemini) [default: Claude]: ") or "Claude"
judge_llm = input("Choose LLM for Judge (ChatGPT, Claude, Gemini) [default: Gemini]: ") or "Gemini"

# Run debate
debate(topic, pro_llm, con_llm, judge_llm)
