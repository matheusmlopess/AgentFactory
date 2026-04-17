// auth.ts — user identity and auth types
// <!-- version: 1.0.0 -->

export type Plan = "free" | "pro" | "team" | "enterprise";

export interface User {
  id: string;
  github_id: number;
  github_handle: string;
  email: string;
  avatar_url: string;
  plan: Plan;
}

export interface AuthState {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
}
