"use client";
/* eslint-disable @next/next/no-img-element -- Cookie-protected server files and local avatar data URLs use native images. */
import { useState } from "react";
import { AuthField } from "@/components/auth/AuthField";
import type { Profile } from "@/lib/api";
export const EMPTY_PROFILE: Profile = { firstName: "", lastName: "", occupation: "", avatar: null };
export function ProfileFields({ value, onChange }: { value: Profile; onChange: (value: Profile) => void }) {
  const [error, setError] = useState("");
  async function avatar(file?: File) {
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 5_000_000) { setError("Выберите PNG, JPG или WebP до 5 МБ."); return; }
    try {
      const bitmap = await createImageBitmap(file);
      const canvas = document.createElement("canvas"); canvas.width = canvas.height = 96;
      const ctx = canvas.getContext("2d"); if (!ctx) throw new Error();
      ctx.fillStyle = "#f1eff0"; ctx.fillRect(0,0,96,96);
      const side = Math.min(bitmap.width, bitmap.height);
      ctx.drawImage(bitmap,(bitmap.width-side)/2,(bitmap.height-side)/2,side,side,0,0,96,96); bitmap.close();
      const data = canvas.toDataURL("image/jpeg", .65);
      if (data.length > 12000) { setError("Фото слишком детальное. Выберите другое изображение."); return; }
      onChange({ ...value, avatar: data }); setError("");
    } catch { setError("Не удалось прочитать изображение."); }
  }
  return <div className="flex w-full flex-col gap-4">
    <AuthField value={value.firstName} onChange={firstName => onChange({ ...value, firstName })} placeholder="Имя · необязательно" autoComplete="given-name" />
    <AuthField value={value.lastName} onChange={lastName => onChange({ ...value, lastName })} placeholder="Фамилия · необязательно" autoComplete="family-name" />
    <label className="flex flex-col gap-2 text-sm">Род деятельности · необязательно<select className="rounded-2xl border border-hairline bg-transparent p-3" value={value.occupation} onChange={e => onChange({ ...value, occupation: e.target.value })}><option value="">Не указан</option><option value="designer">Дизайнер</option><option value="artist">Художник</option><option value="student">Студент</option><option value="researcher">Исследователь</option><option value="other">Другое</option></select></label>
    <label className="flex flex-wrap items-center gap-3 text-sm">{value.avatar ?  <img alt="Ваш аватар" src={value.avatar} className="size-12 rounded-full object-cover" /> : null}Аватар · необязательно<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => void avatar(e.target.files?.[0])} className="max-w-full text-xs" /></label>
    {value.avatar ? <button type="button" className="self-start text-sm underline" onClick={() => onChange({ ...value, avatar: null })}>Убрать аватар</button> : null}
    {error ? <p role="alert" className="api-error">{error}</p> : null}
  </div>;
}
