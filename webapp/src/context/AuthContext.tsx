// AuthContext.tsx — auth state provider
// <!-- version: 1.0.0 -->
//
// Production wiring:
//   Set VITE_AUTH_API_URL to your FastAPI backend root.
//   The provider will call GET /auth/me on mount to rehydrate session
//   from the httpOnly cookie set by /auth/github/callback.
//
//   login()  → redirects to GET /auth/github
//   logout() → calls POST /auth/logout, clears local state

import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import type { AuthState, User } from "../types/auth";

const AuthContext = createContext<AuthState>({
  user: null,
  loading: false,
  login: () => {},
  logout: () => {},
});

const API = import.meta.env.VITE_AUTH_API_URL as string | undefined;

// ---------------------------------------------------------------------------
// Mock user — removed once VITE_AUTH_API_URL is set
// ---------------------------------------------------------------------------
const MOCK_USER: User = {
  id:            "mock-001",
  github_id:     12345678,
  github_handle: "matheusmlopess",
  email:         "matheusmlopess@gmail.com",
  avatar_url:    "https://avatars.githubusercontent.com/u/12345678?v=4",
  plan:          "free",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<User | null>(null);
  const [loading, setLoading] = useState(!!API);

  useEffect(() => {
    if (!API) {
      // No backend configured — start logged-out (demo mode)
      setLoading(false);
      return;
    }
    fetch(`${API}/auth/me`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: User | null) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  function login() {
    if (API) {
      window.location.href = `${API}/auth/github`;
    } else {
      // Demo mode: simulate login with mock user
      setUser(MOCK_USER);
    }
  }

  function logout() {
    if (API) {
      fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" })
        .finally(() => setUser(null));
    } else {
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
