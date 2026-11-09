import React, { useState } from 'react';
import { 
  X, 
  Users, 
  UserPlus, 
  ShieldCheck, 
  Shield, 
  Trash2, 
  Check, 
  ChevronDown, 
  Info 
} from 'lucide-react';
import { Tenant, UserRole, User } from '../types';

interface MemberItem {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  joinedAt: string;
}

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
  const [members, setMembers] = useState<MemberItem[]>([
    {
      id: 'mem-1',
      email: 'alice.dupont@example.com',
      fullName: 'Alice Dupont',
      role: 'OWNER',
      joinedAt: '15 janv. 2026'
    },
    {
      id: 'mem-2',
      email: 'charlie.collegue@example.com',
      fullName: 'Charlie Comptable',
      role: 'VIEWER',
      joinedAt: '02 févr. 2026'
    }
  ]);

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('VIEWER');
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const isOwner = currentTenant.role === 'OWNER' || currentUser.isSuperuser;

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    const newMem: MemberItem = {
      id: `mem-${Date.now()}`,
      email: inviteEmail.trim(),
      fullName: inviteEmail.split('@')[0],
      role: inviteRole,
      joinedAt: "À l'instant"
    };

    setMembers([...members, newMem]);
    setInviteEmail('');
    setSuccessMsg(`Invitation envoyée à ${inviteEmail} avec le rôle ${inviteRole}.`);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleRoleChange = (memberId: string, newRole: UserRole) => {
    setMembers(members.map(m => m.id === memberId ? { ...m, role: newRole } : m));
  };

  const handleRemoveMember = (memberId: string) => {
    setMembers(members.filter(m => m.id !== memberId));
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
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
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
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Invite Form (only if OWNER or Superuser) */}
        {isOwner ? (
          <form onSubmit={handleInvite} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Inviter un nouveau membre dans cet espace
            </span>
            <div className="flex gap-2">
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="collaborateur@exemple.fr"
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
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs flex items-center space-x-1.5 transition-colors shadow-sm"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Inviter</span>
              </button>
            </div>
            {successMsg && (
              <p className="text-[11px] text-emerald-400 font-medium">{successMsg}</p>
            )}
          </form>
        ) : (
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 flex items-center space-x-2">
            <Info className="w-4 h-4 text-blue-400 shrink-0" />
            <span>Vous consultez cet espace avec le rôle {currentTenant.role}. Seul le propriétaire peut inviter de nouveaux membres.</span>
          </div>
        )}

        {/* Members List */}
        <div className="space-y-3">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
            Membres actifs ({members.length})
          </span>

          <div className="space-y-2 max-h-64 overflow-y-auto">
            {members.map((mem) => {
              const isMemOwner = mem.role === 'OWNER';
              return (
                <div
                  key={mem.id}
                  className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between"
                >
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center text-xs font-bold text-white">
                      {mem.fullName[0].toUpperCase()}
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-slate-200 flex items-center space-x-2">
                        <span>{mem.fullName}</span>
                        {mem.email === currentUser.email && (
                          <span className="text-[10px] text-blue-400">(vous)</span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {mem.email} • Rejoint {mem.joinedAt}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {/* Role badge or selector */}
                    {isOwner && !isMemOwner ? (
                      <select
                        value={mem.role}
                        onChange={(e) => handleRoleChange(mem.id, e.target.value as UserRole)}
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
                        onClick={() => handleRemoveMember(mem.id)}
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
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-slate-800">
          <button
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
