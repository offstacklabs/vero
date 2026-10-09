import React, { useState } from 'react';
import { Play, TerminalSquare } from 'lucide-react';

interface ScratchpadProps {
  onExecute: (sql: string) => void;
  loading: boolean;
}

export const Scratchpad: React.FC<ScratchpadProps> = ({ onExecute, loading }) => {
  const [sql, setSql] = useState('SELECT * FROM sqlite_master LIMIT 10;');

  return (
    <div className="scratchpad-container">
      <div className="scratchpad-header">
        <TerminalSquare size={16} />
        <span>SQL Scratchpad</span>
      </div>
      <textarea
        className="sql-editor"
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        placeholder="Write your raw SQL query here..."
        spellCheck={false}
      />
      <div className="scratchpad-actions">
        <button
          className="send-btn"
          onClick={() => onExecute(sql)}
          disabled={loading || !sql.trim()}
        >
          <Play size={14} />
          <span>{loading ? 'Executing...' : 'Run Query'}</span>
        </button>
      </div>
    </div>
  );
};
