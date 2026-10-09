import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
}

export const MetricCard: React.FC<MetricCardProps> = ({ label, value }) => {
  return (
    <div className="metric-card-container">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
    </div>
  );
};
