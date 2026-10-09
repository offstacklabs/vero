import React from 'react';
import { 
  BarChart, Bar, 
  LineChart, Line, 
  PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid 
} from 'recharts';

interface ChartVisualizerProps {
  type: string;
  data: {
    columns: string[];
    rows: any[][];
  };
}

const COLORS = ['#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7', '#bc8cff'];

export const ChartVisualizer: React.FC<ChartVisualizerProps> = ({ type, data }) => {
  if (!data || data.rows.length === 0 || data.columns.length < 2) return null;

  // Assume first column is category (X), second is value (Y)
  const formatData = () => {
    return data.rows.map(row => ({
      name: String(row[0]),
      value: Number(row[1]) || 0
    }));
  };

  const chartData = formatData();

  if (type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
          <XAxis dataKey="name" stroke="#8b949e" />
          <YAxis stroke="#8b949e" />
          <Tooltip contentStyle={{ backgroundColor: '#161b22', borderColor: '#30363d' }} />
          <Line type="monotone" dataKey="value" stroke="#58a6ff" strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            labelLine={false}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
            label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
          >
            {chartData.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ backgroundColor: '#161b22', borderColor: '#30363d' }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  // Default to Bar
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
        <XAxis dataKey="name" stroke="#8b949e" />
        <YAxis stroke="#8b949e" />
        <Tooltip contentStyle={{ backgroundColor: '#161b22', borderColor: '#30363d' }} />
        <Bar dataKey="value" fill="#58a6ff" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
};
