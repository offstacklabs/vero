import { useState, useEffect } from 'react';
import './App.css';
import { 
  Terminal, 
  Send, 
  Database,
  Bot,
  User,
  TerminalSquare,
  RefreshCw,
  LineChart as LineChartIcon,
  Play,
  Sun,
  Moon,
  Loader2,
  BookOpen,
  Plus,
  Trash2,
  BookmarkPlus,
  Save,
  Check,
  MessageSquarePlus,
  MessageSquare,
  LayoutDashboard,
  Activity,
  Lock,
  LogOut,
  Shield,
  Users,
  Copy,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  X,
  Sparkles,
  Layers
} from 'lucide-react';
import { ChartVisualizer } from './components/ChartVisualizer';
import { SqlEditor } from './components/SqlEditor';
import { MetricCard } from './components/MetricCard';
import { DataTable } from './components/DataTable';
import { ReasoningSteps } from './components/ReasoningSteps';
import { PromptChips } from './components/PromptChips';
import { SqlCard } from './components/SqlCard';
import { SchemaTree, type TableEntity } from './components/SchemaTree';
import { DashboardCanvas, type DashboardTile } from './components/DashboardCanvas';
import { ObservabilityDashboard } from './components/ObservabilityDashboard';

interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'analyst' | 'viewer';
  allowed_domains: string[];
}

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'warning' | 'error' | 'info';
}

interface DomainInfo {
  id: string;
  name: string;
  description: string;
}

interface SessionInfo {
  id: string;
  title: string;
  domain: string;
  created_at: string;
}

