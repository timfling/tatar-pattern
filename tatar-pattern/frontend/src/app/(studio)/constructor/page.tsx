import { ConstructorScreen } from "@/components/constructor/ConstructorScreen";
export default async function ConstructorPage({ searchParams }: { searchParams: Promise<{ pattern?: string | string[]; from?: string }> }) {
  const params = await searchParams;
  const patternId = Array.isArray(params.pattern) ? params.pattern[0] : params.pattern;
  return <ConstructorScreen key={patternId ?? "new"} initialPatternId={patternId} returnToLibrary={params.from === "library"} />;
}
