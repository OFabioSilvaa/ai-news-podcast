# AI News Podcast - Automated Daily Briefing

> **Automated Data Engineering & Generative AI System.**
> A serverless automation pipeline that monitors technology RSS feeds, utilizes LLMs for script generation, and synthesizes a daily high-fidelity audio podcast, orchestrated entirely via GitHub Actions.

![Status](https://img.shields.io/github/actions/workflow/status/OFabioSilva/ai-news-podcast/main.yml?label=Pipeline&style=flat-square)
![Python](https://img.shields.io/badge/Made%20with-Python%203.10-blue?style=flat-square&logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-orange?style=flat-square&logo=google&logoColor=white)
![Telegram](https://img.shields.io/badge/Delivery-Telegram%20API-2CA5E0?style=flat-square&logo=telegram&logoColor=white)

---

## System Architecture & Workflow

This project operates on a cost-efficient, serverless event-driven architecture. The automated pipeline follows a strict **ETL (Extract, Transform, Load)** process:

1.  **TRIGGER (07:00 UTC):** GitHub Actions initiates a scheduled Cron job, provisioning an ephemeral Ubuntu Linux runner.
2.  **EXTRACT (RSS Ingestion):** The system polls XML feeds from **OpenAI**, **TechCrunch**, and **Google AI Blog**.
3.  **STATE CHECK (Idempotency):** DuckDB checks local history to filter out previously processed articles, ensuring zero duplication.
4.  **TRANSFORM (Generative AI):**
    * New data is sent to **Google Gemini 2.5 Flash**.
    * The LLM acts as a Senior Scriptwriter, converting technical documentation into a natural dialogue format between two personas.
5.  **AUDIO ENGINEERING:**
    * **Synthesis:** Edge-TTS generates high-fidelity neural voices.
    * **Mixing:** Pydub engine overlays a Jazz background track with automated volume ducking (dynamic compression).
6.  **LOAD (Delivery):** The final `.mp3` file is dispatched via Telegram Bot API to the end-user.
7.  **PERSIST:** The updated DuckDB database file is committed back to the repository to save state for the next run.

## Key Features

* **Automated Data Ingestion:** Continuous monitoring of XML RSS feeds from major technology portals.
* **Idempotency & State Management:** Implementation of **DuckDB** (OLAP database) to maintain a local history of processed news, preventing content duplication even in ephemeral runtime environments.
* **Generative AI Pipeline:** Integration with **Google Gemini 2.5 Flash** using advanced prompt engineering to transform raw technical data into structured, conversational scripts.
* **Python Audio Engineering:**
    * High-fidelity Neural Text-to-Speech (TTS).
    * Dynamic background music mixing with automated volume ducking.
* **CI/CD & DevOps:** Fully automated pipeline via GitHub Actions with scheduled Cron jobs and secure secret management.

## Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Language** | Python 3.10 | Core application logic |
| **LLM Engine** | Google Gemini API | Content summarization and scriptwriting |
| **Database** | DuckDB | Lightweight SQL engine for state tracking |
| **Audio Processing** | Edge-TTS & Pydub | Voice synthesis and audio manipulation |
| **Infrastructure** | GitHub Actions | Serverless orchestration |
| **Notification** | Telebot | Final content delivery via Telegram |

## Local Installation & Setup

To run this project in a local environment:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/OFabioSilva/ai-news-podcast.git](https://github.com/OFabioSilva/ai-news-podcast.git)
    cd ai-news-podcast
    ```

2.  **Install dependencies:**
    Ensure FFmpeg is installed on your system, then run:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration:**
    Set up the following environment variables:
    * `CHAVE_GEMINI`: Your Google AI Studio API Key.
    * `TOKEN_TELEGRAM`: Your Telegram Bot Token.
    * `CHAT_ID_FIXO`: Target Telegram User ID.

4.  **Execution:**
    ```bash
    python main.py
    ```

## Security & Compliance

* **Secret Management:** No API keys are hardcoded. All sensitive data is managed via GitHub Secrets or Environment Variables.
* **Data Validation:** Input sanitization is applied to RSS feeds before processing.

---

### Author

Developed by **Fábio Silva**.
*Data Engineer specializing in Intelligent Automation and AI Ecosystems.*

[![LinkedIn](https://img.shields.io/badge/Connect-LinkedIn-blue?style=flat-square&logo=linkedin)](https://www.linkedin.com/in/fábio-silva-54625230b/)
