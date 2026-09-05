import React, { useState, useEffect } from 'react';
import { 
  X, 
  RotateCcw, 
  Calendar, 
  Clock, 
  User, 
  MapPin, 
  CheckCircle2, 
  AlertTriangle, 
  Sparkles, 
  ChevronRight, 
  ArrowLeft,
  BookOpen,
  GraduationCap,
  Search
} from 'lucide-react';
import { RetakeCatalogResponse, RetakeSubject, AvailableGroupOption } from '../types';
import { apiCall } from '../api';

interface RetakeCourseModalProps {
  studentId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const RetakeCourseModal: React.FC<RetakeCourseModalProps> = ({
  studentId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [catalog, setCatalog] = useState<RetakeCatalogResponse | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [step, setStep] = useState<1 | 2 | 3>(1); // 1: Year, 2: Subject, 3: Class Section
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<RetakeSubject | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Step 3 state
  const [availableSlots, setAvailableSlots] = useState<AvailableGroupOption[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<{ message: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setSelectedYear(null);
      setSelectedSubject(null);
      setSelectedClassId(null);
      setSuccessResult(null);
      setErrorMsg(null);
      setSearchQuery('');
      loadCatalog();
    }
  }, [isOpen, studentId]);

  const loadCatalog = async () => {
    setLoadingCatalog(true);
    try {
      const data = await apiCall<RetakeCatalogResponse>(`/api/students/${studentId}/retake-catalog/`);
      setCatalog(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load course catalog');
    } finally {
      setLoadingCatalog(false);
    }
  };

  const handleSelectYear = (year: number) => {
    setSelectedYear(year);
    setStep(2);
  };

  const handleSelectSubject = async (subject: RetakeSubject) => {
    if (subject.is_enrolled) return;
    setSelectedSubject(subject);
    setSelectedClassId(null);
    setStep(3);
    setLoadingSlots(true);
    setErrorMsg(null);

    try {
      const res = await apiCall<{ options: AvailableGroupOption[] }>(
        `/api/subjects/${subject.subject_id}/available-groups/?student_telegram_id=${studentId}`
      );
      setAvailableSlots(res.options || []);
      // Preselect first recommended or available slot if exists
      const recommended = res.options?.find((o) => o.recommended && o.is_available);
      if (recommended) {
        setSelectedClassId(recommended.class_id);
      } else if (res.options && res.options.length > 0) {
        const firstAvail = res.options.find((o) => o.is_available);
        if (firstAvail) setSelectedClassId(firstAvail.class_id);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load class sections');
    } finally {
      setLoadingSlots(false);
    }
  };

  const handleConfirmEnrollment = async () => {
    if (!selectedClassId || !selectedSubject) return;

    setSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await apiCall<{ success: boolean; message: string }>(
        `/api/students/${studentId}/enroll-retake/`,
        'POST',
        { class_id: selectedClassId }
      );
      setSuccessResult({ message: res.message });
      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message || 'Enrollment failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const yearSubjects = (catalog?.subjects || []).filter(
    (s) => s.year_level === selectedYear
  );

  const filteredSubjects = yearSubjects.filter(
    (s) =>
      s.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.short_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getYearLabel = (y: number) => {
    if (y === 1) return 'Year 1 (Freshman Level)';
    if (y === 2) return 'Year 2 (Sophomore Level)';
    if (y === 3) return 'Year 3 (Junior Level)';
    return `Year ${y}`;
  };

  const getYearSubtitle = (y: number, studentYear: number) => {
    if (y < studentYear) return `Prior year foundation course (${catalog?.subjects.filter((s) => s.year_level === y).length || 0} subjects)`;
    return `Current academic year course (${catalog?.subjects.filter((s) => s.year_level === y).length || 0} subjects)`;
  };

  const selectedSlot = availableSlots.find((s) => s.class_id === selectedClassId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
      <div className="bg-white rounded-2xl max-w-xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
              <RotateCcw className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900 leading-tight">
                  Register Retake Course
                </h3>
                {catalog && (
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                    Year {catalog.student_year} Student
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500">
                Enroll in dropped or prior-year courses and fit them into your timetable
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Step Indicator */}
        {!successResult && (
          <div className="px-5 py-2.5 bg-slate-100/60 border-b border-slate-200 flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <button
                disabled={step === 1}
                onClick={() => setStep(1)}
                className={`font-semibold flex items-center gap-1 ${
                  step === 1 ? 'text-blue-600' : 'text-slate-600 hover:text-blue-600'
                }`}
              >
                <span className="w-4 h-4 rounded-full bg-blue-600 text-white text-[10px] inline-flex items-center justify-center font-bold">
                  1
                </span>
                Academic Year
              </button>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <button
                disabled={step < 2}
                onClick={() => setStep(2)}
                className={`font-semibold flex items-center gap-1 ${
                  step === 2
                    ? 'text-blue-600'
                    : step > 2
                    ? 'text-slate-600 hover:text-blue-600'
                    : 'text-slate-400 opacity-60'
                }`}
              >
                <span className={`w-4 h-4 rounded-full text-[10px] inline-flex items-center justify-center font-bold ${
                  step >= 2 ? 'bg-blue-600 text-white' : 'bg-slate-300 text-slate-600'
                }`}>
                  2
                </span>
                Subject
              </button>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span
                className={`font-semibold flex items-center gap-1 ${
                  step === 3 ? 'text-blue-600' : 'text-slate-400 opacity-60'
                }`}
              >
                <span className={`w-4 h-4 rounded-full text-[10px] inline-flex items-center justify-center font-bold ${
                  step === 3 ? 'bg-blue-600 text-white' : 'bg-slate-300 text-slate-600'
                }`}>
                  3
                </span>
                Class Slot
              </span>
            </div>

            {step > 1 && (
              <button
                onClick={() => setStep((s) => (s - 1) as any)}
                className="flex items-center gap-1 text-slate-500 hover:text-slate-800 text-xs font-semibold"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
            )}
          </div>
        )}

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Success State */}
          {successResult ? (
            <div className="py-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 mx-auto flex items-center justify-center shadow-xs">
                <CheckCircle2 className="w-10 h-10" />
              </div>
              <div className="space-y-1">
                <h4 className="text-base font-bold text-slate-900">
                  Course Retake Enrolled Successfully!
                </h4>
                <p className="text-xs text-slate-600 max-w-md mx-auto">
                  {successResult.message}
                </p>
                <p className="text-xs text-emerald-700 font-medium pt-1">
                  The class schedule has been updated in your timetable and assignments are now active.
                </p>
              </div>
              <div className="pt-3">
                <button
                  onClick={onClose}
                  className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-colors shadow-xs"
                >
                  Done & View Timetable
                </button>
              </div>
            </div>
          ) : loadingCatalog ? (
            <div className="py-12 text-center text-slate-400 text-xs">
              Loading available courses catalog...
            </div>
          ) : step === 1 ? (
            /* Step 1: Select Academic Year */
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-bold text-slate-900">
                  Select Course Academic Year
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  As a Year {catalog?.student_year} student, you can retake courses from your current year or any prior lower academic year.
                </p>
              </div>

              <div className="space-y-2.5">
                {(catalog?.available_years || [1, 2]).map((year) => {
                  const subsInYear = (catalog?.subjects || []).filter((s) => s.year_level === year);
                  const enrolledCount = subsInYear.filter((s) => s.is_enrolled).length;
                  const availableCount = subsInYear.length - enrolledCount;

                  return (
                    <button
                      key={year}
                      onClick={() => handleSelectYear(year)}
                      className="w-full text-left p-4 rounded-xl border border-slate-200 hover:border-blue-400 hover:bg-blue-50/30 transition-all flex items-center justify-between group"
                    >
                      <div className="flex items-center gap-3.5">
                        <div className="w-10 h-10 rounded-xl bg-blue-50 group-hover:bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-base transition-colors">
                          <GraduationCap className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="text-sm font-bold text-slate-900 group-hover:text-blue-700">
                            {getYearLabel(year)}
                          </div>
                          <div className="text-xs text-slate-500">
                            {getYearSubtitle(year, catalog?.student_year || 2)}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 group-hover:bg-blue-100 group-hover:text-blue-800">
                          {availableCount} retake options
                        </span>
                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-transform group-hover:translate-x-0.5" />
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : step === 2 ? (
            /* Step 2: Select Subject */
            <div className="space-y-3.5">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold text-slate-900">
                    Choose Subject ({getYearLabel(selectedYear!)})
                  </h4>
                  <p className="text-xs text-slate-500">
                    Select the subject you want to retake or enroll into
                  </p>
                </div>
              </div>

              {/* Search input */}
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search subject by name or code..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-colors"
                />
              </div>

              {/* Subjects List */}
              <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {filteredSubjects.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    No subjects found for this year.
                  </div>
                ) : (
                  filteredSubjects.map((sub) => {
                    const isEnrolled = sub.is_enrolled;
                    const isDropped = sub.enrollment_status === 'dropped';

                    return (
                      <div
                        key={sub.subject_id}
                        className={`p-3.5 rounded-xl border flex items-center justify-between transition-all ${
                          isEnrolled
                            ? 'bg-slate-50 border-slate-200 opacity-60 cursor-not-allowed'
                            : 'bg-white border-slate-200 hover:border-blue-400 hover:shadow-xs cursor-pointer'
                        }`}
                        onClick={() => !isEnrolled && handleSelectSubject(sub)}
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-bold px-2 py-0.5 rounded-lg bg-blue-100 text-blue-800 border border-blue-200">
                            {sub.short_name}
                          </span>
                          <div>
                            <div className="text-xs font-bold text-slate-900">
                              {sub.full_name}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              {getYearLabel(sub.year_level)}
                            </div>
                          </div>
                        </div>

                        <div>
                          {isEnrolled ? (
                            <span className="text-[11px] font-semibold px-2 py-1 rounded-md bg-slate-200 text-slate-600">
                              Already Active
                            </span>
                          ) : isDropped ? (
                            <span className="text-[11px] font-semibold px-2 py-1 rounded-md bg-amber-50 text-amber-800 border border-amber-200 flex items-center gap-1">
                              <RotateCcw className="w-3 h-3" />
                              Retake Dropped
                            </span>
                          ) : (
                            <span className="text-[11px] font-semibold px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-600 hover:text-white transition-colors">
                              Select &rarr;
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          ) : (
            /* Step 3: Class Section & Time Slot Selection */
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-blue-100 text-blue-800">
                    {selectedSubject?.short_name}
                  </span>
                  <span>{selectedSubject?.full_name}</span>
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  Choose an available class section and time slot across university groups:
                </p>
              </div>

              {loadingSlots ? (
                <div className="py-10 text-center text-xs text-slate-400">
                  Checking timetable conflicts and recommendations...
                </div>
              ) : availableSlots.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No active class sections found for this subject.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                  {availableSlots.map((opt) => {
                    const isSelected = selectedClassId === opt.class_id;
                    const isMultiSession = (opt.sessions_per_week && opt.sessions_per_week > 1) || (opt.slots && opt.slots.length > 1);

                    return (
                      <div
                        key={opt.class_id}
                        onClick={() => setSelectedClassId(opt.class_id)}
                        className={`p-3.5 rounded-xl border text-xs cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-blue-50/70 border-blue-500 ring-1 ring-blue-500 shadow-xs'
                            : opt.recommended
                            ? 'bg-emerald-50/30 border-emerald-300 hover:border-emerald-400'
                            : opt.is_available
                            ? 'bg-white border-slate-200 hover:border-slate-300'
                            : 'bg-slate-50 border-slate-200 opacity-75'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-slate-900 text-sm">
                              {opt.group_name}
                            </span>
                            
                            {/* 1 vs 2 lectures per week badge */}
                            {isMultiSession ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">
                                📚 2 Lectures / Week
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-50 text-sky-700 border border-sky-200">
                                📖 1 Lecture / Week
                              </span>
                            )}

                            {opt.recommended && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                                <Sparkles className="w-3 h-3" />
                                Recommended (Fits Schedule)
                              </span>
                            )}
                            {opt.conflict_reason && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                {opt.conflict_reason}
                              </span>
                            )}
                          </div>

                          <div className="w-4 h-4 rounded-full border flex items-center justify-center shrink-0 mt-0.5 border-slate-400">
                            {isSelected && <div className="w-2 h-2 rounded-full bg-blue-600" />}
                          </div>
                        </div>

                        {/* Professor Info */}
                        <div className="flex items-center gap-1.5 text-slate-600 text-xs mb-2">
                          <User className="w-3.5 h-3.5 text-slate-400" />
                          <span className="font-medium text-slate-800">{opt.professor}</span>
                        </div>

                        {/* Schedule Sessions */}
                        {isMultiSession && opt.slots && opt.slots.length > 0 ? (
                          <div className="space-y-1.5 bg-slate-50/70 p-2 rounded-lg border border-slate-200/80">
                            {opt.slots.map((s, sIdx) => (
                              <div key={sIdx} className="flex items-center justify-between text-xs text-slate-700">
                                <div className="flex items-center gap-2">
                                  <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 font-bold text-[10px] inline-flex items-center justify-center">
                                    {sIdx + 1}
                                  </span>
                                  <span className="font-semibold text-slate-900">{s.day_name}</span>
                                  <span className="text-slate-500">({s.start_time} - {s.end_time})</span>
                                </div>
                                <span className="text-slate-500">Room: <strong className="text-slate-800">{s.room}</strong></span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="grid grid-cols-2 gap-2 text-slate-600 text-xs">
                            <div className="flex items-center gap-1.5">
                              <Calendar className="w-3.5 h-3.5 text-slate-400" />
                              <span className="font-semibold text-slate-800">{opt.day_name}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5 text-slate-400" />
                              <span>{opt.start_time} - {opt.end_time}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <MapPin className="w-3.5 h-3.5 text-slate-400" />
                              <span>Room: <strong>{opt.room}</strong></span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Selection Summary Confirmation Box */}
              {selectedSlot && (
                <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="font-bold">
                      Selected Section: {selectedSlot.group_name} ({selectedSlot.sessions_per_week || 1} {(selectedSlot.sessions_per_week || 1) === 1 ? 'lecture' : 'lectures'}/week)
                    </div>
                    <div className="text-[11px] text-blue-700 mt-0.5">
                      {selectedSlot.slots && selectedSlot.slots.length > 1
                        ? selectedSlot.slots.map((s) => `${s.day_name} ${s.start_time}-${s.end_time}`).join(' • ')
                        : `${selectedSlot.day_name} • ${selectedSlot.start_time}-${selectedSlot.end_time} • Room ${selectedSlot.room}`}
                    </div>
                  </div>
                  <button
                    disabled={submitting}
                    onClick={handleConfirmEnrollment}
                    className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs transition-colors shadow-xs disabled:opacity-50 shrink-0"
                  >
                    {submitting ? 'Registering...' : 'Confirm Enrollment'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
