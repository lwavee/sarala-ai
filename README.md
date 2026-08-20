# 🤖 Sarala AI — Your Smart Personal Assistant & Live Video Companion

Sarala AI is a next-generation, human-like virtual assistant built to think, learn, and interact naturally.
It combines AI intelligence, memory, voice interaction, 3D animated avatar video calling, and a modern UI to create a premier assistant experience.

---

## 🚀 Quick Start (Single Command)

Run both Backend (FastAPI) and Frontend (Next.js) concurrently with a single command from the root directory:

```bash
npm run dev
```

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8008](http://localhost:8008)

---

## 🏗️ Project Structure

```
sarala-ai/
│
├── package.json       # Root orchestrator (starts Backend & Frontend together)
├── backend/           # Python FastAPI Server (Brain, Memory, LLM & Voice API)
│   ├── main.py
│   ├── web/app.py
│   └── requirements.txt
│
└── frontend/          # Next.js 16 Web App with 3D Avatar Video Call Interface
    ├── src/app/chatbot/page.tsx
    └── src/components/live/
```

---

## ⚙️ Setup Instructions

### 1. Install Dependencies

```bash
# Install root orchestrator dependencies
npm install

# Install frontend dependencies
npm --prefix frontend install

# Install backend dependencies
pip install -r backend/requirements.txt
```

### 2. Run Application

```bash
npm run dev
```

---

## 📄 License

MIT License — Built with ❤️ by **Naveen Panchal (Avee)**
