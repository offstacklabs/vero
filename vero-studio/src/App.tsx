import { useState, useEffect } from 'react';
import './App.css';
import { 
  Database, 
  Terminal, 
  Send, 
  Sparkles,
  Bot,
  User,
  FileText,
  TerminalSquare,
  RefreshCw,
  LineChart as LineChartIcon
} from 'lucide-react';
import { marked } from 'marked';
import { ChartVisualizer } from './components/ChartVisualizer';
import { Scratchpad } from './components/Scratchpad';
import { MetricCard } from './components/MetricCard';

interface Schema {
  table: string;
  content: string;
}

interface SemanticMetric {
  name: string;
  description: string;
  sql: string;
}

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  thought?: string;
  sql?: string;
  data?: {
    columns: string[];
    rows: any[][];
    row_count: number;
  };
  suggested_visualization?: string;
  error?: string;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'assistant',
      text: 'Hello! I am Vero. I can connect to Postgres, Snowflake, or BigQuery. How can I assist with your data today?'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [semanticMetrics, setSemanticMetrics] = useState<SemanticMetric[]>([]);
  const [activeTab, setActiveTab] = useState<'chat' | 'schemas' | 'scratchpad' | 'metrics'>('chat');
  const [selectedSchema, setSelectedSchema] = useState<Schema | null>(null);
  const [dialect, setDialect] = useState<string>('postgres');
  const [syncing, setSyncing] = useState(false);

  const fetchConfig = () => {
    fetch('http://127.0.0.1:8000/api/config')
      .then(res => res.json())
      .then(data => {
        if (data.database && data.database.dialect) {
          setDialect(data.database.dialect);
        }
      })
      .catch(() => console.error("Could not fetch config"));
  };

  const fetchSchemas = () => {
    fetch('http://127.0.0.1:8000/api/schemas')
      .then(res => res.json())
      .then(data => {
        if (data.schemas) {
          setSchemas(data.schemas);
          if (data.schemas.length > 0 && !selectedSchema) setSelectedSchema(data.schemas[0]);
        }
      })
      .catch(() => {
        // Fallback demo schemas
        setSchemas([
          { table: 'customers', content: '# Table: customers\n\n- id (INTEGER)\n- name (TEXT)' },
          { table: 'orders', content: '# Table: orders\n\n- id (INTEGER)\n- customer_id (INTEGER)' }
        ]);
      });
  };

  const fetchMetrics = () => {
    fetch('http://127.0.0.1:8000/api/metrics')
      .then(res => res.json())
      .then(data => {
        if (data.metrics) {
          setSemanticMetrics(data.metrics);
        }
      })
      .catch(() => console.error("Could not fetch metrics"));
  };

  useEffect(() => {
    fetchSchemas();
    fetchMetrics();
    fetchConfig();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSyncSchemas = async () => {
    setSyncing(true);
    try {
      await fetch('http://127.0.0.1:8000/api/sync', { method: 'POST' });
      fetchSchemas();
    } catch (err) {
      console.error("Failed to sync schemas:", err);
    } finally {
      setSyncing(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: input
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: currentInput, execute: true })
      });

      if (!response.ok) throw new Error('API request failed');
      const data = await response.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: data.explanation || 'Here is the query and data you requested.',
        thought: data.thought,
        sql: data.sql,
        data: data.data,
        suggested_visualization: data.suggested_visualization,
        error: data.error
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `Error connecting to the Vero agent server.`,
        error: String(err)
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleRunScratchpad = async (sql: string) => {
    setLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql })
      });
      const data = await response.json();
      
      if (!response.ok) throw new Error(data.detail || 'Execution failed');
      
      const resMessage: Message = {
        id: Date.now().toString(),
        sender: 'assistant',
        text: 'Executed scratchpad query:',
        sql: sql,
        data: data.data
      };
      
      setMessages(prev => [...prev, resMessage]);
      setActiveTab('chat');
    } catch (err) {
      alert(`Error executing query: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const isSingleMetric = (data: Message['data']) => {
    return data && data.columns.length === 1 && data.rows.length === 1;
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="brand-badge">VERO</span>
          <span className="sidebar-title">Analytics Studio</span>
        </div>

        <nav className="sidebar-nav">
          <div 
            className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <Terminal size={16} />
            <span>Chat & Explore</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'scratchpad' ? 'active' : ''}`}
            onClick={() => setActiveTab('scratchpad')}
          >
            <TerminalSquare size={16} />
            <span>SQL Scratchpad</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'metrics' ? 'active' : ''}`}
            onClick={() => setActiveTab('metrics')}
          >
            <LineChartIcon size={16} />
            <span>Semantic Layer</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'schemas' ? 'active' : ''}`}
            onClick={() => setActiveTab('schemas')}
          >
            <Database size={16} />
            <span>Synced Schemas</span>
          </div>
        </nav>

        <div className="schemas-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span className="section-label" style={{ marginBottom: 0 }}>Warehouse Entities ({schemas.length})</span>
            <RefreshCw 
              size={12} 
              color="#8b949e" 
              style={{ cursor: 'pointer', animation: syncing ? 'spin 1s linear infinite' : 'none' }}
              onClick={handleSyncSchemas}
            />
          </div>
          {schemas.map(s => (
            <div 
              key={s.table} 
              className={`schema-item ${selectedSchema?.table === s.table && activeTab === 'schemas' ? 'active' : ''}`}
              onClick={() => {
                setSelectedSchema(s);
                setActiveTab('schemas');
              }}
            >
              <FileText size={14} color="#8b949e" />
              <span>{s.table}</span>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-area">
        <header className="top-bar">
          <div className="status-pill">
            <span className="status-dot"></span>
            <span>Agent Status: Connected</span>
          </div>
          <div className="status-pill">
            <Sparkles size={14} color="#58a6ff" />
            <span>Dialect: {dialect}</span>
          </div>
        </header>

        {activeTab === 'chat' && (
          <>
            <div className="chat-container">
              {messages.map(msg => (
                <div key={msg.id} className={`message-card ${msg.sender}`}>
                  <div className="message-header">
                    {msg.sender === 'assistant' ? <Bot size={16} /> : <User size={16} />}
                    <span>{msg.sender === 'assistant' ? 'Vero Agent' : 'You'}</span>
                  </div>

                  <div className="message-body">{msg.text}</div>

                  {msg.thought && (
                    <div className="reasoning-box">
                      <strong>Reasoning:</strong> {msg.thought}
                    </div>
                  )}

                  {msg.sql && (
                    <div>
                      <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '8px' }}>
                        Generated SQL:
                      </div>
                      <div className="sql-box">{msg.sql}</div>
                    </div>
                  )}

                  {msg.data && !isSingleMetric(msg.data) && (
                    <div className="table-wrapper">
                      <table className="data-table">
                        <thead>
                          <tr>
                            {msg.data.columns.map((col, idx) => (
                              <th key={idx}>{col}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {msg.data.rows.map((row, rIdx) => (
                            <tr key={rIdx}>
                              {row.map((cell, cIdx) => (
                                <td key={cIdx}>{String(cell)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {isSingleMetric(msg.data) && (
                    <div style={{ marginTop: '16px' }}>
                      <MetricCard 
                        label={msg.data!.columns[0]} 
                        value={msg.data!.rows[0][0]} 
                      />
                    </div>
                  )}

                  {!isSingleMetric(msg.data) && msg.suggested_visualization && msg.suggested_visualization !== 'table' && msg.data && (
                    <div className="chart-container">
                      <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '12px' }}>
                        Data Visualization ({msg.suggested_visualization})
                      </div>
                      <ChartVisualizer type={msg.suggested_visualization} data={msg.data} />
                    </div>
                  )}

                  {msg.error && (
                    <div style={{ color: '#f85149', marginTop: '8px', fontSize: '13px' }}>
                      Error: {msg.error}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="input-dock">
              <div className="input-box">
                <input
                  type="text"
                  className="input-field"
                  placeholder="Ask a question about your data (e.g. 'Show total revenue by customer')..."
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSend()}
                  disabled={loading}
                />
                <button 
                  className="send-btn" 
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                >
                  <Send size={14} />
                  <span>{loading ? 'Thinking...' : 'Ask'}</span>
                </button>
              </div>
            </div>
          </>
        )}

        {activeTab === 'scratchpad' && (
          <Scratchpad onExecute={handleRunScratchpad} loading={loading} />
        )}

        {activeTab === 'metrics' && (
          <div className="metrics-viewer">
            <h2 style={{ marginBottom: '16px', fontSize: '20px' }}>Semantic Layer (Metrics)</h2>
            <p style={{ color: 'var(--text-muted)', marginBottom: '24px', fontSize: '14px' }}>
              These metrics are automatically injected into the agent's context, ensuring accurate and consistent SQL generation.
            </p>
            {semanticMetrics.length === 0 ? (
              <div style={{ color: '#8b949e' }}>No metrics defined in .vero/metrics.yaml</div>
            ) : (
              semanticMetrics.map(m => (
                <div key={m.name} className="semantic-metric-card">
                  <div className="semantic-metric-name">{m.name}</div>
                  <div className="semantic-metric-desc">{m.description}</div>
                  <div className="sql-box" style={{ margin: 0, backgroundColor: 'var(--bg-primary)' }}>
                    {m.sql}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'schemas' && (
          <div className="schema-viewer">
            {selectedSchema ? (
              <div dangerouslySetInnerHTML={{ __html: marked(selectedSchema.content) as string }} />
            ) : (
              <div style={{ color: '#8b949e' }}>Select a schema on the sidebar to view details.</div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
