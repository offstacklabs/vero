import React from 'react';
import { Sparkles } from 'lucide-react';

interface PromptChipsProps {
  suggestions?: string[];
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

export const PromptChips: React.FC<PromptChipsProps> = ({ suggestions = [], onSelect, disabled }) => {
  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="prompt-chips-container">
      <span className="prompt-chips-label">
        <Sparkles size={12} color="#58a6ff" />
        <span>Suggested follow-ups:</span>
      </span>
      <div className="prompt-chips-list">
        {suggestions.map((prompt, idx) => (
          <button
            key={idx}
            className="prompt-chip"
            onClick={() => onSelect(prompt)}
            disabled={disabled}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
};
