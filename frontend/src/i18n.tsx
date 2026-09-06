import React, { createContext, useContext, useState, useEffect } from 'react';

export type Language = 'en' | 'uz' | 'ru';

export const translations = {
  en: {
    // Navigation
    timetable: 'Timetable',
    courses: 'Courses',
    homework: 'My Homework',
    premium: 'Premium',
    profile: 'Profile',

    // Top Bar
    plan_free: 'FREE',
    plan_premium: 'PREMIUM ⭐',
    upgrade: 'Upgrade',

    // Homework
    homework_title: 'My Homework',
    homework_msg: 'Will be available from 14 September for premium users.',

    // Premium
    premium_title: 'INS Grades Premium',
    premium_price: '10,000 UZS',
    premium_period: '/ month',
    premium_feat1: 'Change class time & make-up lessons',
    premium_feat2: 'Add retake courses & drop classes',
    premium_feat3: 'Telegram notifications before each class',
    premium_btn: 'Get Premium',
    premium_active: 'Active Plan',
    premium_demo_free: 'Switch to Free (Test)',
    premium_demo_prem: 'Activate Premium (Test)',
    premium_only_msg: 'This feature is available for Premium users only.',
    premium_only_change: 'Schedule changes are available for Premium users only.',
    premium_only_retake: 'Adding retake courses is for Premium users only.',
    premium_only_drop: 'Dropping courses is for Premium users only.',
    premium_only_notif: 'Telegram reminders are for Premium users only.',
    premium_close: 'Close',

    // Timetable
    all_days: 'All Days',
    change_time: 'Change Time',
    revert_primary: 'Revert',
    no_classes: 'No classes scheduled for this day',
    room: 'Room',
    group: 'Group',
    prof: 'Professor',
    day_1: 'Monday',
    day_2: 'Tuesday',
    day_3: 'Wednesday',
    day_4: 'Thursday',
    day_5: 'Friday',
    day_1_short: 'Mon',
    day_2_short: 'Tue',
    day_3_short: 'Wed',
    day_4_short: 'Thu',
    day_5_short: 'Fri',

    // Courses Tab
    active_courses: 'Enrolled Courses',
    retake_courses: 'Retake Courses',
    drop_course: 'Drop Course',
    reenroll_course: 'Re-enroll',
    available_retakes: 'Available Retake Courses',
    add_retake: 'Add Retake Course',

    // Settings
    notif_title: 'Telegram Class Reminders',
    notif_toggle: 'Receive Class Reminders',
    notif_active: 'Active: Bot sends reminders before each class',
    notif_disabled: 'Disabled: Alerts muted',
    reminder_timing: 'Reminder Timing (Minutes Before):',
    minutes: 'min',
    telegram_link: 'Telegram Account Link',
    connected: 'Connected',
    pending: 'Pending',
    academic_profile: 'Official Academic Profile',
  },
  uz: {
    // Navigation
    timetable: 'Dars jadvali',
    courses: 'Fanlar',
    homework: 'Vazifalarim',
    premium: 'Premium',
    profile: 'Profil',

    // Top Bar
    plan_free: 'TEKIN',
    plan_premium: 'PREMIUM ⭐',
    upgrade: 'Olish',

    // Homework
    homework_title: 'Mening vazifalarim',
    homework_msg: '14-sentabrdan boshlab premium foydalanuvchilar uchun taqdim etiladi.',

    // Premium
    premium_title: 'INS Grades Premium',
    premium_price: "10 000 so'm",
    premium_period: '/ oyiga',
    premium_feat1: "Dars jadvalini o'zgartirish va make-up darslar",
    premium_feat2: 'Retake fanlarni olish va bekor qilish (drop)',
    premium_feat3: 'Darsdan oldin Telegram botdan avtomatik eslatmalar',
    premium_btn: 'Premium olish',
    premium_active: 'Faol Tarif',
    premium_demo_free: "Free tarifga o'tish (Test)",
    premium_demo_prem: 'Premium faollashtirish (Test)',
    premium_only_msg: 'Bu funksiya faqat Premium foydalanuvchilar uchun!',
    premium_only_change: "Dars jadvalini o'zgartirish faqat Premium foydalanuvchilar uchun.",
    premium_only_retake: "Retake fan qo'shish faqat Premium foydalanuvchilar uchun.",
    premium_only_drop: 'Fanni bekor qilish faqat Premium foydalanuvchilar uchun.',
    premium_only_notif: 'Telegram eslatmalarini yoqish faqat Premium foydalanuvchilar uchun.',
    premium_close: 'Yopish',

    // Timetable
    all_days: 'Barcha kunlar',
    change_time: "Vaqtni o'zgartirish",
    revert_primary: 'Qaytarish',
    no_classes: 'Bu kunga darslar yoq',
    room: 'Xona',
    group: 'Guruh',
    prof: "O'qituvchi",
    day_1: 'Dushanba',
    day_2: 'Seshanba',
    day_3: 'Chorshanba',
    day_4: 'Payshanba',
    day_5: 'Juma',
    day_1_short: 'Dush',
    day_2_short: 'Sesh',
    day_3_short: 'Chor',
    day_4_short: 'Pay',
    day_5_short: 'Juma',

    // Courses Tab
    active_courses: 'Mavjud fanlar',
    retake_courses: 'Retake fanlar',
    drop_course: 'Fanni bekor qilish (Drop)',
    reenroll_course: 'Qayta tiklash',
    available_retakes: 'Mavjud retake fanlar',
    add_retake: "Retake fan qo'shish",

    // Settings
    notif_title: 'Telegram dars eslatmalari',
    notif_toggle: 'Dars eslatmalarini olish',
    notif_active: 'Faol: Bot darsdan oldin xabarnoma yuboradi',
    notif_disabled: "O'chirilgan: Xabarlar kelmaydi",
    reminder_timing: 'Eslatma vaqti (darsdan necha daqiqa oldin):',
    minutes: 'daq',
    telegram_link: 'Telegram profil',
    connected: 'Ulangan',
    pending: 'Ulanmagan',
    academic_profile: 'Talaba ma\'lumotlari',
  },
  ru: {
    // Navigation
    timetable: 'Расписание',
    courses: 'Курсы',
    homework: 'Мои ДЗ',
    premium: 'Премиум',
    profile: 'Профиль',

    // Top Bar
    plan_free: 'БЕСПЛАТНО',
    plan_premium: 'ПРЕМИУМ ⭐',
    upgrade: 'Купить',

    // Homework
    homework_title: 'Мои домашние задания',
    homework_msg: 'Будет доступно с 14 сентября для премиум-пользователей.',

    // Premium
    premium_title: 'INS Grades Premium',
    premium_price: '10 000 сум',
    premium_period: '/ месяц',
    premium_feat1: 'Изменение расписания и отработка занятий (make-up)',
    premium_feat2: 'Добавление Retake и отмена предметов (Drop)',
    premium_feat3: 'Telegram-уведомления перед каждым занятием',
    premium_btn: 'Оформить Premium',
    premium_active: 'Активный план',
    premium_demo_free: 'Перейти на Free (Тест)',
    premium_demo_prem: 'Активировать Premium (Тест)',
    premium_only_msg: 'Эта функция доступна только для пользователей Premium!',
    premium_only_change: 'Изменение расписания доступно только с Premium.',
    premium_only_retake: 'Добавление Retake доступно только с Premium.',
    premium_only_drop: 'Отмена предмета доступна только с Premium.',
    premium_only_notif: 'Уведомления доступны только с Premium.',
    premium_close: 'Закрыть',

    // Timetable
    all_days: 'Все дни',
    change_time: 'Изменить время',
    revert_primary: 'Сбросить',
    no_classes: 'На этот день занятий нет',
    room: 'Аудитория',
    group: 'Группа',
    prof: 'Преподаватель',
    day_1: 'Понедельник',
    day_2: 'Вторник',
    day_3: 'Среда',
    day_4: 'Четверг',
    day_5: 'Пятница',
    day_1_short: 'Пн',
    day_2_short: 'Вт',
    day_3_short: 'Ср',
    day_4_short: 'Чт',
    day_5_short: 'Пт',

    // Courses Tab
    active_courses: 'Изучаемые предметы',
    retake_courses: 'Курсы Retake',
    drop_course: 'Отменить курс (Drop)',
    reenroll_course: 'Восстановить',
    available_retakes: 'Доступные Retake курсы',
    add_retake: 'Добавить Retake курс',

    // Settings
    notif_title: 'Telegram-напоминания',
    notif_toggle: 'Получать напоминания о парах',
    notif_active: 'Активно: Бот отправляет уведомления перед парами',
    notif_disabled: 'Отключено: Уведомления не приходят',
    reminder_timing: 'Время напоминания (за сколько минут до пары):',
    minutes: 'мин',
    telegram_link: 'Telegram аккаунт',
    connected: 'Подключен',
    pending: 'Не привязан',
    academic_profile: 'Данные студента',
  }
};

type Translations = typeof translations.en;

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: keyof Translations) => string;
}

const LanguageContext = createContext<LanguageContextType>({
  language: 'en',
  setLanguage: () => {},
  t: (key) => translations.en[key] || String(key),
});

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>(() => {
    const saved = localStorage.getItem('ins_lang') as Language;
    return saved && (saved === 'en' || saved === 'uz' || saved === 'ru') ? saved : 'en';
  });

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('ins_lang', lang);
  };

  const t = (key: keyof Translations): string => {
    const currentDict = translations[language] || translations.en;
    return (currentDict as any)[key] || translations.en[key] || String(key);
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
