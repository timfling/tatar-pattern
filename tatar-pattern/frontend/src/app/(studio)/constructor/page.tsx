import { ConstructorScreen } from "@/components/constructor/ConstructorScreen";
export default async function ConstructorPage({ searchParams }: { searchParams: Promise<{ pattern?: string | string[]; v3?: string | string[]; from?: string; mode?: string }> }) {
  const params = await searchParams;
  const patternId = Array.isArray(params.pattern) ? params.pattern[0] : params.pattern;
  const v3Id = Array.isArray(params.v3) ? params.v3[0] : params.v3;
  return <ConstructorScreen key={patternId ?? v3Id ?? "new"} initialPatternId={patternId} initialV3Session={v3Id} returnToLibrary={params.from === "library"} initialMode={params.mode === "ai" ? "ai" : "flat"} />;
}
