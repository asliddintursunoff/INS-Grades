import React, { useState, useEffect } from 'react';
import { Users, AlertCircle, CheckCircle2, Clock, MapPin, User, ArrowRight, ShieldAlert } from 'lucide-react';
import { StudentClass, AvailableGroupOption } from '../types';
import { apiCall } from '../api';

interface GroupSwitchTabProps {
  studentId: string;
  classes: StudentClass[];
  preselectedSubjectId?: number | null;
  onSuccess: () => void;
}

export const GroupSwitchTab: React.FC<GroupSwitchTabProps> = ({
  studentId,
  classes,
  preselectedSubjectId,
  onSuccess,
}) => {
  const activeClasses = classes.filter((c) => c.status === 'active');
  const [selectedSubjectId, setSelectedSubjectId] = useState<number | null>(
    preselectedSubjectId || (activeClasses[0] ? activeClasses[0].subject_id : null)
  );
  const [options, setOptions] = useState<AvailableGroupOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [switchingId, setSwitchingId] = useState<number | null>(null);
  const [notification, setNotification] = useState<string | null>(null);

  useEffect(() => {
    if (preselectedSubjectId) {
      setSelectedSubjectId(preselectedSubjectId);
    }
  }, [preselectedSubjectId]);

  useEffect(() => {
    if (!selectedSubjectId) return;

    let isMounted = true;
    setLoading(true);

    apiCall<{ options: AvailableGroupOption[] }>(
      `/api/subjects/${selectedSubjectId}/available-groups/?student_telegram_id=${studentId}`
    )
      .then((res) => {
        if (isMounted) setOptions(res.options || []);
      })
      .catch((err) => {
        console.error('Error fetching available groups:', err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedSubjectId, studentId]);

  const handleSwitchGroup = async (newOption: AvailableGroupOption) => {
    const currentClass = classes.find((c) => c.subject_id === selectedSubjectId);
    if (!currentClass) return;

    if (
      !confirm(
        `Darsni "${newOption.group_name}" guruhiga (${newOption.day_name} ${newOption.start_time}-${newOption.end_time}, Prof. ${newOption.professor}) almashtirishni tasdiqlaysizmi?`
      )
    ) {
      return;
    }

    setSwitchingId(newOption.class_id);
    try {
      const res = await apiCall(`/api/students/${studentId}/change-group/`, 'POST', {
        old_class_id: currentClass.class_id,
        new_class_id: newOption.class_id,
      });

      setNotification(`Guruh muvaffaqiyatli almashtirildi! Dars jadvalingiz yangilandi.`);
      onSuccess();
      // Re-fetch options to recalculate conflicts
      const refreshed = await apiCall<{ options: AvailableGroupOption[] }>(
        `/api/subjects/${selectedSubjectId}/available-groups/?student_telegram_id=${studentId}`
      );
      setOptions(refreshed.options || []);
    } catch (err: any) {
      alert(`Xatolik: ${err.message}`);
    } finally {
      setSwitchingId(null);
    }
  };

  const currentSelectedClass = classes.find((c) => c.subject_id === selectedSubjectId);

  return (
    <div className="space-y-4">
      {/* Intro info */}
      <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
        <h2 className="text-sm font-semibold text-white mb-1 flex items-center gap-2">
          <Users className="w-4 h-4 text-sky-400" />
          Darsni boshqa guruhdan olish (Group Override)
        </h2>
        <p className="text-xs text-slate-300 leading-relaxed">
          Siz o&apos;zingizga qulay bo&apos;lgan guruh darsini tanlashingiz mumkin. Tizim sizning shaxsiy jadvalingiz bilan to&apos;qnashuvlarni (time conflict) avtomatik aniqlaydi.
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

      {/* Subject selection tabs */}
      <div>
        <label className="block text-xs font-semibold text-slate-300 mb-2">
          Fanni tanlang:
        </label>
        <div className="flex flex-wrap gap-2">
          {activeClasses.map((c) => (
            <button
              key={c.subject_id}
              onClick={() => setSelectedSubjectId(c.subject_id)}
              className={`px-3 py-2 rounded-xl text-xs font-medium border transition-all flex items-center gap-2 ${
                selectedSubjectId === c.subject_id
                  ? 'bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-500/20'
                  : 'bg-slate-800/70 text-slate-300 border-slate-700 hover:bg-slate-800'
              }`}
            >
              <span className="font-bold opacity-80">{c.subject_short}</span>
              <span>{c.subject_full}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Options List */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>
            {currentSelectedClass ? `${currentSelectedClass.subject_full} bo'yicha guruh variantlari:` : 'Guruh variantlari:'}
          </span>
          {loading && <span className="text-sky-400 animate-pulse">Yuklanmoqda...</span>}
        </div>

        {options.length === 0 && !loading && (
          <div className="text-center py-8 text-xs text-slate-400 bg-slate-800/30 rounded-xl border border-slate-800">
            Boshqa guruhlar mavjud emas.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {options.map((opt) => {
            const isSwitching = switchingId === opt.class_id;

            return (
              <div
                key={opt.class_id}
                className={`rounded-xl border p-4 transition-all flex flex-col justify-between ${
                  opt.is_available
                    ? 'bg-slate-800/80 border-slate-700/80 hover:border-slate-600'
                    : 'bg-slate-900/40 border-slate-800/80 opacity-75'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-white">{opt.group_name}</span>
                      {opt.is_own_group && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                          Sizning guruhingiz
                        </span>
                      )}
                    </div>

                    {opt.is_available ? (
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        To&apos;qnashuv yo&apos;q
                      </span>
                    ) : (
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30 flex items-center gap-1">
                        <ShieldAlert className="w-3 h-3 shrink-0" />
                        Vaqti to&apos;g&apos;ri kelmaydi
                      </span>
                    )}
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-300 mb-3">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>{opt.day_name}: <strong className="text-white">{opt.start_time} - {opt.end_time}</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span>Professor: <strong className="text-white">{opt.professor}</strong></span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" />
                      <span>Xona: <strong className="text-white">{opt.room}</strong></span>
                    </div>
                  </div>

                  {!opt.is_available && opt.conflict_reason && (
                    <div className="text-[11px] text-rose-300/90 bg-rose-500/10 border border-rose-500/20 rounded-lg px-2.5 py-1.5 mb-3 flex items-start gap-1.5">
                      <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0 mt-0.5" />
                      <span>{opt.conflict_reason}</span>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-slate-700/50 flex justify-end">
                  {opt.is_available ? (
                    <button
                      disabled={isSwitching}
                      onClick={() => handleSwitchGroup(opt)}
                      className="w-full sm:w-auto flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-colors disabled:opacity-50 shadow-sm"
                    >
                      <span>{isSwitching ? 'Almashtirilmoqda...' : 'Ushbu guruhga o\'tish'}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  ) : (
                    <button
                      disabled
                      className="w-full sm:w-auto px-4 py-2 rounded-lg bg-slate-800 text-slate-500 text-xs font-semibold cursor-not-allowed border border-slate-700/50"
                    >
                      Tanlab bo&apos;lmaydi (to&apos;qnashuv)
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
