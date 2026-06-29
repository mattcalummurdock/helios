/** Human-readable model label; null when subclass repeats the MVP class. */
export function detectionModelLabel(
  className: string,
  subclass: string | null | undefined
): string | null {
  if (!subclass) return null;
  const norm = (s: string) => s.toLowerCase().replace(/_/g, "-").trim();
  const alias: Record<string, string> = {
    plane: "aircraft",
    "small-vehicle": "vehicle",
    "large-vehicle": "vehicle",
  };
  const sub = norm(subclass);
  const cls = norm(className);
  const subMvp = norm(alias[sub] ?? sub);
  if (subMvp === cls || sub === cls) return null;
  return subclass.replace(/_/g, "-");
}
