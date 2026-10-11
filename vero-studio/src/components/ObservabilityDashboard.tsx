import React, { useState, useEffect } from 'react';
import { 
  DollarSign, 
  Coins, 
  ShieldCheck, 
  Clock, 
  Database, 
  RotateCcw, 
  ExternalLink, 
  Sparkles,
  Activity
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  CartesianGrid, 
  Legend 
} from 'recharts';

interface ObservabilityStats {
  total_queries: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  llm_spend_usd: number;
  warehouse_spend_usd: number;
  total_spend_usd: number;
  cost_guard_savings_usd: number;
  avg_latency_ms: number;
  active_dialect: string;
  rates: {
    bigquery_per_tb_usd?: number;
    snowflake_credit_usd?: number;
    snowflake_warehouse_size?: string;
    postgres_hourly_usd?: number;
  };
  top_expensive_queries: Array<{
    id: string;
    sql: string;
    duration_ms: number;
    row_count: number;
    status: string;
    error?: string;
    bytes_scanned?: number;
    cost_usd?: number;
    executed_at: string;
  }>;
  daily_breakdown: Array<{
    date: string;
    llm_cost: number;
    warehouse_cost: number;
    total_cost: number;
    query_count: number;
  }>;
}

interface ObservabilityDashboardProps {
  apiBase?: string;
  onOpenQueryInEditor?: (sql: string) => void;
}

