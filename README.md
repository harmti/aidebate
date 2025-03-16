# AI Debate Platform

A web application that facilitates debates between different AI language models (ChatGPT, Claude, Gemini, and Grok) on user-provided topics.

## Features

- Create debates on any topic
- Choose which AI models argue for and against the topic
- Select a third AI to act as a judge
- Configure the number of debate rounds
- View a structured presentation of the debate with a summary
- Comprehensive logging of all operations and API calls
- Protection against double form submission
- Basic authentication to secure the application
- Custom favicon

## Requirements

- Python 3.12+
- OpenAI API key
- Anthropic API key
- Google Gemini API key
- Grok API key

## Installation

### Option 1: Standard Installation

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

### Option 2: Docker Installation

1. Clone this repository
2. Make sure you have Docker and Docker Compose installed
3. Create a `.env` file with your API keys (see Configuration section)
4. Build and run the Docker container:
   ```
   ./run-docker.sh -d
   ```

## Configuration

Set the following environment variables with your API keys:

```bash
# API Keys
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export GOOGLE_GEMINI_API_KEY="your-google-gemini-api-key"
export GROK_API_KEY="your-grok-api-key"
export GROK_API_URL="https://api.grok.ai/v1"

# Basic Authentication (optional, defaults shown)
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="debate123"
```

On Windows, use:

```cmd
set OPENAI_API_KEY=your-openai-api-key
set ANTHROPIC_API_KEY=your-anthropic-api-key
set GOOGLE_GEMINI_API_KEY=your-google-gemini-api-key
set GROK_API_KEY=your-grok-api-key
set GROK_API_URL=https://api.grok.ai/v1
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=debate123
```

For Docker, create a `.env` file in the project root with the following content:
```
# API Keys
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
GOOGLE_GEMINI_API_KEY=your-google-gemini-api-key
GROK_API_KEY=your-grok-api-key
GROK_API_URL=https://api.grok.ai/v1

# Basic Authentication (optional, defaults shown)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=debate123
```

## Running the Application

### Without Docker

You can start the web server in one of two ways:

1. Using the run script:
   ```bash
   python run.py
   ```

2. Using the module directly:
   ```bash
   python -m app.main
   ```

### With Docker

1. Start the container:
   ```bash
   ./run-docker.sh -d
   ```

2. Stop the container:
   ```bash
   docker-compose down
   ```

Then open your browser and navigate to: http://localhost:8000

## Deployment

### Railway Deployment

To deploy this application to Railway:

1. Fork or clone this repository to your GitHub account
2. Create a new project in Railway and connect it to your GitHub repository
3. Add the following environment variables in the Railway dashboard:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_GEMINI_API_KEY`
4. Deploy the application

Railway will automatically detect the Procfile and use it to start the application.

## Project Structure

```
aidebate/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application (modified for robust logging)
│   ├── main.py.modified     # Backup of the modified FastAPI application
│   ├── debate_engine.py     # Core debate functionality
│   ├── static/
│   │   └── css/
│   │       └── styles.css   # Custom styles
│   └── templates/
│       ├── base.html        # Base template
│       ├── index.html       # Home page
│       └── results.html     # Debate results page
├── run.py                   # Entry point script
├── Dockerfile               # Docker configuration
├── docker-compose.yml       # Docker Compose configuration
├── Procfile                 # Procfile for Railway deployment
├── railway.toml             # Railway-specific configuration
├── run-docker.sh            # Script to run Docker
├── debug-docker.sh          # Script to debug Docker container issues
├── .dockerignore            # Files to exclude from Docker build
├── .env.example             # Example environment variables
├── pyproject.toml           # Project dependencies
└── README.md                # This file
```

## License

MIT
