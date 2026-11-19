import React, { useState, useEffect } from 'react';
import { Edit2, X } from 'lucide-react';

interface RenameModalProps {
  isOpen: boolean;
  currentName: string;
  onConfirm: (newName: string) => void;
  onCancel: () => void;
}

export const RenameModal: React.FC<RenameModalProps> = ({
  isOpen,
  currentName,
  onConfirm,
  onCancel,
}) => {
  const [name, setName] = useState(currentName);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(currentName);
    setError(null);
  }, [currentName, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError('Le nom du document ne peut pas être vide.');
      return;
    }
    if (trimmed.includes('/') || trimmed.includes('\\') || trimmed.includes('..')) {
      setError('Caractères de chemin interdits (/, \\, ..).');
      return;
    }
    onConfirm(trimmed);
  };

  return (
    <div
      className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="rename-modal-title"
    >
      <form
        onSubmit={handleSubmit}
        className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Edit2 className="w-4 h-4" />
            </div>
            <h3 id="rename-modal-title" className="text-sm font-bold text-white">
              Renommer le document
            </h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Fermer"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div>
          <label htmlFor="rename-input" className="block text-xs font-medium text-slate-300 mb-1.5">
            Nouveau nom
          </label>
          <input
            id="rename-input"
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setError(null);
            }}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
            autoFocus
          />
          {error && (
            <p role="alert" className="text-xs text-rose-400 mt-1.5">
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end space-x-3 pt-2 border-t border-slate-800">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium whitespace-nowrap"
          >
            Annuler
          </button>
          <button
            type="submit"
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold whitespace-nowrap"
          >
            Enregistrer
          </button>
        </div>
      </form>
    </div>
  );
};