export const ObservabilityDashboard: React.FC<ObservabilityDashboardProps> = ({
  apiBase = '',
  onOpenQueryInEditor
}) => {
  const [stats, setStats] = useState<ObservabilityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/observability/stats`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load stats`);
      const data = await res.json();
      setStats(data);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && !stats) {
    return (
      <div className="obs-loading-container">
        <Activity size={24} className="spin-icon" color="var(--accent-color)" />
        <span>Aggregating cloud warehouse spend & token telemetry...</span>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="obs-error-container">
        <span>Failed to load observability data: {error}</span>
        <button className="editor-tool-btn" onClick={fetchStats} style={{ marginTop: '12px' }}>
          <RotateCcw size={13} />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  const s = stats!;

  return (
    <div className="observability-page">
      {/* Header */}
      <div className="obs-header">
        <div>
          <h2 className="obs-title">Observability & Cost Intelligence</h2>
          <p className="obs-subtitle">
            Audit trail of AI model token consumption, cloud warehouse spend, and Cost Guard protection.
          </p>
        </div>
        <button 
          className="editor-tool-btn" 
          onClick={fetchStats} 
          disabled={loading}
          title="Refresh Observability Metrics"
        >
          <RotateCcw size={13} className={loading ? 'spin-icon' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="obs-kpi-grid">
        <div className="obs-kpi-card highlight">
          <div className="obs-kpi-header">
            <span className="obs-kpi-label">Total Spend</span>
            <DollarSign size={16} color="var(--accent-color)" />
          </div>
          <div className="obs-kpi-value">${s.total_spend_usd.toFixed(4)}</div>
          <div className="obs-kpi-subtext">
            <span>LLM: ${s.llm_spend_usd.toFixed(4)}</span> • <span>WH: ${s.warehouse_spend_usd.toFixed(4)}</span>
          </div>
        </div>

        <div className="obs-kpi-card">
          <div className="obs-kpi-header">
            <span className="obs-kpi-label">Cost Guard Savings</span>
            <ShieldCheck size={16} color="#10b981" />
          </div>
          <div className="obs-kpi-value" style={{ color: '#10b981' }}>
            ~${s.cost_guard_savings_usd.toFixed(4)}
          </div>
          <div className="obs-kpi-subtext">Prevented runaway full-table scans</div>
        </div>

        <div className="obs-kpi-card">
          <div className="obs-kpi-header">
            <span className="obs-kpi-label">Tokens Consumed</span>
            <Coins size={16} color="#a855f7" />
          </div>
          <div className="obs-kpi-value">{s.total_tokens.toLocaleString()}</div>
          <div className="obs-kpi-subtext">
            <span>{s.prompt_tokens.toLocaleString()} in</span> • <span>{s.completion_tokens.toLocaleString()} out</span>
          </div>
        </div>

        <div className="obs-kpi-card">
          <div className="obs-kpi-header">
            <span className="obs-kpi-label">Queries & Latency</span>
            <Clock size={16} color="#3b82f6" />
          </div>
          <div className="obs-kpi-value">{s.total_queries} runs</div>
          <div className="obs-kpi-subtext">Average: {s.avg_latency_ms}ms per query</div>
        </div>
      </div>

      {/* Spend Over Time Chart */}
      <div className="obs-section-card">
        <div className="obs-section-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={16} color="var(--accent-color)" />
            <h3 className="obs-section-title">Daily Cost Breakdown (LLM vs. Warehouse)</h3>
          </div>
          <span className="obs-stat-badge">{s.daily_breakdown.length} active days</span>
        </div>

        <div style={{ width: '100%', height: 260 }}>
          {s.daily_breakdown.length === 0 ? (
            <div className="obs-empty-chart">
              <span>No execution telemetry recorded yet. Ask analytical questions to populate spend trends.</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={s.daily_breakdown} margin={{ top: 15, right: 15, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" opacity={0.6} />
                <XAxis dataKey="date" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', borderRadius: '6px', fontSize: '12px' }} 
                  formatter={(val: any) => [`$${Number(val).toFixed(4)}`, '']}
                />
                <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--text-secondary)' }} />
                <Bar dataKey="llm_cost" name="LLM Inference ($)" stackId="a" fill="#8b5cf6" radius={[0, 0, 0, 0]} />
                <Bar dataKey="warehouse_cost" name="Warehouse Compute ($)" stackId="a" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Active Warehouse Rates & Cost Guard Config */}
      <div className="obs-section-card">
        <div className="obs-section-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={16} color="var(--accent-color)" />
            <h3 className="obs-section-title">Active Warehouse Rates & Guardrails</h3>
          </div>
          <span className="obs-stat-badge" style={{ textTransform: 'capitalize' }}>{s.active_dialect}</span>
        </div>

        <div className="obs-rates-grid">
          <div className="obs-rate-pill">
            <span className="rate-key">Dialect</span>
            <span className="rate-val" style={{ textTransform: 'uppercase' }}>{s.active_dialect}</span>
          </div>
          <div className="obs-rate-pill">
            <span className="rate-key">BigQuery On-Demand</span>
            <span className="rate-val">${s.rates.bigquery_per_tb_usd || 6.25} / TB</span>
          </div>
          <div className="obs-rate-pill">
            <span className="rate-key">Snowflake Warehouse</span>
            <span className="rate-val">{s.rates.snowflake_warehouse_size || 'X-Small'} (${s.rates.snowflake_credit_usd || 3.00}/cr)</span>
          </div>
          <div className="obs-rate-pill">
            <span className="rate-key">Postgres / RDS Compute</span>
            <span className="rate-val">${s.rates.postgres_hourly_usd || 0.10} / hr</span>
          </div>
          <div className="obs-rate-pill">
            <span className="rate-key">Cost Guard Threshold</span>
            <span className="rate-val" style={{ color: 'var(--accent-color)' }}>10 GB / query</span>
          </div>
        </div>
      </div>

      {/* Top 5 Most Expensive Queries Table */}
      <div className="obs-section-card">
        <div className="obs-section-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={16} color="var(--accent-color)" />
            <h3 className="obs-section-title">Top Expensive Queries (Audit Log)</h3>
          </div>
          <span className="obs-stat-badge">Top {s.top_expensive_queries.length}</span>
        </div>

        {s.top_expensive_queries.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
            No executed queries recorded yet.
          </div>
        ) : (
          <div className="table-wrapper" style={{ overflowX: 'auto', width: '100%' }}>
            <table className="data-table" style={{ minWidth: '580px', width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ width: '40%' }}>SQL Query</th>
                  <th>Status</th>
                  <th>Scan Volume</th>
                  <th>Duration</th>
                  <th>Cost (USD)</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {s.top_expensive_queries.map((q, idx) => (
                  <tr key={idx}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11.5px', maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {q.sql}
                    </td>
                    <td>
                      <span className={`status-pill ${q.status === 'success' ? 'active' : 'error'}`}>
                        {q.status}
                      </span>
                    </td>
                    <td>{q.bytes_scanned ? `${(q.bytes_scanned / (1024 * 1024)).toFixed(1)} MB` : 'In-memory'}</td>
                    <td>{q.duration_ms}ms</td>
                    <td style={{ fontWeight: 600, color: 'var(--accent-color)' }}>
                      ${(q.cost_usd || 0).toFixed(4)}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {onOpenQueryInEditor && (
                        <button 
                          className="editor-tool-btn" 
                          onClick={() => onOpenQueryInEditor(q.sql)}
                          title="Open query in SQL Studio"
                          style={{ padding: '3px 8px', fontSize: '11px' }}
                        >
                          <ExternalLink size={11} />
                          <span>Studio</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
