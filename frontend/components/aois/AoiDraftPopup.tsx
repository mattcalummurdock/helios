"use client";

type Props = {
  name: string;
  priority: "high" | "medium" | "low";
  saving: boolean;
  error: string | null;
  onNameChange: (value: string) => void;
  onPriorityChange: (value: "high" | "medium" | "low") => void;
  onSave: () => void;
  onCancel: () => void;
};

export function AoiDraftPopup({
  name,
  priority,
  saving,
  error,
  onNameChange,
  onPriorityChange,
  onSave,
  onCancel,
}: Props) {
  return (
    <div
      className="aoi-draft-popup"
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <h4>New Area of Interest</h4>
      <p className="aoi-draft-popup-hint">Enter details for the shape you drew.</p>
      <label>
        Name
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="e.g. Kyiv staging area"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter") onSave();
          }}
        />
      </label>
      <label>
        Priority
        <select
          value={priority}
          onChange={(e) => onPriorityChange(e.target.value as typeof priority)}
        >
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </label>
      {error && <p className="aoi-draft-popup-error">{error}</p>}
      <div className="aoi-draft-popup-actions">
        <button type="button" onClick={onCancel} disabled={saving}>
          Discard
        </button>
        <button type="button" className="primary" onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save AOI"}
        </button>
      </div>
    </div>
  );
}
