import React, { useState } from 'react';
import { Play, RotateCcw, Copy, Check, Table as TableIcon, BarChart3, Clock, Layers } from 'lucide-react';
import { DataTable } from './DataTable';
import { ChartVisualizer } from './ChartVisualizer';

interface SqlEditorProps {
  initialSql?: string;
  dialect?: string;
  onExecute: (sql: string) => Promise<{ data: any; duration_ms?: number } | void>;
  loading: boolean;
}

export const SqlEditor: React.FC<SqlEditorProps> = ({
  initialSql = 'SELECT * FROM customers LIMIT 10;',
  dialect = 'Postgres',
  onExecute,
  loading
}) => {
  const [sql, setSql] = useState(initialSql);
  const [prevInitialSql, setPrevInitialSql] = useState(initialSql);
  const [copied, setCopied] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table');

  if (initialSql !== prevInitialSql) {
    setPrevInitialSql(initialSql);
    setSql(initialSql);
  }

  const handleRun = async () => {
    if (!sql.trim() || loading) return;
    const res = await onExecute(sql);
    if (res && res.data) {
      setResult(res.data);
      if (res.duration_ms) setDuration(res.duration_ms);
    }
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
    <div className="cursor-editor-container">
      {/* Editor Header */}
      <div className="cursor-editor-toolbar">
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
        </div>
      </div>

      {/* Editor Body */}
      <div className="cursor-editor-codearea">
        <textarea
          className="cursor-sql-textarea"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="-- Write query against warehouse..."
          spellCheck={false}
        />
      </div>

      {/* Editor Output Canvas */}
      {result && (
        <div className="cursor-editor-output">
          <div className="output-header-bar">
            <div className="output-tab-group">
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
            </div>
          </div>

          <div className="output-content-area">
            {viewMode === 'table' ? (
              <DataTable columns={result.columns} rows={result.rows} tableName="scratchpad_export" />
            ) : (
              <div style={{ padding: '16px' }}>
                <ChartVisualizer type="bar" data={result} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
