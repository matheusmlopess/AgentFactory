# Authentication System
<!-- version: 1.0.0 -->

Issue: #83 · Phase 2 of the production platform (epic #77)

Reference document for the GitHub OAuth authentication layer: architecture,
configuration, state machine, backend API contract, plan gating, and operational runbook.

---

## 1. Overview

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  PURPOSE                                                               │
  │                                                                        │
  │  Allows users to sign in to the AgentFactory webapp using their        │
  │  GitHub identity — no separate password or API key required.           │
  │                                                                        │
  │  What it unlocks:                                                      │
  │    · Private workspaces + RBAC  (#84)                                  │
  │    · Pro billing / Stripe       (#85)                                  │
  │    · CLI login/logout           (#86)                                  │
  │    · Publish agents to registry (authenticated POST /registry/publish) │
  └──────────────────────────────────────────────────────────────────────┘
```

Without auth, users can browse the public registry and view completeness reports.
With auth, they gain a persistent identity, billing tier, and write access.

---

## 2. Architecture

### 2.1 Component map

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  FILE LAYOUT                                                           │
  └──────────────────────────────────────────────────────────────────────┘

  src/types/auth.ts              ← User, Plan, AuthState types        (agentfactory-webapp)
  src/context/AuthContext.tsx    ← AuthProvider, useAuth() hook       (agentfactory-webapp)
  src/components/AuthBar.tsx     ← UI: sign-in button / user badge    (agentfactory-webapp)
  src/main.tsx                   ← AuthProvider wraps the app root    (agentfactory-webapp)

  All auth UI files are in the private agentfactory-webapp repo:
  https://github.com/matheusmlopess/agentfactory-webapp
```

### 2.2 React tree

```
  main.tsx
  └─ <AuthProvider>              ← owns User | null state
       │                           fetches /auth/me on mount
       │                           exposes login() / logout()
       └─ <App>
            └─ <AuthBar>         ← reads useAuth() → renders 3 states
                 (in site header)
```

### 2.3 Data flow on startup

```
  Browser loads the app
       │
       ▼
  AuthProvider mounts
       │
       ├─ VITE_AUTH_API_URL set?
       │     NO  ──► demo mode: loading=false, user=null, no network call
       │     YES ──► GET /auth/me  { credentials: "include" }
       │                  │
       │            ┌─────┴──────┐
       │         200 OK       other
       │            │             │
       │        user = JSON    user = null
       │            └─────┬──────┘
       │                  │
       └──────────────────▼
                  loading = false
                  AuthBar renders correct state
```

---

## 3. Auth States

The `user` field in AuthState is the single source of truth. All three rendering
states derive from `{ loading, user }`:

```
  ┌────────────────────────────────────────────────────────────────────┐
  │  AUTH STATE MACHINE                                                  │
  └────────────────────────────────────────────────────────────────────┘

  App starts
       │
       ▼
  ┌──────────┐   /auth/me resolves   ┌─────────────┐
  │ loading   │ ─────────────────────► signed-out   │
  │           │   (or demo mode)      │  user=null  │
  └──────────┘                       └──────┬───────┘
                                            │ login()
                                            ▼
                                     ┌─────────────┐
                                     │ signed-in    │
                                     │  user=User   │
                                     └──────┬───────┘
                                            │ logout()
                                            ▼
                                     ┌─────────────┐
                                     │ signed-out   │
                                     │  user=null  │
                                     └─────────────┘
```

### What each state renders in AuthBar

```
  ┌──────────────┬──────────────────────────────────────────────────────┐
  │  State        │  AuthBar renders                                      │
  ├──────────────┼──────────────────────────────────────────────────────┤
  │  loading      │  Pulsing skeleton pill (auth-loading CSS animation)   │
  ├──────────────┼──────────────────────────────────────────────────────┤
  │  signed-out   │  [ GitHub icon ]  Sign in with GitHub                 │
  ├──────────────┼──────────────────────────────────────────────────────┤
  │  signed-in    │  [ avatar ]  @handle  [ plan badge ]  ▼              │
  │               │  ↳ dropdown: @handle · email · Sign out              │
  └──────────────┴──────────────────────────────────────────────────────┘
```

---

## 4. User & Plan Types

### 4.1 User object

```
  ┌────────────────┬────────────┬──────────────────────────────────────┐
  │  Field          │  Type       │  Description                          │
  ├────────────────┼────────────┼──────────────────────────────────────┤
  │  id             │  string     │  Backend UUID — primary key           │
  │  github_id      │  number     │  GitHub numeric user ID               │
  │  github_handle  │  string     │  e.g. "matheusmlopess"                │
  │  email          │  string     │  Primary email from GitHub profile    │
  │  avatar_url     │  string     │  GitHub avatar CDN URL                │
  │  plan           │  Plan       │  Billing tier (see §4.2)              │
  └────────────────┴────────────┴──────────────────────────────────────┘
```

### 4.2 Plan tiers

```
  ┌────────────────┬───────────────────┬──────────────────────────────┐
  │  Plan           │  Badge colour      │  Unlocks                      │
  ├────────────────┼───────────────────┼──────────────────────────────┤
  │  free           │  muted grey        │  Public registry browse       │
  │  pro            │  amber             │  BYOK live completeness (#105)│
  │  team           │  teal              │  Private workspaces (#84)     │
  │  enterprise     │  purple            │  Compliance export (#89)      │
  └────────────────┴───────────────────┴──────────────────────────────┘
```

---

## 5. Configuration

### 5.1 Environment variable

```
  VITE_AUTH_API_URL=https://api.agentfactory.dev
```

Set in `webapp/.env.production` (not committed — add to `.gitignore`).
Set as a GitHub Actions secret for the GitHub Pages deploy workflow.

| Value | Behaviour |
|-------|-----------|
| set   | Live backend mode — real OAuth, real sessions |
| unset | Demo mode — mock user, no network calls (default for local dev) |

**Vite inlines this at build time.** The same compiled bundle works in both modes
depending solely on whether the env var was present during `npm run build`.

### 5.2 Files not to commit

```
  webapp/.env.production          ← contains VITE_AUTH_API_URL
  webapp/.env.local               ← local overrides
```

Add both to `.gitignore` if not already present.

---

## 6. Backend API Contract

The frontend calls these four endpoints. The backend (FastAPI, tracked separately)
must implement them exactly.

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  BACKEND ENDPOINTS                                                     │
  └──────────────────────────────────────────────────────────────────────┘

  GET  /auth/github
       ─────────────────────────────────────────────────────────────────
       Redirects to GitHub OAuth authorization URL.
       No request body. No auth required.
       Called by: login() when VITE_AUTH_API_URL is set.

  GET  /auth/github/callback?code=<code>&state=<state>
       ─────────────────────────────────────────────────────────────────
       GitHub redirects here after user grants access.
       Backend exchanges code for access_token, creates/updates User,
       issues JWT session, sets httpOnly cookie, redirects to webapp root.
       Sets: Set-Cookie: session=<jwt>; HttpOnly; SameSite=Lax; Secure

  GET  /auth/me
       ─────────────────────────────────────────────────────────────────
       Returns the current user if the session cookie is valid.
       Called by: AuthProvider on mount (rehydration).
       200 → { id, github_id, github_handle, email, avatar_url, plan }
       401 → null (no valid session)

  POST /auth/logout
       ─────────────────────────────────────────────────────────────────
       Invalidates the session cookie server-side.
       Called by: logout() when VITE_AUTH_API_URL is set.
       200 → {} (empty)
```

### 6.1 Full OAuth sequence diagram

```
  Browser              Webapp backend           GitHub OAuth
     │                       │                       │
     │  click Sign In         │                       │
     │──────────────────────►│                       │
     │                       │  redirect to          │
     │◄──────────────────────│  /auth/github         │
     │                       │                       │
     │  GET github.com/login/oauth/authorize         │
     │──────────────────────────────────────────────►│
     │                       │                       │
     │  user approves access  │                       │
     │  GitHub redirects:     │                       │
     │  /auth/github/callback?code=XXXX              │
     │──────────────────────►│                       │
     │                       │  POST /oauth/token    │
     │                       │──────────────────────►│
     │                       │◄── { access_token }───│
     │                       │                       │
     │                       │  GET /user (GitHub API)
     │                       │──────────────────────►│
     │                       │◄── { login, email }───│
     │                       │                       │
     │                       │  upsert User in DB    │
     │                       │  issue JWT session    │
     │◄── Set-Cookie + 302 ──│                       │
     │                       │                       │
     │  GET /auth/me (with cookie)                   │
     │──────────────────────►│                       │
     │◄── User JSON ─────────│                       │
     │                       │                       │
     │  AuthBar: signed-in   │                       │
```

---

## 7. Demo Mode

When `VITE_AUTH_API_URL` is not set, `AuthProvider` enters demo mode:

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  DEMO MODE (no backend)                                                │
  │                                                                        │
  │  login()   → sets mock user directly in React state (no redirect)     │
  │  logout()  → sets user to null                                        │
  │  /auth/me  → not called (no network request)                          │
  │                                                                        │
  │  Mock user:                                                            │
  │    github_handle: "matheusmlopess"                                    │
  │    plan: "free"                                                        │
  │    github_id: 12345678                                                 │
  └──────────────────────────────────────────────────────────────────────┘
```

**Use demo mode for:**
- Local development without a running backend
- Storybook / UI testing
- GitHub Pages deployment before backend is live

---

## 8. Connecting a Real Backend

```
  Step 1 — Create OAuth app on GitHub
  ─────────────────────────────────────────────────────────────────────
  Settings → Developer settings → OAuth Apps → New OAuth App
  Homepage URL:     https://agentfactory.dev
  Callback URL:     https://api.agentfactory.dev/auth/github/callback

  Copy: Client ID and Client Secret

  Step 2 — Configure backend
  ─────────────────────────────────────────────────────────────────────
  GITHUB_CLIENT_ID=<from step 1>
  GITHUB_CLIENT_SECRET=<from step 1>
  JWT_SECRET=<random 32-byte hex>
  FRONTEND_URL=https://agentfactory.dev

  Step 3 — Set webapp env var
  ─────────────────────────────────────────────────────────────────────
  echo "VITE_AUTH_API_URL=https://api.agentfactory.dev" > webapp/.env.production

  Step 4 — Rebuild webapp
  ─────────────────────────────────────────────────────────────────────
  cd webapp && npm run build
  # VITE_AUTH_API_URL is now inlined in the bundle

  Step 5 — Smoke test
  ─────────────────────────────────────────────────────────────────────
  curl https://api.agentfactory.dev/auth/me
  # → 401 (no cookie) — correct

  Open webapp → click "Sign in with GitHub" → completes OAuth →
  AuthBar shows your avatar + @handle
```

---

## 9. Plan Gating

Use `useAuth()` inside any component to show or hide features based on plan tier:

```tsx
import { useAuth } from "../context/AuthContext";

export function SomeFeature() {
  const { user } = useAuth();

  // Require any login
  if (!user) {
    return <p>Sign in to use this feature.</p>;
  }

  // Require pro or above
  if (user.plan === "free") {
    return (
      <div className="gate-pro">
        <p>This feature requires a Pro plan.</p>
        <a href="/upgrade">Upgrade</a>
      </div>
    );
  }

  return <ActualFeature />;
}
```

**Plan hierarchy for gating:**

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  free  ⊂  pro  ⊂  team  ⊂  enterprise                              │
  │                                                                       │
  │  A team user has access to all free + pro features.                  │
  │  Check: user.plan !== "free"  →  pro-or-above                       │
  │  Check: ["team","enterprise"].includes(user.plan)  →  team-or-above  │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 10. Troubleshooting

```
  ┌──────────────────────────────────────┬───────────────────────────────┐
  │  Symptom                              │  Fix                           │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  AuthBar shows loading indefinitely   │  Check VITE_AUTH_API_URL is   │
  │                                       │  reachable from the browser;  │
  │                                       │  inspect Network tab for      │
  │                                       │  /auth/me response            │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  Click "Sign in" does nothing         │  VITE_AUTH_API_URL is unset   │
  │  (in demo mode)                       │  → expected in demo mode;     │
  │                                       │  set env var and rebuild      │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  OAuth callback gives CSRF error      │  GitHub OAuth state param     │
  │                                       │  mismatch — ensure backend    │
  │                                       │  generates and validates state │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  /auth/me returns 401 after login     │  httpOnly cookie not sent:    │
  │                                       │  check credentials: "include" │
  │                                       │  on frontend and CORS         │
  │                                       │  allow-credentials on backend │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  Avatar image broken                  │  GitHub avatar URL expired or │
  │                                       │  CORS blocked — AuthBar hides │
  │                                       │  img on error automatically   │
  ├──────────────────────────────────────┼───────────────────────────────┤
  │  Plan badge shows "free" after        │  User record in DB still has  │
  │  upgrading                            │  old plan — /auth/me returns  │
  │                                       │  stale data; clear cookie and │
  │                                       │  re-login to refresh session  │
  └──────────────────────────────────────┴───────────────────────────────┘
```
