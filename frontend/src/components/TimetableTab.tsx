import React, { useState, useEffect, useCallback } from 'react';
import { 
  Calendar as CalendarIcon, 
  Clock, 
  MapPin, 
  User, 
  RefreshCw, 
  Sparkles, 
  Check, 
  AlertCircle, 
  X, 
  Layers, 
  RotateCcw,
  AlertTriangle,
  ArrowRight,
  HelpCircle
} from 'lucide-react';
import { TimetableResponse, ScheduleSlot, AvailableGroupOption } from '../types';
import { apiCall } from '../api';
import { useLanguage } from '../i18n';

interface TimetableTabProps {
  studentId: string;
  onRefreshTrigger?: () => void;
  isPremium?: boolean;
  onRequirePremium?: (featureName: string) => void;
}

export const TimetableTab: React.FC<TimetableTabProps> = ({
  studentId,
  onRefreshTrigger,
  isPremium,
  onRequirePremium,
}) => {
  const { t } = useLanguage();
  const [data, setData] = useState<TimetableResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<number | null>(null); // null = all days

  const studentHasPremium = isPremium ?? data?.is_premium ?? false;

  // Other slots / Group switch modal state
  const [activeSubjectSlot, setActiveSubjectSlot] = useState<ScheduleSlot | null>(null);
  const [availableSlots, setAvailableSlots] = useState<AvailableGroupOption[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [filterUpcomingOnly, setFilterUpcomingOnly] = useState(false);
  const [changeType, setChangeType] = useState<'permanent' | 'one_time'>('permanent');
  const [applyingClassId, setApplyingClassId] = useState<number | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Inline confirmation state (replaces window.confirm)
  const [switchConfirmOption, setSwitchConfirmOption] = useState<AvailableGroupOption | null>(null);

  const fetchTimetable = useCallback(() => {
    setLoading(true);
    apiCall<TimetableResponse>(`/api/students/${studentId}/timetable/`)
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [studentId]);

  useEffect(() => {
    fetchTimetable();
  }, [fetchTimetable]);

  const days = [
    { num: 1, label: t('day_1'), short: t('day_1_short') },
    { num: 2, label: t('day_2'), short: t('day_2_short') },
    { num: 3, label: t('day_3'), short: t('day_3_short') },
    { num: 4, label: t('day_4'), short: t('day_4_short') },
    { num: 5, label: t('day_5'), short: t('day_5_short') },
  ];

  // Open modal to see all slots for class / switch section
  const handleOpenSlotsModal = async (slot: ScheduleSlot) => {
    if (!studentHasPremium) {
      if (onRequirePremium) {
        onRequirePremium(t('premium_only_change'));
      }
      return;
    }

    setActiveSubjectSlot(slot);
    setLoadingSlots(true);
    setFeedbackMessage(null);
    setSwitchConfirmOption(null);
    setChangeType('permanent');
    setFilterUpcomingOnly(false);
    try {
      const sessionParam = slot.session_number ? `&session_number=${slot.session_number}` : '';
      const slotParam = slot.slot_id ? `&slot_id=${slot.slot_id}` : '';
      const classParam = slot.class_id ? `&class_id=${slot.class_id}` : '';
      const res = await apiCall<{ options: AvailableGroupOption[] }>(
        `/api/subjects/${slot.subject_id}/available-groups/?student_telegram_id=${studentId}${sessionParam}${slotParam}${classParam}`
      );
      setAvailableSlots(res.options || []);
    } catch (err: any) {
      setFeedbackMessage({ type: 'error', text: err.message || 'Failed to load options' });
    } finally {
      setLoadingSlots(false);
    }
  };

  // Revert one-time make-up slot or permanent switch back to primary group
  const handleRevertSlot = async (slot: ScheduleSlot) => {
    if (!studentHasPremium) {
      if (onRequirePremium) {
        onRequirePremium(t('premium_only_change'));
      }
      return;
    }

    try {
      setLoading(true);
      await apiCall<{ success: boolean; message: string }>(
        `/api/students/${studentId}/revert-override/`,
        'POST',
        {
          subject_id: slot.subject_id,
          slot_id: slot.slot_id,
          original_slot_id: slot.original_slot_id || slot.slot_id,
        }
      );
      fetchTimetable();
      if (onRefreshTrigger) onRefreshTrigger();
      if (activeSubjectSlot) {
        setActiveSubjectSlot(null);
      }
    } catch (err: any) {
      console.error('Failed to revert slot:', err);
    } finally {
      setLoading(false);
    }
  };

  // Confirm schedule switch / revert
  const handleApplyGroupSwitch = async (
    option: AvailableGroupOption,
    mode: 'permanent' | 'one_time' = changeType
  ) => {
    if (!activeSubjectSlot) return;

    setApplyingClassId(option.class_id);
    setSwitchConfirmOption(null);
    try {
      const res = await apiCall<{ success: boolean; message: string }>(
        `/api/students/${studentId}/change-group/`,
        'POST',
        {
          old_class_id: activeSubjectSlot.class_id,
          new_class_id: option.class_id,
          target_slot_id: option.slot_id || (option.slots && option.slots[0]?.slot_id),
          original_slot_id: activeSubjectSlot.slot_id,
          session_number: activeSubjectSlot.session_number || 1,
          change_type: option.is_own_group ? 'permanent' : mode,
        }
      );

      setFeedbackMessage({ type: 'success', text: res.message });
      fetchTimetable();
      if (onRefreshTrigger) onRefreshTrigger();

      setTimeout(() => {
        setActiveSubjectSlot(null);
        setFeedbackMessage(null);
      }, 1600);
    } catch (err: any) {
      setFeedbackMessage({ type: 'error', text: err.message || 'Failed to apply schedule change' });
    } finally {
      setApplyingClassId(null);
    }
  };

  const schedule = data?.schedule || [];
  const filteredSchedule = selectedDay
    ? schedule.filter((s) => s.day_of_week === selectedDay)
    : schedule;

  // Group by day of week
  const groupedByDay: { [day: number]: ScheduleSlot[] } = {};
  filteredSchedule.forEach((item) => {
    if (!groupedByDay[item.day_of_week]) {
      groupedByDay[item.day_of_week] = [];
    }
    groupedByDay[item.day_of_week].push(item);
  });

  // Filter out options that meet at the EXACT same day and time as the current active slot
  // (e.g. combined sections with other groups sharing the same room and professor at the exact same hour)
  const nonDuplicateSlots = availableSlots.filter((option) => {
    if (!activeSubjectSlot) return true;
    const isSameTime = (
      option.day_name === activeSubjectSlot.day_name &&
      option.start_time === activeSubjectSlot.start_time &&
      option.end_time === activeSubjectSlot.end_time
    );
    // If it has identical timing to current class, do not show it as an alternative
    if (isSameTime && option.class_id !== activeSubjectSlot.class_id) {
      return false;
    }
    return true;
  });

  const displayedOptions = (changeType === 'one_time' && filterUpcomingOnly)
    ? nonDuplicateSlots.filter((o) => o.is_upcoming)
    : nonDuplicateSlots;

  const upcomingCount = nonDuplicateSlots.filter((o) => o.is_upcoming).length;

  return (
    <div className="space-y-3 sm:space-y-4 w-full max-w-full overflow-hidden">
      {/* Group Header */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 w-full">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base sm:text-lg font-bold text-slate-900 leading-tight">
              {data?.group_name ? `${data.group_name} Schedule` : 'My Schedule'}
            </h2>
            <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              Weekly Classes
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            Click any class below to change your time or choose a make-up lesson if you missed a class.
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            onClick={fetchTimetable}
            disabled={loading}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700 transition-colors shadow-2xs"
            title="Refresh schedule"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-600' : 'text-slate-600'}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Quick Help Banner */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50/40 border border-blue-200/80 rounded-2xl p-3.5 text-xs text-blue-950 flex items-start gap-3">
        <Sparkles className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
        <div className="space-y-1 min-w-0">
          <span className="font-bold text-slate-900 block text-xs">
            {t('timetable_help_title')}
          </span>
          <div className="text-slate-600 text-[11px] leading-relaxed space-y-0.5">
            <p>
              • <strong>{t('timetable_help_makeup_label')}</strong> {t('timetable_help_makeup_desc')}
            </p>
            <p>
              • <strong>{t('timetable_help_perm_label')}</strong> {t('timetable_help_perm_desc')}
            </p>
          </div>
        </div>
      </div>

      {/* Day Filter Pills (Mobile friendly horizontal scroll with no viewport push) */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 max-w-full scrollbar-none">
        <button
          onClick={() => setSelectedDay(null)}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 ${
            selectedDay === null
              ? 'bg-blue-600 text-white shadow-2xs'
              : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          {t('all_days')}
        </button>
        {days.map((d) => (
          <button
            key={d.num}
            onClick={() => setSelectedDay(d.num)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shrink-0 ${
              selectedDay === d.num
                ? 'bg-blue-600 text-white shadow-2xs'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      {/* Timetable List View */}
      {loading ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center text-xs text-slate-400">
          Loading schedule...
        </div>
      ) : filteredSchedule.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center space-y-2">
          <CalendarIcon className="w-8 h-8 text-slate-300 mx-auto" />
          <div className="text-sm font-semibold text-slate-700">{t('no_classes')}</div>
          <div className="text-xs text-slate-400">
            Enjoy your free time or check other days using the filter above.
          </div>
        </div>
      ) : (
        <div className="space-y-3 sm:space-y-4">
          {days
            .filter((d) => (selectedDay ? d.num === selectedDay : groupedByDay[d.num]?.length > 0))
            .map((day) => {
              const daySlots = groupedByDay[day.num] || [];
              if (daySlots.length === 0) return null;

              return (
                <div key={day.num} className="bg-white border border-slate-200 rounded-2xl p-3.5 sm:p-5 shadow-2xs">
                  {/* Day Header */}
                  <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-blue-600"></div>
                      <h3 className="text-sm font-bold text-slate-900 tracking-tight">
                        {day.label}
                      </h3>
                    </div>
                    <span className="text-[11px] text-slate-400 font-medium">
                      {daySlots.length} {daySlots.length === 1 ? 'class' : 'classes'}
                    </span>
                  </div>

                  {/* Slot Cards */}
                  <div className="space-y-2.5">
                    {daySlots.map((slot, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 ${
                          slot.is_changed
                            ? 'bg-amber-50/40 border-amber-300/80 shadow-2xs'
                            : 'bg-slate-50/60 border-slate-200/80 hover:border-slate-300'
                        }`}
                      >
                        {/* Time & Subject Info */}
                        <div className="flex items-start gap-2.5 min-w-0 flex-1">
                          <div className="bg-white px-2.5 py-1.5 rounded-lg border border-slate-200 text-center shrink-0 shadow-2xs">
                            <span className="text-xs font-black text-slate-900 block leading-tight">
                              {slot.start_time}
                            </span>
                            <span className="text-[10px] text-slate-400 block leading-tight">
                              {slot.end_time}
                            </span>
                          </div>

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 flex-wrap mb-1">
                              <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-blue-100 text-blue-800">
                                {slot.subject_short}
                              </span>
                              <h4 className="text-sm font-bold text-slate-900 leading-tight">
                                {slot.subject_full}
                              </h4>

                              {/* Multi-session badge */}
                              {slot.total_sessions && slot.total_sessions > 1 && (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  Session {slot.session_number} of {slot.total_sessions}
                                </span>
                              )}

                              {/* Permanent section change badge */}
                              {slot.is_changed && !slot.is_one_time && (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-900 border border-blue-300 flex items-center gap-1">
                                  <RefreshCw className="w-2.5 h-2.5 text-blue-600 shrink-0" />
                                  Permanent Section Change
                                </span>
                              )}

                              {/* One-time make-up badge */}
                              {slot.is_changed && slot.is_one_time && (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 flex items-center gap-1">
                                  <Sparkles className="w-2.5 h-2.5 text-amber-600 shrink-0" />
                                  One-Time Make-up (This Week Only)
                                </span>
                              )}
                            </div>

                            {/* Details row */}
                            <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
                              <div className="flex items-center gap-1">
                                <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                <span className="truncate">{slot.professor}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                <span>{t('room')}: <strong className="text-slate-700">{slot.room}</strong></span>
                              </div>
                              <div className="flex items-center gap-1 text-[11px] text-slate-500">
                                <Layers className="w-3.5 h-3.5 shrink-0" />
                                <span>{t('group')}: <strong className="text-blue-700">{slot.actual_group}</strong></span>
                              </div>
                            </div>

                            {slot.is_changed && (
                              <div className={`mt-1 text-[11px] flex items-center gap-1 font-medium ${
                                slot.is_one_time ? 'text-amber-800' : 'text-blue-800'
                              }`}>
                                {slot.is_one_time ? (
                                  <span>⚡ Attending with {slot.actual_group} this week only. Will revert to {slot.original_group} next week.</span>
                                ) : (
                                  <span>✓ Permanently attending with section {slot.actual_group} for the semester.</span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Action buttons: Switch or Revert */}
                        <div className="flex items-center gap-2 justify-end shrink-0 pt-1 sm:pt-0">
                          {slot.is_changed ? (
                            <>
                              <button
                                onClick={() => handleRevertSlot(slot)}
                                className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
                                title="Revert back to primary group schedule"
                              >
                                <RotateCcw className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                                <span>{t('revert_primary')}</span>
                              </button>
                              <button
                                onClick={() => handleOpenSlotsModal(slot)}
                                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-white text-xs font-semibold transition-colors shadow-2xs ${
                                  slot.is_one_time ? 'bg-amber-600 hover:bg-amber-700' : 'bg-blue-600 hover:bg-blue-700'
                                }`}
                              >
                                <span>{t('change_time')}</span>
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => handleOpenSlotsModal(slot)}
                              className="w-full sm:w-auto flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 text-xs font-semibold transition-colors shadow-2xs"
                              title="Change class time (permanent or one-time make-up)"
                            >
                              <Clock className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                              <span>{t('change_time')}</span>
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
        </div>
      )}

      {/* Class Schedule Change Modal (Permanent or One-Time) */}
      {activeSubjectSlot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 max-h-[92vh] flex flex-col overflow-hidden">
            {/* Modal Header - Compact & Sticky at Top */}
            <div className="flex items-start justify-between border-b border-slate-100 p-3.5 sm:p-4 shrink-0 bg-white z-10">
              <div className="min-w-0 pr-2">
                <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                  <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-blue-100 text-blue-800">
                    {activeSubjectSlot.subject_short}
                  </span>
                  <h3 className="text-sm font-bold text-slate-900 truncate">
                    {activeSubjectSlot.subject_full}
                  </h3>
                  {activeSubjectSlot.total_sessions && activeSubjectSlot.total_sessions > 1 && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                      {t('modal_session_indicator', {
                        session: activeSubjectSlot.session_number || 1,
                        total: activeSubjectSlot.total_sessions,
                      })}
                    </span>
                  )}
                </div>
                <p className="text-[11px] sm:text-xs text-slate-500 mt-0.5">
                  {t('modal_showing_alternatives', {
                    professor: activeSubjectSlot.professor,
                    session: activeSubjectSlot.session_number || 1,
                  })}
                </p>
              </div>
              <button
                onClick={() => setActiveSubjectSlot(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body: Single Scrollable Container (allows top explanations to scroll out of way on mobile) */}
            <div className="overflow-y-auto flex-1 p-3 sm:p-4 space-y-3 min-h-0">
              {/* Permanent vs One-Time Toggle */}
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 rounded-xl">
                  <button
                    type="button"
                    onClick={() => {
                      setChangeType('permanent');
                      setFilterUpcomingOnly(false);
                    }}
                    className={`py-2 px-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                      changeType === 'permanent'
                        ? 'bg-white text-blue-700 shadow-2xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>{t('modal_perm_toggle')}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setChangeType('one_time');
                      setFilterUpcomingOnly(true);
                    }}
                    className={`py-2 px-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                      changeType === 'one_time'
                        ? 'bg-white text-amber-700 shadow-2xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>{t('modal_makeup_toggle')}</span>
                  </button>
                </div>

                {changeType === 'permanent' ? (
                  <div className="text-[11px] text-blue-900 bg-blue-50/90 border border-blue-200/90 rounded-xl p-3 space-y-1">
                    <div className="flex items-center gap-1.5 font-bold text-blue-950">
                      <RefreshCw className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                      <span>{t('modal_perm_banner_title')}</span>
                    </div>
                    <p className="text-slate-600 leading-normal">
                      {t('modal_perm_banner_desc')}
                    </p>
                  </div>
                ) : (
                  <div className="text-[11px] text-amber-950 bg-amber-50/90 border border-amber-200/90 rounded-xl p-3 space-y-1">
                    <div className="flex items-center gap-1.5 font-bold text-amber-950">
                      <Sparkles className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                      <span>{t('modal_makeup_banner_title')}</span>
                    </div>
                    <p className="text-slate-700 leading-normal">
                      {t('modal_makeup_banner_desc')}
                    </p>
                  </div>
                )}
              </div>

              {/* Current Active Slot Info */}
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                  <span className="uppercase font-bold tracking-wider text-[10px]">{t('modal_current_time')}</span>
                  <span className="font-semibold text-blue-600">{activeSubjectSlot.actual_group}</span>
                </div>
                <div className="flex items-center justify-between text-slate-800 font-bold text-xs">
                  <span>{activeSubjectSlot.day_name}, {activeSubjectSlot.start_time} - {activeSubjectSlot.end_time}</span>
                  <span className="font-normal text-slate-500">{t('modal_room_label')} {activeSubjectSlot.room}</span>
                </div>
              </div>

              {/* Upcoming Lessons Toggle / Filter */}
              <div className="flex items-center justify-between gap-2 pt-0.5">
                <span className="text-xs font-bold text-slate-800">
                  {t('modal_choose_time')}
                </span>
                {changeType === 'one_time' ? (
                  <button
                    onClick={() => setFilterUpcomingOnly(!filterUpcomingOnly)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                      filterUpcomingOnly
                        ? 'bg-amber-600 text-white shadow-2xs'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    <Clock className="w-3.5 h-3.5" />
                    <span>{filterUpcomingOnly ? t('modal_upcoming_only', { count: upcomingCount }) : t('modal_show_all', { count: availableSlots.length })}</span>
                  </button>
                ) : (
                  <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-lg">
                    {t('modal_all_weekly', { count: availableSlots.length })}
                  </span>
                )}
              </div>

              {/* Feedback Message */}
              {feedbackMessage && (
                <div
                  className={`p-3 rounded-xl border text-xs flex items-center gap-2 ${
                    feedbackMessage.type === 'success'
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                      : 'bg-rose-50 border-rose-200 text-rose-800'
                  }`}
                >
                  {feedbackMessage.type === 'success' ? (
                    <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  )}
                  <span>{feedbackMessage.text}</span>
                </div>
              )}

              {/* Available options list */}
              <div className="space-y-2.5">
                {loadingSlots ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    {t('modal_loading_slots')}
                  </div>
                ) : displayedOptions.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-400 space-y-2">
                    <p>{t('modal_no_sections')}</p>
                    {filterUpcomingOnly && (
                      <button
                        onClick={() => setFilterUpcomingOnly(false)}
                        className="text-blue-600 underline font-semibold text-xs"
                      >
                        {t('modal_show_all_link')}
                      </button>
                    )}
                  </div>
                ) : (
                  displayedOptions.map((option) => {
                    const isCurrent = option.class_id === activeSubjectSlot.class_id;
                    const isMultiSession = (option.sessions_per_week && option.sessions_per_week > 1) || (option.slots && option.slots.length > 1);

                    return (
                      <div
                        key={option.class_id}
                        className={`p-3 rounded-xl border transition-all text-xs flex flex-col justify-between gap-2 ${
                          isCurrent
                            ? 'bg-blue-50/60 border-blue-300'
                            : option.recommended
                            ? 'bg-emerald-50/40 border-emerald-300 hover:border-emerald-400'
                            : option.is_available
                            ? 'bg-white border-slate-200 hover:border-slate-300'
                            : 'bg-slate-50/80 border-slate-200 opacity-75'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                              <span className="font-bold text-slate-900 text-sm">
                                {option.group_name}
                              </span>
                              
                              {/* Upcoming / Weekly badge */}
                              {changeType === 'permanent' ? (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                                  {t('modal_every_week')}
                                </span>
                              ) : option.is_upcoming ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                                  <Clock className="w-2.5 h-2.5 text-emerald-600 shrink-0" />
                                  {t('modal_upcoming_lesson')}
                                </span>
                              ) : (
                                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-500">
                                  {t('modal_passed_this_week')}
                                </span>
                              )}

                              {/* 1 vs 2 lectures per week badge */}
                              {isMultiSession ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  {t('modal_sessions_per_wk', { count: 2 })}
                                </span>
                              ) : (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">
                                  {t('modal_sessions_per_wk', { count: 1 })}
                                </span>
                              )}

                              {option.is_own_group && (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-blue-100 text-blue-800">
                                  {t('modal_primary_group')}
                                </span>
                              )}
                            </div>

                            <div className="flex items-center gap-1.5 text-slate-600 text-xs mb-1">
                              <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                              <span className="truncate">{option.professor}</span>
                            </div>

                            {/* Sessions List */}
                            {isMultiSession && option.slots && option.slots.length > 0 ? (
                              <div className="space-y-1 bg-slate-50 p-2 rounded-lg border border-slate-200/80 mb-1">
                                {option.slots.map((s, sIdx) => (
                                  <div key={sIdx} className="flex items-center justify-between text-xs text-slate-700 flex-wrap gap-1">
                                    <div className="flex items-center gap-1.5">
                                      <span className="w-3.5 h-3.5 rounded-full bg-indigo-100 text-indigo-700 font-bold text-[9px] inline-flex items-center justify-center shrink-0">
                                        {sIdx + 1}
                                      </span>
                                      <strong className="text-slate-800">{s.day_name}</strong>
                                      <span className="text-slate-500">({s.start_time} - {s.end_time})</span>
                                    </div>
                                    <span className="text-slate-500 text-[11px]">{t('modal_room_label')} <strong className="text-slate-800">{s.room}</strong></span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="space-y-0.5 text-slate-600 text-xs">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <CalendarIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                  <strong className="text-slate-800">{option.day_name}</strong>
                                  <span>({option.start_time} - {option.end_time})</span>
                                  <span className="text-slate-300">•</span>
                                  <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                  <span>{t('modal_room_label')} <strong>{option.room}</strong></span>
                                </div>
                              </div>
                            )}

                            {option.conflict_reason && (
                              <div className="mt-1 text-[11px] font-semibold text-rose-700 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3 text-rose-600 shrink-0" />
                                <span>{option.conflict_reason}</span>
                              </div>
                            )}
                          </div>

                          {/* Action Button */}
                          <div className="shrink-0 ml-1">
                            {isCurrent ? (
                              <span className="px-3 py-1.5 rounded-lg bg-blue-100 text-blue-800 text-xs font-semibold inline-block">
                                {t('modal_active_badge')}
                              </span>
                            ) : (
                              <button
                                disabled={applyingClassId === option.class_id}
                                onClick={() => setSwitchConfirmOption(option)}
                                className={`px-3 py-1.5 rounded-xl font-bold text-xs transition-colors flex items-center gap-1 ${
                                  option.is_own_group
                                    ? 'bg-slate-800 hover:bg-slate-900 text-white'
                                    : option.is_available
                                    ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-2xs'
                                    : 'bg-slate-200 hover:bg-slate-300 text-slate-700'
                                }`}
                              >
                                <span>
                                  {applyingClassId === option.class_id
                                    ? t('modal_applying_btn')
                                    : option.is_own_group
                                    ? t('modal_revert_btn')
                                    : changeType === 'permanent'
                                    ? t('modal_switch_btn')
                                    : t('modal_choose_makeup_btn')}
                                </span>
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Inline Confirmation Prompt inside Modal */}
              {switchConfirmOption && (
                <div className={`p-3.5 rounded-xl border space-y-2.5 ${
                  switchConfirmOption.is_own_group
                    ? 'bg-slate-50 border-slate-300'
                    : changeType === 'permanent'
                    ? 'bg-blue-50/90 border-blue-200'
                    : 'bg-amber-50/90 border-amber-200'
                }`}>
                  <div className="text-xs font-bold text-slate-900">
                    {switchConfirmOption.is_own_group
                      ? t('modal_confirm_revert_title', { group: switchConfirmOption.group_name })
                      : changeType === 'permanent'
                      ? t('modal_confirm_perm_title', { subject: activeSubjectSlot.subject_short, group: switchConfirmOption.group_name })
                      : t('modal_confirm_makeup_title', { group: switchConfirmOption.group_name })}
                  </div>

                  <div className="text-[11px] text-slate-700 leading-relaxed space-y-1 bg-white p-2.5 rounded-lg border border-slate-200">
                    <p>
                      • <strong>{t('modal_section_prof_label')}</strong> {switchConfirmOption.group_name} ({switchConfirmOption.professor})
                    </p>
                    <p>
                      • <strong>{t('modal_time_label')}</strong> {switchConfirmOption.time_summary || `${switchConfirmOption.day_name} ${switchConfirmOption.start_time}-${switchConfirmOption.end_time}`}
                    </p>
                    <p>
                      • <strong>{t('modal_duration_label')}</strong>{' '}
                      {switchConfirmOption.is_own_group ? (
                        <span className="font-bold text-slate-800">{t('modal_duration_primary')}</span>
                      ) : changeType === 'permanent' ? (
                        <span className="font-bold text-blue-700">{t('modal_duration_permanent')}</span>
                      ) : (
                        <span className="font-bold text-amber-700">{t('modal_duration_makeup')}</span>
                      )}
                    </p>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-1">
                    <button
                      onClick={() => setSwitchConfirmOption(null)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100"
                    >
                      {t('cancel_btn')}
                    </button>
                    <button
                      onClick={() => handleApplyGroupSwitch(switchConfirmOption, changeType)}
                      className={`px-3.5 py-1.5 rounded-lg text-xs font-bold text-white shadow-xs ${
                        switchConfirmOption.is_own_group
                          ? 'bg-slate-800 hover:bg-slate-900'
                          : changeType === 'permanent'
                          ? 'bg-blue-600 hover:bg-blue-700'
                          : 'bg-amber-600 hover:bg-amber-700'
                      }`}
                    >
                      {switchConfirmOption.is_own_group
                        ? t('modal_confirm_revert_btn')
                        : changeType === 'permanent'
                        ? t('modal_confirm_perm_btn')
                        : t('modal_confirm_makeup_btn')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
