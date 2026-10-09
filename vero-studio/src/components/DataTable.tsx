import React, { useState, useMemo } from 'react';
import { Download, Search, ArrowUpDown } from 'lucide-react';

interface DataTableProps {
  columns: string[];
  rows: any[][];
  tableName?: string;
}

export const DataTable: React.FC<DataTableProps> = ({ columns, rows, tableName = 'query_results' }) => {
  const [filter, setFilter] = useState('');
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  const filteredRows = useMemo(() => {
    let result = rows;
    if (filter.trim()) {
      const q = filter.toLowerCase();
      result = result.filter(row => 
        row.some(cell => String(cell).toLowerCase().includes(q))
      );
    }
    if (sortCol !== null) {
      result = [...result].sort((a, b) => {
        const valA = a[sortCol];
        const valB = b[sortCol];
        if (typeof valA === 'number' && typeof valB === 'number') {
          return sortAsc ? valA - valB : valB - valA;
        }
        return sortAsc 
          ? String(valA).localeCompare(String(valB)) 
          : String(valB).localeCompare(String(valA));
      });
    }
    return result;
  }, [rows, filter, sortCol, sortAsc]);

  const handleSort = (colIndex: number) => {
    if (sortCol === colIndex) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(colIndex);
      setSortAsc(true);
    }
  };

  const exportCSV = () => {
    const csvContent = [
      columns.join(','),
      ...rows.map(row => 
        row.map(cell => {
          const str = String(cell ?? '');
          return str.includes(',') ? `"${str.replace(/"/g, '""')}"` : str;
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `${tableName}_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="rich-datatable-container">
      <div className="datatable-toolbar">
        <div className="datatable-search">
          <Search size={14} color="#8b949e" />
          <input
            type="text"
            placeholder={`Filter ${rows.length} rows...`}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <div className="datatable-actions">
          <span className="row-count-badge">
            {filteredRows.length} of {rows.length} rows
          </span>
          <button className="csv-export-btn" onClick={exportCSV} title="Export to CSV">
            <Download size={13} />
            <span>CSV</span>
          </button>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col, idx) => (
                <th key={idx} onClick={() => handleSort(idx)} style={{ cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{col}</span>
                    <ArrowUpDown size={11} color={sortCol === idx ? '#58a6ff' : '#8b949e'} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row, rIdx) => (
              <tr key={rIdx}>
                {row.map((cell, cIdx) => (
                  <td key={cIdx}>{cell === null || cell === undefined ? <span style={{ color: '#8b949e' }}>NULL</span> : String(cell)}</td>
                ))}
              </tr>
            ))}
            {filteredRows.length === 0 && (
              <tr>
                <td colSpan={columns.length} style={{ textAlign: 'center', color: '#8b949e', padding: '24px' }}>
                  No matching records found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
