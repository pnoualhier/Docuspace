import React, { useState } from 'react';
import { 
  X, 
  Share2, 
  Link as LinkIcon, 
  Users, 
  Lock, 
  Calendar, 
  DownloadCloud, 
  Copy, 
  Check, 
  ShieldCheck, 
  AlertCircle 
} from 'lucide-react';
import { DocumentItem, UserRole } from '../types';

interface ShareModalProps {
  document: DocumentItem | null;
  onClose: () => void;
}

export const ShareModal: React.FC<ShareModalProps> = ({
  document,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'link' | 'user'>('link');
  const [copiedLink, setCopiedLink] = useState(false);
  const [requirePassword, setRequirePassword] = useState(false);
  const [password, setPassword] = useState('');
  const [hasExpiry, setHasExpiry] = useState(true);
  const [expiryDays, setExpiryDays] = useState('7');
  const [maxDownloads, setMaxDownloads] = useState('');
  const [invitedEmail, setInvitedEmail] = useState('');
  const [invitedRole, setInvitedRole] = useState<UserRole>('VIEWER');
  const [invitedList, setInvitedList] = useState<Array<{ email: string; role: UserRole }>>([
    { email: 'famille@dupont.fr', role: 'VIEWER' }
  ]);

  if (!document) return null;

  const secureToken = 'share_' + document.id.substring(4, 16) + '_' + Math.random().toString(36).substring(2, 8);
  const publicUrl = `https://docuspace.io/s/${secureToken}`;

  const handleCopyLink = () => {
    navigator.clipboard.writeText(publicUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleAddUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (!invitedEmail) return;
    setInvitedList([...invitedList, { email: invitedEmail, role: invitedRole }]);
    setInvitedEmail('');
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Share2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Partage sécurisé</h3>
              <p className="text-[11px] text-slate-400 truncate max-w-[280px]">
                {document.originalName}
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

        {/* Tab Selector: Lien Public vs Utilisateur Identifié */}
        <div className="flex border-b border-slate-800">
          <button
            onClick={() => setActiveTab('link')}
            className={`pb-2.5 px-4 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
              activeTab === 'link'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <LinkIcon className="w-3.5 h-3.5" />
            <span>Lien sécurisé chiffré</span>
          </button>
          <button
            onClick={() => setActiveTab('user')}
            className={`pb-2.5 px-4 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
              activeTab === 'user'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Utilisateurs identifiés</span>
          </button>
        </div>

        {/* Tab 1: Secure Link */}
        {activeTab === 'link' && (
          <div className="space-y-4">
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-2">
              <div className="truncate font-mono text-xs text-slate-300">
                {publicUrl}
              </div>
              <button
                onClick={handleCopyLink}
                className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center space-x-1.5 shrink-0 transition-colors"
              >
                {copiedLink ? <Check className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedLink ? 'Copié !' : 'Copier'}</span>
              </button>
            </div>

            {/* Options: Password, Expiry, Max downloads */}
            <div className="space-y-3 pt-2 text-xs">
              {/* Password */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={requirePassword}
                    onChange={(e) => setRequirePassword(e.target.checked)}
                    className="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0"
                  />
                  <span className="font-medium text-slate-200">Protéger par mot de passe</span>
                </label>
                {requirePassword && (
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Définir un mot de passe d'accès"
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                )}
              </div>

              {/* Expiry & Download Limit */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                  <span className="text-[10px] text-slate-400 font-semibold uppercase">Expiration</span>
                  <select
                    value={expiryDays}
                    onChange={(e) => setExpiryDays(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200 focus:outline-none"
                  >
                    <option value="1">1 jour</option>
                    <option value="7">7 jours</option>
                    <option value="30">30 jours</option>
                    <option value="never">Sans expiration</option>
                  </select>
                </div>

                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                  <span className="text-[10px] text-slate-400 font-semibold uppercase">Téléchargements max</span>
                  <input
                    type="number"
                    min="1"
                    placeholder="Illimité"
                    value={maxDownloads}
                    onChange={(e) => setMaxDownloads(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="text-[11px] text-slate-400 flex items-center space-x-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>La clé de stockage MinIO n'est jamais exposée dans le lien.</span>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: User-to-User Sharing with Roles */}
        {activeTab === 'user' && (
          <div className="space-y-4">
            <form onSubmit={handleAddUser} className="flex gap-2">
              <input
                type="email"
                required
                value={invitedEmail}
                onChange={(e) => setInvitedEmail(e.target.value)}
                placeholder="adresse@exemple.fr"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <select
                value={invitedRole}
                onChange={(e) => setInvitedRole(e.target.value as UserRole)}
                className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none"
              >
                <option value="VIEWER">Lecteur</option>
                <option value="EDITOR">Éditeur</option>
                <option value="GUEST">Invité</option>
              </select>
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-colors"
              >
                Inviter
              </button>
            </form>

            <div className="space-y-2 pt-2">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Bénéficiaires autorisés ({invitedList.length})
              </span>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {invitedList.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-xl bg-slate-950 border border-slate-800/80 flex items-center justify-between text-xs"
                  >
                    <span className="text-slate-300">{item.email}</span>
                    <div className="flex items-center space-x-2">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-semibold text-slate-400">
                        {item.role === 'VIEWER' ? 'Lecture seule' : item.role === 'EDITOR' ? 'Modification' : 'Invité'}
                      </span>
                      <button
                        onClick={() => setInvitedList(invitedList.filter((_, i) => i !== idx))}
                        className="text-slate-500 hover:text-rose-400"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

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