interface SemanticMetric {
  name: string;
  description: string;
  sql: string;
  domain?: string;
}

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  thought?: string;
  sql?: string;
  tables_used?: string[];
  suggested_followups?: string[];
  duration_ms?: number;
  reflection_steps?: { attempt: number; failed_sql: string; error: string; thought?: string }[];
  is_streaming?: boolean;
  status_message?: string;
  bytes_scanned?: number;
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
  diagnostics?: {
    summary: string;
    findings: Array<{
      dimension: string;
      data: any[][];
    }>;
  };
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'assistant',
      text: 'Hello! I am Vero, your open-source analytics agent. Ask any analytical question, or click any table on the left to preview it.',
      suggested_followups: [
        'Show total revenue by customer',
        'What is our annual recurring revenue?',
        'List active users who signed up this year'
      ]
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [schemas, setSchemas] = useState<TableEntity[]>([]);
  const [semanticMetrics, setSemanticMetrics] = useState<SemanticMetric[]>([]);
  const [activeTab, setActiveTab] = useState<'chat' | 'scratchpad' | 'dashboard' | 'observability' | 'metrics' | 'rules'>('chat');
  const [selectedSchema, setSelectedSchema] = useState<TableEntity | null>(null);
  const [dialect, setDialect] = useState<string>('BigQuery');
  const [syncing, setSyncing] = useState(false);
  const [editorSql, setEditorSql] = useState<string>('SELECT * FROM customers LIMIT 10;');
  const [domains, setDomains] = useState<DomainInfo[]>([
    { id: 'global', name: 'Global (Shared)', description: 'Enterprise-wide' },
    { id: 'finance', name: 'Finance', description: 'Revenue & accounting' },
    { id: 'marketing', name: 'Marketing', description: 'Attribution & spend' },
    { id: 'product', name: 'Product', description: 'Engagement & retention' }
  ]);
  const [selectedDomain, setSelectedDomain] = useState<string>('global');
  const [tiles, setTiles] = useState<DashboardTile[]>([]);
  const [refreshingDashboard, setRefreshingDashboard] = useState(false);
  const [rulesText, setRulesText] = useState<string>('');
  const [rulesSaving, setRulesSaving] = useState(false);
  const [rulesSavedToast, setRulesSavedToast] = useState(false);
  const [showAddMetric, setShowAddMetric] = useState(false);
  const [showImportMetricModal, setShowImportMetricModal] = useState(false);
  const [importMetricSource, setImportMetricSource] = useState<'lookml' | 'dbt' | 'cube'>('lookml');
  const [importMetricContent, setImportMetricContent] = useState('');
  const [importMetricLoading, setImportMetricLoading] = useState(false);
  const [newMetric, setNewMetric] = useState({ name: '', description: '', sql: '', domain: 'global' });
  const [teachingMsgId, setTeachingMsgId] = useState<string | null>(null);
  const [teachRuleInput, setTeachRuleInput] = useState<string>('');
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [diagnosticLoadingId, setDiagnosticLoadingId] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('vero_auth_token'));

  const handleRunDiagnostics = async (msgId: string, sql: string) => {
    setDiagnosticLoadingId(msgId);
    try {
      const res = await fetch(`${API_BASE}/api/diagnostics/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ sql })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessages(prev => prev.map(m => 
          m.id === msgId ? { ...m, diagnostics: data } : m
        ));
        addToast('Diagnostic Root Cause Analysis completed', 'success');
      } else {
        addToast(data.detail || data.error || 'Diagnostic analysis failed', 'error');
      }
    } catch (err: any) {
      addToast(`Diagnostic error: ${err.message || err}`, 'error');
    } finally {
      setDiagnosticLoadingId(null);
    }
  };
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authConfig, setAuthConfig] = useState<{ mode: string; provider_name: string; issuer_url?: string } | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [showLoginModal, setShowLoginModal] = useState<boolean>(false);
  const [loginForm, setLoginForm] = useState({ email: '', password: '', apiKey: '', mode: 'password' as 'password' | 'api_key' });
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState<boolean>(false);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('vero_theme') as 'light' | 'dark') || 'light';
  });

  const addToast = (message: string, type: 'success' | 'warning' | 'error' | 'info' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const getAuthHeaders = (): Record<string, string> => {
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  useEffect(() => {
    fetch(`${API_BASE}/api/auth/me`, {
      headers: getAuthHeaders()
    })
      .then(res => {
        if (res.ok) return res.json();
        throw new Error('Not authenticated');
      })
      .then(data => {
        if (data.user) setCurrentUser(data.user);
      })
      .catch(() => {
        if (token) {
          localStorage.removeItem('vero_auth_token');
          setToken(null);
        }
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError(null);
    try {
      const payload = loginForm.mode === 'api_key'
        ? { api_key: loginForm.apiKey }
        : { email: loginForm.email, password: loginForm.password };

      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');

      localStorage.setItem('vero_auth_token', data.token);
      setToken(data.token);
      setCurrentUser(data.user);
      setShowLoginModal(false);
      fetchDomains();
      addToast(`Signed in as ${data.user.name}`, 'success');
    } catch (err: any) {
      setLoginError(err.message || String(err));
      addToast(err.message || 'Login failed', 'error');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleOidcLogin = async (provider = 'Okta') => {
    setLoginLoading(true);
    setLoginError(null);
    try {
      const res = await fetch(`${API_BASE}/api/auth/oidc/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'analyst@enterprise.com',
          name: 'Corporate Analyst',
          groups: ['Finance-Team', 'Data-Admins']
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'SSO authentication failed');

      localStorage.setItem('vero_auth_token', data.token);
      setToken(data.token);
      setCurrentUser(data.user);
      setShowLoginModal(false);
      fetchDomains();
      addToast(`Signed in via ${provider} as ${data.user.name}`, 'success');
    } catch (err: any) {
      setLoginError(err.message || String(err));
      addToast(`SSO Error: ${err.message || err}`, 'error');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('vero_auth_token');
    setToken(null);
    setCurrentUser(null);
    fetchDomains();
    addToast('Signed out successfully', 'info');
  };

  const [showTeamModal, setShowTeamModal] = useState<boolean>(false);
  const [teamTab, setTeamTab] = useState<'users' | 'domains'>('users');
  const [userList, setUserList] = useState<UserProfile[]>([]);
  const [newUserForm, setNewUserForm] = useState({ email: '', name: '', password: '', role: 'analyst', domain: '*' });
  const [createdApiKey, setCreatedApiKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [newDomainForm, setNewDomainForm] = useState({ id: '', name: '', description: '' });
  const [teamLoading, setTeamLoading] = useState(false);

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/users`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setUserList(data.users || []);
      }
    } catch (e) {
      console.error("Could not fetch users:", e);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setTeamLoading(true);
    try {
      const domainsArr = newUserForm.domain === '*' ? ['*'] : [newUserForm.domain];
      const res = await fetch(`${API_BASE}/api/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          email: newUserForm.email,
          name: newUserForm.name,
          password: newUserForm.password || undefined,
          role: newUserForm.role,
          allowed_domains: domainsArr
        })
      });
      const data = await res.json();
      if (res.ok) {
        setCreatedApiKey(data.api_key);
        setNewUserForm({ email: '', name: '', password: '', role: 'analyst', domain: '*' });
        fetchUsers();
        addToast(`User '${data.user.name}' provisioned successfully!`, 'success');
      } else {
        addToast(data.detail || 'Failed to create user', 'error');
      }
    } catch (err: any) {
      addToast(err.message || 'Error creating user', 'error');
    } finally {
      setTeamLoading(false);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/users/${userId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        fetchUsers();
        addToast('User deleted successfully', 'info');
      } else {
        const data = await res.json();
        addToast(data.detail || 'Could not delete user', 'error');
      }
    } catch (err: any) {
      addToast(err.message || 'Error deleting user', 'error');
    }
  };

  const handleCreateDomain = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDomainForm.id.trim() || !newDomainForm.name.trim()) return;
    setTeamLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/domains`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(newDomainForm)
      });
      if (res.ok) {
        const domainName = newDomainForm.name;
        setNewDomainForm({ id: '', name: '', description: '' });
        fetchDomains();
        addToast(`Domain '${domainName}' created successfully!`, 'success');
      } else {
        const data = await res.json();
        addToast(data.detail || 'Failed to create domain', 'error');
      }
    } catch (err: any) {
      addToast(err.message || 'Error creating domain', 'error');
    } finally {
      setTeamLoading(false);
    }
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('vero_theme', theme);
  }, [theme]);

  const fetchConfig = () => {
    fetch(`${API_BASE}/api/config`, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.database && data.database.dialect) {
          const d = data.database.dialect;
          if (d.toLowerCase() === 'bigquery') {
            setDialect('BigQuery');
          } else {
            setDialect(d.charAt(0).toUpperCase() + d.slice(1));
          }
        }
      })
      .catch(() => console.error("Could not fetch config"));

    fetch(`${API_BASE}/api/auth/config`)
      .then(res => res.json())
      .then(data => {
        setAuthConfig(data);
        if (data.mode === 'local') {
          fetch(`${API_BASE}/api/auth/me`)
            .then(r => r.json())
            .then(d => { if (d.user) setCurrentUser(d.user); })
            .catch(() => {});
        }
      })
      .catch(() => {});
  };

  const fetchDomains = () => {
    fetch(`${API_BASE}/api/domains`, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.domains && data.domains.length > 0) setDomains(data.domains);
      })
      .catch(() => console.error("Could not fetch domains"));
  };

  const fetchSchemas = (domain = selectedDomain) => {
    const url = domain ? `${API_BASE}/api/schemas?domain=${domain}` : `${API_BASE}/api/schemas`;
    fetch(url, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.schemas) {
          setSchemas(data.schemas);
          if (data.schemas.length > 0 && !selectedSchema) setSelectedSchema(data.schemas[0]);
        }
      })
      .catch(() => {
        setSchemas([
          { table: 'customers', content: '# Table: customers\n\n| Column Name | Data Type |\n| `id` | `INTEGER` |\n| `name` | `TEXT` |\n| `email` | `TEXT` |\n| `plan` | `TEXT` |' },
          { table: 'orders', content: '# Table: orders\n\n| Column Name | Data Type |\n| `id` | `INTEGER` |\n| `customer_id` | `INTEGER` |\n| `amount` | `REAL` |\n| `status` | `TEXT` |' }
        ]);
      });
  };

  const fetchMetrics = (domain = selectedDomain) => {
    const url = domain ? `${API_BASE}/api/metrics?domain=${domain}` : `${API_BASE}/api/metrics`;
    fetch(url, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.metrics) {
          setSemanticMetrics(data.metrics);
        }
      })
      .catch(() => console.error("Could not fetch metrics"));
  };

  const fetchRules = (domain = selectedDomain) => {
    const url = domain ? `${API_BASE}/api/rules?domain=${domain}` : `${API_BASE}/api/rules`;
    fetch(url, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.rules !== undefined) setRulesText(data.rules);
      })
      .catch(() => console.error("Could not fetch rules"));
  };

  const fetchSessions = (domain = selectedDomain) => {
    const url = domain ? `${API_BASE}/api/sessions?domain=${domain}` : `${API_BASE}/api/sessions`;
    fetch(url, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.sessions) setSessions(data.sessions);
      })
      .catch(() => console.error("Could not fetch sessions"));
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    fetch(`${API_BASE}/api/sessions/${sessionId}/messages`, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
        }
      })
      .catch(() => console.error("Could not fetch session messages"));
    setActiveTab('chat');
  };

  const handleNewSession = () => {
    setCurrentSessionId(null);
    setMessages([
      {
        id: '1',
        sender: 'assistant',
        text: 'Hello! I am Vero, your open-source analytics agent. Ask any analytical question, or click any table on the left to preview it.',
        suggested_followups: [
          'Show total revenue by customer',
          'What is our annual recurring revenue?',
          'List active users who signed up this year'
        ]
      }
    ]);
    setActiveTab('chat');
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { 
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        if (currentSessionId === sessionId) handleNewSession();
        fetchSessions(selectedDomain);
        addToast('Chat session deleted', 'info');
      }
    } catch (err) {
      addToast(`Failed to delete session: ${err}`, 'error');
    }
  };

  const fetchTiles = (domain = selectedDomain) => {
    const url = domain ? `${API_BASE}/api/dashboard/tiles?domain=${domain}` : `${API_BASE}/api/dashboard/tiles`;
    fetch(url, { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data.tiles) setTiles(data.tiles);
      })
      .catch(() => console.error("Could not fetch dashboard tiles"));
  };

  const handlePinTile = async (tileData: {
    title: string;
    tile_type: 'kpi' | 'chart' | 'table';
    chart_type?: string;
    sql?: string;
    data?: any;
  }) => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/tiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ ...tileData, domain: selectedDomain })
      });
      if (res.ok) {
        fetchTiles(selectedDomain);
        addToast(`Pinned "${tileData.title}" to Dashboard Canvas`, 'success');
      }
    } catch (err) {
      addToast(`Failed to pin tile: ${err}`, 'error');
    }
  };

  const handleUnpinTile = async (tileId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/tiles/${tileId}`, { 
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        fetchTiles(selectedDomain);
        addToast('Tile unpinned from dashboard', 'info');
      }
    } catch (err) {
      addToast(`Failed to unpin tile: ${err}`, 'error');
    }
  };

  const handleRefreshDashboard = () => {
    setRefreshingDashboard(true);
    fetchTiles(selectedDomain);
    setTimeout(() => setRefreshingDashboard(false), 500);
  };

  const handleSaveRules = async () => {
    setRulesSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/rules`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ rules: rulesText, domain: selectedDomain })
      });
      if (res.ok) {
        setRulesSavedToast(true);
        addToast(`Business rules saved for domain '${selectedDomain}'`, 'success');
        setTimeout(() => setRulesSavedToast(false), 2500);
      }
    } catch (err) {
      addToast(`Failed to save rules: ${err}`, 'error');
    } finally {
      setRulesSaving(false);
    }
  };

  const handleCreateMetric = async () => {
    if (!newMetric.name.trim() || !newMetric.sql.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/metrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          ...newMetric,
          domain: newMetric.domain || selectedDomain
        })
      });
      if (res.ok) {
        setNewMetric({ name: '', description: '', sql: '', domain: selectedDomain });
        setShowAddMetric(false);
        fetchMetrics(selectedDomain);
        addToast(`Semantic metric '${newMetric.name}' saved!`, 'success');
      }
    } catch (err) {
      addToast(`Failed to create metric: ${err}`, 'error');
    }
  };

  const handleImportMetrics = async () => {
    if (!importMetricContent.trim()) return;
    setImportMetricLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/metrics/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          source: importMetricSource,
          content: importMetricContent,
          domain: selectedDomain
        })
      });
      const data = await res.json();
      if (res.ok) {
        setShowImportMetricModal(false);
        setImportMetricContent('');
        fetchMetrics(selectedDomain);
        addToast(`Successfully imported ${data.imported_count} metrics from ${importMetricSource.toUpperCase()}`, 'success');
      } else {
        addToast(data.detail || 'Failed to import metrics', 'error');
      }
    } catch (err: any) {
      addToast(`Failed to import metrics: ${err.message || err}`, 'error');
    } finally {
      setImportMetricLoading(false);
    }
  };

  const handleDeleteMetric = async (metricName: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/metrics/${metricName}?domain=${selectedDomain}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        fetchMetrics(selectedDomain);
        addToast(`Metric '${metricName}' removed`, 'info');
      }
    } catch (err) {
      addToast(`Failed to delete metric: ${err}`, 'error');
    }
  };

  const handleTeachVero = async (ruleText: string) => {
    if (!ruleText.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/rules/append`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ rule: ruleText, domain: selectedDomain })
      });
      if (res.ok) {
        setTeachingMsgId(null);
        setTeachRuleInput('');
        fetchRules(selectedDomain);
        addToast(`Rule saved for domain '${selectedDomain}'!`, 'success');
      }
    } catch (err) {
      addToast(`Failed to save rule: ${err}`, 'error');
    }
  };

  useEffect(() => {
    fetchDomains();
    fetchConfig();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchSchemas(selectedDomain);
    fetchMetrics(selectedDomain);
    fetchRules(selectedDomain);
    fetchSessions(selectedDomain);
    fetchTiles(selectedDomain);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDomain]);

  const handleSyncSchemas = async () => {
    setSyncing(true);
    try {
      await fetch(`${API_BASE}/api/sync`, { method: 'POST' });
      fetchSchemas();
    } catch (err) {
      console.error("Failed to sync schemas:", err);
    } finally {
      setSyncing(false);
    }
  };

  const sendMessage = async (textToSend: string) => {
    if (!textToSend.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: textToSend
    };

    const assistantMsgId = (Date.now() + 1).toString();
    const initialAssistantMessage: Message = {
      id: assistantMsgId,
      sender: 'assistant',
      text: '',
      is_streaming: true,
      status_message: 'Grounding schemas & semantic metrics...'
    };

    setMessages(prev => [...prev, userMessage, initialAssistantMessage]);
    setInput('');
    setLoading(true);

    let activeSessId = currentSessionId;
    if (!activeSessId) {
      try {
        const sessRes = await fetch(`${API_BASE}/api/sessions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: textToSend.slice(0, 36), domain: selectedDomain })
        });
        if (sessRes.ok) {
          const sessData = await sessRes.json();
          activeSessId = sessData.id;
          setCurrentSessionId(activeSessId);
          fetchSessions(selectedDomain);
        }
      } catch (e) {
        console.error("Session creation error:", e);
      }
    }

    if (activeSessId) {
      fetch(`${API_BASE}/api/sessions/${activeSessId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userMessage)
      }).catch(err => console.error("Could not persist message:", err));
    }

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: textToSend, execute: true, domain: selectedDomain })
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
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';

          for (const block of parts) {
            const trimmed = block.trim();
            if (trimmed.startsWith('data: ')) {
              try {
                const event = JSON.parse(trimmed.slice(6));
                if (event.type === 'stage') {
                  setMessages(prev => prev.map(m => 
                    m.id === assistantMsgId ? { ...m, status_message: event.message } : m
                  ));
                } else if (event.type === 'complete') {
                  const data = event.result;
                  const completedAssistantMsg: Message = {
                    id: assistantMsgId,
                    sender: 'assistant',
                    text: data.explanation || 'Here is the query and data you requested.',
                    thought: data.thought,
                    sql: data.sql,
                    tables_used: data.tables_used,
                    suggested_followups: data.suggested_followups,
                    duration_ms: data.duration_ms,
                    reflection_steps: data.reflection_steps,
                    bytes_scanned: data.bytes_scanned,
                    bytes_formatted: data.bytes_formatted,
                    cost_usd: data.cost_usd,
                    cost_guard_passed: data.cost_guard_passed,
                    cache_hit: data.cache_hit,
                    telemetry: data.telemetry,
                    data: data.data,
                    suggested_visualization: data.suggested_visualization,
                    error: data.error,
                    is_streaming: false
                  };

                  setMessages(prev => prev.map(m => m.id === assistantMsgId ? completedAssistantMsg : m));

                  if (activeSessId) {
                    fetch(`${API_BASE}/api/sessions/${activeSessId}/messages`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(completedAssistantMsg)
                    }).catch(err => console.error("Could not persist assistant message:", err));
                  }
                }
              } catch (parseErr) {
                console.error("Error parsing stream chunk:", parseErr);
              }
            }
          }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m => 
        m.id === assistantMsgId ? {
          ...m,
          text: `Error connecting to the Vero agent server.`,
          error: String(err),
          is_streaming: false
        } : m
      ));
    } finally {
      setLoading(false);
    }
  };

  const handleSend = () => {
    sendMessage(input);
  };

  const handleExecuteSql = async (sql: string) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ sql })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Execution failed');
      return { data: data.data, duration_ms: data.duration_ms };
    } catch (err: any) {
      addToast(`Query error: ${err.message || err}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handlePreviewTable = async (tableName: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/tables/${tableName}/preview`);
      if (res.ok) {
        const data = await res.json();
        setEditorSql(data.sql);
        setActiveTab('scratchpad');
      } else {
        setEditorSql(`SELECT * FROM ${tableName} LIMIT 10;`);
        setActiveTab('scratchpad');
      }
    } catch {
      setEditorSql(`SELECT * FROM ${tableName} LIMIT 10;`);
      setActiveTab('scratchpad');
    } finally {
      setLoading(false);
    }
  };

  const handleQueryTable = (tableName: string) => {
    setInput(`Analyze table ${tableName} and show key statistics`);
    setActiveTab('chat');
  };

  const handleOpenInEditor = (sql: string) => {
    setEditorSql(sql);
    setActiveTab('scratchpad');
  };

  const isSingleMetric = (data: Message['data']) => {
    return data && data.columns.length === 1 && data.rows.length === 1;
  };

  return (
    <div className="app-container" data-theme={theme}>
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
            <Terminal size={15} />
            <span>Agent Copilot</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'scratchpad' ? 'active' : ''}`}
            onClick={() => setActiveTab('scratchpad')}
          >
            <TerminalSquare size={15} />
            <span>SQL Studio</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={15} />
            <span>Dashboard Canvas</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'observability' ? 'active' : ''}`}
            onClick={() => setActiveTab('observability')}
            title="Observability & Cost Intelligence"
          >
            <Activity size={15} />
            <span>Observability</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'metrics' ? 'active' : ''}`}
            onClick={() => setActiveTab('metrics')}
          >
            <LineChartIcon size={15} />
            <span>Semantic Layer</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'rules' ? 'active' : ''}`}
            onClick={() => setActiveTab('rules')}
          >
            <BookOpen size={15} />
            <span>Rules & Context</span>
          </div>
        </nav>

        {/* Chat Sessions / Threads */}
        <div className="sidebar-sessions-section">
          <button className="new-chat-btn" onClick={handleNewSession} title="Start new conversation">
            <MessageSquarePlus size={13} />
            <span>New Chat</span>
          </button>
          {sessions.map(s => (
            <div 
              key={s.id} 
              className={`session-row ${currentSessionId === s.id ? 'active' : ''}`}
              onClick={() => handleSelectSession(s.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
                <MessageSquare size={12} color="var(--accent-color)" />
                <span className="session-title">{s.title || 'Untitled Session'}</span>
              </div>
              <Trash2 
                size={11} 
                color="var(--text-muted)" 
                style={{ cursor: 'pointer', opacity: 0.7 }}
                onClick={(e) => handleDeleteSession(s.id, e)}
              />
            </div>
          ))}
        </div>

        <div className="schemas-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span className="section-label">Database Catalog ({schemas.length})</span>
            <span title="Introspect warehouse" style={{ display: 'inline-flex', cursor: 'pointer' }} onClick={handleSyncSchemas}>
              <RefreshCw 
                size={12} 
                color="#8b949e" 
                style={{ animation: syncing ? 'spin 1s linear infinite' : 'none' }}
              />
            </span>
          </div>

          <SchemaTree
            schemas={schemas}
            selectedTable={selectedSchema?.table || null}
            onSelectTable={(s) => {
              setSelectedSchema(s);
              handlePreviewTable(s.table);
            }}
            onPreviewTable={handlePreviewTable}
            onQueryTable={handleQueryTable}
          />
        </div>
      </aside>

      {/* Main Studio Area */}
      <main className="main-area">
        <header className="top-bar">
          <div className="top-bar-left">
            <div className="domain-selector-wrapper" title="Filter context by business domain">
              <Layers size={13} color="var(--accent-color)" />
              <select
                className="domain-select"
                value={selectedDomain}
                onChange={e => setSelectedDomain(e.target.value)}
              >
                {domains.map(d => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div className="warehouse-badge" title={`Connected to ${dialect} Data Warehouse`}>
              <Database size={12} color="var(--accent-color)" />
              <span>{dialect}</span>
            </div>
          </div>

          <div className="top-bar-right">
            {authConfig?.mode !== 'oidc' ? (
              <div className="user-profile-badge">
                <Shield size={13} color="var(--accent-color)" />
                <span className="user-profile-name">Local Engineer</span>
                <span className="user-role-tag admin">OSS</span>
              </div>
            ) : currentUser ? (
              <div className="user-profile-badge">
                <Shield size={13} color="var(--accent-color)" />
                <span className="user-profile-name">{currentUser.name}</span>
                <span className={`user-role-tag ${currentUser.role}`}>{currentUser.role.toUpperCase()}</span>
                <button 
                  className="user-logout-btn" 
                  onClick={handleLogout}
                  title="Sign Out"
                >
                  <LogOut size={12} />
                </button>
              </div>
            ) : (
              <button 
                className="theme-toggle-btn"
                onClick={() => setShowLoginModal(true)}
                title={`Sign in with ${authConfig?.provider_name || 'Okta'}`}
              >
                <Lock size={13} />
                <span>Sign In ({authConfig?.provider_name || 'SSO'})</span>
              </button>
            )}

            <button 
              className="theme-toggle-btn"
              onClick={() => {
                setTeamTab('domains');
                setShowTeamModal(true);
              }}
              title="Manage business domain namespaces"
            >
              <Layers size={13} color="var(--accent-color)" />
              <span>Domains</span>
            </button>

            {currentUser?.role === 'admin' && authConfig?.mode === 'oidc' && (
              <button 
                className="theme-toggle-btn"
                onClick={() => {
                  fetchUsers();
                  setTeamTab('users');
                  setShowTeamModal(true);
                }}
                title="Manage Team Members & Roles"
              >
                <Users size={13} color="var(--accent-color)" />
                <span>Team</span>
              </button>
            )}

            <button 
              className="theme-toggle-btn"
              onClick={() => setTheme(prev => prev === 'light' ? 'dark' : 'light')}
              title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
            >
              {theme === 'light' ? <Moon size={13} /> : <Sun size={13} />}
              <span>{theme === 'light' ? 'Dark Mode' : 'Light Mode'}</span>
            </button>
          </div>
        </header>

        {activeTab === 'chat' && (
          <>
            <div className="chat-container">
              {messages.map(msg => (
                <div key={msg.id} className={`message-card ${msg.sender}`}>
                  <div className="message-header">
                    {msg.sender === 'assistant' ? <Bot size={16} /> : <User size={16} />}
                    <span>{msg.sender === 'assistant' ? 'Vero Analytics Agent' : 'You'}</span>
                  </div>

                  {msg.is_streaming ? (
                    <div className="streaming-stage-pill">
                      <Loader2 size={13} className="spin" />
                      <span>{msg.status_message || 'Analyzing warehouse...'}</span>
                    </div>
                  ) : (
                    <div className="message-body">{msg.text}</div>
                  )}

                  {/* Context Grounding & Multi-Step Reasoning Trace */}
                  {msg.sender === 'assistant' && (
                    <ReasoningSteps
                      thought={msg.thought}
                      tablesUsed={msg.tables_used}
                      durationMs={msg.duration_ms}
                      dialect={dialect}
                      reflectionSteps={msg.reflection_steps}
                      bytesFormatted={msg.bytes_formatted}
                      costUsd={msg.cost_usd}
                      telemetry={msg.telemetry}
                      cacheHit={msg.cache_hit}
                    />
                  )}

                  {/* Generated SQL Artifact with Quick Actions */}
                  {msg.sql && (
                    <SqlCard
                      sql={msg.sql}
                      durationMs={msg.duration_ms}
                      rowCount={msg.data?.row_count}
                      dialect={dialect}
                      bytesFormatted={msg.bytes_formatted}
                      costUsd={msg.cost_usd}
                      costGuardPassed={msg.cost_guard_passed}
                      totalTokens={msg.telemetry?.total_tokens}
                      cacheHit={msg.cache_hit}
                      onOpenInEditor={handleOpenInEditor}
                      onPin={() => handlePinTile({
                        title: msg.text.slice(0, 36) || 'Query Result',
                        tile_type: isSingleMetric(msg.data) ? 'kpi' : (msg.suggested_visualization && msg.suggested_visualization !== 'table' ? 'chart' : 'table'),
                        chart_type: msg.suggested_visualization || 'bar',
                        sql: msg.sql,
                        data: msg.data
                      })}
                    />
                  )}

                  {/* Single Value Metric KPI Card */}
                  {isSingleMetric(msg.data) && (
                    <div style={{ marginTop: '16px' }}>
                      <MetricCard 
                        label={msg.data!.columns[0]} 
                        value={msg.data!.rows[0][0]} 
                      />
                    </div>
                  )}

                  {/* Interactive Rich Data Table */}
                  {msg.data && !isSingleMetric(msg.data) && (
                    <DataTable 
                      columns={msg.data.columns} 
                      rows={msg.data.rows} 
                      tableName="vero_analytics_result"
                      maskedColumns={msg.data.masked_columns}
                    />
                  )}

                  {/* Recharts Visualizer */}
                  {!isSingleMetric(msg.data) && msg.suggested_visualization && msg.suggested_visualization !== 'table' && msg.data && (
                    <div className="chart-container">
                      <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '12px' }}>
                        Data Visualization ({msg.suggested_visualization})
                      </div>
                      <ChartVisualizer type={msg.suggested_visualization} data={msg.data} />
                    </div>
                  )}

                  {/* Diagnostic Root Cause Analysis Engine */}
                  {msg.sender === 'assistant' && msg.sql && !msg.is_streaming && !isSingleMetric(msg.data) && (
                    <div style={{ marginTop: '12px' }}>
                      {!msg.diagnostics && diagnosticLoadingId !== msg.id && (
                        <button 
                          className="editor-tool-btn"
                          onClick={() => handleRunDiagnostics(msg.id, msg.sql!)}
                          title="Run automated RCA to find the statistical drivers of this metric"
                        >
                          <Sparkles size={13} color="var(--accent-color)" />
                          <span>Explain Why (Run Diagnostics)</span>
                        </button>
                      )}

                      {diagnosticLoadingId === msg.id && (
                        <div className="streaming-stage-pill" style={{ display: 'inline-flex', marginTop: '0' }}>
                          <Loader2 size={13} className="spin" color="var(--accent-color)" />
                          <span>Slicing metric by dimensions to find top drivers...</span>
                        </div>
                      )}

                      {msg.diagnostics && (
                        <div className="diagnostics-card">
                          <div className="diagnostics-header">
                            <Sparkles size={14} color="var(--accent-color)" />
                            <span>Root Cause Analysis (Drivers)</span>
                          </div>
                          <div className="diagnostics-summary">
                            {msg.diagnostics.summary}
                          </div>
                          <div className="diagnostics-tables">
                            {msg.diagnostics.findings.map((f, i) => (
                              <div key={i} className="diagnostic-finding">
                                <div className="diagnostic-dim-label">Top Segments by {f.dimension}</div>
                                <table className="data-table">
                                  <tbody>
                                    {f.data.map((row, rowIdx) => (
                                      <tr key={rowIdx}>
                                        <td style={{ width: '60%' }}>{row[0] || 'Unknown'}</td>
                                        <td style={{ textAlign: 'right', fontWeight: 600, color: 'var(--text-primary)' }}>
                                          {typeof row[1] === 'number' && row[1] % 1 !== 0 ? row[1].toFixed(2) : row[1]}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Dynamic Follow-up Prompt Chips */}
                  {msg.suggested_followups && msg.suggested_followups.length > 0 && (
                    <PromptChips
                      suggestions={msg.suggested_followups}
                      onSelect={(chipText) => sendMessage(chipText)}
                      disabled={loading}
                    />
                  )}

                  {/* Teach Vero Action */}
                  {msg.sender === 'assistant' && !msg.is_streaming && (
                    <div style={{ marginTop: '12px' }}>
                      {teachingMsgId === msg.id ? (
                        <div className="teach-vero-dialog">
                          <BookmarkPlus size={15} color="var(--accent-color)" />
                          <input
                            type="text"
                            className="metric-input"
                            style={{ flex: 1 }}
                            placeholder="e.g. Always exclude accounts with status = 'internal'"
                            value={teachRuleInput}
                            onChange={e => setTeachRuleInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleTeachVero(teachRuleInput)}
                          />
                          <button 
                            className="save-rules-btn"
                            style={{ padding: '6px 12px', fontSize: '12px' }}
                            onClick={() => handleTeachVero(teachRuleInput)}
                          >
                            Save Rule
                          </button>
                          <button 
                            className="editor-tool-btn"
                            style={{ padding: '6px 10px', fontSize: '12px' }}
                            onClick={() => setTeachingMsgId(null)}
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button 
                          className="teach-vero-btn"
                          onClick={() => {
                            setTeachingMsgId(msg.id);
                            setTeachRuleInput('');
                          }}
                          title="Save a clarification or convention as a persistent business rule"
                        >
                          <BookmarkPlus size={13} />
                          <span>Teach Vero (Save Rule)</span>
                        </button>
                      )}
                    </div>
                  )}

                  {msg.error && (
                    <div style={{ color: '#f85149', marginTop: '12px', fontSize: '13px' }}>
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
                  placeholder="Ask a question about your warehouse (e.g. 'Show total revenue by customer')..."
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

        {/* SQL Studio Editor Tab */}
        {activeTab === 'scratchpad' && (
          <SqlEditor
            initialSql={editorSql}
            dialect={dialect}
            onExecute={handleExecuteSql}
            loading={loading}
            apiBase={API_BASE}
            canExecute={currentUser ? currentUser.role !== 'viewer' : true}
          />
        )}

        {/* Dashboard Canvas Tab */}
        {activeTab === 'dashboard' && (
          <DashboardCanvas
            tiles={tiles}
            selectedDomain={selectedDomain}
            onUnpinTile={handleUnpinTile}
            onOpenInStudio={handleOpenInEditor}
            onRefresh={handleRefreshDashboard}
            refreshing={refreshingDashboard}
          />
        )}

        {/* Observability & Cost Intelligence Tab */}
        {activeTab === 'observability' && (
          <div className="observability-page-wrapper">
            <ObservabilityDashboard 
              apiBase={API_BASE}
              onOpenQueryInEditor={(sql) => {
                setEditorSql(sql);
                setActiveTab('scratchpad');
              }}
            />
          </div>
        )}

        {/* Semantic Layer Manager Tab */}
        {activeTab === 'metrics' && (
          <div className="metrics-viewer">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h2 style={{ fontSize: '20px' }}>Semantic Layer (Metrics)</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  className="editor-tool-btn"
                  onClick={() => setShowImportMetricModal(true)}
                  title="Import metrics from Looker LookML, dbt, or Cube"
                >
                  <RefreshCw size={13} />
                  <span>Import External Metrics</span>
                </button>
                <button 
                  className="save-rules-btn"
                  style={{ padding: '6px 12px', fontSize: '12px' }}
                  onClick={() => setShowAddMetric(!showAddMetric)}
                >
                  <Plus size={14} />
                  <span>{showAddMetric ? 'Cancel' : 'Add Metric'}</span>
                </button>
              </div>
            </div>
            <p style={{ color: 'var(--text-muted)', marginBottom: '20px', fontSize: '13.5px' }}>
              These business metrics are automatically injected into the agent's context, grounding the LLM in your warehouse logic.
            </p>

            {/* Semantic Importer Modal */}
            {showImportMetricModal && (
              <div className="login-modal-overlay">
                <div className="login-modal-card">
                  <div className="login-modal-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Database size={18} color="var(--accent-color)" />
                      <h3 className="login-modal-title">Import Semantic Layer</h3>
                    </div>
                    <button className="login-close-btn" onClick={() => setShowImportMetricModal(false)}>×</button>
                  </div>
                  
                  <p className="login-modal-subtitle">
                    Paste the contents of your LookML, dbt manifest, or Cube schema file below.
                  </p>

                  <div className="login-form">
                    <div className="login-input-group">
                      <label className="login-label">Source Framework</label>
                      <select 
                        className="login-input"
                        value={importMetricSource}
                        onChange={(e) => setImportMetricSource(e.target.value as any)}
                      >
                        <option value="lookml">Looker (LookML .lkml)</option>
                        <option value="dbt">dbt (manifest.json)</option>
                        <option value="cube">Cube.js (Schema YAML/JSON)</option>
                      </select>
                    </div>

                    <div className="login-input-group">
                      <label className="login-label">File Content</label>
                      <textarea 
                        className="login-input"
                        style={{ height: '200px', fontFamily: 'var(--font-mono)', fontSize: '11px', resize: 'vertical' }}
                        value={importMetricContent}
                        onChange={(e) => setImportMetricContent(e.target.value)}
                        placeholder={`Paste ${importMetricSource.toUpperCase()} content here...`}
                        spellCheck={false}
                      />
                    </div>

                    <button 
                      className="login-submit-btn" 
                      onClick={handleImportMetrics}
                      disabled={importMetricLoading || !importMetricContent.trim()}
                    >
                      {importMetricLoading ? 'Importing...' : 'Sync Metrics to Vero'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Metric Creator Form */}
            {showAddMetric && (
              <div className="metric-create-card">
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-main)' }}>
                  Define New Semantic Metric
                </div>
                <div className="metric-form-grid">
                  <input
                    type="text"
                    className="metric-input"
                    placeholder="Metric Name (e.g. gross_margin)"
                    value={newMetric.name}
                    onChange={e => setNewMetric({ ...newMetric, name: e.target.value })}
                  />
                  <select
                    className="metric-input"
                    value={newMetric.domain || selectedDomain}
                    onChange={e => setNewMetric({ ...newMetric, domain: e.target.value })}
                  >
                    {domains.map(d => (
                      <option key={d.id} value={d.id}>Domain: {d.name}</option>
                    ))}
                  </select>
                </div>
                <input
                  type="text"
                  className="metric-input"
                  placeholder="Description (e.g. Total revenue minus COGS)"
                  value={newMetric.description}
                  onChange={e => setNewMetric({ ...newMetric, description: e.target.value })}
                />
                <input
                  type="text"
                  className="metric-input"
                  style={{ fontFamily: 'var(--font-mono)' }}
                  placeholder="SQL Aggregation (e.g. SUM(revenue - cogs))"
                  value={newMetric.sql}
                  onChange={e => setNewMetric({ ...newMetric, sql: e.target.value })}
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                  <button 
                    className="editor-tool-btn" 
                    onClick={() => setShowAddMetric(false)}
                  >
                    Cancel
                  </button>
                  <button 
                    className="save-rules-btn" 
                    onClick={handleCreateMetric}
                    disabled={!newMetric.name || !newMetric.sql}
                  >
                    Save Metric
                  </button>
                </div>
              </div>
            )}

            {semanticMetrics.length === 0 ? (
              <div style={{ color: '#8b949e' }}>No metrics defined yet. Click "Add Metric" to define your first business KPI.</div>
            ) : (
              semanticMetrics.map(m => (
                <div key={`${m.name}-${m.domain || 'global'}`} className="semantic-metric-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div className="semantic-metric-name">{m.name}</div>
                      <span className="column-type-badge">{m.domain || 'global'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button 
                        className="sql-action-btn highlight"
                        onClick={() => {
                          setEditorSql(`SELECT ${m.sql} AS ${m.name};`);
                          setActiveTab('scratchpad');
                        }}
                      >
                        <Play size={11} />
                        <span>Run in Studio</span>
                      </button>
                      <button 
                        className="sql-action-btn"
                        onClick={() => handleDeleteMetric(m.name)}
                        title="Delete Metric"
                      >
                        <Trash2 size={11} color="#f85149" />
                      </button>
                    </div>
                  </div>
                  <div className="semantic-metric-desc">{m.description}</div>
                  <div className="sql-box" style={{ margin: 0, backgroundColor: 'var(--code-bg)' }}>
                    {m.sql}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Rules & Guidelines Editor Tab */}
        {activeTab === 'rules' && (
          <div className="rules-editor-container">
            <div className="rules-editor-header">
              <div>
                <h2 style={{ fontSize: '20px', color: 'var(--text-main)', marginBottom: '4px' }}>Business Rules & SQL Guidelines</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                  Define organization-wide data conventions, fiscal periods, and SQL rules injected into every agent prompt.
                </p>
              </div>
              <button 
                className="save-rules-btn" 
                onClick={handleSaveRules}
                disabled={rulesSaving}
              >
                {rulesSavedToast ? <Check size={14} /> : <Save size={14} />}
                <span>{rulesSavedToast ? 'Saved!' : rulesSaving ? 'Saving...' : 'Save Rules'}</span>
              </button>
            </div>

            <textarea 
              className="rules-textarea"
              value={rulesText}
              onChange={e => setRulesText(e.target.value)}
              placeholder="# Corporate SQL Guidelines&#10;- Always filter out test accounts&#10;- Fiscal year begins in February"
              spellCheck={false}
            />
          </div>
        )}
      </main>

      {/* Team & Domains Management Modal */}
      {showTeamModal && (
        <div className="login-modal-overlay">
          <div className="login-modal-card team-modal-card">
            <div className="login-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Users size={18} color="var(--accent-color)" />
                <h3 className="login-modal-title">Team & Domain Management</h3>
              </div>
              <button className="login-close-btn" onClick={() => setShowTeamModal(false)}>×</button>
            </div>

            <p className="login-modal-subtitle">
              Provision enterprise users, assign role permissions, and partition warehouse domain scopes.
            </p>

            <div className="login-mode-tabs">
              <button 
                type="button"
                className={`login-mode-tab ${teamTab === 'users' ? 'active' : ''}`}
                onClick={() => setTeamTab('users')}
              >
                Team Members ({userList.length})
              </button>
              <button 
                type="button"
                className={`login-mode-tab ${teamTab === 'domains' ? 'active' : ''}`}
                onClick={() => setTeamTab('domains')}
              >
                Domains ({domains.length})
              </button>
            </div>

            {teamTab === 'users' && (
              <div className="team-tab-content">
                {/* Add User Form */}
                <form onSubmit={handleCreateUser} className="team-create-form">
                  <div className="team-form-grid">
                    <input 
                      type="text"
                      className="login-input"
                      placeholder="Full Name"
                      value={newUserForm.name}
                      onChange={e => setNewUserForm({ ...newUserForm, name: e.target.value })}
                      required
                    />
                    <input 
                      type="email"
                      className="login-input"
                      placeholder="user@company.com"
                      value={newUserForm.email}
                      onChange={e => setNewUserForm({ ...newUserForm, email: e.target.value })}
                      required
                    />
                    <select
                      className="login-input"
                      value={newUserForm.role}
                      onChange={e => setNewUserForm({ ...newUserForm, role: e.target.value })}
                    >
                      <option value="analyst">Analyst (Chat + SQL)</option>
                      <option value="viewer">Viewer (Read-only)</option>
                      <option value="admin">Admin (Full Control)</option>
                    </select>
                    <select
                      className="login-input"
                      value={newUserForm.domain}
                      onChange={e => setNewUserForm({ ...newUserForm, domain: e.target.value })}
                    >
                      <option value="*">* (All Domains)</option>
                      {domains.filter(d => d.id !== 'global').map(d => (
                        <option key={d.id} value={d.id}>Domain: {d.name}</option>
                      ))}
                    </select>
                  </div>
                  <button type="submit" className="login-submit-btn" disabled={teamLoading}>
                    {teamLoading ? 'Provisioning...' : '+ Add User'}
                  </button>
                </form>

                {createdApiKey && (
                  <div className="created-key-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, color: '#10b981' }}>User Provisioned Successfully!</span>
                      <button 
                        className="copy-key-btn"
                        onClick={() => {
                          navigator.clipboard.writeText(createdApiKey);
                          setCopiedKey(true);
                          setTimeout(() => setCopiedKey(false), 2000);
                        }}
                      >
                        {copiedKey ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                        <span>{copiedKey ? 'Copied' : 'Copy API Key'}</span>
                      </button>
                    </div>
                    <code className="api-key-code">{createdApiKey}</code>
                  </div>
                )}

                {/* Users List Table */}
                <div className="team-user-list">
                  {userList.map(u => (
                    <div key={u.id} className="team-user-row">
                      <div className="user-row-info">
                        <div className="user-row-name">{u.name}</div>
                        <div className="user-row-email">{u.email}</div>
                      </div>
                      <div className="user-row-meta">
                        <span className={`user-role-tag ${u.role}`}>{u.role.toUpperCase()}</span>
                        <span className="user-domain-badge">{u.allowed_domains.join(', ')}</span>
                        {currentUser?.id !== u.id && (
                          <button 
                            className="delete-user-btn" 
                            onClick={() => handleDeleteUser(u.id)}
                            title="Remove User"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {teamTab === 'domains' && (
              <div className="team-tab-content">
                {/* Add Domain Form */}
                <form onSubmit={handleCreateDomain} className="team-create-form">
                  <div className="team-form-grid">
                    <input 
                      type="text"
                      className="login-input"
                      placeholder="Domain Slug (e.g. sales)"
                      value={newDomainForm.id}
                      onChange={e => setNewDomainForm({ ...newDomainForm, id: e.target.value })}
                      required
                    />
                    <input 
                      type="text"
                      className="login-input"
                      placeholder="Display Name (e.g. Sales & Pipeline)"
                      value={newDomainForm.name}
                      onChange={e => setNewDomainForm({ ...newDomainForm, name: e.target.value })}
                      required
                    />
                    <input 
                      type="text"
                      className="login-input"
                      placeholder="Description (Scope & context)"
                      value={newDomainForm.description}
                      onChange={e => setNewDomainForm({ ...newDomainForm, description: e.target.value })}
                    />
                  </div>
                  <button type="submit" className="login-submit-btn" disabled={teamLoading}>
                    {teamLoading ? 'Creating...' : '+ Create Domain'}
                  </button>
                </form>

                {/* Domains List */}
                <div className="team-user-list">
                  {domains.map(d => (
                    <div key={d.id} className="team-user-row">
                      <div className="user-row-info">
                        <div className="user-row-name">{d.name}</div>
                        <div className="user-row-email">ID: <code>{d.id}</code></div>
                      </div>
                      <div className="user-row-meta">
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{d.description}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Enterprise Login Modal */}
      {showLoginModal && (
        <div className="login-modal-overlay">
          <div className="login-modal-card">
            <div className="login-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={18} color="var(--accent-color)" />
                <h3 className="login-modal-title">Sign in to Vero</h3>
              </div>
              <button className="login-close-btn" onClick={() => setShowLoginModal(false)}>×</button>
            </div>

            <p className="login-modal-subtitle">
              Access your assigned business domains, SQL Studio, and semantic models.
            </p>

            {authConfig?.mode === 'oidc' && (
              <div style={{ marginBottom: '16px' }}>
                <button 
                  type="button" 
                  className="login-oidc-btn"
                  onClick={() => handleOidcLogin(authConfig.provider_name)}
                  disabled={loginLoading}
                >
                  <Shield size={16} color="var(--accent-color)" />
                  <span>Single Sign-On with {authConfig.provider_name}</span>
                </button>
                <div className="login-divider">
                  <span>or enter API key / password</span>
                </div>
              </div>
            )}

            <div className="login-mode-tabs">
              <button 
                type="button"
                className={`login-mode-tab ${loginForm.mode === 'password' ? 'active' : ''}`}
                onClick={() => setLoginForm({ ...loginForm, mode: 'password' })}
              >
                Password
              </button>
              <button 
                type="button"
                className={`login-mode-tab ${loginForm.mode === 'api_key' ? 'active' : ''}`}
                onClick={() => setLoginForm({ ...loginForm, mode: 'api_key' })}
              >
                API Key
              </button>
            </div>

            <form onSubmit={handleLogin} className="login-form">
              {loginForm.mode === 'password' ? (
                <>
                  <div className="login-input-group">
                    <label className="login-label">Email Address</label>
                    <input 
                      type="email" 
                      className="login-input"
                      placeholder="admin@verodata.dev"
                      value={loginForm.email}
                      onChange={e => setLoginForm({ ...loginForm, email: e.target.value })}
                      required
                    />
                  </div>
                  <div className="login-input-group">
                    <label className="login-label">Password</label>
                    <input 
                      type="password" 
                      className="login-input"
                      placeholder="••••••••"
                      value={loginForm.password}
                      onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
                      required
                    />
                  </div>
                </>
              ) : (
                <div className="login-input-group">
                  <label className="login-label">API Key</label>
                  <input 
                    type="password" 
                    className="login-input"
                    placeholder="vero_..."
                    value={loginForm.apiKey}
                    onChange={e => setLoginForm({ ...loginForm, apiKey: e.target.value })}
                    required
                  />
                </div>
              )}

              {loginError && (
                <div className="login-error-msg">{loginError}</div>
              )}

              <button type="submit" className="login-submit-btn" disabled={loginLoading}>
                {loginLoading ? 'Authenticating...' : 'Sign In'}
              </button>

              <div className="login-hint">
                Default credentials: <code>admin@verodata.dev</code> / <code>admin</code>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Floating Toast Notification Stack */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast-card ${t.type}`}>
            <div className="toast-icon">
              {t.type === 'success' && <CheckCircle2 size={16} color="#10b981" />}
              {t.type === 'warning' && <AlertTriangle size={16} color="#f59e0b" />}
              {t.type === 'error' && <XCircle size={16} color="#ef4444" />}
              {t.type === 'info' && <Info size={16} color="var(--accent-color)" />}
            </div>
            <div className="toast-message">{t.message}</div>
            <button className="toast-close-btn" onClick={() => removeToast(t.id)}>
              <X size={13} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
