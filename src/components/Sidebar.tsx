import React from 'react';
import { 
  LayoutDashboard, 
  FileText, 
  FolderTree, 
  Share2, 
  Users, 
  Star, 
  Clock, 
  Trash2, 
  Search, 
  HardDrive, 
  CreditCard, 
  Settings, 
  ShieldAlert, 
  Plus, 
  UploadCloud,
  FolderPlus
} from 'lucide-react';
import { User, Tenant, Plan } from '../types';
import { formatBytes } from '../services/crypto';

export type NavTab = 
  | 'dashboard' 
  | 'documents' 
  | 'folders' 
  | 'shared-with-me' 
  | 'shared-by-me' 
  | 'favorites' 
  | 'recents' 
  | 'trash' 
  | 'search' 
  | 'storage' 
  | 'billing' 
  | 'settings' 
  | 'admin';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  currentUser: User;
  currentTenant: Tenant;
  currentPlan: Plan;
  onOpenUpload: () => void;
  onOpenNewFolder: () => void;
  trashedCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  currentUser,
  currentTenant,
  currentPlan,
  onOpenUpload,
  onOpenNewFolder,
  trashedCount,
}) => {
  const mainNav = [
    { id: 'dashboard' as NavTab, label: 'Tableau de bord', icon: LayoutDashboard },
    { id: 'documents' as NavTab, label: 'Mes documents', icon: FileText },
    { id: 'folders' as NavTab, label: 'Mes dossiers', icon: FolderTree },
    { id: 'shared-with-me' as NavTab, label: 'Partagés avec moi', icon: Users },
    { id: 'shared-by-me' as NavTab, label: 'Partagés par moi', icon: Share2 },
    { id: 'favorites' as NavTab, label: 'Favoris', icon: Star },
    { id: 'recents' as NavTab, label: 'Récents', icon: Clock },
    { id: 'trash' as NavTab, label: 'Corbeille', icon: Trash2, badge: trashedCount > 0 ? trashedCount : null },
  ];

  const secondaryNav = [
    { id: 'search' as NavTab, label: 'Recherche avancée', icon: Search },
    { id: 'storage' as NavTab, label: 'Stockage & Quotas', icon: HardDrive },
    { id: 'billing' as NavTab, label: 'Abonnement', icon: CreditCard },
    { id: 'settings' as NavTab, label: 'Paramètres & RGPD', icon: Settings },
  ];

  const usedBytes = currentTenant.usedBytes || 0;
  const maxBytes = currentPlan.maxStorageBytes;
  const percentUsed = Math.min(100, Math.round((usedBytes / maxBytes) * 100));

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/60 flex flex-col justify-between shrink-0 select-none">
      <div className="p-4 space-y-6">
        {/* Quick Action Buttons: Upload & New Folder */}
        <div className="space-y-2">
          <button
            onClick={onOpenUpload}
            className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-all shadow-md shadow-blue-600/20 active:scale-[0.98]"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Importer un fichier</span>
          </button>
          <button
            onClick={onOpenNewFolder}
            className="w-full flex items-center justify-center space-x-2 py-2 px-4 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 text-slate-300 font-medium text-xs transition-colors"
          >
            <FolderPlus className="w-4 h-4 text-slate-400" />
            <span>Nouveau dossier</span>
          </button>
        </div>

        {/* Main Navigation */}
        <div className="space-y-1">
          <div className="px-3 py-1 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
            Navigation Principale
          </div>
          {mainNav.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20 font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-blue-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge !== null && (
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-400 font-mono">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* System & Account */}
        <div className="space-y-1">
          <div className="px-3 py-1 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
            Compte & Système
          </div>
          {secondaryNav.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20 font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}

          {/* Superadmin specific tab */}
          {currentUser.isSuperuser && (
            <button
              onClick={() => onTabChange('admin')}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-xs font-medium transition-all mt-2 ${
                currentTab === 'admin'
                  ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30 font-semibold'
                  : 'text-purple-400/80 hover:text-purple-300 hover:bg-purple-950/30'
              }`}
            >
              <ShieldAlert className="w-4 h-4 text-purple-400" />
              <span>Espace Administration</span>
            </button>
          )}
        </div>
      </div>

      {/* Bottom: Storage summary & active plan card */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40">
        <div className="rounded-xl p-3 bg-slate-900 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-300">
              Forfait {currentPlan.name}
            </span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-400 font-mono">
              {percentUsed}%
            </span>
          </div>

          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                percentUsed > 90 ? 'bg-rose-500' : percentUsed > 70 ? 'bg-amber-400' : 'bg-blue-500'
              }`}
              style={{ width: `${percentUsed}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[10px] text-slate-400">
            <span>{formatBytes(usedBytes)} utilisés</span>
            <span>{formatBytes(maxBytes)} max</span>
          </div>

          <button
            onClick={() => onTabChange('billing')}
            className="w-full mt-1 text-center text-[10px] text-blue-400 hover:text-blue-300 font-medium transition-colors"
          >
            Changer de forfait →
          </button>
        </div>
      </div>
    </aside>
  );
};
