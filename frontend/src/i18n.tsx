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
    premium_active_title: 'Your Premium Subscription is Active ⭐',
    premium_active_desc: 'All features including schedule adjustments, make-ups, drops/retakes, and automated reminders are unlocked.',
    premium_expires_label: 'Valid until:',
    premium_extend_btn: 'Extend Subscription (+30 days)',
    premium_demo_free: 'Switch to Free (Test)',
    premium_demo_prem: 'Activate Premium (Test)',
    premium_only_msg: 'This feature is available for Premium users only.',
    premium_only_change: 'Schedule changes are available for Premium users only.',
    premium_only_retake: 'Adding retake courses is for Premium users only.',
    premium_only_drop: 'Dropping courses is for Premium users only.',
    premium_only_notif: 'Telegram reminders are for Premium users only.',
    premium_close: 'Close',
    contact_support: 'Questions? @asliddin_tursunoff',

    // Automated Payment
    pay_title: 'Premium Activation',
    pay_subtitle: 'Automated Instant Verification',
    pay_exact_amount: 'Exact Amount to Transfer',
    pay_salt_title: 'Why is the amount slightly different from 10,000 UZS?',
    pay_salt_desc: 'To automatically verify your payment in seconds without manual receipt review, a temporary unique verification code is assigned to your transaction.',
    pay_strict_warning_title: 'CRITICAL: EXACT AMOUNT REQUIRED!',
    pay_strict_warning_desc: 'Transfer the EXACT amount shown above! If you transfer a different amount (e.g. rounded to 10,000 UZS), the system CANNOT detect your payment and IT WILL NOT BE ACCEPTED (PREMIUM WILL NOT BE ACTIVATED)!',
    pay_card_number: 'Bank Card Number',
    pay_card_holder: 'Card Holder',
    pay_copy: 'Copy',
    pay_copied: 'Copied!',
    pay_waiting: 'Waiting for payment confirmation...',
    pay_expires_in: 'Session expires in:',
    pay_success: 'Payment Verified! ⭐',
    pay_success_desc: 'Your INS Grades Premium subscription is active for 30 days.',
    pay_continue: 'Continue',
    pay_timeout: 'Payment Session Expired',
    pay_timeout_desc: 'If you already sent the transfer, please contact the administrator or try again.',
    pay_try_again: 'Try Again',
    pay_cancel: 'Cancel',
    pay_initiating: 'Generating payment request...',
    pay_error_title: 'Payment Error',

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
    enrolled_courses_title: 'Enrolled Courses & Academic Load',
    enrolled_courses_desc: 'Manage your registered subjects. Dropping a course cancels upcoming deadlines; retaking adds it back to your timetable.',
    currently_enrolled: 'Currently Enrolled Courses:',
    courses_count: 'courses',
    loading_courses: 'Loading enrolled courses...',
    no_active_courses: 'No active courses found. You can add or retake courses anytime.',
    register_retake: 'Register Retake Course',
    active_badge: 'Active',
    dropped_badge: 'Dropped',
    professor_label: 'Professor:',
    drop_confirm_title: 'Confirm Course Drop',
    drop_confirm_desc: 'Are you sure you want to drop this course?',
    confirm_btn: 'Confirm',
    cancel_btn: 'Cancel',

    // Settings
    notif_title: 'Telegram Class Reminders',
    notif_toggle: 'Receive Class Reminders',
    notif_active: 'Active: Bot sends reminders before each class',
    notif_disabled: 'Disabled: Alerts muted',
    notif_desc: 'The university bot will automatically dispatch class reminder notifications to your linked Telegram account before each lecture starts.',
    reminder_timing: 'Reminder Timing (Minutes Before):',
    minutes: 'min',
    settings_saved: 'Notification settings saved successfully!',
    telegram_link: 'Telegram Account Link',
    tg_link_status: 'Telegram Link Status',
    tg_link_account: 'Account Linked:',
    tg_link_instruction: 'When starting the bot, send your Student ID. If not found, contact administrator:',
    connected: 'Connected',
    pending: 'Not Linked',
    academic_profile: 'Official Academic Profile',
    profile_info_desc: 'Personal information, student ID, and primary academic group are managed centrally by the university registrar.',
    student_id_label: 'Student ID',
    full_name_label: 'Full Name',
    group_label: 'Primary Academic Group',
    standing_label: 'Academic Standing',
    year_student_format: 'Year {year} Student',
    verified_record: 'Verified Registrar Record',
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
    premium_active_title: 'Sizda Premium tarif faol ⭐',
    premium_active_desc: 'Barcha imkoniyatlar (dars vaqtini o\'zgartirish, drop/retake, bot eslatmalari) cheklovlarsiz ishlamoqda.',
    premium_expires_label: 'Amal qilish muddati:',
    premium_extend_btn: 'Obunani uzaytirish (+30 kun)',
    premium_demo_free: "Free tarifga o'tish (Test)",
    premium_demo_prem: 'Premium faollashtirish (Test)',
    premium_only_msg: 'Bu funksiya faqat Premium foydalanuvchilar uchun!',
    premium_only_change: "Dars jadvalini o'zgartirish faqat Premium foydalanuvchilar uchun.",
    premium_only_retake: "Retake fan qo'shish faqat Premium foydalanuvchilar uchun.",
    premium_only_drop: 'Fanni bekor qilish faqat Premium foydalanuvchilar uchun.',
    premium_only_notif: 'Telegram eslatmalarini yoqish faqat Premium foydalanuvchilar uchun.',
    premium_close: 'Yopish',
    contact_support: 'Savollar bormi? @asliddin_tursunoff',

    // Automated Payment
    pay_title: "Premium to'lovi",
    pay_subtitle: 'Avtomatik tezkor tekshiruv',
    pay_exact_amount: "O'tkaziladigan aniq summa",
    pay_salt_title: "Nega summa 10 000 so'mdan farq qiladi?",
    pay_salt_desc: "Tizim to'lovingizni soniyalar ichida avtomatik tanib olishi va admin tekshiruvisiz Premium yoqishi uchun sizga unikal identifikator kodi biriktirildi.",
    pay_strict_warning_title: "❗️ DIQQAT: QAT'IY TALAB!",
    pay_strict_warning_desc: "Aynan ko'rsatilgan summani to'lang! Agar boshqacha summa (masalan, yaxlitlab 10 000 so'm) to'lasangiz, tizim to'lovingizni aniqlay olmaydi va QABUL QILINMAYDI (PREMIUM YOQILMAYDI)!",
    pay_card_number: 'Karta raqami',
    pay_card_holder: 'Qabul qiluvchi',
    pay_copy: 'Nusxalash',
    pay_copied: 'Nusxa olindi!',
    pay_waiting: "To'lov kutilmoqda...",
    pay_expires_in: "To'lov vaqti:",
    pay_success: "To'lov qabul qilindi! ⭐",
    pay_success_desc: 'Sizning hisobingiz 30 kunga Premium qilindi.',
    pay_continue: 'Davom etish',
    pay_timeout: "To'lov vaqti tugadi",
    pay_timeout_desc: "Agar to'lov qilgan bo'lsangiz, administratorga murojaat qiling yoki qayta urinib ko'ring.",
    pay_try_again: 'Qayta urinish',
    pay_cancel: 'Bekor qilish',
    pay_initiating: "To'lov shakllantirilmoqda...",
    pay_error_title: "To'lov xatoligi",

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
    enrolled_courses_title: 'O\'qiyotgan fanlaringiz va yuklama',
    enrolled_courses_desc: 'Ro\'yxatdan o\'tgan fanlaringizni boshqaring. Fanni bekor qilish (drop) vazifalarni bekor qiladi, retake olish uni yana jadvalingizga qaytaradi.',
    currently_enrolled: 'Hozirda ro\'yxatdan o\'tgan fanlar:',
    courses_count: 'ta fan',
    loading_courses: 'Fanlar yuklanmoqda...',
    no_active_courses: 'Hech qanday faol fan topilmadi. Istalgan vaqtda fan qo\'shishingiz mumkin.',
    register_retake: 'Retake fan olish',
    active_badge: 'Faol',
    dropped_badge: 'Bekor qilingan',
    professor_label: 'O\'qituvchi:',
    drop_confirm_title: 'Fanni bekor qilishni tasdiqlang',
    drop_confirm_desc: 'Haqiqatan ham ushbu fanni bekor qilmoqchimisiz?',
    confirm_btn: 'Tasdiqlash',
    cancel_btn: 'Bekor qilish',

    // Settings
    notif_title: 'Telegram dars eslatmalari',
    notif_toggle: 'Dars eslatmalarini olish',
    notif_active: 'Faol: Bot darsdan oldin xabarnoma yuboradi',
    notif_disabled: "O'chirilgan: Xabarlar kelmaydi",
    notif_desc: 'Universitet boti har bir dars boshlanishidan oldin bog\'langan Telegram profilingizga avtomatik eslatma xabarnomasi yuboradi.',
    reminder_timing: 'Eslatma vaqti (darsdan necha daqiqa oldin):',
    minutes: 'daq',
    settings_saved: 'Eslatma sozlamalari muvaffaqiyatli saqlandi!',
    telegram_link: 'Telegram profil',
    tg_link_status: 'Telegram ulanish holati',
    tg_link_account: 'Ulangan profil:',
    tg_link_instruction: 'Botga kirganingizda talaba ID raqamingizni yuboring. Agar topilmasa, adminga murojaat qiling:',
    connected: 'Ulangan',
    pending: 'Ulanmagan',
    academic_profile: 'Talaba ma\'lumotlari',
    profile_info_desc: 'Shaxsiy ma\'lumotlar, talaba ID va asosiy akademik guruh universitet registratori tomonidan boshqariladi.',
    student_id_label: 'Talaba ID',
    full_name_label: 'F.I.SH.',
    group_label: 'Asosiy akademik guruh',
    standing_label: 'Kursi',
    year_student_format: '{year}-kurs talabasi',
    verified_record: 'Registrator tomonidan tasdiqlangan',
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
    premium_active_title: 'Ваша подписка Premium активна ⭐',
    premium_active_desc: 'Все функции (изменение времени пар, drop/retake, уведомления в Telegram) работают без ограничений.',
    premium_expires_label: 'Действует до:',
    premium_extend_btn: 'Продлить подписку (+30 дней)',
    premium_demo_free: 'Перейти на Free (Тест)',
    premium_demo_prem: 'Активировать Premium (Тест)',
    premium_only_msg: 'Эта функция доступна только для пользователей Premium!',
    premium_only_change: 'Изменение расписания доступно только с Premium.',
    premium_only_retake: 'Добавление Retake доступно только с Premium.',
    premium_only_drop: 'Отмена предмета доступна только с Premium.',
    premium_only_notif: 'Уведомления доступны только с Premium.',
    premium_close: 'Закрыть',
    contact_support: 'Есть вопросы? @asliddin_tursunoff',

    // Automated Payment
    pay_title: 'Оплата Premium',
    pay_subtitle: 'Мгновенная автоматическая проверка',
    pay_exact_amount: 'Точная сумма к переводу',
    pay_salt_title: 'Почему сумма немного отличается от 10 000 сум?',
    pay_salt_desc: 'Чтобы система автоматически и мгновенно распознала ваш перевод без участия администратора, вам назначен уникальный проверочный код.',
    pay_strict_warning_title: '❗️ ВНИМАНИЕ: СТРОГОЕ ТРЕБОВАНИЕ!',
    pay_strict_warning_desc: 'Переведите ТОЧНУЮ сумму, указанную выше! Если вы переведете другую сумму (например, ровно 10 000 сум), система НЕ СМОЖЕТ определить ваш платеж и ОН НЕ БУДЕТ ПРИНЯТ (PREMIUM НЕ ВКЛЮЧИТСЯ)!',
    pay_card_number: 'Номер карты',
    pay_card_holder: 'Получатель',
    pay_copy: 'Скопировать',
    pay_copied: 'Скопировано!',
    pay_waiting: 'Ожидание оплаты...',
    pay_expires_in: 'Время на оплату:',
    pay_success: 'Оплата подтверждена! ⭐',
    pay_success_desc: 'Ваша подписка INS Grades Premium активирована на 30 дней.',
    pay_continue: 'Продолжить',
    pay_timeout: 'Время сессии истекло',
    pay_timeout_desc: 'Если вы уже перевели деньги, свяжитесь с администратором или попробуйте снова.',
    pay_try_again: 'Попробовать снова',
    pay_cancel: 'Отмена',
    pay_initiating: 'Формирование платежа...',
    pay_error_title: 'Ошибка оплаты',

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
    enrolled_courses_title: 'Изучаемые предметы и академическая нагрузка',
    enrolled_courses_desc: 'Управляйте вашими курсами. Отмена курса (drop) отменяет дедлайны; повторный курс (retake) возвращает его в расписание.',
    currently_enrolled: 'Текущие предметы:',
    courses_count: 'курсов',
    loading_courses: 'Загрузка курсов...',
    no_active_courses: 'Активных предметов не найдено. Вы можете добавить Retake в любое время.',
    register_retake: 'Записаться на Retake',
    active_badge: 'Активен',
    dropped_badge: 'Отменен',
    professor_label: 'Преподаватель:',
    drop_confirm_title: 'Подтвердите отмену курса',
    drop_confirm_desc: 'Вы уверены, что хотите отменить этот предмет?',
    confirm_btn: 'Подтвердить',
    cancel_btn: 'Отмена',

    // Settings
    notif_title: 'Telegram-напоминания',
    notif_toggle: 'Получать напоминания о парах',
    notif_active: 'Активно: Бот отправляет уведомления перед парами',
    notif_disabled: 'Отключено: Уведомления не приходят',
    notif_desc: 'Университетский бот автоматически отправляет уведомления о предстоящих парах в ваш привязанный Telegram.',
    reminder_timing: 'Время напоминания (за сколько минут до пары):',
    minutes: 'мин',
    settings_saved: 'Настройки уведомлений успешно сохранены!',
    telegram_link: 'Telegram аккаунт',
    tg_link_status: 'Статус привязки Telegram',
    tg_link_account: 'Привязанный аккаунт:',
    tg_link_instruction: 'При запуске бота отправьте ваш Student ID. Если не найден, обратитесь к администратору:',
    connected: 'Подключен',
    pending: 'Не привязан',
    academic_profile: 'Данные студента',
    profile_info_desc: 'Личные данные, ID студента и академическая группа регулируются деканатом университета.',
    student_id_label: 'Student ID',
    full_name_label: 'Ф.И.О.',
    group_label: 'Основная группа',
    standing_label: 'Курс',
    year_student_format: 'Студент {year}-курса',
    verified_record: 'Подтверждено деканатом',
  }
};

type Translations = typeof translations.en;

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: keyof Translations, params?: Record<string, string | number>) => string;
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

  const t = (key: keyof Translations, params?: Record<string, string | number>): string => {
    const currentDict = translations[language] || translations.en;
    let text = (currentDict as any)[key] || translations.en[key] || String(key);
    if (params) {
      Object.entries(params).forEach(([paramKey, val]) => {
        text = text.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), String(val));
      });
    }
    return text;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);
