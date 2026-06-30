"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { ensureAuth } from "@/lib/auth";
import { isDemoMode } from "@/lib/demo";

type AuthContextValue = {
  ready: boolean;
  error: string | null;
};

const AuthContext = createContext<AuthContextValue>({ ready: false, error: null });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ensureAuth()
      .then(() => setReady(true))
      .catch((e) => setError(e instanceof Error ? e.message : "Auth failed"));
  }, []);

  if (error) {
    return (
      <div className="auth-error">
        <h2>Authentication failed</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="auth-loading">
        {isDemoMode() ? "Loading…" : "Connecting to Helios API…"}
      </div>
    );
  }

  return <AuthContext.Provider value={{ ready, error }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
