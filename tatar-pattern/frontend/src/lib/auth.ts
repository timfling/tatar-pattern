import { api, type User } from "@/lib/api";
export type AuthUser = User;
export async function loadUser(): Promise<AuthUser | null> {
  try { return (await api.me()).user; }
  catch (error) {
    if (error instanceof Error && "status" in error && error.status === 401) return null;
    throw error;
  }
}
export function emailLooksValid(value: string) { const email = value.trim(); const [local, domain, extra] = email.split("@"); return !extra && email.length <= 254 && Boolean(local && local.length <= 64 && !local.startsWith(".") && !local.endsWith(".") && !local.includes("..") && /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$/.test(local) && domain && domain.includes(".") && domain.split(".").every(label => /^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(label)) && /^[A-Za-z]{2,}$/.test(domain.split(".").at(-1) ?? "")); }
