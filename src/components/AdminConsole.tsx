import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  ShieldAlert,
  Server,
  HardDrive,
  CheckCircle2,
  AlertCircle,
  Activity,
  Database,
  ShieldCheck,
  Download,
  Search,
  Filter,
  UserCheck,
  UserX,
  RefreshCw,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { User, Tenant, AuditLogItem, PlanType } from '../types';
import { formatBytes } from '../services/crypto';
import { apiClient, ApiAdminStats, ApiError } from '../services/api';

interface HealthProbeState {
  status: string;
  database: string;
  redis?: string;
  storage: string;
  antivirus: string;
}

interface AdminConsoleProps {
  onWorkspaceRefresh?: () => Promise<void> | void;
}

export const AdminConsole: React.FC<AdminConsoleProps> = ({ onWorkspaceRefresh }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'services' | 'logs'>('overview');
  const [stats, setStats] = useState<ApiAdminStats | null>(null);
  const [health, setHealth] = useState<HealthProbeState | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [logFilterQuery, setLogFilterQuery] = useState('');
  const [logActionFilter, setLogActionFilter] = useState('all');

  const loadAdminData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [healthRes, statsRes, usersRes, tenantsRes, logsRes] = await Promise.all([
        apiClient.health.check(),
        apiClient.admin.stats(),
        apiClient.admin.users({ limit: 100 }),
        apiClient.admin.tenants({ limit: 100 }),
        apiClient.admin.auditLogs({ limit: 100 }),
      ]);

      setHealth({
        status: healthRes.status,
        database: healthRes.database,
        redis: healthRes.redis,
        storage: healthRes.storage,
        antivirus: healthRes.antivirus,
      });
      setStats(statsRes);

      setUsers(
        usersRes.users.map((u) => ({
          id: u.id,
          email: u.email,
          fullName: u.full_name,
          isActive: u.is_active,
          isVerified: u.is_verified,
          isSuperuser: u.is_superuser,
          createdAt: u.created_at,
        }))
      );

      setTenants(
        tenantsRes.tenants.map((t) => ({
          id: t.id,
          name: t.name,
          ownerId: t.owner_id,
          planId: (t.plan_id as PlanType) || 'FREE',
          role: 'OWNER',
          isActive: t.is_active,
          createdAt: t.created_at || '',
          usedBytes: t.used_bytes,
          reservedBytes: t.reserved_bytes,
          documentCount: t.document_count,
          maxStorageBytes: t.max_storage_bytes,
          subscriptionStatus: t.subscription_status as Tenant['subscriptionStatus'],
          isRestrictedReadOnly: t.restricted_read_only,
        }))
      );

      setAuditLogs(
        logsRes.logs.map((l) => ({
          id: l.id,
          tenantId: l.tenant_id,
          userId: l.user_id,
          userEmail: l.user_email,
          action: l.action,
          resourceType: l.resource_type,
          resourceId: l.resource_id,
          resourceName:
            typeof l.details?.resource_name === 'string'
              ? l.details.resource_name
              : l.resource_id || l.resource_type,
          details: l.details,
          ipAddress: l.ip_address,
          userAgent: l.user_agent ?? null,
          timestamp: l.timestamp || '',
          status:
            typeof l.details?.status === 'string'
              ? (l.details.status as AuditLogItem['status'])
              : undefined,
        }))
      );
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError
          ? err.detail
          : "Impossible de récupérer les données d'administration depuis l'API."
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAdminData();
  }, [loadAdminData]);

  const handleUpdateUserStatus = async (userId: string, isActive: boolean) => {
    setIsMutating(true);
    setErrorMsg(null);
    try {
      await apiClient.admin.updateUserStatus(userId, isActive);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, isActive } : u)));
      await loadAdminData();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Impossible de modifier le statut utilisateur.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  const handleUpdateTenantPlan = async (tenantId: string, planId: PlanType) => {
    setIsMutating(true);
    setErrorMsg(null);
    try {
      await apiClient.admin.overrideTenantPlan(tenantId, planId);
      await loadAdminData();
      if (onWorkspaceRefresh) {
        await onWorkspaceRefresh();
      }
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Impossible de modifier le forfait du tenant.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  const serviceProbes = useMemo(() => {
    const formatStatus = (val?: string) => {
      if (!val) return { label: 'Inconnu', healthy: false };
      const ok = val === 'healthy' || val === 'ok' || val === 'test_mode';
      return { label: val, healthy: ok };
    };
    return [
      {
        name: 'PostgreSQL (RLS)',
        probe: formatStatus(health?.database),
        desc: 'Sonde SQL SELECT 1 & politiques Row-Level Security',
        icon: Database,
      },
      {
        name: 'Stockage Objet MinIO S3',
        probe: formatStatus(health?.storage),
        desc: 'Vérification connectivité bucket S3',
        icon: HardDrive,
      },
      {
        name: 'ClamAV Daemon',
        probe: formatStatus(health?.antivirus),
        desc: 'Sonde TCP zPING / PONG (Fail-Closed)',
        icon: ShieldCheck,
      },
      {
        name: 'Redis',
        probe: formatStatus(health?.redis),
        desc: 'Sonde PING / limitation de débit distribuée',
        icon: Activity,
      },
    ];
  }, [health]);

  const filteredLogs = useMemo(() => {
    return auditLogs.filter((log) => {
      if (logActionFilter !== 'all' && log.action !== logActionFilter) return false;
      if (logFilterQuery.trim()) {
        const q = logFilterQuery.toLowerCase();
        const matches =
          log.action.toLowerCase().includes(q) ||
          log.userEmail.toLowerCase().includes(q) ||
          (log.resourceName || '').toLowerCase().includes(q) ||
          (log.ipAddress || '').toLowerCase().includes(q);
        if (!matches) return false;
      }
      return true;
    });
  }, [auditLogs, logFilterQuery, logActionFilter]);

  const uniqueActions = useMemo(() => {
    return Array.from(new Set(auditLogs.map((l) => l.action)));
  }, [auditLogs]);

  const exportAuditLogs = async (format: 'csv' | 'json') => {
    setErrorMsg(null);
    try {
      if (format === 'csv') {
        const blob = await apiClient.admin.exportAuditLogsCsv();
        const url = URL.createObjectURL(blob);
        const link = window.document.createElement('a');
        link.href = url;
        link.download = `docuspace_audit_logs_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        const jsonStr = JSON.stringify(filteredLogs, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = window.document.createElement('a');
        link.href = url;
        link.download = `docuspace_audit_logs_${new Date().toISOString().slice(0, 10)}.json`;
        link.click();
        URL.revokeObjectURL(url);
      }
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : "Erreur lors de l'export des journaux d'audit."
      );
    }
  };

  const totalUsedStorage = stats?.total_storage_bytes ?? tenants.reduce((acc, t) => acc + (t.usedBytes || 0), 0);
  const tenantsCount = stats?.tenants_count ?? tenants.length;
  const usersCount = stats?.users_count ?? users.length;
  const documentsCount = stats?.documents_count ?? 0;

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
            État réel des sondes `/api/v1/health`, espaces multi-tenants PostgreSQL et journalisation d'audit.
          </p>
        </div>

        <div className="flex items-center space-x-3 flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void loadAdminData()}
            disabled={isLoading}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs font-medium flex items-center space-x-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Actualiser</span>
          </button>

          <div className="flex p-1 bg-slate-900 border border-slate-800 rounded-xl text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab('overview')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'overview' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Espaces ({tenants.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('users')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'users' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Utilisateurs ({users.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('services')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'services' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Services ({serviceProbes.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('logs')}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === 'logs' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Journal d'Audit ({auditLogs.length})
            </button>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div role="alert" className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Espaces Isolés (Tenants)</span>
          <div className="text-2xl font-bold text-white">{tenantsCount}</div>
          <span className="text-[10px] text-slate-400 font-medium">{documentsCount} document(s) en base</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Utilisateurs inscrits</span>
          <div className="text-2xl font-bold text-white">{usersCount}</div>
          <span className="text-[10px] text-blue-400 font-medium">Source PostgreSQL</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Volume MinIO stocké</span>
          <div className="text-2xl font-bold text-white font-mono">{formatBytes(totalUsedStorage)}</div>
          <span className="text-[10px] text-purple-400 font-medium">
            Capacité allouée : {formatBytes(stats?.storage_capacity_bytes || 0)}
          </span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Santé Globale API</span>
          <div
            className={`text-2xl font-bold ${
              !health
                ? 'text-slate-400'
                : health.status === 'healthy'
                  ? 'text-emerald-400'
                  : 'text-amber-400'
            }`}
          >
            {isLoading ? '...' : health ? health.status.toUpperCase() : 'INDISPONIBLE'}
          </div>
          <span className="text-[10px] text-slate-400 font-medium">
            Antivirus : {stats?.antivirus_status || health?.antivirus || 'inconnu'}
          </span>
        </div>
      </div>

      {isLoading && tenants.length === 0 ? (
        <div className="py-12 text-center text-xs text-slate-400 flex items-center justify-center space-x-2">
          <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
          <span>Chargement des données d'administration...</span>
        </div>
      ) : (
        <>
          {/* Tab 1: Overview Tenants */}
          {activeTab === 'overview' && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  Espaces Documentaires Multi-Tenants
                </h3>
                <span className="text-[10px] text-slate-400">PostgreSQL RLS</span>
              </div>

              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                  <tr>
                    <th className="p-3 pl-4">Nom de l'espace</th>
                    <th className="p-3">Identifiant Tenant</th>
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
                            <span>{t.subscriptionStatus || 'ACTIVE'}</span>
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-right pr-4">
                        <select
                          aria-label={`Forfait de ${t.name}`}
                          value={t.planId}
                          disabled={isMutating}
                          onChange={(e) => handleUpdateTenantPlan(t.id, e.target.value as PlanType)}
                          className="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-purple-500 cursor-pointer"
                        >
                          <option value="FREE">Forfait FREE</option>
                          <option value="PERSONAL">Forfait PERSONAL</option>
                          <option value="PREMIUM">Forfait PREMIUM</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                  {tenants.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-slate-500">
                        Aucun espace documentaire enregistré.
                      </td>
                    </tr>
                  )}
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
                <span className="text-[10px] text-slate-400">PostgreSQL Users</span>
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
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                            u.isSuperuser
                              ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                              : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                          }`}
                        >
                          {u.isSuperuser ? 'Superadmin' : 'Utilisateur'}
                        </span>
                      </td>
                      <td className="p-3">
                        <span
                          className={`inline-flex items-center space-x-1 text-[11px] font-medium ${
                            u.isActive ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {u.isActive ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                          <span>{u.isActive ? 'Actif' : 'Suspendu'}</span>
                        </span>
                      </td>
                      <td className="p-3 text-slate-500 text-[11px]">
                        {u.createdAt ? new Date(u.createdAt).toLocaleDateString('fr-FR') : '—'}
                      </td>
                      <td className="p-3 text-right pr-4">
                        {!u.isSuperuser && (
                          <button
                            type="button"
                            disabled={isMutating}
                            onClick={() => handleUpdateUserStatus(u.id, !u.isActive)}
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

          {/* Tab 3: Live Health Probes */}
          {activeTab === 'services' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {serviceProbes.map((svc) => {
                const Icon = svc.icon;
                return (
                  <div
                    key={svc.name}
                    className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 flex items-start space-x-4"
                  >
                    <div
                      className={`p-3 rounded-xl bg-slate-950 border border-slate-800 ${
                        svc.probe.healthy ? 'text-emerald-400' : 'text-amber-400'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between gap-2">
                        <h4 className="text-xs font-bold text-white">{svc.name}</h4>
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border font-mono ${
                            svc.probe.healthy
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                          }`}
                        >
                          {svc.probe.label}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">{svc.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Tab 4: Audit Logs */}
          {activeTab === 'logs' && (
            <div className="space-y-4">
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
                      {uniqueActions.map((act) => (
                        <option key={act} value={act}>
                          {act}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => void exportAuditLogs('csv')}
                    className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs flex items-center space-x-1.5 transition-colors shadow-sm"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Exporter CSV</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => void exportAuditLogs('json')}
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
                    Journal d'audit PostgreSQL ({filteredLogs.length} événements)
                  </h3>
                  <span className="text-[10px] text-slate-400">Source : /api/v1/admin/audit-logs</span>
                </div>

                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                    <tr>
                      <th className="p-3 pl-4">Horodatage</th>
                      <th className="p-3">Action</th>
                      <th className="p-3">Ressource</th>
                      <th className="p-3">Utilisateur</th>
                      <th className="p-3">IP & Client</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                    {filteredLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-800/40">
                        <td className="p-3 pl-4 text-slate-400">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString('fr-FR') : '—'}
                        </td>
                        <td className="p-3 font-semibold text-purple-300">{log.action}</td>
                        <td className="p-3 text-slate-300 font-sans">
                          {log.resourceName || log.resourceType}
                        </td>
                        <td className="p-3 text-slate-400">{log.userEmail}</td>
                        <td className="p-3 text-slate-500">
                          {log.ipAddress || '—'}
                          {log.userAgent ? ` (${log.userAgent.slice(0, 32)})` : ''}
                        </td>
                      </tr>
                    ))}
                    {filteredLogs.length === 0 && (
                      <tr>
                        <td colSpan={5} className="p-6 text-center text-slate-500 font-sans">
                          Aucun événement d'audit correspondant.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
