import React from 'react';
import { 
  Search, 
  Filter, 
  RotateCcw, 
  Calendar, 
  HardDrive, 
  Star, 
  Folder as FolderIcon, 
  FileText 
} from 'lucide-react';
import { Folder } from '../types';

export interface SearchFilters {
  query: string;
  category: string;
  sizeRange: string; // 'all' | 'small' | 'medium' | 'large'
  dateRange: string; // 'all' | '7d' | '30d' | '1y'
  folderId: string; // 'all' | folderId
  favoritesOnly: boolean;
}

interface AdvancedSearchPanelProps {
  filters: SearchFilters;
  onFilterChange: (newFilters: SearchFilters) => void;
  onReset: () => void;
  folders: Folder[];
}

export const AdvancedSearchPanel: React.FC<AdvancedSearchPanelProps> = ({
  filters,
  onFilterChange,
  onReset,
  folders,
}) => {
  const activeCount = [
    filters.query.trim() !== '',
    filters.category !== 'all',
    filters.sizeRange !== 'all',
    filters.dateRange !== 'all',
    filters.folderId !== 'all',
    filters.favoritesOnly,
  ].filter(Boolean).length;

  return (
    <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4 mb-4 text-xs">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-blue-400" />
          <span className="font-bold text-white text-xs uppercase tracking-wider">
            Filtres de recherche avancée
          </span>
          {activeCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
              {activeCount} actif(s)
            </span>
          )}
        </div>

        {activeCount > 0 && (
          <button
            onClick={onReset}
            className="text-[11px] text-slate-400 hover:text-white flex items-center space-x-1 transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Réinitialiser</span>
          </button>
        )}
      </div>

      {/* Grid of criteria */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Category */}
        <div className="space-y-1">
          <label className="text-[10px] text-slate-400 font-semibold uppercase">Type de document</label>
          <select
            value={filters.category}
            onChange={(e) => onFilterChange({ ...filters, category: e.target.value })}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Tous types</option>
            <option value="pdf">PDF uniquement</option>
            <option value="image">Images & Photos</option>
            <option value="word">Word & Bureautique</option>
            <option value="excel">Tableurs & CSV</option>
            <option value="archive">Archives ZIP</option>
            <option value="code">Code & Fichiers texte</option>
          </select>
        </div>

        {/* Size Range */}
        <div className="space-y-1">
          <label className="text-[10px] text-slate-400 font-semibold uppercase">Taille du fichier</label>
          <select
            value={filters.sizeRange}
            onChange={(e) => onFilterChange({ ...filters, sizeRange: e.target.value })}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Toutes tailles</option>
            <option value="small">Moins de 1 Mo</option>
            <option value="medium">Entre 1 Mo et 10 Mo</option>
            <option value="large">Plus de 10 Mo</option>
          </select>
        </div>

        {/* Date Range */}
        <div className="space-y-1">
          <label className="text-[10px] text-slate-400 font-semibold uppercase">Période de modification</label>
          <select
            value={filters.dateRange}
            onChange={(e) => onFilterChange({ ...filters, dateRange: e.target.value })}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Toutes dates</option>
            <option value="7d">7 derniers jours</option>
            <option value="30d">30 derniers jours</option>
            <option value="1y">Cette dernière année</option>
          </select>
        </div>

        {/* Folder Scope */}
        <div className="space-y-1">
          <label className="text-[10px] text-slate-400 font-semibold uppercase">Dossier cible</label>
          <select
            value={filters.folderId}
            onChange={(e) => onFilterChange({ ...filters, folderId: e.target.value })}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="all">Tous les dossiers</option>
            {folders.filter(f => !f.isTrashed).map(f => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Favorite Toggle */}
      <div className="flex items-center space-x-2 pt-1 border-t border-slate-800/60">
        <label className="flex items-center space-x-2 cursor-pointer text-xs text-slate-300">
          <input
            type="checkbox"
            checked={filters.favoritesOnly}
            onChange={(e) => onFilterChange({ ...filters, favoritesOnly: e.target.checked })}
            className="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0"
          />
          <span className="flex items-center space-x-1">
            <Star className={`w-3.5 h-3.5 ${filters.favoritesOnly ? 'text-amber-400 fill-current' : 'text-slate-400'}`} />
            <span>Uniquement les favoris</span>
          </span>
        </label>
      </div>
    </div>
  );
};
