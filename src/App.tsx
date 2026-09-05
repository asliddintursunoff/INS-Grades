import { useState, useEffect, useCallback } from 'react';
import { BookOpen, Settings, Calendar, Send } from 'lucide-react';
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

  // Fetch initial students list & system status
  useEffect(() => {
    apiCall<{ students: Student[] }>('/api/demo/students')
      .then((res) => {
        const list = res.students || [];
        setStudents(list);

        // Check if Telegram user is linked
        const tgUser = getTelegramUser();
        if (tgUser) {
          const matched = list.find((s) => s.telegram_id === tgUser.id);
          if (matched) {
            setCurrentStudent(matched);
            return;
          }
        }

        // Default to first student (e.g. U2410252 - Asliddin Xolmatov)
        if (list.length > 0) {
          setCurrentStudent(list[0]);
        }
      })
      .catch((err) => console.error('Failed to load students:', err));

    apiCall('/api/system/status')
      .then((res) => setSystemStatus(res))
      .catch((err) => console.error('Failed to load status:', err));
  }, []);

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
        ) : (
          <div className="text-center py-16 text-slate-500 text-xs">
            Loading student profile...
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
