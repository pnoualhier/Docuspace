import React, { useState, useEffect } from 'react';
import { X, FolderPlus, Edit2, Folder as FolderIcon } from 'lucide-react';
import { Folder } from '../types';

interface FolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  folderToEdit: Folder | null;
  parentFolder: Folder | null;
  onSave: (name: string, color: string) => void;
}

const COLORS = [
  '#3B82F6', // Blue
  '#10B981', // Emerald
  '#F59E0B', // Amber
  '#8B5CF6', // Purple
  '#EC4899', // Pink
  '#06B6D4', // Cyan
  '#64748B', // Slate
];

export const FolderModal: React.FC<FolderModalProps> = ({
  isOpen,
  onClose,
  folderToEdit,
  parentFolder,
  onSave,
}) => {
  const [name, setName] = useState('');
  const [color, setColor] = useState('#3B82F6');

  useEffect(() => {
    if (folderToEdit) {
      setName(folderToEdit.name);
      setColor(folderToEdit.color || '#3B82F6');
    } else {
      setName('');
      setColor('#3B82F6');
    }
  }, [folderToEdit, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSave(name.trim(), color);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              {folderToEdit ? <Edit2 className="w-5 h-5" /> : <FolderPlus className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">
                {folderToEdit ? 'Renommer le dossier' : 'Nouveau dossier'}
              </h3>
              <p className="text-[11px] text-slate-400">
                Emplacement : <span className="text-blue-400 font-semibold">{parentFolder ? parentFolder.name : 'Racine'}</span>
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

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Nom du dossier
            </label>
            <input
              type="text"
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex: Factures Énergie 2026"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Couleur d'accent
            </label>
            <div className="flex items-center space-x-2">
              {COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-transform ${
                    color === c ? 'scale-110 ring-2 ring-white ring-offset-2 ring-offset-slate-900' : 'hover:scale-105'
                  }`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              Annuler
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shadow-md shadow-blue-500/20 transition-all"
            >
              {folderToEdit ? 'Sauvegarder' : 'Créer le dossier'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
