"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/auth/RequireAuth";
import { ProfileFields, EMPTY_PROFILE } from "@/components/account/ProfileFields";
import { api, apiMessage } from "@/lib/api";
export default function ProfilePage() {
  const user = useSession(); const router = useRouter();
  const [profile, setProfile] = useState({ ...EMPTY_PROFILE, ...user });
  const [pending, setPending] = useState(false); const [message, setMessage] = useState("");
  async function save() { setPending(true); setMessage(""); try { await api.updateProfile({ firstName: profile.firstName, lastName: profile.lastName, occupation: profile.occupation, avatar: profile.avatar }); window.dispatchEvent(new Event("tp-profile-updated")); setMessage("Профиль сохранён."); } catch(e) { setMessage(apiMessage(e)); } finally { setPending(false); } }
  async function logout() { setPending(true); try { await api.logout(); router.replace("/login"); } catch(e) { setMessage(apiMessage(e)); setPending(false); } }
  return <section className="studio-page"><div className="studio-article"><h1>Ваш аккаунт</h1><p className="break-all">{user?.email}</p><form className="my-8 flex flex-col gap-5" onSubmit={e => { e.preventDefault(); void save(); }}><ProfileFields value={profile} onChange={setProfile} /><button disabled={pending} className="studio-button self-start">Сохранить профиль</button></form><p role="status">{message}</p><nav className="my-8 flex flex-wrap gap-4"><Link href="/settings">Настройки конструктора ↗</Link><Link href="/trash">Корзина ↗</Link><Link href="/rules">Правила сервиса ↗</Link></nav><button disabled={pending} onClick={logout} className="studio-button">Выйти из аккаунта</button></div></section>;
}
