import React, { useState } from 'react';
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
  FileText 
} from 'lucide-react';
import { User, Tenant, AuditLogItem } from '../types';
import { formatBytes } from '../services/crypto';

interface AdminConsoleProps {
  tenants: Tenant[];
  users: User[];
  auditLogs: AuditLogItem[];
}

export const AdminConsole: React.FC<AdminConsoleProps> = ({
  tenants,
  users,
  auditLogs,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'services' | 'logs'>('overview');

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
            Vue globale
          </button>
          <button
            onClick={() => setActiveTab('services')}
            className={`px-3 py-1.5 rounded-lg transition-colors ${
              activeTab === 'services' ? 'bg-purple-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            État des services (6/6)
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
          <span className="text-[10px] text-emerald-400">100% RLS actif</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Utilisateurs inscrits</span>
          <div className="text-2xl font-bold text-white">{users.length}</div>
          <span className="text-[10px] text-blue-400">Argon2id haché</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Volume MinIO stocké</span>
          <div className="text-2xl font-bold text-white font-mono">{formatBytes(totalUsedStorage)}</div>
          <span className="text-[10px] text-purple-400">Stockage réparti</span>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <span className="text-[11px] text-slate-400 font-medium">Santé Globale Docker</span>
          <div className="text-2xl font-bold text-emerald-400">Optimal</div>
          <span className="text-[10px] text-slate-400">Zéro alerte de sécurité</span>
        </div>
      </div>

      {/* Tab 1: Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Espaces Documentaires (Multi-Tenants)
              </h3>
              <span className="text-[10px] text-slate-400">PostgreSQL RLS activé</span>
            </div>

            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                <tr>
                  <th className="p-3 pl-4">Nom de l'espace</th>
                  <th className="p-3">Identifiant Tenant (UUID)</th>
                  <th className="p-3">Forfait</th>
                  <th className="p-3">Stockage consommé</th>
                  <th className="p-3">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {tenants.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/40">
                    <td className="p-3 pl-4 font-semibold text-slate-200">{t.name}</td>
                    <td className="p-3 font-mono text-[11px] text-slate-400">{t.id}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        {t.planId}
                      </span>
                    </td>
                    <td className="p-3 font-mono text-slate-300">{formatBytes(t.usedBytes)}</td>
                    <td className="p-3">
                      <span className="inline-flex items-center space-x-1 text-emerald-400 text-[11px]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Actif</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Docker Services */}
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

      {/* Tab 3: Audit Logs */}
      {activeTab === 'logs' && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Journal d'audit de sécurité immuable
            </h3>
            <span className="text-[10px] text-slate-400">Zéro mot de passe en clair consigné</span>
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
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-800/40">
                  <td className="p-3 pl-4 text-slate-400">
                    {new Date(log.timestamp).toLocaleString('fr-FR')}
                  </td>
                  <td className="p-3 font-semibold text-purple-300">{log.action}</td>
                  <td className="p-3 text-slate-300 font-sans">{log.resourceName}</td>
                  <td className="p-3 text-slate-400">{log.userEmail}</td>
                  <td className="p-3 text-slate-500">{log.ipAddress}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {log.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
