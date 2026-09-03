# Multi-Agent Research System

An AI-powered multi-agent research system designed to automate the
research workflow using specialized agents.

## Architecture

Supervisor
    ↓
Planner
    ↓
Search
    ↓
Reader
    ↓
RAG
    ↓
Research
    ↓
Fact Checker
    ↓
Citation
    ↓
Writer
    ↓
Reviewer
    ↓
PDF/PPT
    ↓
Memory
    ↓
Streamlit UI

## Features

- Multi-agent research workflow
- Research planning
- Web search
- Document reading
- RAG-based information retrieval
- Fact checking
- Citation generation
- Research report generation
- PDF/PPT generation
- Memory
- Streamlit interface

## Tech Stack

- Python
- LangChain
- LangChain Expression Language (LCEL)
- Google Gemini
- Streamlit
- RAG
- Vector databases
- Web search tools

## Installation

Clone the repository:

git clone YOUR_GITHUB_REPOSITORY_URL

Go into the project:

cd your-project

Create a virtual environment:

python -m venv .venv

Activate the environment:

Windows:

.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

## Environment Variables

Create a `.env` file:

GOOGLE_API_KEY=your_api_key
TAVILY_API_KEY=your_api_key

## Run

python pipeline.py

## Project Status

Currently under development.

## Future Improvements

- More specialized research agents
- Improved fact verification
- Better citation handling
- PDF/PPT report generation
- Long-term memory
- Streamlit dashboard
