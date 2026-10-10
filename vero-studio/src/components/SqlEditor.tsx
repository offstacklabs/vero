import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Copy, Check, Table as TableIcon, BarChart3, Clock, Layers, History, ArrowRight } from 'lucide-react';
import { DataTable } from './DataTable';
import { ChartVisualizer } from './ChartVisualizer';

interface QueryRun {
  id: string;
  sql: string;
  duration_ms: number;
  row_count: number;
  status: string;
  error?: string;
  executed_at: string;
}

interface SqlEditorProps {
  initialSql?: string;
  dialect?: string;
  onExecute: (sql: string) => Promise<{ data: any; duration_ms?: number } | void>;
  loading: boolean;
  apiBase?: string;
}

export const SqlEditor: React.FC<SqlEditorProps> = ({
  initialSql = 'SELECT * FROM customers LIMIT 10;',
  dialect = 'Postgres',
  onExecute,
  loading,
  apiBase = ''
}) => {
  const [sql, setSql] = useState(initialSql);
  const [prevInitialSql, setPrevInitialSql] = useState(initialSql);
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'table' | 'chart' | 'history'>('table');
  const [queryRuns, setQueryRuns] = useState<QueryRun[]>([]);

  if (initialSql !== prevInitialSql) {
    setPrevInitialSql(initialSql);
    setSql(initialSql);
  }

  const fetchHistory = () => {
    fetch(`${apiBase}/api/history/queries`)
      .then(res => res.json())
      .then(data => {
        if (data.runs) setQueryRuns(data.runs);
      })
      .catch(() => console.error("Could not fetch query history"));
  };

  useEffect(() => {
    if (viewMode === 'history') {
      fetchHistory();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode]);

  const handleRun = async () => {
    if (!sql.trim() || loading) return;
    const res = await onExecute(sql);
    if (res && res.data) {
      setResult(res.data);
      if (res.duration_ms) setDuration(res.duration_ms);
    }
    fetchHistory();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleRun();
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="studio-editor-container">
      {/* Editor Header */}
      <div className="studio-editor-toolbar">
        <div className="editor-left-tools">
          <button 
            className="editor-run-btn"
            onClick={handleRun}
            disabled={loading || !sql.trim()}
          >
            <Play size={13} fill={loading ? 'none' : 'currentColor'} />
            <span>{loading ? 'Running...' : 'Run'}</span>
            <kbd className="cmd-kbd">⌘↵</kbd>
          </button>

          <button className="editor-tool-btn" onClick={handleCopy} title="Copy SQL">
            {copied ? <Check size={13} color="#3fb950" /> : <Copy size={13} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>

          <button className="editor-tool-btn" onClick={() => setSql('')} title="Clear Editor">
            <RotateCcw size={13} />
            <span>Clear</span>
          </button>
        </div>

        <div className="editor-right-tools">
          {duration !== null && (
            <span className="editor-stat-pill">
              <Clock size={12} />
              <span>{duration}ms</span>
            </span>
          )}
          {result && (
            <span className="editor-stat-pill">
              <Layers size={12} />
              <span>{result.row_count || result.rows?.length || 0} rows</span>
            </span>
          )}
          <span className="editor-dialect-pill">
            {dialect}
          </span>
          <button 
            className={`editor-tool-btn ${viewMode === 'history' ? 'active' : ''}`}
            onClick={() => setViewMode(viewMode === 'history' ? (result ? 'table' : 'chart') : 'history')}
            title="Toggle Query Execution History"
          >
            <History size={12} />
            <span>History</span>
          </button>
        </div>
      </div>

      {/* Editor Body */}
      <div className="studio-editor-codearea">
        <textarea
          className="studio-sql-textarea"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="-- Write query against warehouse..."
          spellCheck={false}
        />
      </div>

      {/* Editor Output Canvas */}
      {(result || viewMode === 'history') && (
        <div className="studio-editor-output">
          <div className="output-header-bar">
            <div className="output-tab-group">
              {result && (
                <>
                  <button 
                    className={`output-tab ${viewMode === 'table' ? 'active' : ''}`}
                    onClick={() => setViewMode('table')}
                  >
                    <TableIcon size={13} />
                    <span>Result Table</span>
                  </button>
                  <button 
                    className={`output-tab ${viewMode === 'chart' ? 'active' : ''}`}
                    onClick={() => setViewMode('chart')}
                  >
                    <BarChart3 size={13} />
                    <span>Visualizer</span>
                  </button>
                </>
              )}
              <button 
                className={`output-tab ${viewMode === 'history' ? 'active' : ''}`}
                onClick={() => setViewMode('history')}
              >
                <History size={13} />
                <span>Run History ({queryRuns.length})</span>
              </button>
            </div>
          </div>

          <div className="output-content-area">
            {viewMode === 'table' && result && (
              <DataTable columns={result.columns} rows={result.rows} tableName="scratchpad_export" />
            )}
            {viewMode === 'chart' && result && (
              <div style={{ padding: '16px' }}>
                <ChartVisualizer type="bar" data={result} />
              </div>
            )}
            {viewMode === 'history' && (
              <div style={{ padding: '16px' }}>
                {queryRuns.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                    No executed queries yet. Run a query using ⌘↵ to start tracking execution history.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {queryRuns.map(run => (
                      <div 
                        key={run.id} 
                        style={{ 
                          display: 'flex', 
                          justifyContent: 'space-between', 
                          alignItems: 'center', 
                          backgroundColor: 'var(--bg-tertiary)', 
                          padding: '10px 14px', 
                          borderRadius: '6px', 
                          border: '1px solid var(--border-color)' 
                        }}
                      >
                        <div style={{ flex: 1, marginRight: '12px', minWidth: 0 }}>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12.5px', color: 'var(--code-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {run.sql}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', gap: '10px', marginTop: '4px' }}>
                            <span>{run.duration_ms}ms</span>
                            <span>•</span>
                            <span>{run.row_count} rows</span>
                            <span>•</span>
                            <span style={{ color: run.status === 'success' ? 'var(--success-color)' : 'var(--danger-color)' }}>
                              {run.status}
                            </span>
                            <span>•</span>
                            <span>{run.executed_at.slice(11, 19)}</span>
                          </div>
                        </div>
                        <button
                          className="editor-tool-btn"
                          onClick={() => { setSql(run.sql); }}
                          title="Load this query into editor"
                        >
                          <ArrowRight size={12} />
                          <span>Load</span>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
