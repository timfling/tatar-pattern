"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { authDestination } from "@/lib/auth-destination";
import { loadUser } from "@/lib/auth";
import { type User } from "@/lib/api";
const SessionContext = createContext<User | null>(null);
export function useSession() { return useContext(SessionContext); }
import { apiMessage } from "@/lib/api";
function AuthGate({ children, protectedRoute }: { children: ReactNode; protectedRoute: boolean }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    loadUser().then((user) => {
      if (!active) return;
      setUser(user);
      if (protectedRoute && !user) router.replace(`/login?next=${encodeURIComponent(window.location.pathname+window.location.search)}`);
      else if (!protectedRoute && user) router.replace(authDestination());
      else setReady(true);
    }).catch((e) => {
      if (!active) return;
      // Public auth forms remain usable while the API is unavailable.
      if (!protectedRoute) setReady(true); else setError(apiMessage(e));
    });
    const expired = () => { if (protectedRoute) { setReady(false); router.replace(`/login?next=${encodeURIComponent(window.location.pathname+window.location.search)}`); } };
    const profileUpdated = () => { loadUser().then(next => { if(active) setUser(next); }).catch(e => { if(active) setError(apiMessage(e)); }); };
    window.addEventListener("tp-profile-updated", profileUpdated);
    window.addEventListener("tp-session-expired", expired);
    return () => { active = false; window.removeEventListener("tp-profile-updated", profileUpdated); window.removeEventListener("tp-session-expired", expired); };
  }, [router, protectedRoute, retry]);
  if (!ready) return <div className="app-viewport bg-auth flex flex-col items-center justify-center gap-4" role="status">{error || "Проверяем сессию…"}{error ? <button onClick={() => { setError(""); setRetry((n) => n + 1); }}>Попробовать снова</button> : null}</div>;
  return <SessionContext.Provider value={user}>{children}</SessionContext.Provider>;
}
export function RequireAuth({ children }: { children: ReactNode }) { return <AuthGate protectedRoute>{children}</AuthGate>; }
export function RedirectIfAuthed({ children }: { children: ReactNode }) { return <AuthGate protectedRoute={false}>{children}</AuthGate>; }
