export function SourcePicker({ imports, kind, setKind, selected, setSelected }) {
  return (
    <div className="source-picker">
      <label>
        Record type
        <select value={kind} onChange={(event) => setKind(event.target.value)}>
          <option value="inventory">Inventory</option>
          <option value="delivery">Delivery</option>
        </select>
      </label>
      <label>
        Dataset import
        <select
          value={selected?.import_id || ""}
          onChange={(event) => setSelected(event.target.value)}
        >
          {!selected && <option value="">Import a dataset to begin</option>}
          {imports
            .filter((item) => item.kind === kind)
            .map((item) => (
              <option key={item.import_id} value={item.import_id}>
                {item.source} · {item.accepted_rows.toLocaleString()} records
              </option>
            ))}
        </select>
      </label>
    </div>
  );
}
