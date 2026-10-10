import React, { useState } from 'react';
import { Copy, Check, ExternalLink, Database, Clock, Layers, Pin, Zap, Coins } from 'lucide-react';

interface SqlCardProps {
  sql: string;
  durationMs?: number;
  rowCount?: number;
  dialect?: string;
  bytesFormatted?: string;
  costUsd?: number;
  costGuardPassed?: boolean;
  totalTokens?: number;
  onOpenInEditor?: (sql: string) => void;
  onPin?: () => void;
}

export const SqlCard: React.FC<SqlCardProps> = ({
  sql,
  durationMs,
  rowCount,
  dialect = 'BigQuery',
  bytesFormatted,
  costUsd,
  costGuardPassed,
  totalTokens,
  onOpenInEditor,
  onPin
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="generated-sql-card">
      <div className="sql-card-header">
        <div className="sql-card-stats">
          <span className="sql-stat-tag">
            <Database size={11} />
            <span>{dialect}</span>
          </span>
          {totalTokens !== undefined && totalTokens > 0 && (
            <span className="sql-stat-tag" title="LLM Tokens consumed">
              <Coins size={11} />
              <span>{totalTokens.toLocaleString()} tok</span>
            </span>
          )}
          {bytesFormatted && bytesFormatted !== '0 B' && (
            <span className="sql-stat-tag" title="Projected Warehouse Scan & Cost">
              <Zap size={11} color={costGuardPassed === false ? '#f85149' : 'var(--accent-color)'} />
              <span>{bytesFormatted} {costUsd !== undefined && costUsd > 0 ? `($${costUsd.toFixed(4)})` : ''}</span>
            </span>
          )}
          {durationMs !== undefined && durationMs > 0 && (
            <span className="sql-stat-tag">
              <Clock size={11} />
              <span>{durationMs}ms</span>
            </span>
          )}
          {rowCount !== undefined && (
            <span className="sql-stat-tag">
              <Layers size={11} />
              <span>{rowCount} rows</span>
            </span>
          )}
        </div>

        <div className="sql-card-actions">
          {onPin && (
            <button className="sql-action-btn" onClick={onPin} title="Pin to Dashboard">
              <Pin size={12} />
              <span>Pin</span>
            </button>
          )}
          <button className="sql-action-btn" onClick={handleCopy} title="Copy SQL">
            {copied ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
          {onOpenInEditor && (
            <button 
              className="sql-action-btn highlight" 
              onClick={() => onOpenInEditor(sql)}
              title="Open and edit in SQL Studio"
            >
              <ExternalLink size={12} />
              <span>Open in Studio</span>
            </button>
          )}
        </div>
      </div>

      <pre className="sql-card-body">
        <code>{sql}</code>
      </pre>
    </div>
  );
};
