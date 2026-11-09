import React, { useState } from 'react';
import { 
  Folder as FolderIcon, 
  FileText, 
  Image as ImageIcon, 
  FileSpreadsheet, 
  FileArchive, 
  FileCode, 
  File, 
  MoreVertical, 
  Star, 
  Trash2, 
  Download, 
  Share2, 
  History, 
  ShieldCheck, 
  ShieldAlert, 
  Clock, 
  LayoutGrid, 
  List as ListIcon, 
  ArrowUpDown, 
  FolderPlus, 
  UploadCloud, 
  ChevronRight,
  ExternalLink,
  Edit2,
  MoveRight,
  CheckSquare,
  Square
} from 'lucide-react';
import { DocumentItem, Folder } from '../types';
import { formatBytes, getFileCategory } from '../services/crypto';

interface FileExplorerProps {
  currentFolder: Folder | null;
  breadcrumbs: Folder[];
  folders: Folder[];
  documents: DocumentItem[];
  viewMode: 'grid' | 'list';
  onToggleViewMode: () => void;
  onNavigateFolder: (folderId: string | null) => void;
  onPreviewDocument: (doc: DocumentItem) => void;
  onShareDocument: (doc: DocumentItem) => void;
  onViewVersions: (doc: DocumentItem) => void;
  onToggleFavoriteDoc: (docId: string) => void;
  onTrashDoc: (docId: string) => void;
  onRestoreDoc: (docId: string) => void;
  onPurgeDoc: (docId: string) => void;
  onRenameDoc: (doc: DocumentItem) => void;
  onOpenUpload: () => void;
  onOpenNewFolder: () => void;
  onRenameFolder: (folder: Folder) => void;
  onTrashFolder: (folderId: string) => void;
  isTrashView?: boolean;
  userRole?: 'OWNER' | 'EDITOR' | 'VIEWER' | 'GUEST';
}

