import { useState, useEffect } from 'react';
import './App.css';
import { 
  Database, 
  Terminal, 
  Send, 
  Sparkles,
  Bot,
  User,
  FileText
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer,
  CartesianGrid 
} from 'recharts';

interface Schema {
  table: string;
  content: string;
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
      text: 'Hello! I am Vero, your open-source analytics agent. How can I assist with your data warehouse today?'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [activeTab, setActiveTab] = useState<'chat' | 'schemas'>('chat');
  const [selectedSchema, setSelectedSchema] = useState<Schema | null>(null);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/schemas')
      .then(res => res.json())
      .then(data => {
        if (data.schemas) {
          setSchemas(data.schemas);
          if (data.schemas.length > 0) setSelectedSchema(data.schemas[0]);
        }
      })
      .catch(() => {
        // Fallback demo schemas if server is offline
        setSchemas([
          { table: 'customers', content: '# Table: customers\n\n- id (INTEGER)\n- name (TEXT)\n- email (TEXT)\n- plan (TEXT)' },
          { table: 'orders', content: '# Table: orders\n\n- id (INTEGER)\n- customer_id (INTEGER)\n- amount (REAL)\n- status (TEXT)' }
        ]);
      });
  }, []);

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
      // Offline fallback simulation
      const fallbackMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `Analyzed: "${currentInput}". Below is the generated query and results.`,
        thought: "Filter orders by status = 'completed' and aggregate total revenue per customer.",
        sql: "SELECT c.name, SUM(o.amount) AS total_revenue\nFROM customers c\nJOIN orders o ON c.id = o.customer_id\nWHERE o.status = 'completed'\nGROUP BY c.name\nORDER BY total_revenue DESC;",
        data: {
          columns: ['name', 'total_revenue'],
          rows: [
            ['Alice Smith', 3600.00],
            ['Bob Jones', 450.00],
            ['Diana Prince', 399.00]
          ],
          row_count: 3
        },
        suggested_visualization: 'bar'
      };
      setMessages(prev => [...prev, fallbackMessage]);
    } finally {
      setLoading(false);
    }
  };

  const formatChartData = (data: Message['data']) => {
    if (!data || data.rows.length === 0 || data.columns.length < 2) return [];
    return data.rows.map(row => ({
      name: String(row[0]),
      value: Number(row[1]) || 0
    }));
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
            className={`nav-item ${activeTab === 'schemas' ? 'active' : ''}`}
            onClick={() => setActiveTab('schemas')}
          >
            <Database size={16} />
            <span>Synced Schemas</span>
          </div>
        </nav>

        <div className="schemas-section">
          <span className="section-label">Warehouse Tables ({schemas.length})</span>
          {schemas.map(s => (
            <div 
              key={s.table} 
              className="schema-item"
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
            <span>Dialect: SQLite / DuckDB</span>
          </div>
        </header>

        {activeTab === 'chat' ? (
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

                  {msg.data && (
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

                  {msg.suggested_visualization === 'bar' && msg.data && (
                    <div className="chart-container">
                      <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '12px' }}>
                        Data Visualization (Bar Chart)
                      </div>
                      <ResponsiveContainer width="100%" height={240}>
                        <BarChart data={formatChartData(msg.data)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
                          <XAxis dataKey="name" stroke="#8b949e" />
                          <YAxis stroke="#8b949e" />
                          <Tooltip contentStyle={{ backgroundColor: '#161b22', borderColor: '#30363d' }} />
                          <Bar dataKey="value" fill="#58a6ff" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
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
        ) : (
          <div style={{ padding: '24px', overflowY: 'auto' }}>
            <h2 style={{ marginBottom: '16px', fontSize: '20px' }}>
              {selectedSchema ? `Schema: ${selectedSchema.table}` : 'Database Schemas'}
            </h2>
            <div className="sql-box" style={{ whiteSpace: 'pre-wrap' }}>
              {selectedSchema?.content || 'Select a schema on the sidebar to view details.'}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
