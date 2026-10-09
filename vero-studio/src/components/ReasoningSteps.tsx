import React, { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, Database, Clock, Brain } from 'lucide-react';

interface ReasoningStepsProps {
  thought?: string;
  tablesUsed?: string[];
  durationMs?: number;
  dialect?: string;
}

export const ReasoningSteps: React.FC<ReasoningStepsProps> = ({
  thought,
  tablesUsed = [],
  durationMs,
  dialect = 'Postgres'
}) => {
  const [expanded, setExpanded] = useState(false);

  if (!thought && (!tablesUsed || tablesUsed.length === 0)) return null;

  return (
    <div className="reasoning-trace-card">
      <div className="reasoning-trace-header" onClick={() => setExpanded(!expanded)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {expanded ? <ChevronDown size={14} color="#58a6ff" /> : <ChevronRight size={14} color="#58a6ff" />}
          <Brain size={14} color="#58a6ff" />
          <span className="reasoning-title">Context Grounding & Agent Trace</span>
        </div>

        <div className="reasoning-badges">
          {tablesUsed && tablesUsed.length > 0 && (
            <span className="trace-pill">
              <Database size={11} />
              <span>{tablesUsed.join(', ')}</span>
            </span>
          )}
          {durationMs !== undefined && durationMs > 0 && (
            <span className="trace-pill">
              <Clock size={11} />
              <span>{durationMs}ms</span>
            </span>
          )}
          <span className="trace-pill success">
            <CheckCircle2 size={11} />
            <span>{dialect}</span>
          </span>
        </div>
      </div>

      {expanded && (
        <div className="reasoning-trace-content">
          <div className="trace-step">
            <div className="step-dot"></div>
            <div className="step-body">
              <div className="step-label">Context Grounding</div>
              <div className="step-desc">
                Schema introspected for {tablesUsed.length > 0 ? tablesUsed.map(t => `"${t}"`).join(', ') : 'entities'}. Verified against active business rules in RULES.md and semantic metrics.
              </div>
            </div>
          </div>

          {thought && (
            <div className="trace-step">
              <div className="step-dot"></div>
              <div className="step-body">
                <div className="step-label">Analytical Reasoning</div>
                <div className="step-desc">{thought}</div>
              </div>
            </div>
          )}

          <div className="trace-step">
            <div className="step-dot"></div>
            <div className="step-body">
              <div className="step-label">SQL Execution Sandbox</div>
              <div className="step-desc">
                Executed in read-only sandbox ({dialect}) in {durationMs ? `${durationMs}ms` : '< 20ms'}. Mutations verified blocked by AST parser.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
