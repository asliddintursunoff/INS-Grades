import React, { useState } from 'react';
import { Sparkles, Check, X, ArrowRight } from 'lucide-react';
import { useLanguage } from '../i18n';
import { PaymentModal } from './PaymentModal';

interface PremiumModalProps {
  isOpen: boolean;
  onClose: () => void;
  studentId: string;
  isPremium?: boolean;
  onPaymentSuccess?: () => void;
  onPremiumUpdated?: () => void;
  lockReason?: string | null;
}

export const PremiumModal: React.FC<PremiumModalProps> = ({
  isOpen,
  onClose,
  studentId,
  isPremium = false,
  onPaymentSuccess,
  onPremiumUpdated,
  lockReason,
}) => {
  const { t } = useLanguage();
  const [showPaymentModal, setShowPaymentModal] = useState(false);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div className="bg-white rounded-3xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in duration-150">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center font-bold">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">
                {t('premium_title')}
              </h3>
              <div className="text-xs text-slate-500 font-semibold">
                {isPremium ? (
                  <span className="text-emerald-600 font-bold">✓ {t('premium_active')}</span>
                ) : (
                  <>
                    <span className="text-slate-900 font-black">{t('premium_price')}</span>
                    <span> {t('premium_period')}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Optional Context Lock Message */}
        {lockReason && (
          <div className="bg-amber-50 border border-amber-200 text-amber-900 px-3.5 py-2.5 rounded-2xl text-xs font-semibold">
            {lockReason}
          </div>
        )}

        {/* 5 Persuasive Features */}
        <div className="space-y-2.5 py-1">
          <div className="flex items-start gap-2.5 text-xs text-slate-700 font-medium">
            <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3 h-3" />
            </div>
            <span>{t('premium_feat1')}</span>
          </div>

          <div className="flex items-start gap-2.5 text-xs text-slate-700 font-medium">
            <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3 h-3" />
            </div>
            <span>{t('premium_feat2')}</span>
          </div>

          <div className="flex items-start gap-2.5 text-xs text-slate-700 font-medium">
            <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3 h-3" />
            </div>
            <span>{t('premium_feat3')}</span>
          </div>

          <div className="flex items-start gap-2.5 text-xs text-slate-700 font-medium">
            <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3 h-3" />
            </div>
            <span>{t('premium_feat4')}</span>
          </div>

          <div className="flex items-start gap-2.5 text-xs text-slate-700 font-medium">
            <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
              <Check className="w-3 h-3" />
            </div>
            <span>{t('premium_feat5')}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="pt-2 space-y-2.5">
          {isPremium ? (
            <button
              onClick={() => setShowPaymentModal(true)}
              className="w-full py-2.5 px-4 rounded-2xl bg-amber-50 hover:bg-amber-100 border border-amber-300 text-amber-900 font-bold text-xs shadow-2xs flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
            >
              <span>{t('premium_extend_btn')}</span>
              <ArrowRight className="w-4 h-4 text-amber-700" />
            </button>
          ) : (
            <button
              onClick={() => setShowPaymentModal(true)}
              className="w-full py-3 px-4 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
            >
              <span>{t('premium_btn')}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}

          <div className="flex items-center justify-center text-xs pt-1">
            <button
              onClick={onClose}
              className="text-[11px] font-semibold text-slate-600 hover:text-slate-900 px-4 py-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            >
              {t('premium_close')}
            </button>
          </div>
        </div>
      </div>

      {/* Live Payment Modal */}
      <PaymentModal
        isOpen={showPaymentModal}
        onClose={() => {
          setShowPaymentModal(false);
          onClose();
        }}
        studentId={studentId}
        onPaymentSuccess={() => {
          if (onPaymentSuccess) onPaymentSuccess();
          if (onPremiumUpdated) onPremiumUpdated();
          onClose();
        }}
      />
    </div>
  );
};
