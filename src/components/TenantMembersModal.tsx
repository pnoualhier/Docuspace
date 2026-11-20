import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Users,
  UserPlus,
  Trash2,
  Info,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { Tenant, TenantMemberItem, UserRole, User } from '../types';
import { apiClient, ApiError } from '../services/api';

interface TenantMembersModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTenant: Tenant;
  currentUser: User;
}

export const TenantMembersModal: React.FC<TenantMembersModalProps> = ({
  isOpen,
  onClose,
  currentTenant,
  currentUser,
}) => {
  const [members, setMembers] = useState<TenantMemberItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('VIEWER');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadMembers = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const apiMembers = await apiClient.tenants.members(currentTenant.id);
      setMembers(
        apiMembers.map((m) => ({
          id: m.id,
          userId: m.user_id,
          email: m.email,
          fullName: m.full_name,
          role: (m.role as UserRole) || 'VIEWER',
          joinedAt: m.joined_at,
        }))
      );
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Impossible de charger la liste des membres.'
      );
    } finally {
      setIsLoading(false);
    }
  }, [currentTenant.id]);

  useEffect(() => {
    if (isOpen) {
      void loadMembers();
    }
  }, [isOpen, loadMembers]);

  if (!isOpen) return null;

  const isOwner = currentTenant.role === 'OWNER' || currentUser.isSuperuser;

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setIsMutating(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await apiClient.tenants.inviteMember(
        currentTenant.id,
        inviteEmail.trim(),
        inviteRole
      );
      setInviteEmail('');
      setSuccessMsg(res.message);
      await loadMembers();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : "Erreur lors de l'invitation du membre."
      );
    } finally {
      setIsMutating(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: UserRole) => {
    setIsMutating(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await apiClient.tenants.updateMemberRole(currentTenant.id, userId, newRole);
      setSuccessMsg(res.message);
      await loadMembers();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Erreur lors de la mise à jour du rôle.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    setIsMutating(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await apiClient.tenants.removeMember(currentTenant.id, userId);
      setMembers((prev) => prev.filter((m) => m.userId !== userId));
      setSuccessMsg('Membre retiré de l’espace documentaire.');
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof ApiError ? err.detail : 'Impossible de retirer ce membre.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  const getRoleBadge = (role: UserRole) => {
    switch (role) {
      case 'OWNER':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      case 'EDITOR':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'VIEWER':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'GUEST':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      default:
        return 'bg-slate-800 text-slate-400';
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Membres & Contrôle d'Accès (RBAC)</h3>
              <p className="text-[11px] text-slate-400">
                Espace : <span className="text-blue-400 font-semibold">{currentTenant.name}</span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer la gestion des membres"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Invite Form */}
        {isOwner ? (
          <form onSubmit={handleInvite} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Inviter un utilisateur inscrit dans cet espace
            </span>
            <div className="flex gap-2">
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="collaborateur@domaine.fr"
                className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as UserRole)}
                className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="VIEWER">Lecteur (Lecture seule)</option>
                <option value="EDITOR">Éditeur (Lecture & Import)</option>
                <option value="GUEST">Invité (Accès restreint)</option>
              </select>
              <button
                type="submit"
                disabled={isMutating}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-semibold text-xs flex items-center space-x-1.5 transition-colors shadow-sm"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Inviter</span>
              </button>
            </div>
          </form>
        ) : (
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 flex items-center space-x-2">
            <Info className="w-4 h-4 text-blue-400 shrink-0" />
            <span>
              Vous consultez cet espace avec le rôle {currentTenant.role}. Seul le propriétaire peut gérer les membres.
            </span>
          </div>
        )}

        {errorMsg && (
          <div role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div role="status" className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
            {successMsg}
          </div>
        )}

        {/* Members List */}
        <div className="space-y-3">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
            Membres actifs ({members.length})
          </span>

          {isLoading ? (
            <div className="py-8 text-center text-xs text-slate-400 flex items-center justify-center space-x-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              <span>Chargement des membres...</span>
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {members.map((mem) => {
                const isMemOwner = mem.role === 'OWNER';
                const initial = (mem.fullName || mem.email || 'U').trim()[0].toUpperCase();
                return (
                  <div
                    key={mem.id}
                    className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center text-xs font-bold text-white">
                        {initial}
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-slate-200 flex items-center space-x-2">
                          <span>{mem.fullName}</span>
                          {mem.email === currentUser.email && (
                            <span className="text-[10px] text-blue-400">(vous)</span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {mem.email} • Rejoint le {new Date(mem.joinedAt).toLocaleDateString('fr-FR')}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      {isOwner && !isMemOwner ? (
                        <select
                          value={mem.role}
                          disabled={isMutating}
                          onChange={(e) => handleRoleChange(mem.userId, e.target.value as UserRole)}
                          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200 focus:outline-none"
                        >
                          <option value="VIEWER">Lecteur</option>
                          <option value="EDITOR">Éditeur</option>
                          <option value="GUEST">Invité</option>
                        </select>
                      ) : (
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold border ${getRoleBadge(mem.role)}`}>
                          {mem.role === 'OWNER' ? 'Propriétaire' : mem.role}
                        </span>
                      )}

                      {isOwner && !isMemOwner && (
                        <button
                          type="button"
                          disabled={isMutating}
                          onClick={() => handleRemoveMember(mem.userId)}
                          className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                          title="Retirer le membre"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

              {members.length === 0 && (
                <div className="py-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                  Aucun membre trouvé pour cet espace.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs transition-colors"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
};
