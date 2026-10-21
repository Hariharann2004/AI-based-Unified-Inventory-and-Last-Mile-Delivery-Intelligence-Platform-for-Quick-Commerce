import { WorkbenchIcon } from "./WorkbenchIcon.jsx";

export function PageIntro({ eyebrow, title, description, icon, mode, context, children }) {
  return (
    <div className="page-intro">
      <div className="intro-copy">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="intro-context">
        <span className="intro-symbol">
          <WorkbenchIcon name={icon} />
        </span>
        <div>
          <strong>{mode}</strong>
          <p>{context}</p>
        </div>
        {children}
      </div>
    </div>
  );
}

export function PanelHeading({ icon, eyebrow, title, description, id, children }) {
  return (
    <div className="panel-heading">
      <span className="panel-symbol">
        <WorkbenchIcon name={icon} />
      </span>
      <div className="panel-heading-copy">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2 id={id}>{title}</h2>
        {description && <p className="muted">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function WorkflowGuide({ steps, label }) {
  return (
    <ol className="workflow-guide" aria-label={label}>
      {steps.map((step, index) => (
        <li key={step.title}>
          <a href={step.href}>
            <span className="workflow-number">0{index + 1}</span>
            <div>
              <strong>{step.title}</strong>
              <small>{step.description}</small>
            </div>
            <WorkbenchIcon name="arrow" />
          </a>
        </li>
      ))}
    </ol>
  );
}

export function MetricCard({ icon, label, tone = "teal", children }) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="metric-caption">
        <WorkbenchIcon name={icon} />
        <span>{label}</span>
      </div>
      <strong>{children}</strong>
    </div>
  );
}
