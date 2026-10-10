import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronRight, 
  CheckCircle2, 
  Database, 
  Clock, 
  Brain, 
  Wrench, 
  AlertTriangle, 
  Zap,
  Coins,
  DollarSign,
  Activity
} from 'lucide-react';

export interface ReflectionStep {
  attempt: number;
  failed_sql: string;
  error: string;
  thought?: string;
}

export interface ExecutionTelemetry {
  model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  llm_cost_usd?: number;
  warehouse_cost_usd?: number;
  total_cost_usd?: number;
  spans?: {
    retrieval_ms?: number;
    llm_ms?: number;
    ast_ms?: number;
    warehouse_ms?: number;
    total_ms?: number;
  };
}

interface ReasoningStepsProps {
  thought?: string;
  tablesUsed?: string[];
  durationMs?: number;
  dialect?: string;
  reflectionSteps?: ReflectionStep[];
  bytesFormatted?: string;
  costUsd?: number;
  telemetry?: ExecutionTelemetry;
  cacheHit?: boolean;
}

export const ReasoningSteps: React.FC<ReasoningStepsProps> = ({
  thought,
  tablesUsed = [],
  durationMs,
  dialect = 'BigQuery',
  reflectionSteps = [],
  bytesFormatted,
  costUsd,
  telemetry,
  cacheHit
}) => {
  const [expanded, setExpanded] = useState(false);

  if (!thought && (!tablesUsed || tablesUsed.length === 0) && reflectionSteps.length === 0 && !telemetry) return null;

  return (
    <div className="reasoning-trace-card">
      <div className="reasoning-trace-header" onClick={() => setExpanded(!expanded)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {expanded ? <ChevronDown size={14} color="#58a6ff" /> : <ChevronRight size={14} color="#58a6ff" />}
          <Brain size={14} color="#58a6ff" />
          <span className="reasoning-title">Context Grounding & Agent Trace</span>
        </div>

        <div className="reasoning-badges">
          {cacheHit && (
            <span className="trace-pill" style={{ color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.3)', backgroundColor: 'rgba(16, 185, 129, 0.1)', fontWeight: 600 }}>
              <Zap size={11} />
              <span>Cached</span>
            </span>
          )}
          {reflectionSteps && reflectionSteps.length > 0 && (
            <span className="trace-pill" style={{ color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.3)', backgroundColor: 'rgba(245, 158, 11, 0.1)' }}>
              <Wrench size={11} />
              <span>Self-Healed ({reflectionSteps.length})</span>
            </span>
          )}
          {telemetry && telemetry.total_tokens !== undefined && telemetry.total_tokens > 0 && (
            <span className="trace-pill" title={`LLM Tokens: ${telemetry.prompt_tokens} prompt + ${telemetry.completion_tokens} completion (~$${telemetry.llm_cost_usd?.toFixed(4)})`}>
              <Coins size={11} color="var(--accent-color)" />
              <span>{telemetry.total_tokens.toLocaleString()} tok</span>
            </span>
          )}
          {telemetry && telemetry.total_cost_usd !== undefined && telemetry.total_cost_usd > 0 && (
            <span className="trace-pill success" title={`End-to-End Cost: LLM ($${telemetry.llm_cost_usd?.toFixed(4)}) + Warehouse ($${telemetry.warehouse_cost_usd?.toFixed(4)})`}>
              <DollarSign size={11} />
              <span>${telemetry.total_cost_usd.toFixed(4)}</span>
            </span>
          )}
          {bytesFormatted && bytesFormatted !== '0 B' && (
            <span className="trace-pill" title="Warehouse scan estimate">
              <Zap size={11} color="var(--accent-color)" />
              <span>{bytesFormatted}</span>
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
              <div className="step-label">SQL Execution Sandbox & Cost Guard</div>
              <div className="step-desc">
                Executed in read-only sandbox ({dialect}) in {durationMs ? `${durationMs}ms` : '< 20ms'}. 
                {bytesFormatted && bytesFormatted !== '0 B' ? ` Dry run verified scan size: ${bytesFormatted}${costUsd ? ` (~$${costUsd.toFixed(4)})` : ''}.` : ' AST safety verified.'}
              </div>
            </div>
          </div>

          {/* End-to-End Observability & Latency Waterfall */}
          {telemetry && (
            <div className="trace-step" style={{ borderLeft: '2px solid var(--accent-color)', paddingLeft: '8px' }}>
              <div className="step-dot" style={{ backgroundColor: 'var(--accent-color)' }}></div>
              <div className="step-body">
                <div className="step-label" style={{ color: 'var(--accent-color)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Activity size={12} />
                  <span>Observability & Cost Breakdown</span>
                </div>
                <div className="step-desc" style={{ marginTop: '4px' }}>
                  <div>
                    <strong>LLM Inference:</strong> {telemetry.model || 'model'} • {telemetry.prompt_tokens?.toLocaleString()} in / {telemetry.completion_tokens?.toLocaleString()} out ({telemetry.total_tokens?.toLocaleString()} total tokens) • 
                    <span style={{ color: 'var(--accent-color)', fontWeight: 600 }}> ~${telemetry.llm_cost_usd?.toFixed(4)}</span>
                  </div>
                  {telemetry.warehouse_cost_usd !== undefined && telemetry.warehouse_cost_usd > 0 && (
                    <div style={{ marginTop: '2px' }}>
                      <strong>Warehouse Scan:</strong> {bytesFormatted || '0 B'} • 
                      <span style={{ color: 'var(--accent-color)', fontWeight: 600 }}> ~${telemetry.warehouse_cost_usd?.toFixed(4)}</span>
                    </div>
                  )}
                  {telemetry.spans && (
                    <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                      <strong>Latency Waterfall:</strong> LLM: {telemetry.spans.llm_ms || 0}ms • AST: {telemetry.spans.ast_ms || 0}ms • Warehouse: {telemetry.spans.warehouse_ms || 0}ms • Total: {telemetry.spans.total_ms || 0}ms
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
