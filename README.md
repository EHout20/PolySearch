# PolyLens: AI-Powered Market Intelligence

PolyLens is a sophisticated prediction market research platform that combines real-time data from Polymarket with deep agentic web research to provide comprehensive intelligence reports.

## 🚀 Tech Stack

- **Frontend**: [Next.js](https://nextjs.org/) (React, TypeScript, Tailwind CSS)
- **Market Data**: [Polymarket Gamma API](https://polymarket.com/)
- **AI Agents**: [browser-use](https://browser-use.com/) for agentic web browsing
- **Intelligence**: [Google Gemini](https://ai.google.dev/) (Flash & Flash-Lite models)
- **Backend**: Python 3 (Research Agent)

## 🛠 Features

- **Instant Market Lookup**: Real-time odds, volume, and liquidity from Polymarket.
- **On-Demand Deep Research**: A dedicated AI browser agent that:
  - Searches Google News for recent context.
  - Analyzes team standings, player injuries, and seasonal trends.
  - Fetches and synthesizes Polymarket community comments for sentiment analysis.
- **Intelligence Reports**: Structured briefings with key success factors, personnel updates, and market analysis.
- **Price History**: Interactive charts showing market trends over time.

## 📦 Getting Started

### Prerequisites

- Node.js (v18+)
- Python 3.9+
- [Ollama](https://ollama.ai/) (optional, if using local models)
- Google Gemini API Key

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/EHout20/PolySearch.git
   cd PolySearch
   ```

2. **Setup environment variables**:
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   ```

3. **Install Python dependencies**:
   ```bash
   pip install langchain-google-genai browser-use playwright
   playwright install chromium
   ```

4. **Install Frontend dependencies**:
   ```bash
   cd polylens
   npm install
   ```

### Running the App

Start the Next.js development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🤖 How it Works

1. **Data Sourcing**: When you search, the app first queries the Polymarket Gamma API for relevant markets.
2. **Community Pulse**: The system fetches the latest comments from the Polymarket platform to gauge community sentiment.
3. **Agentic Browsing**: If "Deep Research" is triggered, a `browser-use` agent launches a headless browser to scrape current sports standings, injury reports, or political news.
4. **LLM Synthesis**: All gathered data (market odds, comments, web news, context) is sent to Gemini to generate a structured intelligence briefing.

---
Built with ❤️ for prediction market enthusiasts.
