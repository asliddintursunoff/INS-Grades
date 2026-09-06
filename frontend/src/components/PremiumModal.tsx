import React, { useState } from 'react';
import { Sparkles, Check, X, Bell, Clock, RotateCcw, Zap, ArrowRight } from 'lucide-react';
import { apiCall } from '../api';

interface PremiumModalProps {
  isOpen: boolean;
  onClose: () => void;
  studentId: string;
  isPremium?: boolean;
  onPremiumUpdated?: () => void;
  lockReason?: string | null;
}

export const PremiumModal: React.FC<PremiumModalProps> = ({
  isOpen,
  onClose,
  studentId,
  isPremium = false,
  onPremiumUpdated,
  lockReason,
}) => {
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleToggleDemoPremium = async (activate: boolean) => {
    setLoading(true);
    setSuccessMsg(null);
    try {
      const res = await apiCall<{ success: boolean; message: string }>(
        `/api/students/${studentId}/premium/`,
        'POST',
        {
          action: activate ? 'activate' : 'deactivate',
          duration_days: 30,
        }
      );
      setSuccessMsg(res.message);
      if (onPremiumUpdated) onPremiumUpdated();
      setTimeout(() => {
        setSuccessMsg(null);
        onClose();
      }, 1400);
    } catch (err: any) {
      console.error('Failed to update premium:', err);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: <Clock className="w-4 h-4 text-amber-500" />,
      title: "Dars vaqtlarini o'zgartirish (Schedule Customization)",
      desc: "Boshqa guruh bilan 1-martalik make-up darslarga kirish yoki dars vaqtini doimiy almashtirish.",
    },
    {
      icon: <RotateCcw className="w-4 h-4 text-blue-500" />,
      title: "Retake va Drop fankurslar",
      desc: "Qayta o'qish (retake) kurslarini qo'shish yoki ortiqcha fanlarni bekor qilish (drop).",
    },
    {
      icon: <Bell className="w-4 h-4 text-emerald-500" />,
      title: "Avtomatik Telegram eslatmalari",
      desc: "Har bir dars boshlanishidan 5, 10, 15 yoki 30 daqiqa oldin shaxsiy botdan eslatma xabarnomalari.",
    },
    {
      icon: <Zap className="w-4 h-4 text-indigo-500" />,
      title: "To'liq moslashuvchanlik",
      desc: "Shaxsiy o'quv rejangizni o'zingizga qulay qilib shakllantiring.",
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/70 backdrop-blur-xs">
      <div className="bg-white rounded-3xl max-w-md w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh] animate-in fade-in zoom-in duration-150">
        {/* Modal Header with Glow */}
        <div className="relative bg-gradient-to-br from-blue-700 via-indigo-700 to-amber-600 text-white p-6 pb-7 text-center overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-amber-400/20 rounded-full blur-2xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-32 h-32 bg-blue-400/20 rounded-full blur-2xl pointer-events-none" />

          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-full bg-white/15 hover:bg-white/25 text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>

          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-white/15 border border-white/25 mb-3 shadow-inner">
            <Sparkles className="w-6 h-6 text-amber-300" />
          </div>

          <h3 className="text-xl font-black tracking-tight leading-none text-white">
            INS Grades Premium
          </h3>

          <p className="text-xs text-blue-100/90 mt-1.5 max-w-xs mx-auto">
            Dars jadvalingizni o'zingizga to'liq moslang va eslatmalarni yoqing
          </p>

          {/* Pricing Pill */}
          <div className="mt-4 inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white/20 backdrop-blur-sm border border-white/30 text-white font-extrabold text-sm shadow-xs">
            <span className="text-amber-300 font-black">10 000 so'm</span>
            <span className="text-xs text-white/80 font-normal">/ oyiga</span>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-3.5 flex-1 text-xs">
          {/* Lock Reason Warning Banner */}
          {lockReason && (
            <div className="bg-amber-50 border border-amber-200 text-amber-900 p-3 rounded-2xl flex items-start gap-2.5 font-medium leading-relaxed">
              <span className="text-base shrink-0">🔒</span>
              <div>
                <strong className="block font-bold text-amber-950">Bu faqat Premium foydalanuvchilar uchun!</strong>
                <p className="text-[11px] text-amber-800 mt-0.5">{lockReason}</p>
              </div>
            </div>
          )}

          {successMsg && (
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-3 rounded-2xl flex items-center gap-2 font-semibold">
              <Check className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Feature list */}
          <div className="space-y-2.5">
            <span className="font-bold text-slate-800 uppercase tracking-wider text-[10px] block px-1">
              Premium tarifiga kiritilgan imkoniyatlar:
            </span>

            {features.map((f, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 p-3 rounded-2xl bg-slate-50 border border-slate-100/80 transition-all hover:border-slate-200"
              >
                <div className="w-7 h-7 rounded-xl bg-white border border-slate-200/80 flex items-center justify-center shrink-0 shadow-2xs mt-0.5">
                  {f.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-bold text-slate-900 leading-tight">
                    {f.title}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5 leading-normal">
                    {f.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Free vs Premium compare note */}
          <div className="p-3 bg-blue-50/50 rounded-2xl border border-blue-100 text-[11px] text-slate-600 space-y-1">
            <p>
              • <strong>Bepul (Free) versiyada:</strong> Telegram botda to'liq dars jadvali va bugungi darslarni ko'rish doimo tekin.
            </p>
            <p>
              • <strong>Premium versiyada:</strong> Dars vaqtlarini o'zgartirish, retake fanlar va Telegram avtomatik eslatmalari faollashadi.
            </p>
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/70 space-y-2">
          {/* Telegram Contact / Order */}
          <a
            href="https://t.me/asliddin_tursunoff"
            target="_blank"
            rel="noreferrer"
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-amber-600 hover:from-blue-700 hover:to-amber-700 text-white font-bold text-xs shadow-sm flex items-center justify-center gap-2 transition-all active:scale-[0.99]"
          >
            <Sparkles className="w-4 h-4 text-amber-300" />
            <span>Premium olish (10 000 so'm/oy)</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </a>

          {/* Instant Test Activation Toggle (For testing & demo convenience) */}
          <div className="flex items-center justify-between gap-2 pt-1">
            <button
              onClick={() => handleToggleDemoPremium(!isPremium)}
              disabled={loading}
              className="text-[11px] font-semibold text-blue-600 hover:text-blue-700 underline px-1 py-1"
            >
              {loading
                ? 'Yuklanmoqda...'
                : isPremium
                ? "Test: Free tarifga qaytarish"
                : "⚡ Test / Sinov uchun faollashtirish"}
            </button>

            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-200/60 transition-colors"
            >
              Davom etish
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
