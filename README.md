# 👁️ PolyLens: Market Intelligence Layer

PolyLens is an AI-powered intelligence platform designed to decode prediction markets. It bridges the gap between raw Polymarket odds and real-world context using high-speed research agents and LLM-driven synthesis.

![PolyLens Banner](https://images.unsplash.com/photo-1611974714851-48206138d731?q=80&w=2000&auto=format&fit=crop)

---

## 🚀 The Stack

PolyLens is built for speed and precision, using a modern hybrid architecture:

### 🏛️ Frontend & API
- **Framework**: [Next.js 15+](https://nextjs.org/) (App Router)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS 4.0](https://tailwindcss.com/)
- **Runtime**: Node.js / Edge Runtime

### 🧠 Intelligence Engine
- **LLM**: [Google Gemini 1.5 Flash](https://ai.google.dev/) (Ultra-fast reasoning)
- **Deep Research**: Custom synthesis pipeline that merges pre-cached news citations with live market data.
- **Agentic Layer**: Standalone Python research agent using `browser-use` for deep-web scraping.

### 📡 Data Sources
- **Markets**: [Polymarket Gamma API](https://polymarket.com/)
- **Real-time News**: Google News RSS & direct citations.
- **Community Pulse**: Polymarket event comments and sentiment analysis.

---

## 🛠️ Project Structure

```text
PolySearch/
├── polylens/               # Main Next.js Web Application
│   ├── src/app/            # App Router & API Routes
│   ├── src/components/     # UI Components (Results, Leaderboards, Gauges)
│   └── backend/            # Research Agent Engine
│       └── polymarket_agent.py  # Heavy-duty Python Research Agent
├── .env.example            # Template for environment variables
└── README.md               # This project documentation
```

---

## 📦 Getting Started

### 1. Prerequisites
- **Node.js**: v18.18+ or v20+
- **Python**: v3.9+ (optional, for standalone agent)
- **API Key**: [Google Gemini API Key](https://aistudio.google.com/)

### 2. Setup
1. Clone the repo.
2. Create `polylens/.env` (use `.env.example` as a template).
3. Install frontend dependencies:
   ```bash
   cd polylens
   npm install
   ```
4. (Optional) Install Python agent dependencies:
   ```bash
   cd polylens/backend
   pip install langchain-google-genai browser-use playwright
   playwright install chromium
   ```

### 3. Running the App
```bash
cd polylens
npm run dev
```
Navigate to `http://localhost:3000`.

---

## 🤖 Research Modes

### ⚡ Fast Scan (Instant)
When you search for a topic, PolyLens immediately fetches Polymarket odds and the latest relevant news articles via RSS. No AI delay.

### 🔍 Deep Research (On-Demand)
Clicking **"Generate Analysis"** triggers a deep synthesis. Gemini parses the identified articles, cross-references them with market volume and liquidity, and builds a comprehensive **Intelligence Dossier**.

---

## 🧪 Advanced: Standalone Agent
For heavy-duty research without the UI, you can run the Python agent directly:

```bash
python3 polylens/backend/polymarket_agent.py "Who will win the 2026 NBA Finals?" --json
```

---

Built with ❤️ for prediction market enthusiasts.
