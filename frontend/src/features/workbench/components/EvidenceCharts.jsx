export function ComparisonBars({ values, unit = "units", title }) {
  const maximum = Math.max(1, ...values.map((value) => value.value));
  return (
    <figure className="evidence-chart">
      <figcaption>{title}</figcaption>
      {values.map((value) => (
        <div className="comparison-row" key={value.label}>
          <div>
            <span>{value.label}</span>
            <strong>
              {value.value.toLocaleString()} {unit}
            </strong>
          </div>
          <div className="bar-track" aria-hidden="true">
            <div
              className={`bar-fill ${value.tone || ""}`}
              style={{ width: `${(Math.max(0, value.value) / maximum) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </figure>
  );
}

export function EvidencePlot({ points, xLabel, yLabel, title, bounded = false }) {
  if (!points.length) return <p>No plot evidence for this test window.</p>;
  const maximum = bounded
    ? 1
    : Math.max(1, ...points.flatMap((point) => [point.x, point.y])) * 1.08;
  const x = (value) => 85 + (value / maximum) * 475;
  const y = (value) => 260 - (value / maximum) * 200;
  return (
    <figure className="evidence-chart">
      <figcaption>{title}</figcaption>
      <svg
        className="evidence-plot"
        viewBox="0 0 640 345"
        role="img"
        aria-label={`${title}. Horizontal axis: ${xLabel}. Vertical axis: ${yLabel}. ${points.length} sampled points.`}
      >
        <line x1="85" y1="60" x2="85" y2="260" className="axis" />
        <line x1="85" y1="260" x2="560" y2="260" className="axis" />
        {[0, 0.5, 1].map((fraction) => (
          <g key={fraction}>
            <text x={x(maximum * fraction)} y="294" textAnchor="middle">
              {(maximum * fraction).toFixed(bounded ? 1 : 0)}
            </text>
            <text x="72" y={y(maximum * fraction) + 7} textAnchor="end">
              {(maximum * fraction).toFixed(bounded ? 1 : 0)}
            </text>
          </g>
        ))}
        {!bounded && (
          <line x1={x(0)} y1={y(0)} x2={x(maximum)} y2={y(maximum)} className="reference" />
        )}
        {bounded && (
          <polyline
            points={points.map((point) => `${x(point.x)},${y(point.y)}`).join(" ")}
            className="curve"
          />
        )}
        {points.map((point, index) => (
          <circle key={index} cx={x(point.x)} cy={y(point.y)} r="4" className="plot-dot">
            <title>{`${xLabel}: ${point.x.toFixed(2)}; ${yLabel}: ${point.y.toFixed(2)}`}</title>
          </circle>
        ))}
        <text x="325" y="332" textAnchor="middle">
          {xLabel}
        </text>
        <text transform="translate(27,165) rotate(-90)" textAnchor="middle">
          {yLabel}
        </text>
      </svg>
      <details>
        <summary>Accessible plot data</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{xLabel}</th>
                <th>{yLabel}</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point, index) => (
                <tr key={index}>
                  <td>{point.x.toFixed(3)}</td>
                  <td>{point.y.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

export function ConfusionMatrix({ matrix }) {
  return (
    <figure className="evidence-chart">
      <figcaption>Risk classification · test outcomes</figcaption>
      <table className="confusion">
        <thead>
          <tr>
            <th>Actual / predicted</th>
            <th>No risk</th>
            <th>Risk</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th>No risk</th>
            <td className="correct">{matrix[0][0]}</td>
            <td className="incorrect">{matrix[0][1]}</td>
          </tr>
          <tr>
            <th>Risk</th>
            <td className="incorrect">{matrix[1][0]}</td>
            <td className="correct">{matrix[1][1]}</td>
          </tr>
        </tbody>
      </table>
      <p className="muted">Off-diagonal cells are false alarms and missed risks.</p>
    </figure>
  );
}
