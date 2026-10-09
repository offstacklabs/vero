import React, { useState } from 'react';
import { Table as TableIcon, ChevronRight, ChevronDown, Eye, MessageSquare, Key } from 'lucide-react';

export interface TableEntity {
  table: string;
  content: string;
}

interface SchemaTreeProps {
  schemas: TableEntity[];
  selectedTable: string | null;
  onSelectTable: (schema: TableEntity) => void;
  onPreviewTable: (tableName: string) => void;
  onQueryTable: (tableName: string) => void;
}

export const SchemaTree: React.FC<SchemaTreeProps> = ({
  schemas,
  selectedTable,
  onSelectTable,
  onPreviewTable,
  onQueryTable
}) => {
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});

  const toggleExpand = (tableName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedTables(prev => ({ ...prev, [tableName]: !prev[tableName] }));
  };

  const parseColumnsFromMarkdown = (content: string) => {
    const lines = content.split('\n');
    const cols: { name: string; type: string }[] = [];
    let inTable = false;
    for (const line of lines) {
      if (line.includes('| Column Name | Data Type |')) {
        inTable = true;
        continue;
      }
      if (inTable && line.startsWith('| `')) {
        const parts = line.split('|').map(s => s.trim()).filter(Boolean);
        if (parts.length >= 2) {
          const colName = parts[0].replace(/`/g, '');
          const colType = parts[1].replace(/`/g, '');
          cols.push({ name: colName, type: colType });
        }
      }
    }
    return cols;
  };

  return (
    <div className="schema-tree-container">
      {schemas.map(s => {
        const isSelected = selectedTable === s.table;
        const isExpanded = !!expandedTables[s.table];
        const columns = parseColumnsFromMarkdown(s.content);

        return (
          <div key={s.table} className="schema-tree-node">
            <div 
              className={`schema-node-row ${isSelected ? 'active' : ''}`}
              onClick={() => onSelectTable(s)}
            >
              <div 
                className="expand-arrow" 
                onClick={(e) => toggleExpand(s.table, e)}
              >
                {isExpanded ? <ChevronDown size={13} color="#8b949e" /> : <ChevronRight size={13} color="#8b949e" />}
              </div>

              <TableIcon size={14} color="#58a6ff" />
              <span className="schema-node-name">{s.table}</span>

              <div className="schema-node-hover-actions">
                <button
                  className="schema-node-action-btn"
                  title="Preview 10 rows"
                  onClick={(e) => {
                    e.stopPropagation();
                    onPreviewTable(s.table);
                  }}
                >
                  <Eye size={12} />
                </button>
                <button
                  className="schema-node-action-btn"
                  title="Query with Vero"
                  onClick={(e) => {
                    e.stopPropagation();
                    onQueryTable(s.table);
                  }}
                >
                  <MessageSquare size={12} />
                </button>
              </div>
            </div>

            {isExpanded && columns.length > 0 && (
              <div className="schema-node-children">
                {columns.map(col => (
                  <div key={col.name} className="schema-column-row">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {col.name.endsWith('id') ? (
                        <Key size={11} color="#d29922" />
                      ) : (
                        <span className="column-bullet">•</span>
                      )}
                      <span className="column-name">{col.name}</span>
                    </div>
                    <span className="column-type-badge">{col.type}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
