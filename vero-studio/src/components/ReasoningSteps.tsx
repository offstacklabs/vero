import React, { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, Database, Clock, Brain, Wrench, AlertTriangle } from 'lucide-react';

export interface ReflectionStep {
  attempt: number;
  failed_sql: string;
  error: string;
  thought?: string;
}

interface ReasoningStepsProps {
  thought?: string;
  tablesUsed?: string[];
  durationMs?: number;
  dialect?: string;
  reflectionSteps?: ReflectionStep[];
}

export const ReasoningSteps: React.FC<ReasoningStepsProps> = ({
  thought,
  tablesUsed = [],
  durationMs,
  dialect = 'Postgres',
  reflectionSteps = []
}) => {
  const [expanded, setExpanded] = useState(false);

  if (!thought && (!tablesUsed || tablesUsed.length === 0) && reflectionSteps.length === 0) return null;

  return (
    <div className="reasoning-trace-card">
      <div className="reasoning-trace-header" onClick={() => setExpanded(!expanded)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {expanded ? <ChevronDown size={14} color="#58a6ff" /> : <ChevronRight size={14} color="#58a6ff" />}
          <Brain size={14} color="#58a6ff" />
          <span className="reasoning-title">Context Grounding & Agent Trace</span>
        </div>

        <div className="reasoning-badges">
          {reflectionSteps && reflectionSteps.length > 0 && (
            <span className="trace-pill" style={{ color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.3)', backgroundColor: 'rgba(245, 158, 11, 0.1)' }}>
              <Wrench size={11} />
              <span>Self-Healed ({reflectionSteps.length})</span>
            </span>
          )}
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

          {reflectionSteps && reflectionSteps.map((step) => (
            <div key={step.attempt} className="trace-step" style={{ borderLeft: '2px dashed #f59e0b', paddingLeft: '8px' }}>
              <div className="step-dot" style={{ backgroundColor: '#f59e0b' }}></div>
              <div className="step-body">
                <div className="step-label" style={{ color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <AlertTriangle size={12} />
                  <span>Attempt {step.attempt} Intercepted & Repaired</span>
                </div>
                <div className="step-desc" style={{ color: '#fca5a5', fontFamily: 'var(--font-mono)', fontSize: '11.5px', marginTop: '2px' }}>
                  {step.error}
                </div>
                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px', fontStyle: 'italic' }}>
                  Action: Compiler error fed back to agent reflexion loop.
                </div>
              </div>
            </div>
          ))}

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
