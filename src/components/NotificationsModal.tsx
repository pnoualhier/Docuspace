import React, { useState } from 'react';
import { 
  X, 
  Bell, 
  CheckCheck, 
  ShieldAlert, 
  HardDrive, 
  CreditCard, 
  Share2, 
  AlertTriangle,
  CheckCircle2,
  Trash2,
  ExternalLink
} from 'lucide-react';
import { NotificationItem, NotificationCategory } from '../types';

interface NotificationsModalProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: NotificationItem[];
  onMarkAsRead: (id: string) => void;
  onMarkAllAsRead: () => void;
  onDeleteNotification: (id: string) => void;
  onNavigateAction?: (url: string) => void;
}

export const NotificationsModal: React.FC<NotificationsModalProps> = ({
  isOpen,
  onClose,
  notifications,
  onMarkAsRead,
  onMarkAllAsRead,
  onDeleteNotification,
  onNavigateAction,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  if (!isOpen) return null;

  const unreadCount = notifications.filter(n => !n.isRead).length;

  const filteredNotifications = notifications.filter(n => {
    if (selectedCategory === 'all') return true;
    return n.category === selectedCategory;
  });

  const getCategoryIcon = (category: NotificationCategory, level: string) => {
    switch (category) {
      case 'SECURITY':
        return <ShieldAlert className="w-4 h-4 text-purple-400" />;
      case 'STORAGE':
        return level === 'CRITICAL' 
          ? <AlertTriangle className="w-4 h-4 text-rose-400" />
          : <HardDrive className="w-4 h-4 text-amber-400" />;
      case 'BILLING':
        return <CreditCard className="w-4 h-4 text-emerald-400" />;
      case 'SHARING':
        return <Share2 className="w-4 h-4 text-blue-400" />;
      default:
        return <Bell className="w-4 h-4 text-slate-400" />;
    }
  };

  const getCategoryBadge = (category: NotificationCategory) => {
    switch (category) {
      case 'SECURITY':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/20">Sécurité</span>;
      case 'STORAGE':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">Stockage</span>;
      case 'BILLING':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">Facturation</span>;
      case 'SHARING':
        return <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-blue-500/10 text-blue-300 border border-blue-500/20">Partage</span>;
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl flex flex-col max-h-[85vh] shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 relative">
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-blue-500 ring-2 ring-slate-900" />
              )}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white">Centre de Notifications</h3>
                {unreadCount > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-blue-600 text-white text-[10px] font-bold">
                    {unreadCount} non lue{unreadCount > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400">
                Alertes de quotas, sécurité, facturation Stripe et partages.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {unreadCount > 0 && (
              <button
                onClick={onMarkAllAsRead}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center space-x-1 transition-colors"
                title="Tout marquer comme lu"
              >
                <CheckCheck className="w-3.5 h-3.5 text-blue-400" />
                <span>Tout lire</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="px-5 py-2.5 border-b border-slate-800/80 bg-slate-950/40 flex items-center space-x-1.5 overflow-x-auto text-xs">
          {[
            { id: 'all', label: 'Toutes' },
            { id: 'STORAGE', label: 'Stockage & Quotas' },
            { id: 'SECURITY', label: 'Sécurité' },
            { id: 'BILLING', label: 'Facturation' },
            { id: 'SHARING', label: 'Partages' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setSelectedCategory(tab.id)}
              className={`px-3 py-1 rounded-lg transition-colors shrink-0 text-xs font-medium ${
                selectedCategory === tab.id
                  ? 'bg-blue-600 text-white font-semibold'
                  : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Notifications List */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {filteredNotifications.length > 0 ? (
            filteredNotifications.map((n) => (
              <div
                key={n.id}
                onClick={() => !n.isRead && onMarkAsRead(n.id)}
                className={`p-4 rounded-xl border transition-all flex items-start justify-between gap-3 cursor-pointer ${
                  !n.isRead
                    ? 'bg-slate-900 border-blue-500/40 shadow-sm'
                    : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-300'
                }`}
              >
                <div className="flex items-start space-x-3.5 flex-1">
                  <div className="p-2 rounded-xl bg-slate-950 border border-slate-800 mt-0.5 shrink-0">
                    {getCategoryIcon(n.category, n.level)}
                  </div>
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center space-x-2 flex-wrap gap-1">
                      <span className="text-xs font-bold text-white">{n.title}</span>
                      {getCategoryBadge(n.category)}
                      {!n.isRead && (
                        <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" title="Non lu" />
                      )}
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">{n.message}</p>
                    <div className="flex items-center space-x-3 text-[10px] text-slate-500 pt-1">
                      <span>{new Date(n.createdAt).toLocaleString('fr-FR')}</span>
                      {n.actionUrl && onNavigateAction && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onNavigateAction(n.actionUrl!);
                            onClose();
                          }}
                          className="text-blue-400 hover:text-blue-300 font-semibold flex items-center space-x-0.5"
                        >
                          <span>Accéder</span>
                          <ExternalLink className="w-2.5 h-2.5 ml-0.5" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                  {!n.isRead && (
                    <button
                      onClick={() => onMarkAsRead(n.id)}
                      className="p-1 rounded text-slate-400 hover:text-blue-400 hover:bg-slate-800"
                      title="Marquer comme lu"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => onDeleteNotification(n.id)}
                    className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800"
                    title="Supprimer cette alerte"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="py-12 text-center border-2 border-dashed border-slate-800 rounded-xl space-y-2">
              <Bell className="w-8 h-8 text-slate-600 mx-auto" />
              <div className="text-xs font-semibold text-slate-300">Aucune notification</div>
              <p className="text-[11px] text-slate-500">
                Vous êtes à jour. Les alertes de sécurité et de quotas apparaîtront ici.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs text-slate-400">
          <span className="text-[11px]">
            Notifications temps réel & alertes e-mail configurables (Debian SMTP)
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
