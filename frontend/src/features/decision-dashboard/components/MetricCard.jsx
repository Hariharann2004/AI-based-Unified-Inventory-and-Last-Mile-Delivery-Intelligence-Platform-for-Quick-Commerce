function formatLabel(value) {
  return value.replaceAll("_", " ");
}

export function MetricCard({ title, values }) {
  return (
    <article>
      <h2>{title}</h2>
      {Object.entries(values).map(([key, value]) => (
        <p key={key}>
          <span>{formatLabel(key)}</span>
          <strong>{String(value)}</strong>
        </p>
      ))}
    </article>
  );
}
