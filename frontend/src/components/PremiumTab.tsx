import React, { useState } from 'react';
import { Sparkles, Check, Clock, RotateCcw, Bell, Zap, ArrowRight, ShieldCheck, Star } from 'lucide-react';
import { Student } from '../types';
import { apiCall } from '../api';

interface PremiumTabProps {
  student: Student;
  onPremiumUpdated?: () => void;
}

export const PremiumTab: React.FC<PremiumTabProps> = ({ student, onPremiumUpdated }) => {
  const isPremium = student.is_premium || student.plan === 'premium';
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleToggleDemo = async (activate: boolean) => {
    setLoading(true);
    setMessage(null);
    try {
      const res = await apiCall<{ success: boolean; message: string }>(
        `/api/students/${student.student_id}/premium/`,
        'POST',
        {
          action: activate ? 'activate' : 'deactivate',
          duration_days: 30,
        }
      );
      setMessage(res.message);
      if (onPremiumUpdated) onPremiumUpdated();
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: <Clock className="w-5 h-5 text-amber-600" />,
      badge: "Dars Jadvali",
      title: "Dars vaqtlarini o'zingizga moslab o'zgartirish",
      desc: "Agar biror darsni o'tkazib yuborsangiz, shu haftaning o'zida boshqa guruh darsiga 1-martalik make-up sifatida qatnashing yoki dars vaqtingizni butun semestrga doimiy almashtiring.",
    },
    {
      icon: <RotateCcw className="w-5 h-5 text-blue-600" />,
      badge: "Fanlar",
      title: "Retake va Drop kurslarni erkin boshqarish",
      desc: "Oldingi yillardagi fanni qayta o'qish (Retake) uchun katalogdan tanlab qo'shing yoki kerak bo'lmagan fanlarni jadvaldan olib tashlang (Drop).",
    },
    {
      icon: <Bell className="w-5 h-5 text-emerald-600" />,
      badge: "Eslatmalar",
      title: "Avtomatik Telegram eslatmalari",
      desc: "Darsingiz boshlanishidan 5, 10, 15, 30 daqiqa oldin Telegram bot xonasi, o'qituvchisi va vaqti bilan to'liq eslatma xabarini yetkazadi.",
    },
    {
      icon: <Zap className="w-5 h-5 text-indigo-600" />,
      badge: "Aniq Sinxronizatsiya",
      title: "Toshkent vaqti bilan daqiqama-daqiqa aniqlik",
      desc: "Barcha darslar, xonalar va dars jadvallari Toshkent vaqti bo'yicha to'liq sinxron holatda ishlaydi.",
    },
  ];

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* Hero Card */}
      <div className="relative rounded-3xl bg-gradient-to-br from-blue-700 via-indigo-700 to-amber-600 p-6 sm:p-8 text-white shadow-md overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-amber-400/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 space-y-4 text-center sm:text-left">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/15 border border-white/25 text-amber-300 font-extrabold text-xs mx-auto sm:mx-0">
              <Sparkles className="w-4 h-4" />
              <span>INS GRADES PREMIUM</span>
            </div>

            {isPremium ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/30 border border-emerald-300 text-emerald-200 text-xs font-bold mx-auto sm:mx-0">
                <Check className="w-3.5 h-3.5" />
                <span>Faol Obuna</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/20 text-white text-xs font-semibold mx-auto sm:mx-0">
                <span>Free Plan</span>
              </span>
            )}
          </div>

          <div>
            <h2 className="text-2xl sm:text-3xl font-black tracking-tight text-white leading-tight">
              O'qishingizni yanada qulay va oson qiling
            </h2>
            <p className="text-xs sm:text-sm text-blue-100/90 mt-2 leading-relaxed max-w-lg">
              Dars vaqtlarini o'zingiz xohlagandek tanlang, retake fanlarni oling va dars boshlanishidan oldin Telegram eslatmalariga ega bo'ling.
            </p>
          </div>

          {/* Pricing Highlight Box */}
          <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-white/15">
            <div>
              <span className="text-[11px] text-blue-200 uppercase font-bold tracking-wider block">
                Tarif narxi
              </span>
              <div className="flex items-baseline gap-1.5 mt-0.5">
                <span className="text-2xl sm:text-3xl font-black text-amber-300">
                  10 000 so'm
                </span>
                <span className="text-xs text-blue-200 font-medium">/ oyiga</span>
              </div>
            </div>

            <a
              href="https://t.me/asliddin_tursunoff"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-2xl bg-white text-blue-900 font-extrabold text-xs shadow-lg hover:bg-amber-50 hover:text-blue-950 transition-all active:scale-[0.98]"
            >
              <Star className="w-4 h-4 text-amber-500 fill-amber-400" />
              <span>{isPremium ? "Obunani uzaytirish" : "Premium olish"}</span>
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      </div>

      {message && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-3.5 rounded-2xl text-xs font-semibold flex items-center gap-2 shadow-2xs">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {/* Feature cards */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider px-1">
          Premium imkoniyatlari:
        </h3>

        <div className="grid grid-cols-1 gap-3">
          {features.map((f, idx) => (
            <div
              key={idx}
              className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 flex items-start gap-3.5 shadow-2xs transition-all hover:border-slate-300"
            >
              <div className="w-10 h-10 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-center shrink-0 shadow-2xs">
                {f.icon}
              </div>
              <div className="space-y-1 min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                    {f.badge}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900">
                    {f.title}
                  </h4>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {f.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Free vs Premium comparison table */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-2xs space-y-3">
        <h3 className="text-sm font-bold text-slate-900">
          Tariflar taqqoslovi:
        </h3>

        <div className="overflow-hidden rounded-xl border border-slate-200 text-xs">
          <table className="w-full text-left">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 text-[11px]">
              <tr>
                <th className="p-3">Xizmat turi</th>
                <th className="p-3 text-center w-24">Free</th>
                <th className="p-3 text-center w-28 bg-amber-50/50 text-amber-950 font-bold">Premium</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr>
                <td className="p-3 text-slate-700 font-medium">Telegram botda to'liq dars jadvalini ko'rish</td>
                <td className="p-3 text-center text-emerald-600 font-bold">✓ Tekin</td>
                <td className="p-3 text-center text-emerald-600 font-bold bg-amber-50/30">✓ Mavjud</td>
              </tr>
              <tr>
                <td className="p-3 text-slate-700 font-medium">Bugungi darslarni ko'rish</td>
                <td className="p-3 text-center text-emerald-600 font-bold">✓ Tekin</td>
                <td className="p-3 text-center text-emerald-600 font-bold bg-amber-50/30">✓ Mavjud</td>
              </tr>
              <tr>
                <td className="p-3 text-slate-700 font-medium">Dars vaqtlarini o'zgartirish (Make-up va Doimiy)</td>
                <td className="p-3 text-center text-slate-400">✕</td>
                <td className="p-3 text-center text-emerald-600 font-bold bg-amber-50/30">✓ Mavjud</td>
              </tr>
              <tr>
                <td className="p-3 text-slate-700 font-medium">Retake va Drop fankurslar</td>
                <td className="p-3 text-center text-slate-400">✕</td>
                <td className="p-3 text-center text-emerald-600 font-bold bg-amber-50/30">✓ Mavjud</td>
              </tr>
              <tr>
                <td className="p-3 text-slate-700 font-medium">Avtomatik Telegram dars eslatmalari</td>
                <td className="p-3 text-center text-slate-400">✕</td>
                <td className="p-3 text-center text-emerald-600 font-bold bg-amber-50/30">✓ Mavjud</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Demo Tester Actions */}
      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <span className="font-bold text-slate-800 block">
            Sinov rejimi (Demo Switcher):
          </span>
          <span className="text-[11px] text-slate-500">
            Hozirgi holat: <strong>{isPremium ? 'PREMIUM (Faol)' : 'FREE (Tekin)'}</strong>
          </span>
        </div>

        <button
          onClick={() => handleToggleDemo(!isPremium)}
          disabled={loading}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-2xs ${
            isPremium
              ? 'bg-slate-200 hover:bg-slate-300 text-slate-700'
              : 'bg-gradient-to-r from-blue-600 to-amber-600 text-white hover:opacity-95'
          }`}
        >
          {loading
            ? 'Yangilanmoqda...'
            : isPremium
            ? 'Free tarifga o\'tish (Test)'
            : '⚡ Premium faollashtirish (Test)'}
        </button>
      </div>
    </div>
  );
};
