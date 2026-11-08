import React from 'react';
import { 
  HardDrive, 
  FileText, 
  Image as ImageIcon, 
  FileSpreadsheet, 
  FileArchive, 
  FileCode, 
  CheckCircle2, 
  ShieldCheck, 
  Zap, 
  Sparkles 
} from 'lucide-react';
import { Tenant, Plan, DocumentItem, PlanType } from '../types';
import { formatBytes, getFileCategory } from '../services/crypto';
import { PLANS } from '../services/mockData';

interface StorageGaugeProps {
  currentTenant: Tenant;
  currentPlan: Plan;
  documents: DocumentItem[];
  onUpgradePlan: (planId: PlanType) => void;
}

export const StorageGauge: React.FC<StorageGaugeProps> = ({
  currentTenant,
  currentPlan,
  documents,
  onUpgradePlan,
}) => {
  const usedBytes = currentTenant.usedBytes || 0;
  const maxBytes = currentPlan.maxStorageBytes;
  const percentUsed = Math.min(100, Math.round((usedBytes / maxBytes) * 100));

  // Compute breakdown by category
  const breakdown = {
    pdf: 0,
    image: 0,
    word: 0,
    excel: 0,
    archive: 0,
    other: 0,
  };

  documents.forEach((doc) => {
    const cat = getFileCategory(doc.mimeType, doc.extension);
    if (cat in breakdown) {
      breakdown[cat as keyof typeof breakdown] += doc.sizeBytes;
    } else {
      breakdown.other += doc.sizeBytes;
    }
  });

  const categories = [
    { key: 'pdf', label: 'Documents PDF', bytes: breakdown.pdf, color: 'bg-rose-500', text: 'text-rose-400', icon: FileText },
    { key: 'image', label: 'Images & Photos', bytes: breakdown.image, color: 'bg-sky-500', text: 'text-sky-400', icon: ImageIcon },
    { key: 'word', label: 'Fichiers Word & Bureautique', bytes: breakdown.word, color: 'bg-blue-500', text: 'text-blue-400', icon: FileText },
    { key: 'excel', label: 'Tableurs & CSV', bytes: breakdown.excel, color: 'bg-emerald-500', text: 'text-emerald-400', icon: FileSpreadsheet },
    { key: 'archive', label: 'Archives ZIP & Sauvegardes', bytes: breakdown.archive, color: 'bg-amber-500', text: 'text-amber-400', icon: FileArchive },
    { key: 'other', label: 'Code & Fichiers divers', bytes: breakdown.other, color: 'bg-purple-500', text: 'text-purple-400', icon: FileCode },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 max-w-5xl mx-auto">
      {/* Top Header Card */}
      <div className="rounded-3xl p-8 bg-gradient-to-br from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 space-y-6 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-[11px] font-bold text-blue-400 uppercase tracking-wider flex items-center space-x-1.5">
              <HardDrive className="w-3.5 h-3.5" />
              <span>Gestion des Quotas Transactionnels</span>
            </span>
            <h2 className="text-xl font-extrabold text-white">
              Espace de stockage — {currentTenant.name}
            </h2>
            <p className="text-xs text-slate-400">
              Forfait actif : <span className="text-white font-semibold">{currentPlan.name}</span> • Limite max : {formatBytes(maxBytes)}
            </p>
          </div>

          <div className="text-right sm:text-right">
            <div className="text-2xl font-black text-white font-mono">
              {formatBytes(usedBytes)}
            </div>
            <div className="text-xs text-slate-400 font-medium">
              sur {formatBytes(maxBytes)} alloués ({percentUsed}% utilisé)
            </div>
          </div>
        </div>

        {/* Global Progress Bar with Category Stacks */}
        <div className="space-y-2">
          <div className="w-full h-3.5 bg-slate-800 rounded-full overflow-hidden flex p-0.5">
            {categories.map((cat) => {
              const catPercent = maxBytes > 0 ? (cat.bytes / maxBytes) * 100 : 0;
              if (catPercent <= 0) return null;
              return (
                <div
                  key={cat.key}
                  className={`h-full first:rounded-l-full last:rounded-r-full transition-all duration-500 ${cat.color}`}
                  style={{ width: `${Math.max(1, catPercent)}%` }}
                  title={`${cat.label}: ${formatBytes(cat.bytes)}`}
                />
              );
            })}
          </div>

          <div className="flex justify-between text-[11px] text-slate-500 font-mono">
            <span>0 o</span>
            <span>Disponible : {formatBytes(Math.max(0, maxBytes - usedBytes))}</span>
            <span>{formatBytes(maxBytes)}</span>
          </div>
        </div>

        {/* Category Breakdown Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 border-t border-slate-800/80">
          {categories.map((cat) => {
            const Icon = cat.icon;
            return (
              <div
                key={cat.key}
                className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800/80 flex items-center space-x-3"
              >
                <div className={`p-2 rounded-xl bg-slate-900 ${cat.text}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="truncate">
                  <div className="text-[11px] text-slate-400 truncate">{cat.label}</div>
                  <div className="text-xs font-bold text-white font-mono mt-0.5">
                    {formatBytes(cat.bytes)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Subscription Plans Comparison */}
      <div className="space-y-4">
        <div>
          <h3 className="text-base font-bold text-white">Forfaits & Évolution de Stockage</h3>
          <p className="text-xs text-slate-400">
            Passez à un forfait supérieur pour augmenter instantanément votre quota et vos versions de documents.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {(Object.keys(PLANS) as PlanType[]).map((planKey) => {
            const plan = PLANS[planKey];
            const isCurrent = currentPlan.id === planKey;

            return (
              <div
                key={planKey}
                className={`rounded-3xl p-6 border transition-all flex flex-col justify-between space-y-6 ${
                  isCurrent
                    ? 'bg-blue-950/20 border-blue-500/50 ring-1 ring-blue-500/40 shadow-lg shadow-blue-500/10'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-base text-white">{plan.name}</span>
                    {isCurrent && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                        Actuel
                      </span>
                    )}
                  </div>

                  <div className="flex items-baseline space-x-1">
                    <span className="text-3xl font-extrabold text-white">
                      {plan.priceMonthly === 0 ? 'Gratuit' : `${plan.priceMonthly}€`}
                    </span>
                    {plan.priceMonthly > 0 && <span className="text-xs text-slate-400">/mois</span>}
                  </div>

                  <p className="text-xs text-blue-400 font-semibold font-mono">
                    {formatBytes(plan.maxStorageBytes)} de stockage cloud chiffré
                  </p>

                  <div className="space-y-2 pt-2 border-t border-slate-800 text-xs">
                    {plan.features.map((feat, idx) => (
                      <div key={idx} className="flex items-start space-x-2 text-slate-300">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                        <span className="text-[11px] leading-tight">{feat}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <button
                    disabled={isCurrent}
                    onClick={() => onUpgradePlan(planKey)}
                    className={`w-full py-2.5 px-4 rounded-xl font-semibold text-xs transition-all ${
                      isCurrent
                        ? 'bg-slate-800 text-slate-400 cursor-default'
                        : 'bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20'
                    }`}
                  >
                    {isCurrent ? 'Forfait actif' : 'Choisir ce forfait'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
