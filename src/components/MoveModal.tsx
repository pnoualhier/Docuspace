import React, { useState } from 'react';
import { 
  X, 
  Folder as FolderIcon, 
  FolderTree, 
  ChevronRight, 
  ChevronDown, 
  Check, 
  MoveRight,
  HardDrive 
} from 'lucide-react';
import { Folder, DocumentItem } from '../types';

interface MoveModalProps {
  isOpen: boolean;
  onClose: () => void;
  itemToMove: { type: 'document' | 'folder' | 'bulk'; item: DocumentItem | Folder | null; bulkIds?: string[] };
  folders: Folder[];
  onConfirmMove: (targetFolderId: string | null) => void;
}

export const MoveModal: React.FC<MoveModalProps> = ({
  isOpen,
  onClose,
  itemToMove,
  folders,
  onConfirmMove,
}) => {
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<string[]>([]);

  if (!isOpen) return null;

  const toggleExpand = (fId: string) => {
    setExpandedFolders(prev => 
      prev.includes(fId) ? prev.filter(id => id !== fId) : [...prev, fId]
    );
  };

  // Build root and nested folder map
  const activeFolders = folders.filter(f => !f.isTrashed);

  // Check if target is invalid (cycle detection)
  const isInvalidTarget = (targetId: string | null): boolean => {
    if (itemToMove.type === 'document' || itemToMove.type === 'bulk') return false;
    const movingFolder = itemToMove.item as Folder;
    if (!movingFolder) return false;
    if (targetId === movingFolder.id) return true; // Cannot move into self

    // Check if targetId is a descendant of movingFolder.id
    let curr = activeFolders.find(f => f.id === targetId);
    while (curr && curr.parentId) {
      if (curr.parentId === movingFolder.id) return true;
      curr = activeFolders.find(f => f.id === curr?.parentId);
    }
    return false;
  };

  const handleSelect = (targetId: string | null) => {
    if (!isInvalidTarget(targetId)) {
      setSelectedFolderId(targetId);
    }
  };

  const renderFolderBranch = (parentId: string | null, depth = 0) => {
    const children = activeFolders.filter(f => f.parentId === parentId);
    if (children.length === 0) return null;

    return (
      <div className="space-y-1" style={{ paddingLeft: depth > 0 ? '16px' : '0px' }}>
        {children.map((f) => {
          const hasChildren = activeFolders.some(sub => sub.parentId === f.id);
          const isExpanded = expandedFolders.includes(f.id);
          const isSelected = selectedFolderId === f.id;
          const disabled = isInvalidTarget(f.id);

          return (
            <div key={f.id} className="space-y-1">
              <div
                onClick={() => !disabled && handleSelect(f.id)}
                className={`p-2 rounded-xl flex items-center justify-between text-xs transition-colors cursor-pointer ${
                  disabled
                    ? 'opacity-40 cursor-not-allowed bg-slate-900/40 text-slate-500'
                    : isSelected
                    ? 'bg-blue-600/20 border border-blue-500/40 text-blue-300 font-semibold'
                    : 'hover:bg-slate-800/80 text-slate-300'
                }`}
              >
                <div className="flex items-center space-x-2 truncate">
                  {hasChildren ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleExpand(f.id);
                      }}
                      className="p-1 rounded hover:bg-slate-700 text-slate-400"
                    >
                      {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </button>
                  ) : (
                    <div className="w-5" />
                  )}
                  <div
                    className="w-5 h-5 rounded flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${f.color}25`, color: f.color }}
                  >
                    <FolderIcon className="w-3 h-3 fill-current" />
                  </div>
                  <span className="truncate">{f.name}</span>
                </div>

                {isSelected && (
                  <Check className="w-4 h-4 text-blue-400 shrink-0" />
                )}
              </div>

              {/* Render children recursively if expanded */}
              {isExpanded && renderFolderBranch(f.id, depth + 1)}
            </div>
          );
        })}
      </div>
    );
  };

  const itemName = 
    itemToMove.type === 'bulk'
      ? `${itemToMove.bulkIds?.length || 0} élément(s) sélectionné(s)`
      : (itemToMove.item as any)?.originalName || (itemToMove.item as any)?.name || 'Élément';

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2.5 truncate">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <MoveRight className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h3 className="text-sm font-bold text-white">Déplacer l'élément</h3>
              <p className="text-[11px] text-slate-400 truncate max-w-[280px]">
                {itemName}
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

        {/* Tree Selector */}
        <div className="space-y-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
            Choisir le dossier de destination
          </span>

          <div className="p-2 rounded-xl bg-slate-950 border border-slate-800 max-h-64 overflow-y-auto space-y-1">
            {/* Root Option */}
            <div
              onClick={() => handleSelect(null)}
              className={`p-2 rounded-xl flex items-center justify-between text-xs transition-colors cursor-pointer ${
                selectedFolderId === null
                  ? 'bg-blue-600/20 border border-blue-500/40 text-blue-300 font-semibold'
                  : 'hover:bg-slate-800 text-slate-300'
              }`}
            >
              <div className="flex items-center space-x-2">
                <div className="w-5" />
                <HardDrive className="w-4 h-4 text-sky-400" />
                <span>Espace racine (aucun sous-dossier)</span>
              </div>
              {selectedFolderId === null && <Check className="w-4 h-4 text-blue-400" />}
            </div>

            {/* Recursive Branches */}
            {renderFolderBranch(null, 0)}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex justify-end space-x-3 pt-2 border-t border-slate-800">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={() => {
              onConfirmMove(selectedFolderId);
              onClose();
            }}
            className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shadow-md shadow-blue-500/20 transition-all flex items-center space-x-1.5"
          >
            <MoveRight className="w-3.5 h-3.5" />
            <span>Déplacer ici</span>
          </button>
        </div>
      </div>
    </div>
  );
};