export const FileExplorer: React.FC<FileExplorerProps> = ({
  currentFolder,
  breadcrumbs,
  folders,
  documents,
  viewMode,
  onToggleViewMode,
  onNavigateFolder,
  onPreviewDocument,
  onShareDocument,
  onViewVersions,
  onToggleFavoriteDoc,
  onTrashDoc,
  onRestoreDoc,
  onPurgeDoc,
  onRenameDoc,
  onOpenUpload,
  onOpenNewFolder,
  onRenameFolder,
  onTrashFolder,
  isTrashView = false,
  userRole = 'OWNER',
}) => {
  const isReadOnly = userRole === 'VIEWER' || userRole === 'GUEST';
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'name' | 'date' | 'size'>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [activeMenuDocId, setActiveMenuDocId] = useState<string | null>(null);

  // Filter documents
  const filteredDocs = documents.filter((doc) => {
    if (filterCategory === 'all') return true;
    const cat = getFileCategory(doc.mimeType, doc.extension);
    return cat === filterCategory;
  });

  // Sort documents
  const sortedDocs = [...filteredDocs].sort((a, b) => {
    if (sortBy === 'name') {
      return sortOrder === 'asc' 
        ? a.originalName.localeCompare(b.originalName) 
        : b.originalName.localeCompare(a.originalName);
    }
    if (sortBy === 'size') {
      return sortOrder === 'asc' ? a.sizeBytes - b.sizeBytes : b.sizeBytes - a.sizeBytes;
    }
    // Default: date
    const dateA = new Date(a.updatedAt).getTime();
    const dateB = new Date(b.updatedAt).getTime();
    return sortOrder === 'asc' ? dateA - dateB : dateB - dateA;
  });

  const toggleSelectDoc = (id: string) => {
    setSelectedDocIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedDocIds.length === sortedDocs.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(sortedDocs.map(d => d.id));
    }
  };

  const getDocIcon = (mimeType: string, extension: string) => {
    const cat = getFileCategory(mimeType, extension);
    switch (cat) {
      case 'pdf':
        return <FileText className="w-6 h-6 text-rose-400" />;
      case 'image':
        return <ImageIcon className="w-6 h-6 text-sky-400" />;
      case 'word':
        return <FileText className="w-6 h-6 text-blue-400" />;
      case 'excel':
        return <FileSpreadsheet className="w-6 h-6 text-emerald-400" />;
      case 'archive':
        return <FileArchive className="w-6 h-6 text-amber-400" />;
      case 'code':
        return <FileCode className="w-6 h-6 text-violet-400" />;
      default:
        return <File className="w-6 h-6 text-slate-400" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950/40">
      {/* Top Bar: Breadcrumbs & Controls */}
      <div className="p-6 pb-3 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Breadcrumb Navigation */}
        <div className="flex items-center space-x-2 text-xs overflow-x-auto py-1">
          <button
            onClick={() => onNavigateFolder(null)}
            className={`font-medium hover:text-white transition-colors ${
              currentFolder === null ? 'text-white font-semibold' : 'text-slate-400'
            }`}
          >
            {isTrashView ? 'Corbeille (Purgée à 30j)' : 'Espace racine'}
          </button>

          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={crumb.id}>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
              <button
                onClick={() => onNavigateFolder(crumb.id)}
                className={`font-medium hover:text-white truncate max-w-[140px] transition-colors ${
                  idx === breadcrumbs.length - 1 ? 'text-blue-400 font-semibold' : 'text-slate-400'
                }`}
              >
                {crumb.name}
              </button>
            </React.Fragment>
          ))}
        </div>

        {/* Action Controls & Filters */}
        <div className="flex items-center space-x-3 shrink-0">
          {/* Category filter pills */}
          <div className="hidden lg:flex items-center space-x-1 p-1 bg-slate-900 border border-slate-800 rounded-lg text-[11px]">
            {['all', 'pdf', 'image', 'word', 'excel', 'archive'].map((cat) => (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                className={`px-2.5 py-1 rounded capitalize transition-colors ${
                  filterCategory === cat
                    ? 'bg-blue-600 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {cat === 'all' ? 'Tous' : cat}
              </button>
            ))}
          </div>

          {/* Sort Menu */}
          <div className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-300">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer text-xs"
            >
              <option value="date" className="bg-slate-900">Date modif.</option>
              <option value="name" className="bg-slate-900">Nom (A-Z)</option>
              <option value="size" className="bg-slate-900">Taille</option>
            </select>
            <button
              onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
              className="text-[10px] text-slate-400 hover:text-white px-1"
              title="Inverser l'ordre"
            >
              {sortOrder === 'asc' ? '↑' : '↓'}
            </button>
          </div>

          {/* View Mode Toggle */}
          <button
            onClick={onToggleViewMode}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
            title={viewMode === 'grid' ? 'Affichage Liste' : 'Affichage Grille'}
          >
            {viewMode === 'grid' ? <ListIcon className="w-4 h-4" /> : <LayoutGrid className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Read-Only RBAC Policy Indicator */}
      {isReadOnly && (
        <div className="mx-6 mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center space-x-2.5 text-xs text-amber-300 animate-in fade-in">
          <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            <strong>Contrôle RBAC actif ({userRole}) :</strong> Vous disposez d'un accès en lecture seule à cet espace documentaire. Les imports, modifications et suppressions sont verrouillés côté backend.
          </span>
        </div>
      )}

      {/* Multi-selection banner */}
      {selectedDocIds.length > 0 && (
        <div className="mx-6 mt-4 p-3 rounded-xl bg-blue-950/40 border border-blue-500/30 flex items-center justify-between text-xs text-blue-200 animate-in fade-in">
          <div className="flex items-center space-x-2">
            <span className="font-semibold">{selectedDocIds.length} fichier(s) sélectionné(s)</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => alert(`Téléchargement groupé de ${selectedDocIds.length} fichiers sous archive ZIP sécurisée.`)}
              className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium flex items-center space-x-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Télécharger (.ZIP)</span>
            </button>
            <button
              onClick={() => {
                selectedDocIds.forEach(id => onTrashDoc(id));
                setSelectedDocIds([]);
              }}
              className="px-3 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 font-medium flex items-center space-x-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Placer à la corbeille</span>
            </button>
            <button
              onClick={() => setSelectedDocIds([])}
              className="text-slate-400 hover:text-white text-xs px-2"
            >
              Désélectionner
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Folders Section (if not in trash) */}
        {!isTrashView && folders.length > 0 && (
          <div className="space-y-3">
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-2">
              <FolderIcon className="w-3.5 h-3.5 text-blue-400" />
              <span>Dossiers ({folders.length})</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
              {folders.map((folder) => (
                <div
                  key={folder.id}
                  onClick={() => onNavigateFolder(folder.id)}
                  className="group relative p-3.5 rounded-xl bg-slate-900/80 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer flex items-center justify-between"
                >
                  <div className="flex items-center space-x-3 truncate">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                      style={{ backgroundColor: `${folder.color}20`, color: folder.color }}
                    >
                      <FolderIcon className="w-4 h-4 fill-current" />
                    </div>
                    <div className="truncate">
                      <div className="text-xs font-semibold text-slate-200 group-hover:text-blue-400 truncate">
                        {folder.name}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Dossier sécurisé
                      </div>
                    </div>
                  </div>

                  {/* Actions on folder */}
                  <div 
                    onClick={(e) => e.stopPropagation()} 
                    className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center space-x-1"
                  >
                    <button
                      onClick={() => onRenameFolder(folder)}
                      className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700"
                      title="Renommer le dossier"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => onTrashFolder(folder.id)}
                      className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-700"
                      title="Supprimer le dossier"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Documents Section */}
        <div className="space-y-3">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FileText className="w-3.5 h-3.5 text-sky-400" />
              <span>Fichiers ({sortedDocs.length})</span>
            </div>
            {sortedDocs.length > 0 && (
              <button
                onClick={selectAll}
                className="text-[11px] text-slate-400 hover:text-white flex items-center space-x-1"
              >
                {selectedDocIds.length === sortedDocs.length ? (
                  <CheckSquare className="w-3.5 h-3.5 text-blue-400" />
                ) : (
                  <Square className="w-3.5 h-3.5 text-slate-500" />
                )}
                <span>Tout sélectionner</span>
              </button>
            )}
          </div>

          {/* Empty State */}
          {sortedDocs.length === 0 && folders.length === 0 && (
            <div className="py-16 text-center border-2 border-dashed border-slate-800 rounded-2xl p-8 space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 mx-auto flex items-center justify-center text-slate-500">
                <UploadCloud className="w-8 h-8 text-blue-500/60" />
              </div>
              <div className="max-w-sm mx-auto space-y-1">
                <h3 className="text-sm font-semibold text-slate-200">
                  {isTrashView ? 'La corbeille est vide' : 'Cet espace est prêt pour vos documents'}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {isTrashView
                    ? 'Aucun élément supprimé récemment.'
                    : 'Glissez-déposez vos fichiers pour les chiffrer, les analyser avec ClamAV et les classer.'}
                </p>
              </div>
              {!isTrashView && (
                <div className="flex items-center justify-center space-x-3 pt-2">
                  <button
                    onClick={onOpenUpload}
                    className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center space-x-2 shadow-sm transition-colors"
                  >
                    <UploadCloud className="w-4 h-4" />
                    <span>Importer un document</span>
                  </button>
                  <button
                    onClick={onOpenNewFolder}
                    className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-xs font-medium transition-colors"
                  >
                    <span>Créer un sous-dossier</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Grid View */}
          {viewMode === 'grid' && sortedDocs.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
              {sortedDocs.map((doc) => {
                const isSelected = selectedDocIds.includes(doc.id);
                return (
                  <div
                    key={doc.id}
                    onClick={() => onPreviewDocument(doc)}
                    className={`group relative rounded-2xl p-4 bg-slate-900/70 hover:bg-slate-900 border transition-all cursor-pointer flex flex-col justify-between space-y-3 shadow-sm ${
                      isSelected
                        ? 'border-blue-500 ring-1 ring-blue-500/50 bg-blue-950/20'
                        : 'border-slate-800/90 hover:border-slate-700'
                    }`}
                  >
                    {/* Header: Icon, Antivirus badge & Checkbox */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2.5">
                        <div className="p-2 rounded-xl bg-slate-800/80">
                          {getDocIcon(doc.mimeType, doc.extension)}
                        </div>
                        {/* Antivirus ClamAV badge */}
                        <div
                          className={`flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                            doc.antivirusStatus === 'CLEAN'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          }`}
                          title={`ClamAV Status: ${doc.antivirusStatus}`}
                        >
                          <ShieldCheck className="w-3 h-3 text-emerald-400" />
                          <span>ClamAV Sain</span>
                        </div>
                      </div>

                      {/* Select & Favorite buttons */}
                      <div 
                        onClick={(e) => e.stopPropagation()} 
                        className="flex items-center space-x-1"
                      >
                        {!isTrashView && (
                          <button
                            onClick={() => onToggleFavoriteDoc(doc.id)}
                            className={`p-1.5 rounded-lg transition-colors ${
                              doc.isFavorite
                                ? 'text-amber-400 hover:text-amber-300'
                                : 'text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100'
                            }`}
                            title={doc.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
                          >
                            <Star className={`w-3.5 h-3.5 ${doc.isFavorite ? 'fill-current' : ''}`} />
                          </button>
                        )}
                        <button
                          onClick={() => toggleSelectDoc(doc.id)}
                          className={`p-1.5 rounded-lg transition-colors ${
                            isSelected ? 'text-blue-400' : 'text-slate-500 hover:text-slate-300 opacity-0 group-hover:opacity-100'
                          }`}
                        >
                          {isSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    {/* Body: Title & Hash */}
                    <div>
                      <h4 className="text-xs font-semibold text-slate-100 truncate group-hover:text-blue-400 transition-colors">
                        {doc.originalName}
                      </h4>
                      <div className="flex items-center space-x-2 text-[10px] text-slate-400 mt-1 font-mono">
                        <span>{formatBytes(doc.sizeBytes)}</span>
                        <span>•</span>
                        <span className="truncate max-w-[120px]" title={`SHA-256: ${doc.sha256Hash}`}>
                          sha256:{doc.sha256Hash.substring(0, 8)}...
                        </span>
                      </div>
                    </div>

                    {/* Footer: Date & Quick Actions */}
                    <div 
                      onClick={(e) => e.stopPropagation()} 
                      className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500"
                    >
                      <span>{new Date(doc.updatedAt).toLocaleDateString('fr-FR')}</span>

                      <div className="flex items-center space-x-1">
                        {!isTrashView ? (
                          <>
                            <button
                              onClick={() => onShareDocument(doc)}
                              className="p-1 rounded text-slate-400 hover:text-blue-400 hover:bg-slate-800 transition-colors"
                              title="Partager en toute sécurité"
                            >
                              <Share2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => onViewVersions(doc)}
                              className="p-1 rounded text-slate-400 hover:text-purple-400 hover:bg-slate-800 transition-colors"
                              title="Historique des versions"
                            >
                              <History className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => onTrashDoc(doc.id)}
                              className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                              title="Déplacer vers la corbeille"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => onRestoreDoc(doc.id)}
                              className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-[10px] font-medium"
                            >
                              Restaurer
                            </button>
                            <button
                              onClick={() => onPurgeDoc(doc.id)}
                              className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-[10px] font-medium"
                            >
                              Détruire
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* List View */}
          {viewMode === 'list' && sortedDocs.length > 0 && (
            <div className="rounded-2xl border border-slate-800 overflow-hidden bg-slate-900/60">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 text-[11px] uppercase font-semibold">
                  <tr>
                    <th className="p-3 pl-4 w-8">
                      <button onClick={selectAll} className="text-slate-400 hover:text-white">
                        {selectedDocIds.length === sortedDocs.length ? (
                          <CheckSquare className="w-3.5 h-3.5 text-blue-400" />
                        ) : (
                          <Square className="w-3.5 h-3.5 text-slate-500" />
                        )}
                      </button>
                    </th>
                    <th className="p-3">Nom du document</th>
                    <th className="p-3">Taille</th>
                    <th className="p-3">Empreinte SHA-256</th>
                    <th className="p-3">Contrôle ClamAV</th>
                    <th className="p-3">Date</th>
                    <th className="p-3 text-right pr-4">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {sortedDocs.map((doc) => {
                    const isSelected = selectedDocIds.includes(doc.id);
                    return (
                      <tr
                        key={doc.id}
                        onClick={() => onPreviewDocument(doc)}
                        className={`hover:bg-slate-800/50 transition-colors cursor-pointer ${
                          isSelected ? 'bg-blue-950/20' : ''
                        }`}
                      >
                        <td className="p-3 pl-4" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => toggleSelectDoc(doc.id)}
                            className="text-slate-400 hover:text-white"
                          >
                            {isSelected ? <CheckSquare className="w-3.5 h-3.5 text-blue-400" /> : <Square className="w-3.5 h-3.5 text-slate-600" />}
                          </button>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center space-x-2.5">
                            {getDocIcon(doc.mimeType, doc.extension)}
                            <div>
                              <span className="font-semibold text-slate-200 hover:text-blue-400 transition-colors">
                                {doc.originalName}
                              </span>
                              {doc.versions.length > 1 && (
                                <span className="ml-2 px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-400 text-[10px] font-mono">
                                  v{doc.versions[0].versionNumber}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="p-3 text-slate-300 font-mono text-[11px]">
                          {formatBytes(doc.sizeBytes)}
                        </td>
                        <td className="p-3 text-slate-400 font-mono text-[11px]">
                          {doc.sha256Hash.substring(0, 12)}...
                        </td>
                        <td className="p-3">
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <ShieldCheck className="w-3 h-3" />
                            <span>Certifié ClamAV</span>
                          </span>
                        </td>
                        <td className="p-3 text-slate-400 text-[11px]">
                          {new Date(doc.updatedAt).toLocaleDateString('fr-FR')}
                        </td>
                        <td className="p-3 text-right pr-4" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end space-x-1">
                            {!isTrashView ? (
                              <>
                                <button
                                  onClick={() => onToggleFavoriteDoc(doc.id)}
                                  className={`p-1.5 rounded hover:bg-slate-800 ${
                                    doc.isFavorite ? 'text-amber-400' : 'text-slate-400 hover:text-white'
                                  }`}
                                  title="Favori"
                                >
                                  <Star className={`w-3.5 h-3.5 ${doc.isFavorite ? 'fill-current' : ''}`} />
                                </button>
                                <button
                                  onClick={() => onShareDocument(doc)}
                                  className="p-1.5 rounded text-slate-400 hover:text-blue-400 hover:bg-slate-800"
                                  title="Partager"
                                >
                                  <Share2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => onViewVersions(doc)}
                                  className="p-1.5 rounded text-slate-400 hover:text-purple-400 hover:bg-slate-800"
                                  title="Versions"
                                >
                                  <History className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => onRenameDoc(doc)}
                                  className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-800"
                                  title="Renommer"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => onTrashDoc(doc.id)}
                                  className="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-slate-800"
                                  title="Corbeille"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  onClick={() => onRestoreDoc(doc.id)}
                                  className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-medium"
                                >
                                  Restaurer
                                </button>
                                <button
                                  onClick={() => onPurgeDoc(doc.id)}
                                  className="px-2.5 py-1 rounded bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs font-medium"
                                >
                                  Détruire
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
