import React from 'react';
import {
  ShieldCheck,
  Search,
  Server,
  HardDrive,
  ChevronDown,
  LogOut,
  CheckCircle2,
  Users,
  Bell,
  AlertCircle,
} from 'lucide-react';
import { User, Tenant, Plan } from '../types';
import { formatBytes } from '../services/crypto';

interface HeaderProps {
  currentUser: User;
  currentTenant: Tenant;
  userTenants: Tenant[];
  currentPlan: Plan;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onSelectTenant: (tenantId: string) => void;
  onOpenArchitecture: () => void;
  onOpenUpload: () => void;
  onOpenMembers: () => void;
  onOpenNotifications?: () => void;
  unreadNotificationsCount?: number;
  onLogout: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentUser,
  currentTenant,
  userTenants,
  currentPlan,
  searchQuery,
  onSearchChange,
  onSelectTenant,
  onOpenArchitecture,
  onOpenUpload,
  onOpenMembers,
  onOpenNotifications,
  unreadNotificationsCount = 0,
  onLogout,
}) => {
  const [showTenantDropdown, setShowTenantDropdown] = React.useState(false);
  const [showUserDropdown, setShowUserDropdown] = React.useState(false);

  const usedBytes = currentTenant.usedBytes || 0;
  const maxBytes = currentTenant.maxStorageBytes || currentPlan.maxStorageBytes || 1;
  const percentUsed = Math.min(100, Math.round((usedBytes / maxBytes) * 100));

  const initials = currentUser.fullName
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join('') || 'U';

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Left: Brand & Tenant Switcher */}
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-sky-400 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-bold text-xl">
            <ShieldCheck className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                DocuSpace
              </span>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                SaaS B2C
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-none">
              Stockage Chiffré & Multi-Tenant
            </p>
          </div>
        </div>

        {/* Multi-Tenant Selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setShowTenantDropdown(!showTenantDropdown);
              setShowUserDropdown(false);
            }}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 text-xs text-slate-200 transition-colors shadow-sm"
            title="Espace documentaire actif (Isolation PostgreSQL RLS)"
          >
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-medium max-w-[150px] truncate">{currentTenant.name}</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-700 text-slate-300 font-mono">
              {currentTenant.role}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {showTenantDropdown && (
            <div className="absolute left-0 mt-2 w-64 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95 duration-100">
              <div className="px-2 py-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Espaces autorisés</span>
                <span className="text-[10px] text-blue-400">PostgreSQL RLS</span>
              </div>
              <div className="space-y-1 mt-1">
                {userTenants.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => {
                      onSelectTenant(t.id);
                      setShowTenantDropdown(false);
                    }}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs flex items-center justify-between transition-colors ${
                      t.id === currentTenant.id
                        ? 'bg-blue-600/15 text-blue-300 border border-blue-500/30'
                        : 'text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    <div className="truncate pr-2">
                      <div className="font-medium truncate">{t.name}</div>
                      <div className="text-[10px] text-slate-400">
                        {t.role === 'OWNER' ? 'Propriétaire' : t.role} • Forfait {t.planId}
                      </div>
                    </div>
                    {t.id === currentTenant.id && (
                      <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Center: Search Bar */}
      <div className="flex-1 max-w-md mx-8">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Rechercher par nom, type, extension, hash..."
            className="w-full bg-slate-950/60 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/80 focus:ring-1 focus:ring-blue-500/80 transition-all"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Right: Quota indicator, Members, Architecture & User profile */}
      <div className="flex items-center space-x-4">
        <div
          onClick={onOpenUpload}
          className="hidden md:flex items-center space-x-3 px-3 py-1.5 rounded-lg bg-slate-950/60 border border-slate-800 cursor-pointer hover:border-slate-700 transition-colors"
          title={`Stockage consommé : ${formatBytes(usedBytes)} sur ${formatBytes(maxBytes)}`}
        >
          <HardDrive className="w-4 h-4 text-sky-400" />
          <div className="text-right">
            <div className="flex items-center space-x-1.5 text-[11px]">
              <span className="font-semibold text-slate-200">{formatBytes(usedBytes)}</span>
              <span className="text-slate-500">/</span>
              <span className="text-slate-400">{formatBytes(maxBytes)}</span>
            </div>
            <div className="w-24 bg-slate-800 h-1.5 rounded-full overflow-hidden mt-0.5">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  percentUsed > 90 ? 'bg-rose-500' : percentUsed > 70 ? 'bg-amber-400' : 'bg-blue-500'
                }`}
                style={{ width: `${percentUsed}%` }}
              />
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenMembers}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
          title="Gérer les membres et rôles RBAC de cet espace"
        >
          <Users className="w-3.5 h-3.5 text-blue-400" />
          <span className="hidden xl:inline">Membres ({currentTenant.role})</span>
        </button>

        <button
          type="button"
          onClick={onOpenArchitecture}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-indigo-500/10 to-blue-500/10 hover:from-indigo-500/20 hover:to-blue-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-medium transition-all shadow-sm"
          title="Consulter l'architecture Docker, FastAPI, PostgreSQL et Alembic"
        >
          <Server className="w-3.5 h-3.5 text-indigo-400" />
          <span className="hidden sm:inline">Architecture & API</span>
        </button>

        {onOpenNotifications && (
          <button
            type="button"
            onClick={onOpenNotifications}
            className="relative p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
            title="Centre de notifications et alertes"
          >
            <Bell className="w-4 h-4" />
            {unreadNotificationsCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center ring-2 ring-slate-900 shadow-sm">
                {unreadNotificationsCount}
              </span>
            )}
          </button>
        )}

        {/* User profile dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setShowUserDropdown(!showUserDropdown);
              setShowTenantDropdown(false);
            }}
            className="flex items-center space-x-2.5 p-1 pl-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 transition-colors"
          >
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
              {initials}
            </div>
            <div className="text-left hidden sm:block pr-1">
              <div className="text-xs font-medium text-slate-200 leading-tight">
                {currentUser.fullName}
              </div>
              <div className="text-[10px] text-slate-400 leading-tight truncate max-w-[120px]">
                {currentUser.email}
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {showUserDropdown && (
            <div className="absolute right-0 mt-2 w-64 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95 duration-100">
              <div className="p-2 border-b border-slate-800 mb-1">
                <p className="text-xs font-semibold text-white">{currentUser.fullName}</p>
                <p className="text-[11px] text-slate-400 truncate">{currentUser.email}</p>
                <div className="mt-1.5 flex items-center flex-wrap gap-1.5">
                  {currentUser.isVerified ? (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Compte Vérifié
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 inline-flex items-center space-x-1">
                      <AlertCircle className="w-3 h-3" />
                      <span>E-mail non vérifié</span>
                    </span>
                  )}
                  {currentUser.isSuperuser && (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-semibold">
                      Superadmin
                    </span>
                  )}
                </div>
              </div>

              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setShowUserDropdown(false);
                    onLogout();
                  }}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-rose-400 hover:bg-rose-500/10 flex items-center space-x-2 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Se déconnecter</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
