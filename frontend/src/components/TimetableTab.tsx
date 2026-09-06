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

interface TimetableTabProps {
  studentId: string;
  onRefreshTrigger?: () => void;
}

export const TimetableTab: React.FC<TimetableTabProps> = ({ studentId, onRefreshTrigger }) => {
  const [data, setData] = useState<TimetableResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<number | null>(null); // null = all days

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
    { num: 1, label: 'Monday' },
    { num: 2, label: 'Tuesday' },
    { num: 3, label: 'Wednesday' },
    { num: 4, label: 'Thursday' },
    { num: 5, label: 'Friday' },
  ];

  // Open modal to see all slots for class / switch section
  const handleOpenSlotsModal = async (slot: ScheduleSlot) => {
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

  const displayedOptions = (changeType === 'one_time' && filterUpcomingOnly)
    ? availableSlots.filter((o) => o.is_upcoming)
    : availableSlots;

  const upcomingCount = availableSlots.filter((o) => o.is_upcoming).length;

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
            How changing class times works:
          </span>
          <div className="text-slate-600 text-[11px] leading-relaxed space-y-0.5">
            <p>
              • <strong>⚡ One-Time Make-Up:</strong> If you missed or will miss a class this week, pick an upcoming lecture with the same professor to earn your attendance. Reverts back to normal next week.
            </p>
            <p>
              • <strong>🔄 Permanent Change:</strong> Switch this class to another section for the rest of the semester.
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
          All Days
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
          <div className="text-sm font-semibold text-slate-700">No classes scheduled for this day</div>
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
                                <span>Room: <strong className="text-slate-700">{slot.room}</strong></span>
                              </div>
                              <div className="flex items-center gap-1 text-[11px] text-slate-500">
                                <Layers className="w-3.5 h-3.5 shrink-0" />
                                <span>Group: <strong className="text-blue-700">{slot.actual_group}</strong></span>
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
                                <span>Revert to Primary</span>
                              </button>
                              <button
                                onClick={() => handleOpenSlotsModal(slot)}
                                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-white text-xs font-semibold transition-colors shadow-2xs ${
                                  slot.is_one_time ? 'bg-amber-600 hover:bg-amber-700' : 'bg-blue-600 hover:bg-blue-700'
                                }`}
                              >
                                <span>Change Time</span>
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => handleOpenSlotsModal(slot)}
                              className="w-full sm:w-auto flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 text-xs font-semibold transition-colors shadow-2xs"
                              title="Change class time (permanent or one-time make-up)"
                            >
                              <Clock className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                              <span>Change Class Time</span>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full p-4 sm:p-5 shadow-2xl border border-slate-200 space-y-3.5 max-h-[92vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div className="min-w-0 pr-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-blue-100 text-blue-800">
                    {activeSubjectSlot.subject_short}
                  </span>
                  <h3 className="text-sm font-bold text-slate-900 truncate">
                    {activeSubjectSlot.subject_full}
                  </h3>
                  {activeSubjectSlot.total_sessions && activeSubjectSlot.total_sessions > 1 && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                      Session {activeSubjectSlot.session_number} of {activeSubjectSlot.total_sessions}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Showing alternative times with <strong>Prof. {activeSubjectSlot.professor}</strong> for <strong>Session {activeSubjectSlot.session_number || 1}</strong>.
                </p>
              </div>
              <button
                onClick={() => setActiveSubjectSlot(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

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
                  <span>Permanent Change</span>
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
                  <span>One-Time Make-Up</span>
                </button>
              </div>

              {changeType === 'permanent' ? (
                <div className="text-[11px] text-blue-900 bg-blue-50/90 border border-blue-200/90 rounded-xl p-3 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-blue-950">
                    <RefreshCw className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                    <span>Permanent Schedule Change (Full Semester)</span>
                  </div>
                  <p className="text-slate-600 leading-normal">
                    Change this lecture session to another group’s weekly time slot for all remaining weeks of the semester. All weekly section options are listed below.
                  </p>
                </div>
              ) : (
                <div className="text-[11px] text-amber-950 bg-amber-50/90 border border-amber-200/90 rounded-xl p-3 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-amber-950">
                    <Sparkles className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    <span>One-Time Make-Up Lesson (Missed a Class?)</span>
                  </div>
                  <p className="text-slate-700 leading-normal">
                    If you missed or cannot attend your regular class this week, pick an <strong>upcoming lesson</strong> from another section with the same professor to earn your attendance. Applies for <strong>this week only</strong> — your schedule automatically reverts next week.
                  </p>
                </div>
              )}
            </div>

            {/* Current Active Slot Info */}
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                <span className="uppercase font-bold tracking-wider text-[10px]">Your Current Time:</span>
                <span className="font-semibold text-blue-600">{activeSubjectSlot.actual_group}</span>
              </div>
              <div className="flex items-center justify-between text-slate-800 font-bold text-xs">
                <span>{activeSubjectSlot.day_name}, {activeSubjectSlot.start_time} - {activeSubjectSlot.end_time}</span>
                <span className="font-normal text-slate-500">Room: {activeSubjectSlot.room}</span>
              </div>
            </div>

            {/* Upcoming Lessons Toggle / Filter */}
            <div className="flex items-center justify-between gap-2 pt-0.5">
              <span className="text-xs font-bold text-slate-800">
                Choose New Section Time:
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
                  <span>{filterUpcomingOnly ? `Upcoming Only (${upcomingCount})` : `Show All (${availableSlots.length})`}</span>
                </button>
              ) : (
                <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-lg">
                  All Weekly Sections ({availableSlots.length})
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
            <div className="overflow-y-auto flex-1 space-y-2.5 pr-1 min-h-0">
              {loadingSlots ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  Loading available group lessons and checking conflicts...
                </div>
              ) : displayedOptions.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400 space-y-2">
                  <p>No sections found matching your filter.</p>
                  {filterUpcomingOnly && (
                    <button
                      onClick={() => setFilterUpcomingOnly(false)}
                      className="text-blue-600 underline font-semibold text-xs"
                    >
                      Show all week sections
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
                                Every Week
                              </span>
                            ) : option.is_upcoming ? (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1">
                                <Clock className="w-2.5 h-2.5 text-emerald-600 shrink-0" />
                                Upcoming Lesson
                              </span>
                            ) : (
                              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-500">
                                Already passed this week
                              </span>
                            )}

                            {/* 1 vs 2 lectures per week badge */}
                            {isMultiSession ? (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                                2 Sessions / Wk
                              </span>
                            ) : (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">
                                1 Session / Wk
                              </span>
                            )}

                            {option.is_own_group && (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-blue-100 text-blue-800">
                                Primary Group
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
                                  <span className="text-slate-500 text-[11px]">Room: <strong className="text-slate-800">{s.room}</strong></span>
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
                                <span>Room: <strong>{option.room}</strong></span>
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
                              Active
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
                                  ? 'Applying...'
                                  : option.is_own_group
                                  ? 'Revert to Primary'
                                  : changeType === 'permanent'
                                  ? 'Switch to This Time'
                                  : 'Choose Make-Up'}
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
                    ? `Revert schedule to your primary group (${switchConfirmOption.group_name})?`
                    : changeType === 'permanent'
                    ? `Permanently switch ${activeSubjectSlot.subject_short} to section ${switchConfirmOption.group_name}?`
                    : `Schedule one-time make-up with ${switchConfirmOption.group_name} this week?`}
                </div>

                <div className="text-[11px] text-slate-700 leading-relaxed space-y-1 bg-white p-2.5 rounded-lg border border-slate-200">
                  <p>
                    • <strong>Section & Professor:</strong> {switchConfirmOption.group_name} ({switchConfirmOption.professor})
                  </p>
                  <p>
                    • <strong>Time:</strong> {switchConfirmOption.time_summary || `${switchConfirmOption.day_name} ${switchConfirmOption.start_time}-${switchConfirmOption.end_time}`}
                  </p>
                  <p>
                    • <strong>Duration:</strong>{' '}
                    {switchConfirmOption.is_own_group ? (
                      <span className="font-bold text-slate-800">Primary Group Schedule</span>
                    ) : changeType === 'permanent' ? (
                      <span className="font-bold text-blue-700">Permanent Change (Entire Semester)</span>
                    ) : (
                      <span className="font-bold text-amber-700">One-Time Make-Up (This Week Only)</span>
                    )}
                  </p>
                </div>

                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    onClick={() => setSwitchConfirmOption(null)}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100"
                  >
                    Cancel
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
                      ? 'Confirm Revert'
                      : changeType === 'permanent'
                      ? 'Confirm Permanent Change'
                      : 'Confirm One-Time Make-up'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
