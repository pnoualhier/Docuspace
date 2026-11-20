import React, { useState } from 'react';
import {
  X,
  ShieldCheck,
  Lock,
  Mail,
  User as UserIcon,
  ArrowRight,
  KeyRound,
  CheckCircle2,
} from 'lucide-react';
import { apiClient, ApiError } from '../services/api';

interface AuthModalProps {
  isOpen: boolean;
  onClose?: () => void;
  canDismiss?: boolean;
  onLogin: (email: string, password: string) => void | Promise<void>;
  onRegister: (fullName: string, email: string, password: string) => void | Promise<void>;
  errorMessage?: string | null;
  isSubmitting?: boolean;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  canDismiss = false,
  onLogin,
  onRegister,
  errorMessage = null,
  isSubmitting = false,
}) => {
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [resetStep, setResetStep] = useState<'request' | 'confirm'>('request');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [isResetSubmitting, setIsResetSubmitting] = useState(false);

  if (!isOpen) return null;

  const displayedError = localError || errorMessage;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setResetMessage(null);

    if (mode === 'login') {
      await onLogin(email.trim(), password);
      return;
    }

    if (mode === 'register') {
      if (password.length < 8) {
        setLocalError('Le mot de passe doit contenir au moins 8 caractères.');
        return;
      }
      await onRegister(fullName.trim(), email.trim(), password);
      return;
    }

    setIsResetSubmitting(true);
    try {
      if (resetStep === 'request') {
        const res = await apiClient.auth.passwordResetRequest(email.trim());
        setResetMessage(res.message);
        setResetStep('confirm');
      } else {
        if (newPassword.length < 8) {
          setLocalError('Le nouveau mot de passe doit contenir au moins 8 caractères.');
          return;
        }
        const res = await apiClient.auth.passwordResetConfirm(resetToken.trim(), newPassword);
        setResetMessage(res.message);
        setResetToken('');
        setNewPassword('');
        setMode('login');
        setResetStep('request');
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setLocalError(err.detail);
      } else {
        setLocalError('Impossible de traiter la demande de réinitialisation.');
      }
    } finally {
      setIsResetSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      className="fixed inset-0 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in"
    >
      <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-md p-8 space-y-6 shadow-2xl relative overflow-hidden">
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-blue-600/20 rounded-full blur-3xl pointer-events-none" />

        {canDismiss && onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer la fenêtre de connexion"
            className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Brand header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-sky-400 mx-auto flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h2 id="auth-modal-title" className="text-xl font-black text-white tracking-tight">
            DocuSpace
          </h2>
          <p className="text-xs text-slate-400">
            {mode === 'login' && 'Connexion sécurisée avec chiffrement Argon2id'}
            {mode === 'register' && 'Création de votre espace documentaire personnel'}
            {mode === 'forgot' && 'Réinitialisation sécurisée de votre mot de passe'}
          </p>
        </div>

        {/* Mode selector */}
        {mode !== 'forgot' && (
          <div className="flex p-1 bg-slate-950 border border-slate-800 rounded-xl text-xs font-medium">
            <button
              type="button"
              onClick={() => {
                setMode('login');
                setLocalError(null);
              }}
              className={`flex-1 py-2 rounded-lg transition-colors ${
                mode === 'login' ? 'bg-blue-600 text-white font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Se connecter
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register');
                setLocalError(null);
              }}
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
              <label htmlFor="auth-fullname" className="block text-xs font-semibold text-slate-300 mb-1">
                Nom complet
              </label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="auth-fullname"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Prénom Nom"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          )}

          {(mode !== 'forgot' || resetStep === 'request') && (
            <div>
              <label htmlFor="auth-email" className="block text-xs font-semibold text-slate-300 mb-1">
                Adresse e-mail
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="auth-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="nom@domaine.fr"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          )}

          {mode !== 'forgot' && (
            <div>
              <div className="flex justify-between items-center mb-1">
                <label htmlFor="auth-password" className="block text-xs font-semibold text-slate-300">
                  Mot de passe
                </label>
                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => {
                      setMode('forgot');
                      setResetStep('request');
                      setResetMessage(null);
                      setLocalError(null);
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
                  id="auth-password"
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

          {mode === 'forgot' && resetStep === 'confirm' && (
            <>
              <div>
                <label htmlFor="auth-reset-token" className="block text-xs font-semibold text-slate-300 mb-1">
                  Jeton de réinitialisation
                </label>
                <div className="relative">
                  <KeyRound className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="auth-reset-token"
                    type="text"
                    required
                    value={resetToken}
                    onChange={(e) => setResetToken(e.target.value)}
                    placeholder="Collez le jeton reçu par e-mail"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="auth-new-password" className="block text-xs font-semibold text-slate-300 mb-1">
                  Nouveau mot de passe
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="auth-new-password"
                    type="password"
                    required
                    minLength={8}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Minimum 8 caractères"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            </>
          )}

          {displayedError && (
            <div
              role="alert"
              className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs"
            >
              {displayedError}
            </div>
          )}

          {resetMessage && (
            <div
              role="status"
              className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-start space-x-2"
            >
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
              <span>{resetMessage}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting || isResetSubmitting}
            className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white font-semibold text-xs shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center space-x-2"
          >
            <span>
              {isSubmitting || isResetSubmitting
                ? 'Vérification en cours...'
                : mode === 'login'
                  ? 'Se connecter'
                  : mode === 'register'
                    ? 'Créer mon espace'
                    : resetStep === 'request'
                      ? 'Envoyer le lien'
                      : 'Valider le nouveau mot de passe'}
            </span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>

          {mode === 'forgot' && (
            <div className="flex items-center justify-between pt-2 text-xs">
              <button
                type="button"
                onClick={() => {
                  setMode('login');
                  setLocalError(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                ← Retour à la connexion
              </button>
              <button
                type="button"
                onClick={() =>
                  setResetStep((prev) => (prev === 'request' ? 'confirm' : 'request'))
                }
                className="text-blue-400 hover:text-blue-300"
              >
                {resetStep === 'request' ? "J'ai déjà un jeton" : 'Renvoyer un e-mail'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
