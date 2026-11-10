import React, { useState, useMemo } from 'react';
import { 
  ShieldAlert, 
  Server, 
  Users, 
  HardDrive, 
  CheckCircle2, 
  AlertCircle, 
  Activity, 
  Terminal, 
  Database, 
  ShieldCheck, 
  Layers, 
  FileText,
  Download,
  Search,
  Filter,
  UserCheck,
  UserX,
  Lock,
  Unlock,
  RefreshCw
} from 'lucide-react';
import { User, Tenant, AuditLogItem, PlanType } from '../types';
import { formatBytes } from '../services/crypto';

interface AdminConsoleProps {
  tenants: Tenant[];
  users: User[];
  auditLogs: AuditLogItem[];
  onUpdateUserStatus?: (userId: string, isActive: boolean) => void;
  onUpdateTenantPlan?: (tenantId: string, planId: PlanType) => void;
}

export const AdminConsole: React.FC<AdminConsoleProps> = ({
  tenants,
  users,
  auditLogs,
  onUpdateUserStatus,
  onUpdateTenantPlan,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'services' | 'logs'>('overview');
  const [logFilterQuery, setLogFilterQuery] = useState('');
  const [logActionFilter, setLogActionFilter] = useState('all');

  const totalUsedStorage = tenants.reduce((acc, t) => acc + (t.usedBytes || 0), 0);
  const totalDocs = tenants.reduce((acc, t) => acc + (t.documentCount || 0), 0);

  const services = [
    { name: 'PostgreSQL 16 (RLS Actif)', status: 'Opérationnel', uptime: '99.98%', desc: 'Isolation des tables via app.current_tenant_id', icon: Database, color: 'text-emerald-400' },
    { name: 'MinIO S3 Object Storage', status: 'Opérationnel', uptime: '99.99%', desc: 'Bucket docuspace-documents chiffré', icon: HardDrive, color: 'text-emerald-400' },
    { name: 'ClamAV Antivirus Daemon', status: 'Actif (Fail-Closed)', uptime: '100%', desc: 'Définitions virales à jour (Version 1.3.1)', icon: ShieldCheck, color: 'text-emerald-400' },
    { name: 'Redis Cache & Tâches', status: 'Opérationnel', uptime: '99.95%', desc: 'Persistance AOF & gestion de verrous', icon: Activity, color: 'text-emerald-400' },
    { name: 'Nginx Reverse Proxy & WAF', status: 'Opérationnel', uptime: '100%', desc: 'Rate-limiting & terminaison HTTP/HTTPS', icon: Server, color: 'text-emerald-400' },
    { name: 'Sauvegardes Automatiques (pg_dump + S3)', status: 'À jour (2h00)', uptime: '100%', desc: 'Rétention 14 jours & checksums SHA256', icon: FileText, color: 'text-emerald-400' },
  ];

  // Filter audit logs
  const filteredLogs = useMemo(() => {
    return auditLogs.filter(log => {
      if (logActionFilter !== 'all' && log.action !== logActionFilter) return false;
      if (logFilterQuery.trim()) {
        const q = logFilterQuery.toLowerCase();
        const matches = 
          log.action.toLowerCase().includes(q) ||
          log.userEmail.toLowerCase().includes(q) ||
          log.resourceName.toLowerCase().includes(q) ||
          log.ipAddress.includes(q);
        if (!matches) return false;
      }
      return true;
    });
  }, [auditLogs, logFilterQuery, logActionFilter]);

  // Unique actions for filter
  const uniqueActions = useMemo(() => {
    return Array.from(new Set(auditLogs.map(l => l.action)));
  }, [auditLogs]);

  // Export Audit Logs (CSV / JSON)
  const exportAuditLogs = (format: 'csv' | 'json') => {
    if (format === 'csv') {
      const headers = ['id', 'timestamp', 'action', 'resourceName', 'userEmail', 'ipAddress', 'status'];
      const rows = filteredLogs.map(l => [
        l.id,
        `"${l.timestamp}"`,
        `"${l.action}"`,
        `"${l.resourceName}"`,
        `"${l.userEmail}"`,
        `"${l.ipAddress}"`,
        `"${l.status}"`
      ]);
      const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `docuspace_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      const jsonStr = JSON.stringify(filteredLogs, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `docuspace_audit_logs_${new Date().toISOString().slice(0, 10)}.json`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-purple-400 text-xs font-bold uppercase tracking-wider">
            <ShieldAlert className="w-4 h-4" />
            <span>Console d'Administration Globale</span>
          </div>
          <h2 className="text-xl font-extrabold text-white mt-1">Supervision Système & Audit</h2>
          <p className="text-xs text-slate-400">
            Contrôle d'intégrité, services conteneurisés Debian, gestion des espaces isolés et journalisation d'accès.
          </p>
        </div>

        {/* Tab switch */}
        <div className="flex p-1 bg-slate-900 border border-slate-800 rounded-xl text-xs font-medium">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'overview' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Espaces ({tenants.length})
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'users' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Utilisateurs ({users.length})
          </button>
          <button
            onClick={() => setActiveTab('services')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'services' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Services (6/6)
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'logs' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Journal d'Audit ({auditLogs.length})
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Espaces Isolés (Tenants)</span>
          <div className="text-2xl font-bold text-white">{tenants.length}</div>
          <span className="text-[10px] text-emerald-400 font-medium">100% RLS actif</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Utilisateurs inscrits</span>
          <div className="text-2xl font-bold text-white">{users.length}</div>
          <span className="text-[10px] text-blue-400 font-medium">Argon2id haché</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Volume MinIO stocké</span>
          <div className="text-2xl font-bold text-white font-mono">{formatBytes(totalUsedStorage)}</div>
          <span className="text-[10px] text-purple-400 font-medium">Stockage réparti</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Santé Globale Docker</span>
          <div className="text-2xl font-bold text-emerald-400">Optimal</div>
          <span className="text-[10px] text-slate-400 font-medium">Zéro alerte de sécurité</span>
        </div>
      </div>

      {/* Tab 1: Overview Tenants */}
      {activeTab === 'overview' && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Espaces Documentaires Multi-Tenants (Isolation PostgreSQL RLS)
            </h3>
            <span className="text-[10px] text-slate-400">Plafonds de stockage applicatifs</span>
          </div>

          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase">
              <tr>
                <th className="p-3 pl-4">Nom de l'espace</th>
                <th className="p-3">Identifiant Tenant (UUID)</th>
                <th className="p-3">Forfait</th>
                <th className="p-3">Stockage consommé</th>
                <th className="p-3">Statut Quota</th>
                <th className="p-3 text-right pr-4">Action Forfait</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {tenants.map((t) => (
                <tr key={t.id} className="hover:bg-slate-800/40">
                  <td className="p-3 pl-4 font-semibold text-slate-200">{t.name}</td>
                  <td className="p-3 font-mono text-[11px] text-slate-400">{t.id}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      {t.planId}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-slate-300">{formatBytes(t.usedBytes)}</td>
                  <td className="p-3">
                    {t.isRestrictedReadOnly ? (
                      <span className="inline-flex items-center space-x-1 text-amber-400 text-[11px] font-semibold">
                        <AlertCircle className="w-3.5 h-3.5" />
                        <span>Lecture Seule (Dépassement)</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center space-x-1 text-emerald-400 text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Opérationnel</span>
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-right pr-4">
                    {onUpdateTenantPlan && (
                      <select
                        value={t.planId}
                        onChange={(e) => onUpdateTenantPlan(t.id, e.target.value as PlanType)}
                        className="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-purple-500 cursor-pointer"
                      >
                        <option value="FREE">Forfait FREE</option>
                        <option value="PERSONAL">Forfait PERSONAL</option>
                        <option value="PREMIUM">Forfait PREMIUM</option>
                      </select>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 2: User Management */}
      {activeTab === 'users' && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Gestion des Utilisateurs & Contrôle d'Accès
            </h3>
            <span className="text-[10px] text-slate-400">Authentification Argon2id</span>
          </div>

          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase">
              <tr>
                <th className="p-3 pl-4">Nom complet</th>
                <th className="p-3">Adresse e-mail</th>
                <th className="p-3">Rôle Plateforme</th>
                <th className="p-3">Statut Compte</th>
                <th className="p-3">Date d'inscription</th>
                <th className="p-3 text-right pr-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-800/40">
                  <td className="p-3 pl-4 font-semibold text-slate-200">{u.fullName}</td>
                  <td className="p-3 text-slate-400">{u.email}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                      u.isSuperuser
                        ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                        : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                    }`}>
                      {u.isSuperuser ? 'Superadmin' : 'Utilisateur'}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={`inline-flex items-center space-x-1 text-[11px] font-medium ${
                      u.isActive ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {u.isActive ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                      <span>{u.isActive ? 'Actif' : 'Suspendu'}</span>
                    </span>
                  </td>
                  <td className="p-3 text-slate-500 text-[11px]">
                    {new Date(u.createdAt).toLocaleDateString('fr-FR')}
                  </td>
                  <td className="p-3 text-right pr-4">
                    {onUpdateUserStatus && !u.isSuperuser && (
                      <button
                        onClick={() => onUpdateUserStatus(u.id, !u.isActive)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1 ml-auto ${
                          u.isActive
                            ? 'bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30'
                            : 'bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {u.isActive ? <UserX className="w-3 h-3" /> : <UserCheck className="w-3 h-3" />}
                        <span>{u.isActive ? 'Suspendre' : 'Réactiver'}</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 3: Docker Services */}
      {activeTab === 'services' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {services.map((svc, idx) => {
            const Icon = svc.icon;
            return (
              <div
                key={idx}
                className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-start space-x-4"
              >
                <div className={`p-3 rounded-xl bg-slate-950 border border-slate-800 ${svc.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white">{svc.name}</h4>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {svc.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">{svc.desc}</p>
                  <div className="text-[10px] text-slate-500 pt-1 font-mono">
                    Disponibilité : {svc.uptime}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Tab 4: Audit Logs */}
      {activeTab === 'logs' && (
        <div className="space-y-4">
          {/* Controls: Search, Filter, Export */}
          <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-3 flex-1">
              <div className="relative flex-1 max-w-xs">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Rechercher action, utilisateur, IP..."
                  value={logFilterQuery}
                  onChange={(e) => setLogFilterQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center space-x-1.5">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <select
                  value={logActionFilter}
                  onChange={(e) => setLogActionFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-purple-500 cursor-pointer"
                >
                  <option value="all">Toutes les actions</option>
                  {uniqueActions.map(act => (
                    <option key={act} value={act}>{act}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => exportAuditLogs('csv')}
                className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs flex items-center space-x-1.5 transition-colors shadow-sm"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Exporter CSV</span>
              </button>
              <button
                onClick={() => exportAuditLogs('json')}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs flex items-center space-x-1.5 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Exporter JSON</span>
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Journal d'audit de sécurité immuable ({filteredLogs.length} événements)
              </h3>
              <span className="text-[10px] text-slate-400">Empreintes cryptographiques vérifiées</span>
            </div>

            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                <tr>
                  <th className="p-3 pl-4">Horodatage (UTC)</th>
                  <th className="p-3">Action</th>
                  <th className="p-3">Ressource</th>
                  <th className="p-3">Utilisateur</th>
                  <th className="p-3">IP & Client</th>
                  <th className="p-3">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/40">
                    <td className="p-3 pl-4 text-slate-400">
                      {new Date(log.timestamp).toLocaleString('fr-FR')}
                    </td>
                    <td className="p-3 font-semibold text-purple-300">{log.action}</td>
                    <td className="p-3 text-slate-300 font-sans">{log.resourceName}</td>
                    <td className="p-3 text-slate-400">{log.userEmail}</td>
                    <td className="p-3 text-slate-500">{log.ipAddress}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] ${
                        log.status === 'SUCCESS' 
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
