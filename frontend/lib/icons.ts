const CLASS_ICON: Record<string, string> = {
  vehicle: "/icons/vehicle.svg",
  ship: "/icons/ship.svg",
  aircraft: "/icons/aircraft.svg",
  plane: "/icons/aircraft.svg",
  helicopter: "/icons/helicopter.svg",
  tank: "/icons/vehicle.svg",
  "large-vehicle": "/icons/vehicle.svg",
  "small-vehicle": "/icons/vehicle.svg",
};

export function iconForClass(className: string): string {
  return CLASS_ICON[className.toLowerCase()] || "/icons/vehicle.svg";
}

export function scaleForConfidence(confidence: number): number {
  return 0.6 + confidence * 0.8;
}

export const CHANGE_COLORS: Record<string, string> = {
  appeared: "#98c379",
  disappeared: "#e06c75",
  moved: "#e5c07b",
};

export function coverageColor(hoursAgo: number): string {
  if (hoursAgo < 6) return "rgba(152, 195, 121, 0.55)";
  if (hoursAgo < 48) return "rgba(229, 192, 123, 0.55)";
  return "rgba(224, 108, 117, 0.55)";
}

export const AOI_STYLE: Record<
  string,
  { fill: string; stroke: string; label: string }
> = {
  high: { fill: "#0099ff", stroke: "#00d4ff", label: "#ffffff" },
  medium: { fill: "#e5a020", stroke: "#ffcc44", label: "#ffffff" },
  low: { fill: "#8899bb", stroke: "#aabbdd", label: "#ffffff" },
};

export function aoiStyle(priority: string) {
  return AOI_STYLE[priority] ?? AOI_STYLE.medium;
}
