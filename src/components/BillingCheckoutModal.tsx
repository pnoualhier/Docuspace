import React, { useState } from 'react';
import { 
  X, 
  CreditCard, 
  ShieldCheck, 
  CheckCircle2, 
  AlertTriangle, 
  HardDrive, 
  Lock, 
  Download, 
  FileText,
  Sparkles,
  ArrowRight,
  Loader2
} from 'lucide-react';
import { Plan, PlanType, Tenant, InvoiceItem } from '../types';
import { formatBytes } from '../services/crypto';
import { PLANS } from '../services/mockData';

interface BillingCheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetPlan: Plan | null;
  currentTenant: Tenant;
  invoices: InvoiceItem[];
  onConfirmUpgrade: (planId: PlanType, interval: 'monthly' | 'yearly') => void;
}

export const BillingCheckoutModal: React.FC<BillingCheckoutModalProps> = ({
  isOpen,
  onClose,
  targetPlan,
  currentTenant,
  invoices,
  onConfirmUpgrade,
}) => {
  const [activeTab, setActiveTab] = useState<'checkout' | 'invoices'>('checkout');
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [cardNumber, setCardNumber] = useState('4242 •••• •••• 4242');
  const [cardExpiry, setCardExpiry] = useState('12/28');
  const [cardCvc, setCardCvc] = useState('888');
  const [cardName, setCardName] = useState('Alice Dupont');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  if (!isOpen || !targetPlan) return null;

  const isDowngrade = targetPlan.maxStorageBytes < (PLANS[currentTenant.planId]?.maxStorageBytes || 0);
  const willExceedQuota = isDowngrade && (currentTenant.usedBytes > targetPlan.maxStorageBytes);

  const price = billingInterval === 'yearly' 
    ? (targetPlan.priceMonthly * 10).toFixed(2) // 2 mois offerts
    : targetPlan.priceMonthly.toFixed(2);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);

    // Simulate Stripe payment processing & webhook dispatch
    await new Promise(r => setTimeout(r, 900));

    setIsProcessing(false);
    setIsSuccess(true);

    setTimeout(() => {
      onConfirmUpgrade(targetPlan.id, billingInterval);
      setIsSuccess(false);
      onClose();
    }, 1200);
  };

  const handleDownloadInvoice = (inv: InvoiceItem) => {
    alert(`Téléchargement du reçu fiscal Stripe ${inv.number} (${inv.amountEur}€) au format PDF.`);
  };

  return (
    <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Souscription & Facturation Stripe</h3>
              <p className="text-[11px] text-slate-400">
                Paiement chiffré TLS 1.3 avec prélèvement automatisé et factures conformes.
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

        {/* Tab switch */}
        <div className="px-5 pt-3 pb-0 border-b border-slate-800 flex items-center space-x-4 text-xs font-medium">
          <button
            onClick={() => setActiveTab('checkout')}
            className={`pb-2.5 transition-colors border-b-2 ${
              activeTab === 'checkout'
                ? 'border-purple-500 text-white font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Passerelle de paiement
          </button>
          <button
            onClick={() => setActiveTab('invoices')}
            className={`pb-2.5 transition-colors border-b-2 ${
              activeTab === 'invoices'
                ? 'border-purple-500 text-white font-bold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Historique des factures ({invoices.length})
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {activeTab === 'checkout' ? (
            <>
              {/* Plan Recap Card */}
              <div className="p-4 rounded-xl bg-slate-950 border border-purple-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-white text-sm">{targetPlan.name}</span>
                    <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-semibold border border-purple-500/30">
                      {formatBytes(targetPlan.maxStorageBytes)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Jusqu'à {targetPlan.maxMembers} membre(s) • ClamAV • Rollback {targetPlan.maxVersionsPerFile} versions
                  </p>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-2xl font-extrabold text-white">
                    {targetPlan.priceMonthly === 0 ? '0€' : `${price}€`}
                    <span className="text-xs font-normal text-slate-400">
                      {targetPlan.priceMonthly > 0 ? (billingInterval === 'yearly' ? ' / an' : ' / mois') : ''}
                    </span>
                  </div>
                  {targetPlan.priceMonthly > 0 && billingInterval === 'yearly' && (
                    <span className="text-[10px] text-emerald-400 font-semibold">2 mois offerts inclus</span>
                  )}
                </div>
              </div>

              {/* Billing Interval Toggle (for paid plans) */}
              {targetPlan.priceMonthly > 0 && (
                <div className="flex items-center justify-center p-1 bg-slate-950 border border-slate-800 rounded-xl max-w-xs mx-auto text-xs">
                  <button
                    type="button"
                    onClick={() => setBillingInterval('monthly')}
                    className={`flex-1 py-1.5 rounded-lg font-medium transition-colors ${
                      billingInterval === 'monthly' ? 'bg-purple-600 text-white font-bold' : 'text-slate-400'
                    }`}
                  >
                    Facturation mensuelle
                  </button>
                  <button
                    type="button"
                    onClick={() => setBillingInterval('yearly')}
                    className={`flex-1 py-1.5 rounded-lg font-medium transition-colors ${
                      billingInterval === 'yearly' ? 'bg-purple-600 text-white font-bold' : 'text-slate-400'
                    }`}
                  >
                    Annuelle (-17%)
                  </button>
                </div>
              )}

              {/* Grace Period / Quota Warning on Downgrade */}
              {willExceedQuota && (
                <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3 text-xs text-amber-200 animate-in fade-in">
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <strong className="block text-amber-300 font-semibold">Avertissement de dépassement de quota (Période de grâce) :</strong>
                    <p className="text-[11px] leading-relaxed">
                      Votre consommation actuelle ({formatBytes(currentTenant.usedBytes)}) dépasse la limite du forfait sélectionné ({formatBytes(targetPlan.maxStorageBytes)}).
                      Si vous confirmez, votre espace sera placé en <strong>lecture seule stricte</strong> jusqu'à ce que vous libériez du stockage.
                    </p>
                  </div>
                </div>
              )}

              {/* Credit Card Form (Stripe Elements simulation) */}
              {targetPlan.priceMonthly > 0 ? (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">
                        Titulaire de la carte
                      </label>
                      <input
                        type="text"
                        required
                        value={cardName}
                        onChange={(e) => setCardName(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">
                        Numéro de carte bancaire
                      </label>
                      <div className="relative">
                        <input
                          type="text"
                          required
                          value={cardNumber}
                          onChange={(e) => setCardNumber(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-purple-500 pl-9"
                        />
                        <CreditCard className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-slate-300 mb-1">
                          Expiration (MM/AA)
                        </label>
                        <input
                          type="text"
                          required
                          value={cardExpiry}
                          onChange={(e) => setCardExpiry(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-purple-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-300 mb-1">
                          Cryptogramme (CVC)
                        </label>
                        <div className="relative">
                          <input
                            type="password"
                            required
                            maxLength={4}
                            value={cardCvc}
                            onChange={(e) => setCardCvc(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-purple-500 pl-8"
                          />
                          <Lock className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                    <div className="flex items-center space-x-1.5">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" />
                      <span>Chiffrement AES-256 Stripe & 3D Secure 2.0</span>
                    </div>
                    <span className="font-semibold text-slate-300">Total : {price}€ TTC</span>
                  </div>

                  <button
                    type="submit"
                    disabled={isProcessing || isSuccess}
                    className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-bold text-xs shadow-md transition-colors flex items-center justify-center space-x-2"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Validation du paiement auprès de Stripe...</span>
                      </>
                    ) : isSuccess ? (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-emerald-300" />
                        <span>Abonnement activé avec succès !</span>
                      </>
                    ) : (
                      <>
                        <span>Confirmer l'abonnement ({price}€)</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>
              ) : (
                <div className="space-y-4">
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Vous avez sélectionné l'offre <strong>Gratuite</strong>. Aucun moyen de paiement n'est requis.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      onConfirmUpgrade('FREE', 'monthly');
                      onClose();
                    }}
                    className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs transition-colors"
                  >
                    Basculer vers l'offre Gratuite
                  </button>
                </div>
              )}
            </>
          ) : (
            /* Invoices List */
            <div className="space-y-3">
              {invoices.length > 0 ? (
                invoices.map((inv) => (
                  <div
                    key={inv.id}
                    className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="p-2 rounded-lg bg-slate-900 text-purple-400">
                        <FileText className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="font-semibold text-white">{inv.number}</div>
                        <div className="text-[10px] text-slate-500">
                          {inv.planName} • {new Date(inv.date).toLocaleDateString('fr-FR')}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      <span className="font-mono font-bold text-slate-200">{inv.amountEur.toFixed(2)}€</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Payée
                      </span>
                      <button
                        onClick={() => handleDownloadInvoice(inv)}
                        className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                        title="Télécharger le reçu fiscal (PDF)"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-xs text-slate-400">
                  Aucune facture générée pour le moment.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
