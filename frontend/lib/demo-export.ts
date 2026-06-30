import type { DetectionFeature, ExportQuery } from "./types";
import { demoDetections } from "./demo";

function filterForExport(
  features: DetectionFeature[],
  params: ExportQuery
): DetectionFeature[] {
  let out = features;
  if (params.aoi_id != null) {
    out = out.filter((f) => f.properties.aoi_id === params.aoi_id);
  }
  if (params.classes?.length) {
    const set = new Set(params.classes);
    out = out.filter((f) => set.has(f.properties.class));
  }
  if (params.time_start) {
    const start = new Date(params.time_start).getTime();
    out = out.filter((f) => new Date(f.properties.timestamp).getTime() >= start);
  }
  if (params.time_end) {
    const end = new Date(params.time_end).getTime();
    out = out.filter((f) => new Date(f.properties.timestamp).getTime() <= end);
  }
  return out;
}

function classStyle(className: string): string {
  const mapping: Record<string, string> = {
    aircraft: "http://maps.google.com/mapfiles/kml/paddle/ylw-stars.png",
    plane: "http://maps.google.com/mapfiles/kml/paddle/ylw-stars.png",
    ship: "http://maps.google.com/mapfiles/kml/paddle/blu-circle.png",
    vehicle: "http://maps.google.com/mapfiles/kml/paddle/red-circle.png",
    helicopter: "http://maps.google.com/mapfiles/kml/paddle/orange-circle.png",
  };
  return mapping[className.toLowerCase()] ?? "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png";
}

function exportCsv(features: DetectionFeature[]): Blob {
  const header =
    "detection_id,class,subclass,confidence,lat,lon,heading_degrees,timestamp,satellite_source\n";
  const rows = features.map((f) => {
    const p = f.properties;
    const esc = (v: string | number | null | undefined) => {
      const s = v == null ? "" : String(v);
      return s.includes(",") ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return [
      p.detection_id,
      p.class,
      p.subclass ?? "",
      p.confidence,
      p.lat,
      p.lon,
      p.heading_degrees ?? "",
      p.timestamp,
      p.satellite_source ?? "",
    ]
      .map(esc)
      .join(",");
  });
  return new Blob([header + rows.join("\n")], { type: "text/csv" });
}

function exportKml(features: DetectionFeature[]): Blob {
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<kml xmlns="http://www.opengis.net/kml/2.2">',
    "<Document>",
    "<name>Helios Detections</name>",
  ];
  for (const f of features) {
    const p = f.properties;
    lines.push(
      "<Placemark>",
      `<name>${p.class} (${p.confidence.toFixed(2)})</name>`,
      "<Style><IconStyle>",
      `<Icon><href>${classStyle(p.class)}</href></Icon>`,
      "</IconStyle></Style>",
      "<Point>",
      `<coordinates>${p.lon},${p.lat},0</coordinates>`,
      "</Point>",
      "</Placemark>"
    );
  }
  lines.push("</Document>", "</kml>");
  return new Blob([lines.join("\n")], { type: "application/vnd.google-earth.kml+xml" });
}

function exportGeoJson(features: DetectionFeature[]): Blob {
  const body = JSON.stringify({ type: "FeatureCollection", features }, null, 2);
  return new Blob([body], { type: "application/geo+json" });
}

function exportPdfHtml(features: DetectionFeature[]): Blob {
  const byClass: Record<string, number> = {};
  features.forEach((f) => {
    byClass[f.properties.class] = (byClass[f.properties.class] ?? 0) + 1;
  });
  const counts = Object.entries(byClass)
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");
  const rows = features
    .map(
      (f) => {
        const p = f.properties;
        return `<tr><td>${p.detection_id}</td><td>${p.class}</td><td>${(p.confidence * 100).toFixed(1)}%</td><td>${p.lat.toFixed(5)}</td><td>${p.lon.toFixed(5)}</td><td>${new Date(p.timestamp).toLocaleString()}</td></tr>`;
      }
    )
    .join("");
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Helios Mission Report</title>
<style>body{font-family:sans-serif;margin:2rem}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:12px}th{background:#333;color:#fff}</style>
</head><body><h1>Helios Mission Report</h1>
<p>Generated: ${new Date().toUTCString()}</p><p>Total detections: ${features.length}</p>
<p>${counts ? `Counts: ${counts}` : ""}</p>
<table><thead><tr><th>ID</th><th>Class</th><th>Conf</th><th>Lat</th><th>Lon</th><th>Time</th></tr></thead><tbody>${rows}</tbody></table>
<p><em>Print this page to PDF (Ctrl+P) for a portable report.</em></p></body></html>`;
  return new Blob([html], { type: "text/html" });
}

export async function exportDemoDetections(params: ExportQuery): Promise<Blob> {
  const { features } = await demoDetections();
  const filtered = filterForExport(features, params);
  switch (params.format) {
    case "csv":
      return exportCsv(filtered);
    case "kml":
      return exportKml(filtered);
    case "geojson":
      return exportGeoJson(filtered);
    case "pdf":
      return exportPdfHtml(filtered);
    default:
      throw new Error(`Unsupported format: ${params.format}`);
  }
}

/** File extension for demo export (PDF is HTML for print-to-PDF). */
export function demoExportExtension(format: ExportQuery["format"]): string {
  return format === "pdf" ? "html" : format === "geojson" ? "geojson" : format;
}
