// AuthBar.tsx — sign-in button + user badge for the site header
// <!-- version: 1.0.0 -->

import { useState, useRef, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import type { Plan } from "../types/auth";

const PLAN_LABEL: Record<Plan, string> = {
  free:       "free",
  pro:        "pro",
  team:       "team",
  enterprise: "enterprise",
};

const PLAN_CLASS: Record<Plan, string> = {
  free:       "plan--free",
  pro:        "plan--pro",
  team:       "plan--team",
  enterprise: "plan--enterprise",
};

export function AuthBar() {
  const { user, loading, login, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (loading) {
    return <span className="auth-loading" aria-label="Loading auth state" />;
  }

  if (!user) {
    return (
      <button className="auth-signin" onClick={login} aria-label="Sign in with GitHub">
        <GitHubIcon />
        Sign in with GitHub
      </button>
    );
  }

  return (
    <div className="auth-user" ref={menuRef}>
      <button
        className="auth-avatar-btn"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`@${user.github_handle} — open account menu`}
      >
        <img
          className="auth-avatar"
          src={user.avatar_url}
          alt={`@${user.github_handle}`}
          width={28}
          height={28}
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
        <span className="auth-handle">@{user.github_handle}</span>
        <span className={`auth-plan ${PLAN_CLASS[user.plan]}`}>
          {PLAN_LABEL[user.plan]}
        </span>
      </button>

      {open && (
        <div className="auth-menu" role="menu" aria-label="Account menu">
          <div className="auth-menu-header">
            <strong className="auth-menu-handle">@{user.github_handle}</strong>
            <span className="auth-menu-email">{user.email}</span>
          </div>
          <hr className="auth-menu-divider" />
          <button
            className="auth-menu-item"
            role="menuitem"
            onClick={() => { setOpen(false); logout(); }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function GitHubIcon() {
  return (
    <svg
      className="auth-gh-icon"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
               0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
               -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
               .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
               -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09
               2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82
               2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01
               2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
