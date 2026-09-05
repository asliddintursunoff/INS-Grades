import React, { useState, useEffect, useCallback } from 'react';
import { CalendarX, Sparkles, CheckCircle2, Clock, User, MapPin, Award, ArrowRight, X } from 'lucide-react';
import { AbsenceItem, MakeupOption } from '../types';
import { apiCall } from '../api';

interface AbsencesTabProps {
  studentId: string;
  onSuccess: () => void;
}

export const AbsencesTab: React.FC<AbsencesTabProps> = ({ studentId, onSuccess }) => {
  const [absences, setAbsences] = useState<AbsenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAbsence, setSelectedAbsence] = useState<AbsenceItem | null>(null);
  const [makeupOptions, setMakeupOptions] = useState<MakeupOption[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [notification, setNotification] = useState<string | null>(null);

  const fetchAbsences = useCallback(() => {
    setLoading(true);
    apiCall<{ absences: AbsenceItem[] }>(`/api/students/${studentId}/absences/`)
      .then((res) => setAbsences(res.absences || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [studentId]);

  useEffect(() => {
    fetchAbsences();
  }, [fetchAbsences]);

  const handleOpenMakeupModal = async (abs: AbsenceItem) => {
    setSelectedAbsence(abs);
    setLoadingOptions(true);
    try {
      const res = await apiCall<{ options: MakeupOption[] }>(
        `/api/attendance/${abs.session_id}/makeup-options/?student_telegram_id=${studentId}`
      );
      setMakeupOptions(res.options || []);
    } catch (err: any) {
      alert(`Xatolik: ${err.message}`);
    } finally {
      setLoadingOptions(false);
    }
  };

  const handleConfirmMakeup = async (opt: MakeupOption) => {
    if (!selectedAbsence) return;

    if (
      !confirm(
        `"${selectedAbsence.subject_full}" fanidan o'tkazib yuborilgan darsni ${opt.session_date} sanasidagi "${opt.group_name}" guruhida (${opt.start_time}-${opt.end_time}) to'ldirishni tasdiqlaysizmi?`
      )
    ) {
      return;
    }

    setConfirmingId(opt.session_id);
    try {
      const res = await apiCall(`/api/attendance/${selectedAbsence.session_id}/makeup/`, 'POST', {
        student_telegram_id: studentId,
        makeup_session_id: opt.session_id,
      });

      setNotification(`${res.message}! Davomat holati yangilandi.`);
      setSelectedAbsence(null);
      fetchAbsences();
      onSuccess();
    } catch (err: any) {
      alert(`Xatolik: ${err.message}`);
    } finally {
      setConfirmingId(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Intro info */}
      <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
        <h2 className="text-sm font-semibold text-white mb-1 flex items-center gap-2">
          <CalendarX className="w-4 h-4 text-amber-400" />
          Qoldirilgan darslar va Makeup (O&apos;rnini to&apos;ldirish)
        </h2>
        <p className="text-xs text-slate-300 leading-relaxed">
          Agar siz darsga kira olmagan bo&apos;lsangiz, tizim o&apos;sha professorning boshqa guruhdagi darslarini va jadvalingizga to&apos;g&apos;ri keluvchi eng maqul variantlarni avtomatik tavsiya qiladi.
        </p>
      </div>

      {notification && (
        <div className="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{notification}</span>
          </div>
          <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-white font-bold">
            ✕
          </button>
        </div>
      )}

      {/* Absences list */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>O&apos;tkazib yuborilgan darslar:</span>
          <span>{absences.length} ta dars</span>
        </div>

        {absences.length === 0 && !loading && (
          <div className="text-center py-10 bg-slate-800/30 rounded-xl border border-slate-800 p-6">
            <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2 opacity-90" />
            <h3 className="text-sm font-semibold text-white">Ajoyib natija!</h3>
            <p className="text-xs text-slate-400 mt-1">
              Sizda qoldirilgan yoki to&apos;ldirilishi kerak bo&apos;lgan darslar yo&apos;q.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {absences.map((abs) => (
            <div
              key={abs.session_id}
              className="bg-slate-800/80 border border-slate-700/80 hover:border-slate-600 rounded-xl p-4 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {abs.subject_short}
                    </span>
                    <h3 className="text-sm font-semibold text-white">{abs.subject_full}</h3>
                  </div>

                  <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30">
                    Kelmagan (Absent)
                  </span>
                </div>

                <div className="space-y-1.5 text-xs text-slate-300 mb-4 mt-2">
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>Sana &amp; Vaqt: <strong className="text-white">{abs.session_date}, {abs.start_time} - {abs.end_time}</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    <span>Professor: <strong className="text-white">{abs.professor}</strong></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    <span>Xona: <strong className="text-white">{abs.room}</strong></span>
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-700/50 flex justify-end">
                <button
                  onClick={() => handleOpenMakeupModal(abs)}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-colors shadow-sm"
                >
                  <Sparkles className="w-3.5 h-3.5 text-slate-950" />
                  <span>Buni to&apos;ldirish (Makeup)</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Makeup Modal */}
      {selectedAbsence && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-900 z-10">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-400" />
                <div>
                  <h3 className="text-sm font-bold text-white leading-tight">
                    Makeup variantlari: {selectedAbsence.subject_full}
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    O&apos;tkazib yuborilgan dars: {selectedAbsence.session_date} ({selectedAbsence.start_time})
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedAbsence(null)}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 space-y-3">
              {loadingOptions && (
                <div className="text-center py-8 text-xs text-sky-400 animate-pulse">
                  Eng mos darslar hisoblanmoqda...
                </div>
              )}

              {!loadingOptions && makeupOptions.length === 0 && (
                <div className="text-center py-8 text-xs text-slate-400 bg-slate-800/40 rounded-xl border border-slate-800">
                  Ushbu fan bo&apos;yicha to&apos;qnashuvsiz yaqin kunlarda dars topilmadi.
                </div>
              )}

              {!loadingOptions &&
                makeupOptions.map((opt) => {
                  const isConfirming = confirmingId === opt.session_id;

                  return (
                    <div
                      key={opt.session_id}
                      className={`rounded-xl border p-3.5 transition-all ${
                        opt.recommended
                          ? 'bg-amber-500/10 border-amber-500/40 ring-1 ring-amber-500/20'
                          : 'bg-slate-800/80 border-slate-700/80'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-700 text-white">
                            {opt.group_name}
                          </span>
                          {opt.recommended && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500 text-slate-950 flex items-center gap-1 shadow-xs">
                              <Award className="w-3 h-3" />
                              ⭐ Eng maqul variant
                            </span>
                          )}
                        </div>

                        {opt.same_professor ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300 border border-blue-500/30">
                            Bir xil professor
                          </span>
                        ) : (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
                            Boshqa professor
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs text-slate-300 mb-3">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          <span>{opt.session_date} ({opt.start_time}-{opt.end_time})</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-slate-400" />
                          <span>{opt.professor}</span>
                        </div>
                        <div className="flex items-center gap-1.5 col-span-2">
                          <MapPin className="w-3.5 h-3.5 text-slate-400" />
                          <span>Xona: <strong className="text-white">{opt.room}</strong></span>
                        </div>
                      </div>

                      <div className="pt-2 border-t border-slate-700/50 flex justify-end">
                        <button
                          disabled={isConfirming}
                          onClick={() => handleConfirmMakeup(opt)}
                          className={`w-full sm:w-auto flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-colors disabled:opacity-50 ${
                            opt.recommended
                              ? 'bg-amber-500 hover:bg-amber-400 text-slate-950'
                              : 'bg-blue-600 hover:bg-blue-500 text-white'
                          }`}
                        >
                          <span>{isConfirming ? 'Tasdiqlanmoqda...' : 'Tanlash va to\'ldirish'}</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
