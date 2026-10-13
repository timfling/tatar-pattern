import { api, type Project } from "@/lib/api";
export type SavedProject = { id: string; name: string; createdAt: number };
function mapped(p: Project): SavedProject { return { id: p.id, name: p.title, createdAt: Date.parse(p.createdAt) }; }
export async function loadProjects() { return (await api.projects()).items.map(mapped); }
export async function addProject(name = "Новый проект") { return mapped((await api.addProject(name)).project); }
export async function renameProject(id: string, name: string) { return mapped((await api.renameProject(id, name)).project); }
export async function deleteProjects(ids: string[]) { for (const id of ids) await api.deleteProject(id); }

export function formatProjectDate(createdAt: number) {
  const date = new Date(createdAt);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`;
}

export function generationsLabel(count: number) {
  const n10 = count % 10;
  const n100 = count % 100;
  if (n10 === 1 && n100 !== 11) return `${count} генерация`;
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) {
    return `${count} генерации`;
  }
  return `${count} генераций`;
}
