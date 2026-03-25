# AutoClaim — Frontend Client

React 19 (JavaScript/JSX) single-page application built with Vite 7.

## Tech Stack

- **React 19** — UI component framework (JavaScript/JSX)
- **Vite 7** — Build tool and dev server
- **React Router DOM 7** — Client-side routing
- **Axios** — HTTP client with JWT interceptor
- **Recharts** — Analytics charts
- **Framer Motion** — UI animations
- **Lucide React** — Icon library
- **Bootstrap 5.3** — Grid and utility CSS

## Getting Started

```bash
npm install
npm run dev     # → http://localhost:5173
```

## Key Components

| Component | Purpose |
|---|---|
| `Login.jsx` / `LoginModal.jsx` | Authentication (page and modal) |
| `Register.jsx` | User registration |
| `UserDashboard.jsx` | Policyholder claim list & submission |
| `ClaimUpload.jsx` | Multi-step claim submission wizard |
| `ViewClaim.jsx` | Full claim detail + AI analysis results |
| `AgentDashboard.jsx` | Claim review panel for agents |
| `AdminDashboard.jsx` | Admin control: agents, policies, claims |
| `AnalyticsDashboard.jsx` | Charts: fraud distribution, AI recommendations |
| `UserProfile.jsx` | Profile update + active policy display |
| `TrackClaimRedirect.jsx` | Public claim tracking redirect |
| `Navbar.jsx` | Role-aware navigation with notifications |
| `AITestPage.jsx` | Developer AI testing UI |
