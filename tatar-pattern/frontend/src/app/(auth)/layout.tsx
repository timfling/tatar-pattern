import { RedirectIfAuthed } from "@/components/auth/RequireAuth";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="app-viewport">
      <div className="app-screen">
        <RedirectIfAuthed>{children}</RedirectIfAuthed>
      </div>
    </div>
  );
}
