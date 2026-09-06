import { useState, useEffect, useCallback } from 'react';
import { BookOpen, Settings, Calendar, Database, AlertCircle, RefreshCw } from 'lucide-react';
import { Navbar } from './components/Navbar';
import { ClassesTab } from './components/ClassesTab';
import { SettingsTab } from './components/SettingsTab';
import { TimetableTab } from './components/TimetableTab';
import { Student } from './types';
import { apiCall, getTelegramUser } from './api';

type TabKey = 'timetable' | 'classes' | 'settings';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('timetable');
  const [students, setStudents] = useState<Student[]>([]);
  const [currentStudent, setCurrentStudent] = useState<Student | null>(null);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Initialize Telegram WebApp SDK if opened in Telegram
  useEffect(() => {
    if (typeof window !== 'undefined' && (window as any).Telegram?.WebApp) {
      const tg = (window as any).Telegram.WebApp;
      tg.ready();
      tg.expand();
    }
  }, []);

  const [loading, setLoading] = useState(true);
  const [notRegistered, setNotRegistered] = useState(false);

  const fetchInitialData = useCallback(() => {
    setLoading(true);
    setNotRegistered(false);

    apiCall('/api/system/status')
      .then((res) => setSystemStatus(res))
      .catch((err) => console.error('Failed to load status:', err));

    const tgUser = getTelegramUser();
    if (tgUser && tgUser.id) {
      // Query specific student record by telegram_id
      apiCall<{ found: boolean; student?: Student }>(`/api/auth/me/${tgUser.id}`)
        .then((res) => {
          if (res.found && res.student) {
            setCurrentStudent(res.student);
            setNotRegistered(false);
          } else {
            setCurrentStudent(null);
            setNotRegistered(true);
          }
        })
        .catch((err) => {
          console.error('Failed to load student for telegram user:', err);
          setNotRegistered(true);
        })
        .finally(() => setLoading(false));
      return;
    }

    // Default web preview (when opening outside Telegram WebApp)
    apiCall<{ students: Student[]; database_connected?: boolean; error?: string }>('/api/demo/students')
      .then((res) => {
        const list = res.students || [];
        setStudents(list);
        if (list.length > 0) {
          setCurrentStudent(list[0]);
        }
      })
      .catch((err) => console.error('Failed to load students:', err))
      .finally(() => setLoading(false));
  }, []);

  // Fetch initial students list & system status
  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  const handleDataChanged = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const botUsername = systemStatus?.bot_username || 'INS_gradesbot';

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Top Navigation */}
      <Navbar currentStudent={currentStudent} />

      {/* Main Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-3 sm:p-6 space-y-4 sm:space-y-5 overflow-x-hidden">
        {/* Navigation Tabs */}
        <div className="bg-white border border-slate-200 rounded-2xl p-1.5 shadow-2xs w-full max-w-full">
          <nav className="grid grid-cols-3 gap-1" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('timetable')}
              className={`flex items-center justify-center gap-1.5 sm:gap-2 px-2.5 py-2.5 rounded-xl text-[11px] sm:text-xs font-bold transition-all ${
                activeTab === 'timetable'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Calendar className="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0" />
              <span className="truncate">📅 Timetable</span>
            </button>

            <button
              onClick={() => setActiveTab('classes')}
              className={`flex items-center justify-center gap-1.5 sm:gap-2 px-2.5 py-2.5 rounded-xl text-[11px] sm:text-xs font-bold transition-all ${
                activeTab === 'classes'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0" />
              <span className="truncate">📚 Courses</span>
            </button>

            <button
              onClick={() => setActiveTab('settings')}
              className={`flex items-center justify-center gap-1.5 sm:gap-2 px-2.5 py-2.5 rounded-xl text-[11px] sm:text-xs font-bold transition-all ${
                activeTab === 'settings'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Settings className="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0" />
              <span className="truncate">⚙️ Profile</span>
            </button>
          </nav>
        </div>

        {/* Tab Content */}
        {currentStudent ? (
          <div className="w-full max-w-full overflow-x-hidden">
            {activeTab === 'timetable' && (
              <TimetableTab
                key={`timetable-${currentStudent.student_id}-${refreshTrigger}`}
                studentId={currentStudent.student_id}
                onRefreshTrigger={handleDataChanged}
              />
            )}

            {activeTab === 'classes' && (
              <ClassesTab
                key={`classes-${currentStudent.student_id}-${refreshTrigger}`}
                studentId={currentStudent.student_id}
                onClassesUpdated={handleDataChanged}
              />
            )}

            {activeTab === 'settings' && (
              <SettingsTab
                key={`settings-${currentStudent.student_id}`}
                student={currentStudent}
                botUsername={botUsername}
              />
            )}
          </div>
        ) : notRegistered ? (
          <div className="py-8 max-w-md mx-auto">
            <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 text-center space-y-5 shadow-xs">
              <div className="w-16 h-16 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto border border-amber-200 shadow-2xs">
                <AlertCircle className="w-8 h-8" />
              </div>
              <div className="space-y-1.5">
                <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">
                  Please Register First
                </h2>
                <p className="text-xs text-slate-500 leading-relaxed max-w-xs mx-auto">
                  Your Telegram account is not linked to any student profile yet.
                  Please register in our bot to unlock your timetable, courses, and attendance.
                </p>
              </div>

              <div className="bg-slate-50 border border-slate-100 rounded-2xl p-4 text-left space-y-2 text-xs text-slate-600">
                <p className="font-bold text-slate-800 flex items-center gap-1.5">
                  <span>📋</span> Simple 3-step registration:
                </p>
                <ol className="list-decimal list-inside space-y-1.5 text-[11px] text-slate-600 pl-0.5">
                  <li>Open the Telegram bot: <span className="font-semibold text-blue-600">@{botUsername}</span></li>
                  <li>Send your <b>Student ID</b> (e.g. <code>U2410252</code>)</li>
                  <li>Select your course and group</li>
                </ol>
              </div>

              <div className="space-y-2 pt-1">
                <a
                  href={`https://t.me/${botUsername}`}
                  target="_blank"
                  rel="noreferrer"
                  className="w-full inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-all active:scale-[0.99]"
                >
                  <span>Open @{botUsername}</span>
                </a>
                <button
                  onClick={fetchInitialData}
                  disabled={loading}
                  className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  <span>{loading ? 'Checking...' : 'I have registered, refresh'}</span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="py-10 max-w-xl mx-auto">
            {systemStatus && systemStatus.database_connected === false ? (
              <div className="bg-white border border-amber-200 rounded-2xl p-6 shadow-sm space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center shrink-0 text-amber-700">
                    <Database className="w-5 h-5" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <span>Railway PostgreSQL Database</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                        Disconnected
                      </span>
                    </h3>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      The application is configured to strictly query your live Railway PostgreSQL database without fallback mock data.
                    </p>
                  </div>
                </div>

                <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200 space-y-2 text-xs">
                  <div className="flex items-center gap-2 text-slate-700 font-semibold">
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>Connection Status</span>
                  </div>
                  <p className="text-[11px] text-slate-600 font-mono break-all bg-white p-2 rounded border border-slate-200">
                    {systemStatus.database_error || 'DATABASE_URL is not set or credentials invalid.'}
                  </p>
                </div>

                <div className="space-y-1.5 text-xs text-slate-600">
                  <p className="font-semibold text-slate-800">To connect Railway PostgreSQL:</p>
                  <ol className="list-decimal list-inside space-y-1 text-[11px] text-slate-600">
                    <li>In your Railway project, ensure a PostgreSQL service is added.</li>
                    <li>Verify the <code className="bg-slate-100 px-1 py-0.5 rounded text-blue-700 font-mono">DATABASE_URL</code> variable is linked to your service.</li>
                    <li>Deploy the changes; tables and university schema will sync automatically.</li>
                  </ol>
                </div>

                <div className="pt-2 flex items-center justify-end gap-2">
                  <button
                    onClick={fetchInitialData}
                    disabled={loading}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white transition-all shadow-sm disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    <span>{loading ? 'Checking...' : 'Retry Connection'}</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-16 space-y-3">
                <div className="w-8 h-8 mx-auto border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-slate-500 font-medium">
                  {loading ? 'Connecting to University Database...' : 'No student records found in database.'}
                </p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500 w-full max-w-full overflow-hidden">
        <div className="max-w-5xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
          <div className="flex items-center gap-2">
            <span className="font-black text-blue-700 tracking-tight">INS grades</span>
            <span>•</span>
            <span className="text-slate-600 font-medium">Student Timetable &amp; Make-up Portal</span>
          </div>
          <div className="flex items-center gap-2 text-[11px]">
            <span className="text-slate-400 font-normal">developed with precision</span>
            <span>•</span>
            <span className="text-blue-600 font-semibold hover:underline">
              powered by @asliddin_tursunoff
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
