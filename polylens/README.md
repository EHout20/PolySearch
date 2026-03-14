# PolyLens: AI-Powered Market Intelligence

PolyLens is a sophisticated prediction market research platform that combines real-time data from Polymarket with deep agentic web research to provide comprehensive intelligence reports.

## 🚀 Tech Stack

- **Frontend**: [Next.js](https://nextjs.org/) (React, TypeScript)
- **Market Data**: [Polymarket Gamma API](https://polymarket.com/)
- **AI Agents**: [browser-use](https://browser-use.com/) for agentic web browsing
- **Intelligence**: [Google Gemini](https://ai.google.dev/) (Flash models)
- **Backend**: Python 3 (Research Agent)

## 🛠 Features

- **Instant Market Lookup**: Real-time odds, volume, and liquidity from Polymarket.
- **On-Demand Deep Research**: A dedicated AI browser agent that:
  - Searches Google News for recent context.
  - Analyzes team standings, player injuries, and seasonal trends.
  - Fetches and synthesizes Polymarket community comments for sentiment analysis.
- **Intelligence Reports**: Structured briefings with key success factors, personnel updates, and market analysis.
- **Side-by-Side View**: Compare AI analysis and source news articles in a single dashboard.

## 📦 Getting Started

### Prerequisites

- Node.js (v18+)
- Python 3.9+
- Google Gemini API Key

### Installation & Setup

1. **Install dependencies**:
   ```bash
   # Install frontend dependencies
   npm install

   # Install Python dependencies
   pip install langchain-google-genai browser-use playwright
   playwright install chromium
   ```

2. **Setup environment variables**:
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   ```

### Running the App

Start the Next.js development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🤖 How it Works

1. **Data Sourcing**: Search triggers a query to the Polymarket Gamma API.
2. **Community Pulse**: Fetches the latest community comments via the Gamma extension.
3. **Agentic Browsing**: "Deep Research" launches a `browser-use` agent to scrape the web for real-time context.
4. **LLM Synthesis**: gathered data is synthesized by Gemini into a professional-grade intelligence dossier.

---
Built with ❤️ for prediction market enthusiasts.
