"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthField, ContinueButton } from "@/components/auth/AuthField";
import { ProfileFields, EMPTY_PROFILE } from "@/components/account/ProfileFields";
import { emailLooksValid } from "@/lib/auth";
import { api, apiMessage } from "@/lib/api";
export function RegisterScreen() {
  const router = useRouter();
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [pending, setPending] = useState(false); const [error, setError] = useState("");
  const ready = emailLooksValid(email) && password.length >= 10 && password.length <= 128 && profile.firstName.trim().length > 0 && profile.lastName.trim().length > 0 && !pending;
  async function submit() {
    if (!ready) return; setPending(true); setError("");
    try { await api.register(email.trim(), password, profile); router.replace("/constructor"); }
    catch (e) { setError(apiMessage(e)); setPending(false); }
  }
  return <AuthShell><div className="flex min-h-0 flex-1 overflow-y-auto px-6 py-10 max-md:py-6"><form className="auth-form m-auto flex w-full max-w-[607px] flex-col items-center gap-6" onSubmit={e => { e.preventDefault(); void submit(); }}>
    <h1 className="font-display text-[48px] italic max-md:text-[32px]">Регистрация</h1>
    <p className="text-center text-sm">Есть аккаунт? <Link href="/login" className="font-semibold underline">[ Войти ]</Link></p>
    <div className="flex w-full flex-col gap-4"><AuthField type="email" value={email} onChange={setEmail} placeholder="Ваша почта" autoComplete="email" /><AuthField type="password" value={password} onChange={setPassword} placeholder="Пароль — не менее 10 символов" autoComplete="new-password" /><ProfileFields value={profile} onChange={setProfile} /></div>
    {error ? <p role="alert" className="api-error">{error}</p> : null}
    <ContinueButton disabled={!ready}>{pending ? "Создаём аккаунт…" : "Создать аккаунт"}</ContinueButton>
  </form></div></AuthShell>;
}
