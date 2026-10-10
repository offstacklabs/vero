import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Bot, User, Layers } from 'lucide-react';
import { ChartVisualizer } from './components/ChartVisualizer';
import { DataTable } from './components/DataTable';
import { SqlCard } from './components/SqlCard';
import { ReasoningSteps } from './components/ReasoningSteps';
import { PromptChips } from './components/PromptChips';
import './VeroChat.css';

export interface VeroChatProps {
  /** API Key or SSO JWT Token for authentication */
  token: string;
  /** URL to the Vero Backend Server (e.g. https://api.verodata.dev) */
  apiBaseUrl: string;
  /** Limit context to a specific business domain */
  domain?: string;
  /** Suggested starter prompts */
  initialFollowUps?: string[];
  /** Custom Welcome Message */
  welcomeMessage?: string;
}

interface Message {
  id: string;
  sender: 'assistant' | 'user';
  text: string;
  sql?: string;
  tables_used?: string[];
  suggested_followups?: string[];
  duration_ms?: number;
  reflection_steps?: any[];
  is_streaming?: boolean;
  status_message?: string;
  bytes_formatted?: string;
  cost_usd?: number;
  cost_guard_passed?: boolean;
  cache_hit?: boolean;
  telemetry?: any;
  data?: {
    columns: string[];
    rows: any[][];
    row_count: number;
    masked_columns?: string[];
  };
  suggested_visualization?: string;
  error?: string;
  diagnostics?: any;
}

export const VeroChat: React.FC<VeroChatProps> = ({
  token,
  apiBaseUrl,
  domain = 'global',
  initialFollowUps = ['Show me total revenue this month'],
  welcomeMessage = 'Hello! I am your AI data assistant powered by Vero.'
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome_1',
      sender: 'assistant',
      text: welcomeMessage,
      suggested_followups: initialFollowUps
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (questionToAsk?: string) => {
    const q = (questionToAsk || input).trim();
    if (!q || loading) return;

    setInput('');
    setLoading(true);

    const userMsgId = Math.random().toString(36).substring(2, 9);
    setMessages(prev => [...prev, { id: userMsgId, sender: 'user', text: q }]);

    const assistantMsgId = Math.random().toString(36).substring(2, 9);
    setMessages(prev => [...prev, { 
      id: assistantMsgId, 
      sender: 'assistant', 
      text: '', 
      is_streaming: true,
      status_message: 'Analyzing context...' 
    }]);

    try {
      const response = await fetch(`${apiBaseUrl}/api/chat/stream`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ question: q, execute: true, domain })
      });

      if (!response.ok) throw new Error('Streaming API request failed');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.substring(6));
                
                if (data.type === 'stage') {
                  setMessages(prev => prev.map(m => 
                    m.id === assistantMsgId ? { ...m, status_message: data.message } : m
                  ));
                } else if (data.type === 'complete') {
                  const completedMsg: Message = {
                    id: assistantMsgId,
                    sender: 'assistant',
                    text: data.result.explanation || 'Here is the data you requested.',
                    sql: data.result.sql,
                    tables_used: data.result.tables_used,
                    suggested_followups: data.result.suggested_followups,
                    duration_ms: data.result.duration_ms,
                    reflection_steps: data.result.reflection_steps,
                    bytes_formatted: data.result.bytes_formatted,
                    cost_usd: data.result.cost_usd,
                    cost_guard_passed: data.result.cost_guard_passed,
                    cache_hit: data.result.cache_hit,
                    telemetry: data.result.telemetry,
                    data: data.result.data,
                    suggested_visualization: data.result.suggested_visualization,
                    error: data.result.error,
                    is_streaming: false
                  };
                  setMessages(prev => prev.map(m => m.id === assistantMsgId ? completedMsg : m));
                }
              } catch (e) {
                console.error("SDK Stream Parse Error:", e);
              }
            }
          }
        }
      }
    } catch (err: any) {
      setMessages(prev => prev.map(m => 
        m.id === assistantMsgId ? {
          ...m,
          text: `Error connecting to Vero.`,
          error: String(err),
          is_streaming: false
        } : m
      ));
    } finally {
      setLoading(false);
    }
  };

  const isSingleMetric = (data: any) => data && data.columns && data.columns.length === 1 && data.rows && data.rows.length === 1;

  return (
    <div className="vero-sdk-container">
      <div className="vero-sdk-messages">
        {messages.map(msg => (
          <div key={msg.id} className={`vero-msg-card ${msg.sender}`}>
            <div className="vero-msg-header">
              {msg.sender === 'assistant' ? <Bot size={16} /> : <User size={16} />}
              <span>{msg.sender === 'assistant' ? 'Vero Analytics Agent' : 'You'}</span>
            </div>

            {msg.is_streaming && (
              <div className="vero-streaming-pill">
                <Loader2 size={13} className="vero-spin" />
                <span>{msg.status_message || 'Analyzing...'}</span>
              </div>
            )}

            {msg.text && <div className="vero-msg-body">{msg.text}</div>}

            {msg.sender === 'assistant' && (
              <ReasoningSteps
                thought={undefined}
                tablesUsed={msg.tables_used}
                durationMs={msg.duration_ms}
                dialect="Data Warehouse"
                reflectionSteps={msg.reflection_steps}
                bytesFormatted={msg.bytes_formatted}
                costUsd={msg.cost_usd}
                telemetry={msg.telemetry}
                cacheHit={msg.cache_hit}
              />
            )}

            {msg.sql && (
              <SqlCard
                sql={msg.sql}
                durationMs={msg.duration_ms}
                rowCount={msg.data?.row_count}
                dialect="Data Warehouse"
                bytesFormatted={msg.bytes_formatted}
                costUsd={msg.cost_usd}
                costGuardPassed={msg.cost_guard_passed}
                totalTokens={msg.telemetry?.total_tokens}
                cacheHit={msg.cache_hit}
              />
            )}

            {isSingleMetric(msg.data) && (
              <div className="vero-kpi-card">
                <div className="vero-kpi-label">{msg.data!.columns[0]}</div>
                <div className="vero-kpi-value">{msg.data!.rows[0][0]}</div>
              </div>
            )}

            {msg.data && !isSingleMetric(msg.data) && (
              <DataTable 
                columns={msg.data.columns} 
                rows={msg.data.rows} 
                tableName="query_result"
                maskedColumns={msg.data.masked_columns}
              />
            )}

            {!isSingleMetric(msg.data) && msg.suggested_visualization && msg.suggested_visualization !== 'table' && msg.data && (
              <div className="vero-chart-container">
                <ChartVisualizer type={msg.suggested_visualization} data={msg.data} />
              </div>
            )}

            {msg.suggested_followups && msg.suggested_followups.length > 0 && (
              <PromptChips
                suggestions={msg.suggested_followups}
                onSelect={handleSend}
                disabled={loading}
              />
            )}

            {msg.error && (
              <div className="vero-error-msg">
                Error: {msg.error}
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="vero-sdk-input-dock">
        <div className="vero-sdk-input-box">
          <input
            type="text"
            className="vero-sdk-input"
            placeholder="Ask a question about your data..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            disabled={loading}
          />
          <button 
            className="vero-sdk-send-btn" 
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
          >
            <Send size={14} />
          </button>
        </div>
        <div className="vero-sdk-footer-brand">
          <Layers size={10} /> Powered by Vero
        </div>
      </div>
    </div>
  );
};
