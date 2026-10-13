import { AppFrame } from "@/components/layout/AppFrame";
import { RequireAuth } from "@/components/auth/RequireAuth";

export default function StudioLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <AppFrame>{children}</AppFrame>
    </RequireAuth>
  );
}
