# AI Debate Platform

A web application that facilitates debates between different AI language models (ChatGPT, Claude, and Gemini) on user-provided topics.

## Features

- Create debates on any topic
- Choose which AI models argue for and against the topic
- Select a third AI to act as a judge
- Configure the number of debate rounds
- View a structured presentation of the debate with a summary
- Comprehensive logging of all operations and API calls
- Protection against double form submission

## Requirements

- Python 3.12+
- OpenAI API key
- Anthropic API key
- Google Gemini API key

## Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -e .
   ```

## Configuration

Set the following environment variables with your API keys:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export GOOGLE_GEMINI_API_KEY="your-google-gemini-api-key"
```

On Windows, use:

```cmd
set OPENAI_API_KEY=your-openai-api-key
set ANTHROPIC_API_KEY=your-anthropic-api-key
set GOOGLE_GEMINI_API_KEY=your-google-gemini-api-key
```

## Running the Application

You can start the web server in one of two ways:

1. Using the run script:
   ```bash
   python run.py
   ```

2. Using the module directly:
   ```bash
   python -m app.main
   ```

Then open your browser and navigate to: http://localhost:8000

## Project Structure

```
aidebate/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── debate_engine.py     # Core debate functionality
│   ├── static/
│   │   └── css/
│   │       └── styles.css   # Custom styles
│   └── templates/
│       ├── base.html        # Base template
│       ├── index.html       # Home page
│       └── results.html     # Debate results page
├── run.py                   # Entry point script
├── .venv/                   # Virtual environment (not in repo)
├── pyproject.toml           # Project dependencies
└── README.md                # This file
```

## License

MIT
