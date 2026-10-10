import React, { useState, useMemo } from 'react';
import { 
  BarChart, Bar, 
  LineChart, Line, 
  AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';
import { 
  BarChart3, 
  LineChart as LineIcon, 
  PieChart as PieIcon, 
  TrendingUp, 
  SlidersHorizontal, 
  DollarSign, 
  Percent, 
  Hash 
} from 'lucide-react';

interface ChartVisualizerProps {
  type?: string;
  data: {
    columns: string[];
    rows: any[][];
  };
  height?: number;
  onConfigChange?: (config: { chartType: string; xAxis: string; yAxis: string }) => void;
}

type PaletteKey = 'violet' | 'emerald' | 'amber';
type FormatType = 'raw' | 'currency' | 'percent' | 'number';

const PALETTES: Record<PaletteKey, string[]> = {
  violet: ['#8b5cf6', '#6366f1', '#a855f7', '#ec4899', '#3b82f6', '#14b8a6'],
  emerald: ['#10b981', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6'],
  amber: ['#f59e0b', '#f97316', '#ef4444', '#ec4899', '#8b5cf6', '#6366f1']
};

export const ChartVisualizer: React.FC<ChartVisualizerProps> = ({ 
  type = 'bar', 
  data,
  height = 250,
  onConfigChange
}) => {
  const [chartType, setChartType] = useState<string>(type || 'bar');
  const [showControls, setShowControls] = useState<boolean>(false);
  const [palette, setPalette] = useState<PaletteKey>('violet');
  const [formatType, setFormatType] = useState<FormatType>('raw');

  // Automatic column classification
  const { defaultX, defaultY, numericColumns } = useMemo(() => {
    if (!data || !data.columns || data.columns.length === 0) {
      return { defaultX: '', defaultY: '', numericColumns: [] };
    }

    const numCols: string[] = [];
    data.columns.forEach((col, idx) => {
      const sampleVals = data.rows.slice(0, 10).map(r => r[idx]).filter(v => v !== null && v !== undefined);
      const isNum = sampleVals.length > 0 && sampleVals.every(v => !isNaN(Number(v)) && typeof v !== 'boolean');
      if (isNum) numCols.push(col);
    });

    const xCol = data.columns.find(c => !numCols.includes(c)) || data.columns[0];
    const yCol = numCols.find(c => c !== xCol) || (data.columns.length > 1 ? data.columns[1] : data.columns[0]);

    return { defaultX: xCol, defaultY: yCol, numericColumns: numCols };
  }, [data]);

  const [xCol, setXCol] = useState<string>(defaultX);
  const [yCol, setYCol] = useState<string>(defaultY);

  // Sync if data changes
  const activeX = data.columns.includes(xCol) ? xCol : defaultX;
  const activeY = data.columns.includes(yCol) ? yCol : defaultY;

  const xIdx = data.columns.indexOf(activeX);
  const yIdx = data.columns.indexOf(activeY);

  const colors = PALETTES[palette];
  const primaryColor = colors[0];

  const formatValue = (val: number): string => {
    if (isNaN(val) || val === null || val === undefined) return '0';
    if (formatType === 'currency') {
      return `$${val >= 1000000 ? `${(val / 1000000).toFixed(1)}M` : val >= 1000 ? `${(val / 1000).toFixed(1)}K` : val.toLocaleString()}`;
    }
    if (formatType === 'percent') {
      return `${(val > 1 ? val : val * 100).toFixed(1)}%`;
    }
    if (formatType === 'number') {
      return val.toLocaleString();
    }
    return String(val);
  };

  const chartData = useMemo(() => {
    if (!data || !data.rows) return [];
    return data.rows.map(row => ({
      name: String(row[xIdx] ?? 'N/A'),
      value: Number(row[yIdx]) || 0
    }));
  }, [data, xIdx, yIdx]);

  if (!data || data.rows.length === 0 || data.columns.length < 2) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
        Dataset requires at least 2 columns and 1 row for visual plotting.
      </div>
    );
  }

  const handleTypeChange = (newType: string) => {
    setChartType(newType);
    if (onConfigChange) {
      onConfigChange({ chartType: newType, xAxis: activeX, yAxis: activeY });
    }
  };

  const handleAxisChange = (axis: 'x' | 'y', colName: string) => {
    if (axis === 'x') setXCol(colName);
    if (axis === 'y') setYCol(colName);
    if (onConfigChange) {
      onConfigChange({ 
        chartType, 
        xAxis: axis === 'x' ? colName : activeX, 
        yAxis: axis === 'y' ? colName : activeY 
      });
    }
  };

  return (
    <div className="chart-visualizer-wrapper">
      {/* Interactive Chart Customizer Toolbar */}
      <div className="chart-toolbar">
        <div className="chart-type-toggles">
          <button 
            className={`chart-type-btn ${chartType === 'bar' ? 'active' : ''}`}
            onClick={() => handleTypeChange('bar')}
            title="Bar Chart"
          >
            <BarChart3 size={13} />
            <span>Bar</span>
          </button>
          <button 
            className={`chart-type-btn ${chartType === 'line' ? 'active' : ''}`}
            onClick={() => handleTypeChange('line')}
            title="Line Chart"
          >
            <LineIcon size={13} />
            <span>Line</span>
          </button>
          <button 
            className={`chart-type-btn ${chartType === 'area' ? 'active' : ''}`}
            onClick={() => handleTypeChange('area')}
            title="Area Chart"
          >
            <TrendingUp size={13} />
            <span>Area</span>
          </button>
          <button 
            className={`chart-type-btn ${chartType === 'pie' ? 'active' : ''}`}
            onClick={() => handleTypeChange('pie')}
            title="Pie Chart"
          >
            <PieIcon size={13} />
            <span>Pie</span>
          </button>
        </div>

        <div className="chart-toolbar-right">
          <button 
            className={`chart-type-btn ${showControls ? 'active' : ''}`}
            onClick={() => setShowControls(!showControls)}
            title="Customize Axes & Formatting"
          >
            <SlidersHorizontal size={13} />
            <span>Customize</span>
          </button>
        </div>
      </div>

      {/* Slide-down Pivot & Axis Controls Drawer */}
      {showControls && (
        <div className="chart-controls-drawer">
          <div className="chart-control-group">
            <label className="chart-control-label">X-Axis (Category)</label>
            <select 
              className="chart-control-select"
              value={activeX}
              onChange={(e) => handleAxisChange('x', e.target.value)}
            >
              {data.columns.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="chart-control-group">
            <label className="chart-control-label">Y-Axis (Metric)</label>
            <select 
              className="chart-control-select"
              value={activeY}
              onChange={(e) => handleAxisChange('y', e.target.value)}
            >
              {data.columns.map((c) => (
                <option key={c} value={c}>
                  {c} {numericColumns.includes(c) ? '(123)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="chart-control-group">
            <label className="chart-control-label">Format</label>
            <div className="chart-format-buttons">
              <button 
                className={`format-btn ${formatType === 'raw' ? 'active' : ''}`}
                onClick={() => setFormatType('raw')}
                title="Raw Values"
              >
                Raw
              </button>
              <button 
                className={`format-btn ${formatType === 'currency' ? 'active' : ''}`}
                onClick={() => setFormatType('currency')}
                title="Currency ($)"
              >
                <DollarSign size={11} />
              </button>
              <button 
                className={`format-btn ${formatType === 'percent' ? 'active' : ''}`}
                onClick={() => setFormatType('percent')}
                title="Percentage (%)"
              >
                <Percent size={11} />
              </button>
              <button 
                className={`format-btn ${formatType === 'number' ? 'active' : ''}`}
                onClick={() => setFormatType('number')}
                title="Formatted Number (#)"
              >
                <Hash size={11} />
              </button>
            </div>
          </div>

          <div className="chart-control-group">
            <label className="chart-control-label">Palette</label>
            <div className="chart-palette-picker">
              {(['violet', 'emerald', 'amber'] as PaletteKey[]).map((p) => (
                <button
                  key={p}
                  className={`palette-swatch ${palette === p ? 'active' : ''}`}
                  onClick={() => setPalette(p)}
                  style={{ backgroundColor: PALETTES[p][0] }}
                  title={p.toUpperCase()}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Chart Canvas Rendering */}
      <div className="chart-canvas-container" style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          {chartType === 'line' ? (
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" opacity={0.6} />
              <XAxis dataKey="name" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
              <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={formatValue} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', borderRadius: '6px', fontSize: '12px' }} 
                formatter={(val: any) => [formatValue(Number(val)), activeY]}
              />
              <Legend wrapperStyle={{ fontSize: '11px', color: 'var(--text-secondary)' }} />
              <Line type="monotone" dataKey="value" name={activeY} stroke={primaryColor} strokeWidth={2.5} dot={{ r: 4, fill: primaryColor }} />
            </LineChart>
          ) : chartType === 'area' ? (
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
              <defs>
                <linearGradient id={`areaGrad-${palette}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={primaryColor} stopOpacity={0.6}/>
                  <stop offset="95%" stopColor={primaryColor} stopOpacity={0.05}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" opacity={0.6} />
              <XAxis dataKey="name" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
              <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={formatValue} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', borderRadius: '6px', fontSize: '12px' }} 
                formatter={(val: any) => [formatValue(Number(val)), activeY]}
              />
              <Area type="monotone" dataKey="value" name={activeY} stroke={primaryColor} strokeWidth={2} fillOpacity={1} fill={`url(#areaGrad-${palette})`} />
            </AreaChart>
          ) : chartType === 'pie' ? (
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={75}
                dataKey="value"
                label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
              >
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', borderRadius: '6px', fontSize: '12px' }} 
                formatter={(val: any) => [formatValue(Number(val)), activeY]}
              />
              <Legend wrapperStyle={{ fontSize: '11px', color: 'var(--text-secondary)' }} />
            </PieChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" opacity={0.6} />
              <XAxis dataKey="name" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
              <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={formatValue} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)', borderRadius: '6px', fontSize: '12px' }} 
                formatter={(val: any) => [formatValue(Number(val)), activeY]}
              />
              <Legend wrapperStyle={{ fontSize: '11px', color: 'var(--text-secondary)' }} />
              <Bar dataKey="value" name={activeY} fill={primaryColor} radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};
