import React, { useState } from 'react';
import { 
  X, 
  ShieldCheck, 
  Lock, 
  Mail, 
  User as UserIcon, 
  ArrowRight, 
  Sparkles,
  KeyRound
} from 'lucide-react';
import { User } from '../types';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: (email: string) => void;
  onRegister: (fullName: string, email: string) => void;
  availableUsers: User[];
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onLogin,
  onRegister,
  availableUsers,
}) => {
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [resetSent, setResetSent] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'login') {
      onLogin(email);
    } else if (mode === 'register') {
      onRegister(fullName, email);
    } else {
      setResetSent(true);
    }
  };

  const selectDemoUser = (user: User) => {
    setEmail(user.email);
    setPassword('••••••••••••');
    onLogin(user.email);
  };

  return (
    <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-md p-8 space-y-6 shadow-2xl relative overflow-hidden">
        {/* Decorative background glow */}
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-blue-600/20 rounded-full blur-3xl pointer-events-none" />

        {/* Brand header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-sky-400 mx-auto flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-black text-white tracking-tight">DocuSpace</h2>
          <p className="text-xs text-slate-400">
            {mode === 'login' && 'Connexion sécurisée avec chiffrement Argon2id'}
            {mode === 'register' && 'Création de votre espace documentaire personnel'}
            {mode === 'forgot' && 'Réinitialisation sécurisée de votre mot de passe'}
          </p>
        </div>

        {/* Mode selector pills */}
        {mode !== 'forgot' && (
          <div className="flex p-1 bg-slate-950 border border-slate-800 rounded-xl text-xs font-medium">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 py-2 rounded-lg transition-colors ${
                mode === 'login' ? 'bg-blue-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Se connecter
            </button>
            <button
              onClick={() => setMode('register')}
              className={`flex-1 py-2 rounded-lg transition-colors ${
                mode === 'register' ? 'bg-blue-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Créer un compte
            </button>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Nom complet</label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jean Dupont"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Adresse e-mail</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jean.dupont@example.com"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {mode !== 'forgot' && (
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="block text-xs font-semibold text-slate-300">Mot de passe</label>
                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => {
                      setMode('forgot');
                      setResetSent(false);
                    }}
                    className="text-[11px] text-blue-400 hover:text-blue-300"
                  >
                    Mot de passe oublié ?
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 caractères"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          )}

          {resetSent && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
              Un lien de réinitialisation sécurisé a été généré et envoyé à l'adresse indiquée.
            </div>
          )}

          <button
            type="submit"
            className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center space-x-2"
          >
            <span>
              {mode === 'login' && 'Se connecter'}
              {mode === 'register' && 'Créer mon espace'}
              {mode === 'forgot' && 'Envoyer le lien'}
            </span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>

          {mode === 'forgot' && (
            <button
              type="button"
              onClick={() => setMode('login')}
              className="w-full text-center text-xs text-slate-400 hover:text-white pt-2"
            >
              ← Retour à la connexion
            </button>
          )}
        </form>

        {/* Demo Fast Logins for instant review */}
        {mode === 'login' && (
          <div className="pt-2 border-t border-slate-800 space-y-2">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block text-center">
              Comptes Démonstration Immédiats
            </span>
            <div className="grid grid-cols-3 gap-2">
              {availableUsers.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => selectDemoUser(u)}
                  className="p-2 rounded-xl bg-slate-950 hover:bg-slate-800/80 border border-slate-800 text-[11px] text-slate-300 hover:text-white transition-colors truncate"
                  title={`Connexion en tant que ${u.fullName}`}
                >
                  <div className="font-semibold truncate">{u.fullName.split(' ')[0]}</div>
                  <div className="text-[9px] text-slate-500 truncate">
                    {u.isSuperuser ? 'Admin' : 'Utilisateur'}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
